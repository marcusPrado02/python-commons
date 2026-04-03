# Adapters

Each adapter is an optional extra. Install only what you need.

## PostgreSQL / SQLAlchemy Async

```bash
pip install "mp-commons[sqlalchemy]"
# requires: sqlalchemy[asyncio] aiosqlite asyncpg
```

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

## Redis

```bash
pip install "mp-commons[redis]"
# requires: redis[asyncio]>=5.0
```

```python
import redis.asyncio as redis
from mp_commons.adapters.cache import RedisCache

client = redis.from_url("redis://localhost:6379")
cache = RedisCache(client, prefix="myapp:", ttl=300)
```

## Kafka

```bash
pip install "mp-commons[kafka]"
# requires: aiokafka>=0.10
```

```python
from mp_commons.adapters.messaging import KafkaMessageBus

bus = KafkaMessageBus(bootstrap_servers="localhost:9092", group_id="my-group")
await bus.start()
```

## Vault (HashiCorp)

```bash
pip install "mp-commons[vault]"
# requires: hvac>=2.0
```

```python
from mp_commons.config.secrets import VaultSecretStore

vault = VaultSecretStore(url="http://vault:8200", token="dev-root-token")
secret = await vault.get("secret/data/myapp")
```

## OpenTelemetry

```bash
pip install "mp-commons[otel]"
# requires: opentelemetry-sdk opentelemetry-exporter-otlp
```

```python
from mp_commons.observability.tracing import configure_tracing

configure_tracing(service_name="my-service", otlp_endpoint="http://localhost:4317")
```

## i18n (Babel)

```bash
pip install "mp-commons[i18n]"
# requires: babel>=2.12
```

```python
from mp_commons.application.i18n import Translator, Locale

translator = Translator(locale_dir="locales", supported_locales=["en", "pt-BR"])
text = translator.translate("welcome.message", locale=Locale.parse("pt-BR"))
```

## Environment variables

| Variable | Used by | Example |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy adapter | `postgresql+asyncpg://user:pass@host/db` |
| `REDIS_URL` | Redis adapter | `redis://localhost:6379` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka adapter | `kafka:9092` |
| `VAULT_ADDR` | Vault adapter | `http://vault:8200` |
| `VAULT_TOKEN` | Vault adapter | `s.xxxx` |
| `OTLP_ENDPOINT` | OpenTelemetry | `http://otel-collector:4317` |
