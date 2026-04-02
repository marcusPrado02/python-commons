"""DynamoDB adapter."""

from __future__ import annotations

from mp_commons.adapters.dynamodb.repository import (
    DynamoDBIdempotencyStore,
    DynamoDBOutboxStore,
    DynamoDBRepository,
    DynamoDBTable,
)

__all__ = [
    "DynamoDBIdempotencyStore",
    "DynamoDBOutboxStore",
    "DynamoDBRepository",
    "DynamoDBTable",
]
