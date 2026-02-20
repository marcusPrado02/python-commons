"""SQLAlchemy adapter – SqlAlchemySessionFactory."""
from __future__ import annotations

from typing import Any


def _require_sqlalchemy() -> None:
    try:
        import sqlalchemy  # noqa: F401
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[sqlalchemy]' to use the SQLAlchemy adapter") from exc


class SqlAlchemySessionFactory:
    """Creates async SQLAlchemy sessions from an engine URL."""

    def __init__(self, database_url: str, **engine_kwargs: Any) -> None:
        _require_sqlalchemy()
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # type: ignore[import-untyped]
        self._engine = create_async_engine(database_url, **engine_kwargs)
        self._session_factory = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)

    def __call__(self) -> Any:
        return self._session_factory()

    async def dispose(self) -> None:
        await self._engine.dispose()


__all__ = ["SqlAlchemySessionFactory"]
