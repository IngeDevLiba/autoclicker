"""Tests for autoclicker.py that avoid launching a browser."""

import autoclicker


class FakeDriver:
    pass


def test_desktop_news_flow_is_skipped(monkeypatch):
    messages: list[str] = []
    monkeypatch.setattr(autoclicker, "_say", lambda message: messages.append(message))

    autoclicker._maybe_read_homepage_news(FakeDriver(), "account@example.com", "noticias hoy")

    assert messages
    assert "no se acredita en pc" in messages[0].lower()