"""Unit tests for §72 – Workflow Engine."""
import asyncio

import pytest

from mp_commons.application.workflow import (
    InMemoryWorkflowInstanceStore,
    InvalidTransitionError,
    WorkflowEngine,
    WorkflowState,
    WorkflowTransition,
)


def _build_engine():
    store = InMemoryWorkflowInstanceStore()
    engine = WorkflowEngine(store)

    states = [
        WorkflowState("draft", is_initial=True),
        WorkflowState("pending"),
        WorkflowState("approved"),
        WorkflowState("rejected", is_terminal=True),
    ]
    transitions = [
        WorkflowTransition(from_state="draft", to_state="pending", trigger="submit"),
        WorkflowTransition(from_state="pending", to_state="approved", trigger="approve"),
        WorkflowTransition(from_state="pending", to_state="rejected", trigger="reject"),
    ]
    engine.define("order", states, transitions)
    return engine


class TestWorkflowEngine:
    def test_start_sets_initial_state(self):
        engine = _build_engine()
        instance = asyncio.run(engine.start("order"))
        assert instance.current_state == "draft"

    def test_valid_transition(self):
        engine = _build_engine()
        instance = asyncio.run(engine.start("order"))
        asyncio.run(engine.trigger(instance.id, "submit"))
        loaded = asyncio.run(engine._store.load(instance.id))
        assert loaded.current_state == "pending"

    def test_transition_records_history(self):
        engine = _build_engine()
        instance = asyncio.run(engine.start("order"))
        asyncio.run(engine.trigger(instance.id, "submit"))
        loaded = asyncio.run(engine._store.load(instance.id))
        assert len(loaded.history) == 1
        assert loaded.history[0].trigger == "submit"

    def test_invalid_trigger_raises(self):
        engine = _build_engine()
        instance = asyncio.run(engine.start("order"))
        with pytest.raises(InvalidTransitionError):
            asyncio.run(engine.trigger(instance.id, "approve"))  # can't approve from draft

    def test_guard_blocks_transition(self):
        store = InMemoryWorkflowInstanceStore()
        engine = WorkflowEngine(store)
        states = [
            WorkflowState("open", is_initial=True),
            WorkflowState("closed", is_terminal=True),
        ]

        async def always_block(ctx):
            return False

        transitions = [
            WorkflowTransition(from_state="open", to_state="closed", trigger="close", guard=always_block),
        ]
        engine.define("ticket", states, transitions)
        instance = asyncio.run(engine.start("ticket"))
        with pytest.raises(InvalidTransitionError):
            asyncio.run(engine.trigger(instance.id, "close"))

    def test_on_enter_called(self):
        entered = []

        async def on_enter(instance_id, ctx):
            entered.append(instance_id)

        store = InMemoryWorkflowInstanceStore()
        engine = WorkflowEngine(store)
        states = [
            WorkflowState("start", is_initial=True),
            WorkflowState("done", is_terminal=True, on_enter=on_enter),
        ]
        transitions = [
            WorkflowTransition(from_state="start", to_state="done", trigger="finish"),
        ]
        engine.define("simple", states, transitions)
        instance = asyncio.run(engine.start("simple"))
        asyncio.run(engine.trigger(instance.id, "finish"))
        assert len(entered) == 1

    def test_on_exit_called(self):
        exited = []

        async def on_exit(instance_id, ctx):
            exited.append(instance_id)

        store = InMemoryWorkflowInstanceStore()
        engine = WorkflowEngine(store)
        states = [
            WorkflowState("start", is_initial=True, on_exit=on_exit),
            WorkflowState("done", is_terminal=True),
        ]
        transitions = [
            WorkflowTransition(from_state="start", to_state="done", trigger="finish"),
        ]
        engine.define("simple2", states, transitions)
        instance = asyncio.run(engine.start("simple2"))
        asyncio.run(engine.trigger(instance.id, "finish"))
        assert len(exited) == 1

    def test_chain_transitions(self):
        engine = _build_engine()
        instance = asyncio.run(engine.start("order"))
        asyncio.run(engine.trigger(instance.id, "submit"))
        asyncio.run(engine.trigger(instance.id, "approve"))
        loaded = asyncio.run(engine._store.load(instance.id))
        assert loaded.current_state == "approved"
        assert len(loaded.history) == 2
