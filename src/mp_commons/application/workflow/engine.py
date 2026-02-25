from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
import uuid

from mp_commons.application.workflow.state import WorkflowState
from mp_commons.application.workflow.transition import (
    InvalidTransitionError,
    TransitionRecord,
    WorkflowTransition,
)

__all__ = [
    "InMemoryWorkflowInstanceStore",
    "WorkflowDefinition",
    "WorkflowEngine",
    "WorkflowInstance",
    "WorkflowInstanceStore",
]


@dataclass
class WorkflowInstance:
    """Runtime instance of a workflow."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    current_state: str = ""
    history: list[TransitionRecord] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Any = None


class WorkflowInstanceStore(Protocol):
    async def save(self, instance: WorkflowInstance) -> None: ...
    async def load(self, instance_id: str) -> WorkflowInstance | None: ...


class InMemoryWorkflowInstanceStore:
    def __init__(self) -> None:
        self._store: dict[str, WorkflowInstance] = {}

    async def save(self, instance: WorkflowInstance) -> None:
        self._store[instance.id] = instance

    async def load(self, instance_id: str) -> WorkflowInstance | None:
        return self._store.get(instance_id)


@dataclass
class WorkflowDefinition:
    name: str
    states: dict[str, WorkflowState] = field(default_factory=dict)
    transitions: list[WorkflowTransition] = field(default_factory=list)

    @property
    def initial_state(self) -> WorkflowState:
        for s in self.states.values():
            if s.is_initial:
                return s
        raise ValueError(f"No initial state defined in workflow '{self.name}'")


class WorkflowEngine:
    """Drives workflow transitions for instances."""

    def __init__(self, store: WorkflowInstanceStore) -> None:
        self._store = store
        self._definitions: dict[str, WorkflowDefinition] = {}

    def define(
        self,
        workflow_name: str,
        states: list[WorkflowState],
        transitions: list[WorkflowTransition],
    ) -> WorkflowDefinition:
        defn = WorkflowDefinition(
            name=workflow_name,
            states={s.name: s for s in states},
            transitions=transitions,
        )
        self._definitions[workflow_name] = defn
        return defn

    async def start(self, workflow_name: str, ctx: Any = None) -> WorkflowInstance:
        defn = self._definitions[workflow_name]
        initial = defn.initial_state
        instance = WorkflowInstance(
            workflow_name=workflow_name,
            current_state=initial.name,
            context=ctx,
        )
        if initial.on_enter:
            await initial.on_enter(instance.id, ctx)
        await self._store.save(instance)
        return instance

    async def trigger(self, instance_id: str, event: str, ctx: Any = None) -> WorkflowInstance:
        instance = await self._store.load(instance_id)
        if instance is None:
            raise KeyError(f"Workflow instance '{instance_id}' not found")

        defn = self._definitions[instance.workflow_name]
        current_state_obj = defn.states[instance.current_state]

        # Find matching transition
        candidate: WorkflowTransition | None = None
        for t in defn.transitions:
            if t.from_state == instance.current_state and t.trigger == event:
                if t.guard is None or await t.guard(ctx):
                    candidate = t
                    break

        if candidate is None:
            raise InvalidTransitionError(instance.current_state, event)

        # Execute on_exit of current state
        if current_state_obj.on_exit:
            await current_state_obj.on_exit(instance.id, ctx)

        # Execute transition action
        if candidate.action:
            await candidate.action(ctx)

        # Record history
        record = TransitionRecord(
            from_state=candidate.from_state,
            to_state=candidate.to_state,
            trigger=event,
            context=ctx,
        )
        instance.history.append(record)
        instance.current_state = candidate.to_state

        # Execute on_enter of new state
        new_state_obj = defn.states[candidate.to_state]
        if new_state_obj.on_enter:
            await new_state_obj.on_enter(instance.id, ctx)

        await self._store.save(instance)
        return instance
