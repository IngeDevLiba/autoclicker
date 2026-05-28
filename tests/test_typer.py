"""
Tests for typer.py.

These tests mock the Selenium WebElement so no browser is required.
They verify that type_naturally sends the correct characters
(possibly via adjacent-key typos + Backspace corrections) and
that the output is observable via the mock.
"""

import types
import random
import pytest

from unittest.mock import MagicMock, call, patch
from selenium.webdriver.common.keys import Keys

import typer as typer_module
from typer import type_naturally


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_element() -> MagicMock:
    """Return a mock WebElement."""
    elem = MagicMock()
    elem.send_keys = MagicMock()
    return elem


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_type_naturally_sends_all_chars_no_typo():
    """With TYPO_PROBABILITY=0 every character in the text must be sent."""
    elem = _make_element()
    text = "hello world"

    with (
        patch.object(typer_module, "TYPO_PROBABILITY", 0),
        patch("typer.time.sleep"),
    ):
        type_naturally(elem, text)

    sent = [c[0][0] for c in elem.send_keys.call_args_list]
    assert sent == list(text), f"Expected {list(text)}, got {sent}"


def test_type_naturally_introduces_backspace_on_typo():
    """With TYPO_PROBABILITY=1 every eligible character triggers a typo + Backspace."""
    elem = _make_element()
    text = "as"  # both 'a' and 's' have adjacent keys

    with (
        patch.object(typer_module, "TYPO_PROBABILITY", 1.0),
        patch("typer.time.sleep"),
    ):
        type_naturally(elem, text)

    sent = [c[0][0] for c in elem.send_keys.call_args_list]
    # Each character should have: wrong_char, Backspace, correct_char
    backspace_indices = [i for i, k in enumerate(sent) if k == Keys.BACKSPACE]
    assert len(backspace_indices) == len(text), (
        f"Expected {len(text)} Backspace(s), got {len(backspace_indices)}: {sent}"
    )


def test_type_naturally_empty_string():
    """Empty string must not send anything."""
    elem = _make_element()
    with patch("typer.time.sleep"):
        type_naturally(elem, "")
    elem.send_keys.assert_not_called()


def test_type_naturally_space_never_typo():
    """The space character has only one adjacent key (itself), so no typo is generated."""
    elem = _make_element()
    with (
        patch.object(typer_module, "TYPO_PROBABILITY", 1.0),
        patch("typer.time.sleep"),
    ):
        type_naturally(elem, "   ")  # three spaces

    sent = [c[0][0] for c in elem.send_keys.call_args_list]
    assert Keys.BACKSPACE not in sent, "Space should never produce a typo+backspace"
    assert sent.count(" ") == 3
