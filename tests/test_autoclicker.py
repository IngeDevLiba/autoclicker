"""Tests for autoclicker.py that avoid launching a browser."""

from types import SimpleNamespace

import autoclicker


class FakeElement:
    def __init__(self, text: str, href: str = "https://example.com/news") -> None:
        self.text = text
        self._href = href

    def get_attribute(self, name: str) -> str:
        if name == "href":
            return self._href
        return ""


class FakeDriver:
    def __init__(self, selector_map: dict[str, list[FakeElement]]) -> None:
        self.selector_map = selector_map
        self.current_window_handle = "main"
        self.window_handles = ["main"]
        self.switch_to = SimpleNamespace(window=lambda handle: None)

    def find_elements(self, by, selector):
        return list(self.selector_map.get(selector, []))


def test_find_first_element_uses_first_matching_selector():
    driver = FakeDriver(
        {
            "missing": [],
            ".news-card a": [FakeElement("Primera noticia")],
            ".b_promoteItem a": [FakeElement("Segunda noticia")],
        }
    )

    element = autoclicker._find_first_element(
        driver, ["missing", ".news-card a", ".b_promoteItem a"]
    )

    assert element is not None
    assert element.text == "Primera noticia"


def test_homepage_news_path_prefers_visible_news_cards(monkeypatch):
    driver = FakeDriver({".news-card a": [FakeElement("Titular destacado")]})
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(autoclicker.random, "random", lambda: 0.0)
    monkeypatch.setattr(
        autoclicker,
        "_read_link_page",
        lambda *args, **kwargs: calls.append(kwargs),
    )

    autoclicker._maybe_read_homepage_news(driver, "account@example.com", "noticias hoy")

    assert len(calls) == 1
    assert calls[0]["preserve_current_page"] is True