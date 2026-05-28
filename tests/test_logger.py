"""Tests for logger.py — writes CSV files to a tmp directory."""

import csv
import os
import tempfile
import pytest

import logger as log_module
from logger import log_action


@pytest.fixture(autouse=True)
def tmp_log_dir(tmp_path, monkeypatch):
    """Redirect LOG_DIR to a temporary directory for each test."""
    monkeypatch.setattr(log_module, "LOG_DIR", str(tmp_path / "logs"))
    return tmp_path / "logs"


def test_log_creates_file(tmp_log_dir):
    log_action("test@example.com", "python tutorial", "https://example.com", 25.5)
    expected = tmp_log_dir / "test_at_example.com.csv"
    assert expected.is_file(), "Log file was not created"


def test_log_header(tmp_log_dir):
    log_action("test@example.com", "python", "https://example.com", 10)
    path = tmp_log_dir / "test_at_example.com.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert set(reader.fieldnames) == {"date", "account", "keyword", "url", "dwell_seconds"}


def test_log_row_content(tmp_log_dir):
    log_action("user@test.com", "noticias hoy", "https://bing.com/search?q=noticias", 30)
    path = tmp_log_dir / "user_at_test.com.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    row = rows[0]
    assert row["account"] == "user@test.com"
    assert row["keyword"] == "noticias hoy"
    assert row["url"] == "https://bing.com/search?q=noticias"
    assert float(row["dwell_seconds"]) == pytest.approx(30, abs=0.1)


def test_log_appends_multiple_rows(tmp_log_dir):
    account = "multi@test.com"
    for i in range(5):
        log_action(account, f"query {i}", f"https://example.com/{i}", float(i * 5))
    path = tmp_log_dir / "multi_at_test.com.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 5


def test_log_header_written_once(tmp_log_dir):
    account = "header@test.com"
    for _ in range(3):
        log_action(account, "query", "https://example.com", 10)
    path = tmp_log_dir / "header_at_test.com.csv"
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    # Header line should appear exactly once
    assert content.count("date,account,keyword") == 1
