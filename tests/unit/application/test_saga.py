"""Unit tests for Saga / Process Manager (§43)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mp_commons.application.saga import (
    InMemorySagaStore,
    SagaCompensationFailedError,
    SagaContext,
    SagaFailedError,
    SagaOrchestrator,
    SagaRecord,
    SagaState,
    SagaStep,
    SagaStore,
)


# ---------------------------------------------------------------------------
# Helpers — concrete step implementations
# ---------------------------------------------------------------------------


class RecordingStep(SagaStep):
    """A step that records every call made on it."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.action_calls: list[dict[str, Any]] = []
        self.compensate_calls: list[dict[str, Any]] = []
        self._action_exc: Exception | None = None
        self._compensate_exc: Exception | None = None

    @property
    def name(self) -> str:
        return self._name

    def fail_action(self, exc: Exception) -> None:
        self._action_exc = exc

    def fail_compensate(self, exc: Exception) -> None:
        self._compensate_exc = exc

    async def action(self, ctx: SagaContext) -> None:
        self.action_calls.append(ctx.snapshot())
        ctx.set(f"{self._name}_done", True)
        if self._action_exc is not None:
            raise self._action_exc

    async def compensate(self, ctx: SagaContext) -> None:
        self.compensate_calls.append(ctx.snapshot())
        ctx.set(f"{self._name}_compensated", True)
        if self._compensate_exc is not None:
            raise self._compensate_exc


# ---------------------------------------------------------------------------
# §43.3  SagaContext
# ---------------------------------------------------------------------------


class TestSagaContext:
    def test_get_set(self) -> None:
        ctx = SagaContext()
        ctx.set("order_id", "123")
        assert ctx.get("order_id") == "123"

    def test_default_value(self) -> None:
        ctx = SagaContext()
        assert ctx.get("missing", "default") == "default"

    def test_contains(self) -> None:
        ctx = SagaContext({"x": 1})
        assert "x" in ctx
        assert "y" not in ctx

    def test_initial_data(self) -> None:
        ctx = SagaContext({"a": 1, "b": 2})
        assert ctx.get("a") == 1
        assert ctx.get("b") == 2

    def test_snapshot_is_copy(self) -> None:
        ctx = SagaContext({"key": "value"})
        snap = ctx.snapshot()
        snap["key"] = "mutated"
        assert ctx.get("key") == "value"  # original unchanged

    def test_from_snapshot(self) -> None:
        data = {"x": 42}
        ctx = SagaContext.from_snapshot(data)
        assert ctx.get("x") == 42

    def test_repr(self) -> None:
        ctx = SagaContext({"a": 1})
        assert "SagaContext" in repr(ctx)


# ---------------------------------------------------------------------------
# §43.4  SagaState
# ---------------------------------------------------------------------------


class TestSagaState:
    def test_all_states_exist(self) -> None:
        states = {s.value for s in SagaState}
        assert states == {
            "RUNNING",
            "COMPLETED",
            "COMPENSATING",
            "COMPENSATION_FAILED",
            "FAILED",
        }

    def test_states_are_distinct(self) -> None:
        values = [s.value for s in SagaState]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# §43.5  SagaStore + InMemorySagaStore
# ---------------------------------------------------------------------------


class TestInMemorySagaStore:
    def test_save_and_load(self) -> None:
        store = InMemorySagaStore()

        async def run() -> SagaRecord | None:
            await store.save("saga-1", SagaState.RUNNING, 1, {"key": "val"})
            return await store.load("saga-1")

        record = asyncio.run(run())
        assert record is not None
        assert record.saga_id == "saga-1"
        assert record.state == SagaState.RUNNING
        assert record.step_index == 1
        assert record.ctx_snapshot == {"key": "val"}

    def test_load_missing_returns_none(self) -> None:
        store = InMemorySagaStore()
        result = asyncio.run(store.load("nonexistent"))
        assert result is None

    def test_save_upserts(self) -> None:
        store = InMemorySagaStore()

        async def run() -> SagaRecord | None:
            await store.save("saga-1", SagaState.RUNNING, 0, {})
            await store.save("saga-1", SagaState.COMPLETED, 3, {"done": True})
            return await store.load("saga-1")

        record = asyncio.run(run())
        assert record is not None
        assert record.state == SagaState.COMPLETED
        assert record.step_index == 3

    def test_ctx_snapshot_is_copied(self) -> None:
        store = InMemorySagaStore()
        original: dict[str, Any] = {"key": "original"}

        async def run() -> SagaRecord | None:
            await store.save("s1", SagaState.RUNNING, 0, original)
            original["key"] = "mutated"
            return await store.load("s1")

        record = asyncio.run(run())
        assert record is not None
        assert record.ctx_snapshot["key"] == "original"

    def test_all_records(self) -> None:
        store = InMemorySagaStore()

        async def run() -> None:
            await store.save("s1", SagaState.RUNNING, 0, {})
            await store.save("s2", SagaState.COMPLETED, 2, {})

        asyncio.run(run())
        records = store.all_records()
        assert set(records.keys()) == {"s1", "s2"}

    def test_is_subclass_of_store(self) -> None:
        assert issubclass(InMemorySagaStore, SagaStore)


