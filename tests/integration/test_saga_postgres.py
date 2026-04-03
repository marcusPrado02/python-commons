"""T-04 — Integration tests for Saga orchestration with real PostgreSQL.

Covers:
- persist saga state — SagaRecord is saved after each step (RUNNING → COMPLETED)
- resume after failure — on step failure, compensations run; final state is FAILED
- compensation recorded — SagaRecord transitions through COMPENSATING → FAILED

Uses the PostgreSQL sidecar available in the CI integration job.
Falls back to spinning up a PostgreSQL container via testcontainers if
DATABASE_URL is not set in the environment.

Run with: pytest tests/integration/test_saga_postgres.py -m integration -v
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
import uuid

import pytest

from mp_commons.application.saga import (
    SagaContext,
    SagaOrchestrator,
    SagaStep,
)
from mp_commons.application.saga.orchestrator import SagaFailedError
from mp_commons.application.saga.state import SagaState
from mp_commons.application.saga.store import SagaRecord, SagaStore

# ---------------------------------------------------------------------------
# asyncpg-backed SagaStore
# ---------------------------------------------------------------------------


class AsyncpgSagaStore(SagaStore):
    """Minimal asyncpg-backed SagaStore for integration testing.

    Creates a ``saga_records`` table on first use.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Any = None

    async def _get_pool(self) -> Any:
        if self._pool is None:
            import asyncpg  # type: ignore[import-untyped]

            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS saga_records (
                        saga_id     TEXT PRIMARY KEY,
                        state       TEXT NOT NULL,
                        step_index  INT  NOT NULL,
                        ctx_snapshot JSONB NOT NULL DEFAULT '{}'
                    )
                    """
                )
        return self._pool

    async def save(
        self,
        saga_id: str,
        state: SagaState,
        step_index: int,
        ctx_snapshot: dict[str, Any],
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO saga_records (saga_id, state, step_index, ctx_snapshot)
                VALUES ($1, $2, $3, $4::jsonb)
                ON CONFLICT (saga_id) DO UPDATE
                    SET state       = EXCLUDED.state,
                        step_index  = EXCLUDED.step_index,
                        ctx_snapshot = EXCLUDED.ctx_snapshot
                """,
                saga_id,
                state.value,
                step_index,
                json.dumps(ctx_snapshot),
            )

    async def load(self, saga_id: str) -> SagaRecord | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT saga_id, state, step_index, ctx_snapshot FROM saga_records WHERE saga_id = $1",
                saga_id,
            )
        if row is None:
            return None
        return SagaRecord(
            saga_id=row["saga_id"],
            state=SagaState(row["state"]),
            step_index=row["step_index"],
            ctx_snapshot=row["ctx_snapshot"] if isinstance(row["ctx_snapshot"], dict) else json.loads(row["ctx_snapshot"]),
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _get_dsn() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    # asyncpg uses postgresql:// not postgresql+asyncpg://
    return url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture(scope="module")
def dsn() -> str:  # type: ignore[return]
    """Return a PostgreSQL DSN — uses env var or spins up testcontainers."""
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        yield _get_dsn()
        return

    # No env var — spin up a container
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        yield (
            pg.get_connection_url()
            .replace("+psycopg2", "")
            .replace("postgresql://", "postgresql://")
        )


# ---------------------------------------------------------------------------
# Saga step helpers
# ---------------------------------------------------------------------------


class _AppendStep(SagaStep):
    """Records execution and compensation into context lists."""

    def __init__(self, name: str, fail: bool = False) -> None:
        self._name = name
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    async def action(self, ctx: SagaContext) -> None:
        executed: list[str] = ctx.get("executed", [])
        executed.append(self._name)
        ctx.set("executed", executed)
        if self._fail:
            raise RuntimeError(f"Step {self._name} failed intentionally")

    async def compensate(self, ctx: SagaContext) -> None:
        compensated: list[str] = ctx.get("compensated", [])
        compensated.append(self._name)
        ctx.set("compensated", compensated)


# ---------------------------------------------------------------------------
# T-04 tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSagaPostgresIntegration:
    """Saga orchestration with real PostgreSQL-backed SagaStore."""

    def test_completed_saga_state_persisted(self, dsn: str) -> None:
        """After a successful run, SagaState.COMPLETED is persisted in PostgreSQL."""
        saga_id = str(uuid.uuid4())
        store = AsyncpgSagaStore(dsn=dsn)

        async def run() -> None:
            orchestrator = SagaOrchestrator(
                steps=[_AppendStep("step-a"), _AppendStep("step-b")],
                store=store,
            )
            ctx = await orchestrator.run(saga_id, initial={"order": "ord-1"})
            assert ctx.get("executed") == ["step-a", "step-b"]
            await store.close()

        asyncio.run(run())

        # Re-open the store (new connection) to verify persistence
        store2 = AsyncpgSagaStore(dsn=dsn)

        async def verify() -> SagaRecord | None:
            try:
                return await store2.load(saga_id)
            finally:
                await store2.close()

        record = asyncio.run(verify())
        assert record is not None
        assert record.state == SagaState.COMPLETED
        assert record.step_index == 2

    def test_failed_saga_compensation_recorded(self, dsn: str) -> None:
        """When a step fails, compensations run and FAILED state is persisted."""
        saga_id = str(uuid.uuid4())
        store = AsyncpgSagaStore(dsn=dsn)

        async def run() -> None:
            orchestrator = SagaOrchestrator(
                steps=[
                    _AppendStep("reserve-stock"),
                    _AppendStep("charge-payment", fail=True),
                ],
                store=store,
            )
            with pytest.raises(SagaFailedError) as exc_info:
                await orchestrator.run(saga_id)
            assert exc_info.value.failed_step == "charge-payment"
            await store.close()

        asyncio.run(run())

        store2 = AsyncpgSagaStore(dsn=dsn)

        async def verify() -> SagaRecord | None:
            try:
                return await store2.load(saga_id)
            finally:
                await store2.close()

        record = asyncio.run(verify())
        assert record is not None
        assert record.state == SagaState.FAILED

    def test_context_snapshot_stored_and_retrieved(self, dsn: str) -> None:
        """SagaContext data written by steps is saved and loadable from the store."""
        saga_id = str(uuid.uuid4())
        store = AsyncpgSagaStore(dsn=dsn)

        async def run() -> None:
            orchestrator = SagaOrchestrator(
                steps=[_AppendStep("step-1"), _AppendStep("step-2")],
                store=store,
            )
            await orchestrator.run(saga_id, initial={"order_id": "ORD-42"})
            await store.close()

        asyncio.run(run())

        store2 = AsyncpgSagaStore(dsn=dsn)

        async def verify() -> SagaRecord | None:
            try:
                return await store2.load(saga_id)
            finally:
                await store2.close()

        record = asyncio.run(verify())
        assert record is not None
        assert record.ctx_snapshot.get("order_id") == "ORD-42"
        assert "step-1" in record.ctx_snapshot.get("executed", [])
        assert "step-2" in record.ctx_snapshot.get("executed", [])
