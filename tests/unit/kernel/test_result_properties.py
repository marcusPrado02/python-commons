"""Hypothesis property tests for Result[T, E] monad laws (T-05)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
import pytest

from mp_commons.kernel.types.result import Err, Ok, Result

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

VALUES = st.one_of(
    st.integers(),
    st.text(max_size=20),
    st.floats(allow_nan=False, allow_infinity=False),
    st.none(),
)

ERRORS = st.builds(ValueError, st.text(max_size=30))


def ok_strategy() -> st.SearchStrategy:
    return st.builds(Ok, VALUES)


def err_strategy() -> st.SearchStrategy:
    return st.builds(Err, ERRORS)


def result_strategy() -> st.SearchStrategy:
    return st.one_of(ok_strategy(), err_strategy())


# ---------------------------------------------------------------------------
# Functor laws (map)
# ---------------------------------------------------------------------------


@given(result_strategy())
def test_map_identity(r: Result) -> None:
    """map(id) == id — Functor identity law."""
    mapped = r.map(lambda x: x)
    assert mapped.is_ok() == r.is_ok()
    assert mapped.is_err() == r.is_err()
    if r.is_ok():
        assert mapped.unwrap() == r.unwrap()


@given(st.builds(Ok, st.integers()), st.integers(min_value=-100, max_value=100))
def test_map_ok_applies_function(r: Ok, n: int) -> None:
    """Ok(x).map(f) == Ok(f(x))."""
    result = r.map(lambda x: x + n)
    assert result.is_ok()
    assert result.unwrap() == r.unwrap() + n


@given(err_strategy(), st.integers())
def test_map_err_is_noop(r: Err, n: int) -> None:
    """Err(e).map(f) == Err(e) — map is a no-op on Err."""
    original_error = r.error
    result = r.map(lambda x: x + n)
    assert result.is_err()
    assert result.error is original_error


# ---------------------------------------------------------------------------
# Monad laws (flat_map)
# ---------------------------------------------------------------------------


@given(VALUES)
def test_left_identity(a) -> None:
    """Ok(a).flat_map(f) == f(a) — Monad left identity."""

    def f(x):
        if x is None or (isinstance(x, float) and x != x):
            return Ok(0)
        return Ok(str(x))

    assert Ok(a).flat_map(f).is_ok() == f(a).is_ok()
    if Ok(a).flat_map(f).is_ok():
        assert Ok(a).flat_map(f).unwrap() == f(a).unwrap()


@given(VALUES)
def test_right_identity(a) -> None:
    """Ok(a).flat_map(Ok) == Ok(a) — Monad right identity."""
    result = Ok(a).flat_map(Ok)
    assert result.is_ok()
    assert result.unwrap() == a


@given(ERRORS)
def test_right_identity_err(e: ValueError) -> None:
    """Err(e).flat_map(Ok) == Err(e) — right identity propagates Err."""
    result = Err(e).flat_map(Ok)
    assert result.is_err()
    assert result.error is e


@given(VALUES)
def test_associativity(a) -> None:
    """(Ok(a).flat_map(f)).flat_map(g) == Ok(a).flat_map(lambda x: f(x).flat_map(g))."""

    def f(x):
        if isinstance(x, (int, float)) and not (isinstance(x, float) and (x != x)):
            return Ok(abs(int(x)) % 1000)
        return Ok(0)

    def g(x):
        return Ok(x * 2)

    lhs = Ok(a).flat_map(f).flat_map(g)
    rhs = Ok(a).flat_map(lambda x: f(x).flat_map(g))

    assert lhs.is_ok() == rhs.is_ok()
    if lhs.is_ok():
        assert lhs.unwrap() == rhs.unwrap()


# ---------------------------------------------------------------------------
# Short-circuit on Err propagation
# ---------------------------------------------------------------------------


@given(ERRORS)
def test_flat_map_err_short_circuits(e: ValueError) -> None:
    """Err short-circuits the flat_map chain — f is never called."""
    calls: list[int] = []

    def f(x):
        calls.append(x)
        return Ok(x)

    Err(e).flat_map(f).flat_map(f)
    assert calls == []


# ---------------------------------------------------------------------------
# unwrap / unwrap_or invariants
# ---------------------------------------------------------------------------


@given(VALUES, VALUES)
def test_ok_unwrap_or_returns_value(value, default) -> None:
    assert Ok(value).unwrap_or(default) == value


@given(ERRORS, VALUES)
def test_err_unwrap_or_returns_default(e: ValueError, default) -> None:
    assert Err(e).unwrap_or(default) is default


@given(ERRORS)
def test_err_unwrap_raises(e: ValueError) -> None:
    with pytest.raises(ValueError):
        Err(e).unwrap()


@given(VALUES)
def test_ok_unwrap_returns_value(value) -> None:
    assert Ok(value).unwrap() == value


# ---------------------------------------------------------------------------
# is_ok / is_err are complements
# ---------------------------------------------------------------------------


@given(result_strategy())
def test_is_ok_and_is_err_are_complements(r: Result) -> None:
    assert r.is_ok() != r.is_err()