# ---------------------------------------------------------------------------
# §43.1/43.2  SagaStep abstract base
# ---------------------------------------------------------------------------


class TestSagaStep:
    def test_recording_step_implements_saga_step(self) -> None:
        step = RecordingStep("my-step")
        assert isinstance(step, SagaStep)

    def test_name_property(self) -> None:
        step = RecordingStep("reserve-inventory")
        assert step.name == "reserve-inventory"

    def test_repr(self) -> None:
        step = RecordingStep("my-step")
        assert "my-step" in repr(step)

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            SagaStep()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# §43.2  SagaOrchestrator — happy path
# ---------------------------------------------------------------------------


class TestSagaOrchestratorHappyPath:
    def test_single_step_completes(self) -> None:
        step = RecordingStep("step-a")
        orch = SagaOrchestrator([step])
        ctx = asyncio.run(orch.run("saga-1"))
        assert ctx.get("step-a_done") is True
        assert len(step.action_calls) == 1
        assert len(step.compensate_calls) == 0

    def test_multiple_steps_all_run(self) -> None:
        steps = [RecordingStep(f"step-{i}") for i in range(3)]
        orch = SagaOrchestrator(steps)
        ctx = asyncio.run(orch.run("saga-2"))
        for i, step in enumerate(steps):
            assert ctx.get(f"step-{i}_done") is True
            assert len(step.action_calls) == 1
            assert len(step.compensate_calls) == 0

    def test_steps_share_context(self) -> None:
        """Later steps can read data written by earlier steps."""
        class WriterStep(SagaStep):
            @property
            def name(self) -> str: return "writer"
            async def action(self, ctx: SagaContext) -> None:
                ctx.set("shared_value", 42)
            async def compensate(self, ctx: SagaContext) -> None: ...

        class ReaderStep(SagaStep):
            read_value: int | None = None
            @property
            def name(self) -> str: return "reader"
            async def action(self, ctx: SagaContext) -> None:
                ReaderStep.read_value = ctx.get("shared_value")
            async def compensate(self, ctx: SagaContext) -> None: ...

        asyncio.run(SagaOrchestrator([WriterStep(), ReaderStep()]).run("saga-3"))
        assert ReaderStep.read_value == 42

    def test_returns_saga_context(self) -> None:
        step = RecordingStep("step-a")
        result = asyncio.run(SagaOrchestrator([step]).run("saga-4"))
        assert isinstance(result, SagaContext)

    def test_initial_data_available_in_steps(self) -> None:
        initial_value: Any = None

        class ReadInitialStep(SagaStep):
            @property
            def name(self) -> str: return "read-initial"
            async def action(self, ctx: SagaContext) -> None:
                nonlocal initial_value
                initial_value = ctx.get("order_id")
            async def compensate(self, ctx: SagaContext) -> None: ...

        asyncio.run(
            SagaOrchestrator([ReadInitialStep()]).run(
                "saga-5", initial={"order_id": "order-99"}
            )
        )
        assert initial_value == "order-99"

    def test_store_updated_to_completed(self) -> None:
        store = InMemorySagaStore()
        step = RecordingStep("step-a")
        asyncio.run(SagaOrchestrator([step], store=store).run("saga-6"))
        record = asyncio.run(store.load("saga-6"))
        assert record is not None
        assert record.state == SagaState.COMPLETED

    def test_requires_at_least_one_step(self) -> None:
        with pytest.raises(ValueError, match="at least one step"):
            SagaOrchestrator([])


# ---------------------------------------------------------------------------
# §43.6  SagaOrchestrator — failure and compensation
# ---------------------------------------------------------------------------


