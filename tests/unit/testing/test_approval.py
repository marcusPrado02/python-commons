"""Unit tests for §97 Approval Tests — ApprovalAsserter, JsonApprovalAsserter, HtmlApprovalAsserter."""
import json
import pathlib
import tempfile

import pytest

from mp_commons.testing.approval import (
    ApprovalAsserter,
    ApprovalError,
    HtmlApprovalAsserter,
    JsonApprovalAsserter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _asserter(tmp_path, approve=False):
    return ApprovalAsserter(directory=str(tmp_path), approve=approve)


# ---------------------------------------------------------------------------
# ApprovalAsserter — first run (no approved file)
# ---------------------------------------------------------------------------

def test_approval_first_run_creates_received_and_raises(tmp_path):
    a = _asserter(tmp_path)
    with pytest.raises(ApprovalError, match="approved"):
        a.approve("hello world", "test_first_run")
    received = tmp_path / "test_first_run.received.txt"
    assert received.exists()
    assert received.read_text() == "hello world"


# ---------------------------------------------------------------------------
# ApprovalAsserter — passing (received matches approved)
# ---------------------------------------------------------------------------

def test_approval_passes_when_content_matches(tmp_path):
    approved = tmp_path / "test_match.approved.txt"
    approved.write_text("expected content")
    a = _asserter(tmp_path)
    a.approve("expected content", "test_match")  # must not raise


# ---------------------------------------------------------------------------
# ApprovalAsserter — mismatch shows diff
# ---------------------------------------------------------------------------

def test_approval_raises_with_diff_on_mismatch(tmp_path):
    approved = tmp_path / "test_diff.approved.txt"
    approved.write_text("expected content")
    a = _asserter(tmp_path)
    with pytest.raises(ApprovalError) as exc_info:
        a.approve("different content", "test_diff")
    assert "expected" in str(exc_info.value) or "different" in str(exc_info.value)


# ---------------------------------------------------------------------------
# ApprovalAsserter — auto-promote mode
# ---------------------------------------------------------------------------

def test_approval_auto_promote_creates_approved_and_passes(tmp_path):
    a = ApprovalAsserter(directory=str(tmp_path), approve=True)
    a.approve("auto approved text", "test_promote")  # must not raise
    approved = tmp_path / "test_promote.approved.txt"
    assert approved.exists()
    assert approved.read_text() == "auto approved text"


def test_approval_auto_promote_overwrites_existing(tmp_path):
    approved = tmp_path / "test_overwrite.approved.txt"
    approved.write_text("old content")
    a = ApprovalAsserter(directory=str(tmp_path), approve=True)
    a.approve("new content", "test_overwrite")
    assert approved.read_text() == "new content"


# ---------------------------------------------------------------------------
# ApprovalAsserter — file existence helpers
# ---------------------------------------------------------------------------

def test_approved_file_exists_false_when_absent(tmp_path):
    a = _asserter(tmp_path)
    assert a.approved_file_exists("ghost") is False


def test_approved_file_exists_true_when_present(tmp_path):
    (tmp_path / "ghost.approved.txt").write_text("x")
    a = _asserter(tmp_path)
    assert a.approved_file_exists("ghost") is True


def test_received_file_exists_after_first_run(tmp_path):
    a = _asserter(tmp_path)
    try:
        a.approve("x", "test_received_check")
    except ApprovalError:
        pass
    assert a.received_file_exists("test_received_check") is True


# ---------------------------------------------------------------------------
# JsonApprovalAsserter — normalisation
# ---------------------------------------------------------------------------

def test_json_asserter_normalises_key_order(tmp_path):
    a = JsonApprovalAsserter(directory=str(tmp_path), approve=True)
    payload1 = '{"b": 2, "a": 1}'
    a.approve(payload1, "test_json_keys")

    # second call with different key order must not raise
    payload2 = '{"a": 1, "b": 2}'
    a2 = JsonApprovalAsserter(directory=str(tmp_path), approve=False)
    a2.approve(payload2, "test_json_keys")


def test_json_asserter_detects_value_mismatch(tmp_path):
    a = JsonApprovalAsserter(directory=str(tmp_path), approve=True)
    a.approve('{"a": 1}', "test_json_mismatch")

    a2 = JsonApprovalAsserter(directory=str(tmp_path), approve=False)
    with pytest.raises(ApprovalError):
        a2.approve('{"a": 99}', "test_json_mismatch")


def test_json_asserter_invalid_json_raises_value_error(tmp_path):
    a = JsonApprovalAsserter(directory=str(tmp_path))
    with pytest.raises((ValueError, ApprovalError)):
        a.approve("not json {{{", "test_json_invalid")


# ---------------------------------------------------------------------------
# HtmlApprovalAsserter — normalisation
# ---------------------------------------------------------------------------

def test_html_asserter_normalises_whitespace(tmp_path):
    html1 = "<html><body><p>Hello</p></body></html>"
    a = HtmlApprovalAsserter(directory=str(tmp_path), approve=True)
    a.approve(html1, "test_html_ws")

    html2 = "<html>  <body>  <p>Hello</p>  </body>  </html>"
    a2 = HtmlApprovalAsserter(directory=str(tmp_path), approve=False)
    a2.approve(html2, "test_html_ws")


def test_html_asserter_strips_timestamps(tmp_path):
    html_with_ts = '<html><body><span>2024-01-01T00:00:00</span></body></html>'
    a = HtmlApprovalAsserter(directory=str(tmp_path), approve=True)
    a.approve(html_with_ts, "test_html_ts")

    html_diff_ts = '<html><body><span>2099-12-31T23:59:59</span></body></html>'
    a2 = HtmlApprovalAsserter(directory=str(tmp_path), approve=False)
    a2.approve(html_diff_ts, "test_html_ts")  # different timestamp → still passes


def test_html_asserter_detects_structural_mismatch(tmp_path):
    html1 = "<html><body><p>Hello</p></body></html>"
    a = HtmlApprovalAsserter(directory=str(tmp_path), approve=True)
    a.approve(html1, "test_html_mismatch")

    html2 = "<html><body><p>World</p></body></html>"
    a2 = HtmlApprovalAsserter(directory=str(tmp_path), approve=False)
    with pytest.raises(ApprovalError):
        a2.approve(html2, "test_html_mismatch")


# §97.4 – --approve plugin flag
# ---------------------------------------------------------------------------


def test_is_approve_mode_default_false():
    """is_approve_mode() returns False when MP_APPROVE not set."""
    import os
    # Ensure env var is not set
    os.environ.pop("MP_APPROVE", None)
    from mp_commons.testing.approval.plugin import is_approve_mode, _APPROVE_MODE
    # Module-level flag should be False in normal test run
    assert not is_approve_mode()


def test_asserter_uses_mp_approve_env(tmp_path):
    """ApprovalAsserter defaults approve=True when MP_APPROVE=1."""
    import os
    os.environ["MP_APPROVE"] = "1"
    try:
        asserter = ApprovalAsserter(directory=str(tmp_path))
        assert asserter._approve is True
    finally:
        os.environ.pop("MP_APPROVE", None)


def test_asserter_approve_false_when_env_unset(tmp_path):
    """ApprovalAsserter defaults approve=False when MP_APPROVE not set."""
    import os
    os.environ.pop("MP_APPROVE", None)
    asserter = ApprovalAsserter(directory=str(tmp_path))
    assert asserter._approve is False


def test_asserter_explicit_approve_overrides_env(tmp_path):
    """Explicitly passing approve=False overrides MP_APPROVE env var."""
    import os
    os.environ["MP_APPROVE"] = "1"
    try:
        asserter = ApprovalAsserter(directory=str(tmp_path), approve=False)
        assert asserter._approve is False
    finally:
        os.environ.pop("MP_APPROVE", None)


def test_approve_plugin_session_finish_promotes_files(tmp_path):
    """pytest_sessionfinish bulk-promotes .received.txt to .approved.txt."""
    import mp_commons.testing.approval.plugin as plugin

    # Set approve mode
    orig = plugin._APPROVE_MODE
    plugin._APPROVE_MODE = True
    approvals_dir = tmp_path / "tests" / "__approvals__"
    approvals_dir.mkdir(parents=True)

    # Create some received files
    (approvals_dir / "test_a.received.txt").write_text("A")
    (approvals_dir / "test_b.received.txt").write_text("B")

    # Patch Path("tests/__approvals__") to point to tmp_path / "tests" / "__approvals__"
    import importlib, os
    orig_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        plugin.pytest_sessionfinish(session=None, exitstatus=0)
    finally:
        os.chdir(orig_cwd)
        plugin._APPROVE_MODE = orig

    approved_a = approvals_dir / "test_a.approved.txt"
    approved_b = approvals_dir / "test_b.approved.txt"
    assert approved_a.exists()
    assert approved_b.exists()
    assert approved_a.read_text() == "A"
    assert approved_b.read_text() == "B"
