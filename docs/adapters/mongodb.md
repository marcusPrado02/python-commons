# MongoDB Adapter Runbook

## Installation

```bash
pip install 'mp-commons[mongodb]'
```

## Required Environment Variables

| Variable | Example | Description |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection URL |
| `MONGODB_DATABASE` | `myapp` | Default database name |

## Basic Usage

```python
from mp_commons.adapters.mongodb import MongoRepository

class OrderRepository(MongoRepository[Order]):
    collection_name = "orders"
    model_class = Order

repo = OrderRepository(url="mongodb://localhost:27017", database="myapp")
async with repo:
    await repo.save(order)
    found = await repo.get(order.id)
    await repo.delete(order.id)
```

## Health Check

```python
async def mongo_health() -> bool:
    client = AsyncIOMotorClient(MONGODB_URL)
    await client.admin.command("ping")
    return True
```

## Common Error Codes

| Error | Cause | Fix |
|---|---|---|
| `pymongo.errors.ServerSelectionTimeoutError` | Cannot reach MongoDB | Check `MONGODB_URL` and firewall |
| `pymongo.errors.DuplicateKeyError` | Unique index violation | Handle in app layer; check `_id` or unique fields |
| `pymongo.errors.OperationFailure: not authorized` | Auth failure | Add credentials to URL: `mongodb://user:pass@host` |
| `ConcurrencyConflictError` | Optimistic lock version mismatch | Retry the operation |
| `pymongo.errors.DocumentTooLarge` | Document > 16 MB | Split large documents; use GridFS for binary blobs |

## Performance Tuning

- **Indexes**: Always create indexes on frequently queried fields:
  ```python
  await collection.create_index([("tenant_id", 1), ("created_at", -1)])
  ```
- **Connection pool**: Motor uses a pool; set `maxPoolSize` in the URL:
  `mongodb://host/?maxPoolSize=100`
- **Projection**: Fetch only needed fields with `projection={"_id": 1, "status": 1}`.
- **Write concern**: For durability, use `w="majority"` on critical writes.
- **TTL indexes**: For auto-expiring documents (e.g., sessions, inbox records):
  ```python
  await collection.create_index("expires_at", expireAfterSeconds=0)
  ```
