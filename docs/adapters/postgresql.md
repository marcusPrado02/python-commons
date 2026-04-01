# PostgreSQL / SQLAlchemy Adapter Runbook

## Installation

```bash
pip install 'mp-commons[sqlalchemy]'
pip install asyncpg  # async driver
```

## Required Environment Variables

| Variable | Example | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` | SQLAlchemy async connection URL |

## Basic Usage

```python
from mp_commons.adapters.sqlalchemy import SqlAlchemySessionFactory

factory = SqlAlchemySessionFactory(url=DATABASE_URL)

async with factory.session() as session:
    result = await session.execute(text("SELECT 1"))
```

### Unit of Work

```python
from mp_commons.application.uow import SqlAlchemyUnitOfWork

uow = SqlAlchemyUnitOfWork(session_factory=factory)
async with uow:
    repo = OrderRepository(session=uow.session)
    repo.add(order)
    await uow.commit()
```

## Health Check

```python
async def db_health() -> bool:
    async with factory.session() as s:
        await s.execute(text("SELECT 1"))
    return True
```

## Common Error Codes

| Error | Cause | Fix |
|---|---|---|
| `asyncpg.exceptions.TooManyConnectionsError` | Pool exhausted | Increase `pool_size` and `max_overflow` |
| `asyncpg.exceptions.PostgresConnectionError` | Cannot reach DB | Check `DATABASE_URL` host/port/firewall |
| `sqlalchemy.exc.IntegrityError` | Unique/FK constraint violation | Handle in application layer; rollback UoW |
| `sqlalchemy.exc.OperationalError: SSL` | SSL required by server | Add `?ssl=require` to `DATABASE_URL` |
| `ConcurrencyConflictError` | Optimistic lock mismatch | Retry the operation; use exponential backoff |

## Performance Tuning

- **Connection pool**: Tune for your service's concurrency:
  ```python
  SqlAlchemySessionFactory(
      url=DATABASE_URL,
      pool_size=20,       # base connections
      max_overflow=40,    # burst allowance
      pool_timeout=30,    # wait time before ConnectionError
      pool_recycle=1800,  # recycle connections every 30 min
  )
  ```
- **Statement timeout**: Prevent runaway queries:
  ```python
  # In session options
  execution_options={"statement_timeout": 5000}  # ms
  ```
- **ORM lazy loading**: Avoid N+1 with `selectinload` / `joinedload` in queries.
- **OpenTelemetry**: SQLAlchemy queries are auto-traced when `mp_commons.adapters.opentelemetry` is configured.

## Migrations (Alembic)

```bash
# Generate migration
alembic revision --autogenerate -m "add orders table"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```
