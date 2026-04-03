# Kafka Adapter Runbook

## Installation

```bash
pip install 'mp-commons[kafka]'
```

## Required Environment Variables

| Variable | Example | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Comma-separated list of broker addresses |

## Basic Usage

### Producer

```python
from mp_commons.adapters.kafka import KafkaProducer
from mp_commons.kernel.messaging import Message, MessageHeaders

producer = KafkaProducer(bootstrap_servers="kafka:9092")
async with producer:
    msg = Message(
        id="evt-1",
        topic="orders",
        payload={"order_id": "123"},
        headers=MessageHeaders(correlation_id="corr-abc"),
    )
    await producer.publish(msg)
```

### Consumer

```python
from mp_commons.adapters.kafka import KafkaConsumer

consumer = KafkaConsumer(
    bootstrap_servers="kafka:9092",
    group_id="order-service",
    topics=["orders"],
    auto_offset_reset="earliest",
)
async with consumer:
    async for msg in consumer:
        payload = json.loads(msg.value)
        # process...
```

### Outbox Dispatcher

```python
from mp_commons.adapters.kafka import KafkaOutboxDispatcher

dispatcher = KafkaOutboxDispatcher(bus=producer, repo=outbox_repo)
count = await dispatcher.dispatch_pending()
```

## Health Check

```python
from mp_commons.adapters.kafka.health import KafkaHealthCheck

check = KafkaHealthCheck(bootstrap_servers="kafka:9092")
healthy = await check()
```

## Common Error Codes

| Error | Cause | Fix |
|---|---|---|
| `aiokafka.errors.NoBrokersAvailable` | Cannot reach broker | Verify `KAFKA_BOOTSTRAP_SERVERS` and network connectivity |
| `aiokafka.errors.KafkaTimeoutError` | Broker slow/unresponsive | Increase `request_timeout_ms` (default: 40s) |
| `aiokafka.errors.UnknownTopicOrPartitionError` | Topic doesn't exist | Create topic or enable `auto.create.topics.enable` |
| `aiokafka.errors.GroupAuthorizationFailedError` | ACL denied for consumer group | Add ACL for group and topic |
| Outbox dispatcher logs `outbox.dispatch_failed` | Publish failed | Check broker logs; records stay PENDING and will retry |

## Performance Tuning

- **Batch producer**: Use `linger_ms=5` and `batch_size=32768` to batch small messages:
  ```python
  KafkaProducer(bootstrap_servers=..., linger_ms=5, batch_size=32768)
  ```
- **Consumer lag**: Increase `max_poll_records` (default: 500) and process partitions concurrently.
- **Compression**: Enable `compression_type="lz4"` on the producer for high-throughput topics.
- **Idempotent producer**: Set `enable_idempotence=True` to prevent duplicate publishes on retry.

## Distributed Tracing

The Kafka adapter automatically propagates `traceparent` / `tracestate` headers
when OpenTelemetry is configured (see `mp_commons.adapters.opentelemetry`).
