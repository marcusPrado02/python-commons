# Elasticsearch Adapter Runbook

## Installation

```bash
pip install 'mp-commons[elasticsearch]'
```

## Required Environment Variables

| Variable | Example | Description |
|---|---|---|
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch base URL |
| `ELASTICSEARCH_API_KEY` | *(optional)* | API key for authentication |

## Basic Usage

```python
from mp_commons.adapters.elasticsearch import ElasticsearchClient

client = ElasticsearchClient(url="http://localhost:9200")
async with client:
    await client.index("orders", doc_id="ord-1", document={"status": "pending"})
    doc = await client.get("orders", doc_id="ord-1")
    results = await client.search("orders", query={"match": {"status": "pending"}})
```

## Health Check

```python
from mp_commons.adapters.elasticsearch.health import ElasticsearchHealthCheck

check = ElasticsearchHealthCheck(url=ELASTICSEARCH_URL)
healthy = await check()
```

## Common Error Codes

| Error | Cause | Fix |
|---|---|---|
| `elastic_transport.ConnectionError` | Cannot reach ES | Check URL and network connectivity |
| `elasticsearch.NotFoundError (404)` | Index or document missing | Check index name and document ID |
| `elasticsearch.ConflictError (409)` | Version conflict on update | Use `retry_on_conflict=3` or implement backoff |
| `elasticsearch.RequestError (400)` | Invalid DSL query | Validate query structure against ES DSL docs |
| `elasticsearch.AuthenticationException (401)` | Bad credentials | Check `ELASTICSEARCH_API_KEY` or username/password |
| Circuit breaker `SearchParserException` | Malformed aggregation | Validate aggregation syntax; use `explain=True` |

## Performance Tuning

- **Bulk indexing**: Use `helpers.async_bulk()` for inserting large datasets.
- **Index templates**: Define mappings upfront to avoid dynamic field explosion.
- **Refresh interval**: Set `index.refresh_interval: 30s` (or `-1` during bulk load) to improve write throughput.
- **Search timeout**: Always pass `timeout="10s"` to search calls in production.
- **Connection pool**: The default HTTP pool handles concurrent requests; adjust `connections_per_node` for high throughput.
