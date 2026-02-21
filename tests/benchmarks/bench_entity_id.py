"""§47.4 — Benchmark: EntityId.generate() throughput.

Compares UUID v7 generation (via EntityId.generate()) against the stdlib
uuid.uuid4() baseline to quantify the overhead of the custom generator.

Sub-benchmarks:
- ``uuid.uuid4()``                — raw stdlib baseline
- ``str(uuid.uuid4())``           — stringify baseline (matching EntityId output)
- ``EntityId.generate()``         — mp-commons custom v7 generator
- ``EntityId.generate().value``   — access .value after generation
- ``EntityId(str(uuid.uuid4()))`` — direct construction from an existing UUID
"""

from __future__ import annotations

import uuid

from mp_commons.kernel.types.ids import EntityId


def test_uuid4_baseline(benchmark):
    """stdlib ``uuid.uuid4()`` — raw generation baseline."""
    result = benchmark(uuid.uuid4)
    assert result is not None


def test_uuid4_str_baseline(benchmark):
    """``str(uuid.uuid4())`` — string conversion adds cost similar to EntityId."""

    def run():
        return str(uuid.uuid4())

    result = benchmark(run)
    assert len(result) == 36


def test_entity_id_generate(benchmark):
    """``EntityId.generate()`` — full v7/v4 generation + wrapping."""
    result = benchmark(EntityId.generate)
    assert isinstance(result, EntityId)
    assert result.value  # non-empty string


def test_entity_id_generate_access_value(benchmark):
    """``EntityId.generate().value`` — generation plus attribute access."""

    def run():
        return EntityId.generate().value

    result = benchmark(run)
    assert result  # truthy non-empty string


def test_entity_id_construct_from_str(benchmark):
    """``EntityId(str)`` — construction from a pre-existing string."""
    uid = str(uuid.uuid4())

    def run():
        return EntityId(uid)

    result = benchmark(run)
    assert result.value == uid


def test_entity_id_equality_check(benchmark):
    """Equality comparison between two EntityIds (frozen dataclass)."""
    a = EntityId.generate()
    b = EntityId(a.value)

    def run():
        return a == b

    result = benchmark(run)
    assert result is True


def test_entity_id_hash(benchmark):
    """``hash(EntityId)`` — used by sets and dict keys."""
    eid = EntityId.generate()

    def run():
        return hash(eid)

    result = benchmark(run)
    assert isinstance(result, int)