class TestSagaOrchestratorFailure:
    def test_first_step_failure_no_compensation(self) -> None:
        step = RecordingStep("step-a")
        step.fail_action(RuntimeError("boom"))
        with pytest.raises(SagaFailedError) as exc_info:
            asyncio.run(SagaOrchestrator([step]).run("saga-7"))
        assert exc_info.value.failed_step == "step-a"
        assert len(step.compensate_calls) == 0

    def test_second_step_failure_compensates_first(self) -> None:
        step_a = RecordingStep("step-a")
        step_b = RecordingStep("step-b")
        step_b.fail_action(RuntimeError("step-b failed"))
        with pytest.raises(SagaFailedError) as exc_info:
            asyncio.run(SagaOrchestrator([step_a, step_b]).run("saga-8"))
        assert exc_info.value.failed_step == "step-b"
        assert len(step_a.compensate_calls) == 1  # step-a was compensated
        assert len(step_b.compensate_calls) == 0  # step-b never completed

    def test_compensation_runs_in_reverse_order(self) -> None:
        order: list[str] = []

        class TrackingStep(SagaStep):
            def __init__(self, n: str, fail: bool = False) -> None:
                self._n = n
                self._fail = fail

            @property
            def name(self) -> str: return self._n

            async def action(self, ctx: SagaContext) -> None:
                if self._fail:
                    raise RuntimeError(f"{self._n} failed")

            async def compensate(self, ctx: SagaContext) -> None:
                order.append(self._n)

        steps = [
            TrackingStep("a"),
            TrackingStep("b"),
            TrackingStep("c", fail=True),
        ]
        with pytest.raises(SagaFailedError):
            asyncio.run(SagaOrchestrator(steps).run("saga-9"))

        assert order == ["b", "a"]  # reverse of completion order

    def test_saga_failed_error_contains_cause(self) -> None:
        cause = ValueError("bad value")
        step = RecordingStep("step-a")
        step.fail_action(cause)
        with pytest.raises(SagaFailedError) as exc_info:
            asyncio.run(SagaOrchestrator([step]).run("saga-10"))
        assert exc_info.value.cause is cause
        assert exc_info.value.saga_id == "saga-10"

    def test_store_updated_to_failed(self) -> None:
        store = InMemorySagaStore()
        step = RecordingStep("step-a")
        step.fail_action(RuntimeError("x"))
        with pytest.raises(SagaFailedError):
            asyncio.run(SagaOrchestrator([step], store=store).run("saga-11"))
        record = asyncio.run(store.load("saga-11"))
        assert record is not None
        assert record.state == SagaState.FAILED

    def test_store_updated_to_compensating(self) -> None:
        """Store should reflect COMPENSATING state between failure and finished compensation."""
        stored_states: list[SagaState] = []

        class SpyStore(SagaStore):
            async def save(
                self,
                saga_id: str,
                state: SagaState,
                step_index: int,
                ctx_snapshot: dict[str, Any],
            ) -> None:
                stored_states.append(state)

            async def load(self, saga_id: str) -> SagaRecord | None:
                return None

        step_a = RecordingStep("step-a")
        step_b = RecordingStep("step-b")
        step_b.fail_action(RuntimeError())

        with pytest.raises(SagaFailedError):
            asyncio.run(
                SagaOrchestrator([step_a, step_b], store=SpyStore()).run("saga-12")
            )

        assert SagaState.COMPENSATING in stored_states
        assert SagaState.FAILED in stored_states

    def test_partial_compensation_failure(self) -> None:
        """When a compensation step raises, end state is COMPENSATION_FAILED."""
        step_a = RecordingStep("step-a")
        step_a.fail_compensate(RuntimeError("compensate-a failed"))
        step_b = RecordingStep("step-b")
        step_b.fail_action(RuntimeError("step-b failed"))

        with pytest.raises(SagaCompensationFailedError) as exc_info:
            asyncio.run(SagaOrchestrator([step_a, step_b]).run("saga-13"))

        err = exc_info.value
        assert err.saga_id == "saga-13"
        assert err.failed_step == "step-b"
        assert isinstance(err.action_error, RuntimeError)
        assert isinstance(err.compensation_error, RuntimeError)

    def test_compensation_failed_store_state(self) -> None:
        store = InMemorySagaStore()
        step_a = RecordingStep("step-a")
        step_a.fail_compensate(RuntimeError("comp fail"))
        step_b = RecordingStep("step-b")
        step_b.fail_action(RuntimeError("action fail"))

        with pytest.raises(SagaCompensationFailedError):
            asyncio.run(
                SagaOrchestrator([step_a, step_b], store=store).run("saga-14")
            )
        record = asyncio.run(store.load("saga-14"))
        assert record is not None
        assert record.state == SagaState.COMPENSATION_FAILED

    def test_all_steps_compensated_on_last_step_failure(self) -> None:
        steps = [RecordingStep(f"step-{i}") for i in range(4)]
        steps[-1].fail_action(RuntimeError("last step fails"))

        with pytest.raises(SagaFailedError):
            asyncio.run(SagaOrchestrator(steps).run("saga-15"))

        # All but the last step (never completed) must have been compensated
        for step in steps[:-1]:
            assert len(step.compensate_calls) == 1
        assert len(steps[-1].compensate_calls) == 0


# ---------------------------------------------------------------------------
# §43  __init__ exports
# ---------------------------------------------------------------------------


class TestSagaInit:
    def test_all_public_names_importable(self) -> None:
        from mp_commons.application.saga import (
            InMemorySagaStore,
            SagaCompensationFailedError,
            SagaContext,
            SagaError,
            SagaFailedError,
            SagaOrchestrator,
            SagaRecord,
            SagaState,
            SagaStep,
            SagaStore,
        )
        for obj in (
            InMemorySagaStore,
            SagaCompensationFailedError,
            SagaContext,
            SagaError,
            SagaFailedError,
            SagaOrchestrator,
            SagaRecord,
            SagaState,
            SagaStep,
            SagaStore,
        ):
            assert obj is not None
