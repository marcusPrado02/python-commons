# OpenAPI Compatibility Guide

`mp-commons` provides contract testing utilities in
`mp_commons.testing.contracts` to verify that API schema changes do not break
consumers.

---

## Compatibility Modes

| Mode | Rule |
|---|---|
| `BACKWARD` | New schema can read data written by old schema |
| `FORWARD` | Old schema can read data written by new schema |
| `FULL` | Both backward and forward compatible |
| `NONE` | No compatibility guarantee (internal/experimental APIs) |

## Using `OpenAPIContractTest`

```python
from mp_commons.testing.contracts import OpenAPIContractTest, CompatibilityMode

class TestOrdersAPIContract(OpenAPIContractTest):
    schema_path = "docs/contracts/orders-v1.yaml"
    compatibility = CompatibilityMode.BACKWARD

    def test_new_field_is_optional(self) -> None:
        self.assert_compatible(new_schema_path="docs/contracts/orders-v2.yaml")
```

## Rules for Backward-Compatible Changes

**Allowed:**
- Adding optional fields to request/response bodies
- Adding new endpoints
- Adding new optional query parameters
- Adding new enum values (with caution — consumers must ignore unknowns)

**Forbidden:**
- Removing or renaming fields
- Making optional fields required
- Changing field types
- Removing endpoints
- Removing enum values

## Contract Storage

Store versioned schemas in `docs/contracts/`:

```
docs/contracts/
  orders-v1.yaml
  orders-v2.yaml
  payments-v1.yaml
```

Reference the current production schema with a symlink:
```
orders-current.yaml -> orders-v2.yaml
```

## AsyncAPI (Event Contracts)

For event-driven interfaces use `AsyncAPIContractTest` with the same
`CompatibilityMode` semantics applied to message payload schemas.

```python
from mp_commons.testing.contracts import AsyncAPIContractTest

class TestOrderEventsContract(AsyncAPIContractTest):
    schema_path = "docs/contracts/order-events-v1.yaml"
    compatibility = CompatibilityMode.FULL
```
