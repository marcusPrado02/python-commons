"""Pytest plugin for approval tests — §97.4.

Registers the ``--approve`` command-line flag.  When active:

* Every :class:`~mp_commons.testing.approval.asserter.ApprovalAsserter` call
  automatically promotes *received* output to *approved* (i.e. the test never
  fails on content mismatch — only on unexpected errors).
* After the session ends all remaining ``.received.txt`` files under
  ``tests/__approvals__`` (or the configured directory) are bulk-moved to
  ``.approved.txt``.

Activation (add to ``tests/conftest.py`` or ``conftest.py``)::

    pytest_plugins = [
        "mp_commons.testing.fixtures",
        "mp_commons.testing.approval.plugin",
    ]

Or copy the ``conftest.py`` snippet::

    # conftest.py
    def pytest_addoption(parser):
        from mp_commons.testing.approval.plugin import add_approve_option
        add_approve_option(parser)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

# Module-level flag read by ApprovalAsserter
_APPROVE_MODE: bool = False


def is_approve_mode() -> bool:
    """Return ``True`` when the ``--approve`` flag was passed."""
    return _APPROVE_MODE


def add_approve_option(parser: Any) -> None:
    """Register the ``--approve`` pytest option on *parser*.

    Call this from a ``pytest_addoption`` hook when you embed the plugin
    manually rather than via ``pytest_plugins``.
    """
    try:
        parser.addoption(
            "--approve",
            action="store_true",
            default=False,
            help=(
                "Approval-test mode: automatically promote all .received.txt "
                "files to .approved.txt (batch-approve a new baseline)."
            ),
        )
    except ValueError:
        # Option already registered (e.g. plugin loaded twice)
        pass


# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------


def pytest_addoption(parser: Any) -> None:
    add_approve_option(parser)


def pytest_configure(config: Any) -> None:
    """Persist the --approve flag so ApprovalAsserter can read it."""
    global _APPROVE_MODE  # noqa: PLW0603
    _APPROVE_MODE = bool(config.getoption("--approve", default=False))

    # Also set env-var so out-of-process asserters can check it
    if _APPROVE_MODE:
        os.environ["MP_APPROVE"] = "1"
    else:
        os.environ.pop("MP_APPROVE", None)


def pytest_sessionfinish(session: Any, exitstatus: Any) -> None:
    """After the session, bulk-promote any remaining .received.txt files."""
    if not _APPROVE_MODE:
        return

    approvals_dirs: list[Path] = []
    # Search common approval directories
    for candidate in ["tests/__approvals__", "__approvals__"]:
        p = Path(candidate)
        if p.is_dir():
            approvals_dirs.append(p)

    promoted = 0
    for approvals_dir in approvals_dirs:
        for received in approvals_dir.rglob("*.received.txt"):
            approved = received.with_suffix("").with_suffix(".approved.txt")
            received.replace(approved)
            promoted += 1

    if promoted:
        print(f"\n[mp-commons approval] Promoted {promoted} received → approved file(s).")


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(name="approve_mode")
def approve_mode_fixture() -> bool:
    """Return ``True`` when the test run was started with ``--approve``."""
    return _APPROVE_MODE


__all__ = [
    "add_approve_option",
    "approve_mode_fixture",
    "is_approve_mode",
]
