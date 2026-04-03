# Quickstart

## 1. Install

```bash
pip install mp-commons
# or with adapter extras:
pip install "mp-commons[redis,sqlalchemy,kafka]"
```

## 2. Configure settings

Create a `settings.py`:

```python
from mp_commons.config.settings import BaseAppSettings

class AppSettings(BaseAppSettings):
    database_url: str = "sqlite+aiosqlite:///./app.db"
    redis_url: str = "redis://localhost:6379"
    service_name: str = "my-service"

settings = AppSettings()
```

## 3. Wire up FastAPI

```python
from fastapi import FastAPI
from mp_commons.observability.logging import configure_logging
from mp_commons.observability.health import HealthRegistry, LambdaHealthCheck

configure_logging(service_name=settings.service_name)

app = FastAPI()
registry = HealthRegistry()
registry.register(LambdaHealthCheck("ping", lambda: True))

@app.get("/health")
async def health():
    report = await registry.run_all()
    return report.to_dict()
```

## 4. Dispatch your first command

```python
from mp_commons.kernel.cqrs import CommandBus, command_handler
from dataclasses import dataclass

@dataclass(frozen=True)
class CreateUser:
    name: str
    email: str

@command_handler(CreateUser)
async def handle_create_user(cmd: CreateUser) -> None:
    print(f"Creating user: {cmd.name} <{cmd.email}>")

bus = CommandBus()
bus.register(CreateUser, handle_create_user)
await bus.dispatch(CreateUser(name="Alice", email="alice@example.com"))
```
