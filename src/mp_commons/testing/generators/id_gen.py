"""Testing generators – ID generators."""
from __future__ import annotations

import random
import string


def ulid_gen() -> str:
    """Generate a 26-character ULID-like random string."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=26))  # noqa: S311


def correlation_id_gen() -> str:
    """Generate a UUID4 correlation ID string."""
    import uuid
    return str(uuid.uuid4())


__all__ = ["correlation_id_gen", "ulid_gen"]
