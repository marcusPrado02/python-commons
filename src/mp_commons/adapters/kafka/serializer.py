"""Kafka adapter – KafkaMessageSerializer."""
from __future__ import annotations

import json
from typing import Any

from mp_commons.kernel.messaging import MessageSerializer


class KafkaMessageSerializer(MessageSerializer[Any]):
    """JSON serialiser/deserialiser for Kafka messages."""

    def serialize(self, payload: Any) -> bytes:
        if isinstance(payload, bytes):
            return payload
        return json.dumps(payload, default=str).encode()

    def deserialize(self, data: bytes, target_type: type[Any]) -> Any:
        parsed = json.loads(data)
        if hasattr(target_type, "model_validate"):
            return target_type.model_validate(parsed)
        return parsed


__all__ = ["KafkaMessageSerializer"]
