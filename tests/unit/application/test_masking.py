"""Unit tests for §73 – Data Masking / PII."""
import hashlib
import logging
import uuid

import pytest

from mp_commons.application.masking import DataMasker, MaskingRule, PiiLogFilter


class TestDataMaskerRedact:
    def test_redact_string(self):
        masker = DataMasker()
        result = masker.mask({"email": "user@example.com"}, [MaskingRule("email", "redact")])
        assert result["email"] == "***"

    def test_non_matching_untouched(self):
        masker = DataMasker()
        result = masker.mask({"name": "Alice"}, [MaskingRule("email", "redact")])
        assert result["name"] == "Alice"

    def test_original_unchanged(self):
        masker = DataMasker()
        original = {"email": "user@example.com", "name": "Alice"}
        masker.mask(original, [MaskingRule("email", "redact")])
        assert original["email"] == "user@example.com"


class TestDataMaskerHash:
    def test_hash_deterministic(self):
        masker = DataMasker()
        r1 = masker.mask({"ssn": "123"}, [MaskingRule("ssn", "hash", salt="s")])
        r2 = masker.mask({"ssn": "123"}, [MaskingRule("ssn", "hash", salt="s")])
        assert r1["ssn"] == r2["ssn"]

    def test_hash_different_salt(self):
        masker = DataMasker()
        r1 = masker.mask({"ssn": "123"}, [MaskingRule("ssn", "hash", salt="s1")])
        r2 = masker.mask({"ssn": "123"}, [MaskingRule("ssn", "hash", salt="s2")])
        assert r1["ssn"] != r2["ssn"]

    def test_hash_length(self):
        masker = DataMasker()
        result = masker.mask({"ssn": "123"}, [MaskingRule("ssn", "hash")])
        assert len(result["ssn"]) == 8


class TestDataMaskerPartial:
    def test_partial_shows_edges(self):
        masker = DataMasker()
        rule = MaskingRule("card", "partial", partial_show_start=2, partial_show_end=2)
        result = masker.mask({"card": "1234567890"}, [rule])
        assert result["card"].startswith("12")
        assert result["card"].endswith("90")

    def test_partial_middle_hidden(self):
        masker = DataMasker()
        rule = MaskingRule("card", "partial", partial_show_start=2, partial_show_end=2)
        result = masker.mask({"card": "1234567890"}, [rule])
        assert "*" in result["card"]


class TestDataMaskerTokenize:
    def test_tokenize_deterministic(self):
        masker = DataMasker()
        r1 = masker.mask({"id": "user-1"}, [MaskingRule("id", "tokenize", salt="x")])
        r2 = masker.mask({"id": "user-1"}, [MaskingRule("id", "tokenize", salt="x")])
        assert r1["id"] == r2["id"]

    def test_tokenize_uuid_format(self):
        masker = DataMasker()
        result = masker.mask({"id": "user-1"}, [MaskingRule("id", "tokenize")])
        # Should parse as uuid
        parsed = uuid.UUID(result["id"])
        assert str(parsed) == result["id"]


class TestDataMaskerRecursive:
    def test_nested_dict(self):
        masker = DataMasker()
        data = {"user": {"email": "a@b.com", "name": "Bob"}}
        result = masker.mask(data, [MaskingRule("email", "redact")])
        assert result["user"]["email"] == "***"
        assert result["user"]["name"] == "Bob"

    def test_list_of_dicts(self):
        masker = DataMasker()
        data = {"users": [{"email": "a@b.com"}, {"email": "c@d.com"}]}
        result = masker.mask(data, [MaskingRule("email", "redact")])
        assert result["users"][0]["email"] == "***"
        assert result["users"][1]["email"] == "***"


class TestPiiLogFilter:
    def test_masks_dict_msg(self):
        masker_filter = PiiLogFilter([MaskingRule("email", "redact")])
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg={"email": "user@example.com", "text": "hello"},
            args=(), exc_info=None,
        )
        masker_filter.filter(record)
        assert record.msg["email"] == "***"
        assert record.msg["text"] == "hello"

    def test_filter_returns_true(self):
        f = PiiLogFilter([MaskingRule("ssn", "redact")])
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="plain text", args=(), exc_info=None,
        )
        assert f.filter(record) is True
