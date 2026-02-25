"""Unit tests for Hypothesis strategies – §38.3 (mocked, no hypothesis required)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_st() -> MagicMock:
    """Return a mock for hypothesis.strategies that tracks all calls."""
    st = MagicMock(name="hypothesis.strategies")
    # Make chained calls return new MagicMocks so we can inspect them
    st.uuids.return_value = MagicMock(name="uuids_strategy")
    st.uuids.return_value.map.return_value = MagicMock(name="mapped_uuids")
    st.decimals.return_value = MagicMock(name="decimals_strategy")
    st.sampled_from.return_value = MagicMock(name="currency_strategy")
    st.builds.return_value = MagicMock(name="built_strategy")
    st.text.return_value = MagicMock(name="text_strategy")
    return st


# ===========================================================================
# Import guard
# ===========================================================================

class TestRequireHypothesis:
    def test_raises_import_error_without_hypothesis(self):
        import sys
        from mp_commons.testing.generators.strategies import _require_hypothesis

        with patch.dict(sys.modules, {"hypothesis.strategies": None}):
            # Simulate hypothesis not installed by patching the import
            with patch("builtins.__import__", side_effect=ImportError("hypothesis")):
                with pytest.raises(ImportError):
                    _require_hypothesis()

    def test_error_message_mentions_hypothesis(self):
        import mp_commons.testing.generators.strategies as _strat_mod

        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            side_effect=ImportError("Install 'hypothesis'"),
        ):
            with pytest.raises(ImportError, match="hypothesis"):
                _strat_mod._require_hypothesis()


# ===========================================================================
# Module-level – import should work without hypothesis installed
# ===========================================================================

class TestModuleImport:
    def test_module_importable_without_hypothesis(self):
        """Importing strategies.py itself must not raise even without hypothesis."""
        import importlib
        import mp_commons.testing.generators.strategies as mod

        assert hasattr(mod, "entity_id_strategy")
        assert hasattr(mod, "money_strategy")
        assert hasattr(mod, "email_strategy")

    def test_exported_from_generators_package(self):
        from mp_commons.testing.generators import (
            email_strategy,
            entity_id_strategy,
            money_strategy,
        )

        assert callable(entity_id_strategy)
        assert callable(money_strategy)
        assert callable(email_strategy)

    def test_exported_from_testing_package(self):
        from mp_commons.testing import (
            email_strategy,
            entity_id_strategy,
            money_strategy,
        )

        assert callable(entity_id_strategy)
        assert callable(money_strategy)
        assert callable(email_strategy)

    def test_present_in_generators_all(self):
        import mp_commons.testing.generators as pkg

        assert "entity_id_strategy" in pkg.__all__
        assert "money_strategy" in pkg.__all__
        assert "email_strategy" in pkg.__all__

    def test_present_in_testing_all(self):
        import mp_commons.testing as pkg

        assert "entity_id_strategy" in pkg.__all__
        assert "money_strategy" in pkg.__all__
        assert "email_strategy" in pkg.__all__


# ===========================================================================
# §38.3 – entity_id_strategy
# ===========================================================================

class TestEntityIdStrategy:
    def test_calls_st_uuids(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import entity_id_strategy
            entity_id_strategy()
        mock_st.uuids.assert_called_once()

    def test_maps_uuid_to_entity_id(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import entity_id_strategy
            entity_id_strategy()
        # .map() should have been called on the uuids strategy
        mock_st.uuids.return_value.map.assert_called_once()

    def test_map_lambda_produces_valid_entity_id(self):
        """The map function passed to st.uuids() must create a valid EntityId."""
        import uuid
        from mp_commons.kernel.types.ids import EntityId

        captured_map_fn: list[Any] = []
        mock_st = _make_mock_st()
        mock_st.uuids.return_value.map.side_effect = lambda fn: (
            captured_map_fn.append(fn) or MagicMock()
        )

        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import entity_id_strategy
            entity_id_strategy()

        assert len(captured_map_fn) == 1
        sample_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = captured_map_fn[0](sample_uuid)
        assert isinstance(result, EntityId)
        assert result.value == str(sample_uuid)

    def test_returns_strategy_object(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import entity_id_strategy
            result = entity_id_strategy()
        # Should be the return value of .map()
        assert result is mock_st.uuids.return_value.map.return_value

    def test_raises_when_hypothesis_missing(self):
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            side_effect=ImportError("Install 'hypothesis'"),
        ):
            from mp_commons.testing.generators.strategies import entity_id_strategy
            with pytest.raises(ImportError, match="hypothesis"):
                entity_id_strategy()


# ===========================================================================
# §38.3 – money_strategy
# ===========================================================================

class TestMoneyStrategy:
    def test_calls_st_decimals(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy()
        mock_st.decimals.assert_called_once()

    def test_decimals_min_is_zero_by_default(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy()
        kwargs = mock_st.decimals.call_args.kwargs
        assert kwargs["min_value"] == Decimal("0")

    def test_decimals_disallows_nan_and_infinity(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy()
        kwargs = mock_st.decimals.call_args.kwargs
        assert kwargs["allow_nan"] is False
        assert kwargs["allow_infinity"] is False

    def test_decimals_has_two_decimal_places(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy()
        kwargs = mock_st.decimals.call_args.kwargs
        assert kwargs["places"] == 2

    def test_calls_st_sampled_from_for_currencies(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy()
        mock_st.sampled_from.assert_called_once()

    def test_uses_default_common_currencies(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy()
        sampled_arg = mock_st.sampled_from.call_args.args[0]
        assert "BRL" in sampled_arg
        assert "USD" in sampled_arg
        assert "EUR" in sampled_arg

    def test_custom_currencies_are_passed_to_sampled_from(self):
        mock_st = _make_mock_st()
        custom = ["BRL", "USD"]
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy(currencies=custom)
        sampled_arg = mock_st.sampled_from.call_args.args[0]
        assert sampled_arg == custom

    def test_calls_st_builds_with_money(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy()
        from mp_commons.kernel.types.money import Money
        mock_st.builds.assert_called_once()
        assert mock_st.builds.call_args.args[0] is Money

    def test_custom_min_max_amount(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy(min_amount="10.00", max_amount="100.00")
        kwargs = mock_st.decimals.call_args.kwargs
        assert kwargs["min_value"] == Decimal("10.00")
        assert kwargs["max_value"] == Decimal("100.00")

    def test_tuple_currencies_accepted(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            money_strategy(currencies=("GBP", "JPY"))
        sampled_arg = mock_st.sampled_from.call_args.args[0]
        assert "GBP" in sampled_arg
        assert "JPY" in sampled_arg

    def test_raises_when_hypothesis_missing(self):
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            side_effect=ImportError("Install 'hypothesis'"),
        ):
            from mp_commons.testing.generators.strategies import money_strategy
            with pytest.raises(ImportError, match="hypothesis"):
                money_strategy()


# ===========================================================================
# §38.3 – email_strategy
# ===========================================================================

class TestEmailStrategy:
    def test_calls_st_text_three_times(self):
        """user, domain, tld parts each get their own st.text() call."""
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import email_strategy
            email_strategy()
        assert mock_st.text.call_count == 3

    def test_all_text_parts_have_min_size(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import email_strategy
            email_strategy()
        for call in mock_st.text.call_args_list:
            assert "min_size" in call.kwargs or len(call.args) >= 2

    def test_calls_st_builds_for_email_construction(self):
        mock_st = _make_mock_st()
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import email_strategy
            email_strategy()
        mock_st.builds.assert_called_once()

    def test_builds_lambda_produces_valid_email(self):
        """The lambda passed to st.builds() must create a valid Email."""
        from mp_commons.kernel.types.email import Email

        captured_fn: list[Any] = []
        mock_st = _make_mock_st()
        mock_st.builds.side_effect = lambda fn, **_kw: (
            captured_fn.append(fn) or MagicMock()
        )

        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import email_strategy
            email_strategy()

        assert len(captured_fn) == 1
        result = captured_fn[0](u="alice", d="example", t="com")
        assert isinstance(result, Email)
        assert result.value == "alice@example.com"

    def test_tld_part_alphabet_lowercase_only(self):
        """TLD part should only use lowercase letters (a–z)."""
        mock_st = _make_mock_st()
        calls: list[Any] = []
        mock_st.text.side_effect = lambda alphabet, **_kw: (
            calls.append(alphabet) or MagicMock()
        )

        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            return_value=mock_st,
        ):
            from mp_commons.testing.generators.strategies import email_strategy
            email_strategy()

        # Third st.text() call is the TLD
        tld_alphabet = calls[2]
        assert all(c.isalpha() for c in tld_alphabet)
        assert tld_alphabet == tld_alphabet.lower()

    def test_raises_when_hypothesis_missing(self):
        with patch(
            "mp_commons.testing.generators.strategies._require_hypothesis",
            side_effect=ImportError("Install 'hypothesis'"),
        ):
            from mp_commons.testing.generators.strategies import email_strategy
            with pytest.raises(ImportError, match="hypothesis"):
                email_strategy()
