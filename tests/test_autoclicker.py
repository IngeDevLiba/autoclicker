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


def test_parse_android_bounds_returns_centerable_box():
    bounds = autoclicker._parse_android_bounds("[10,20][110,220]")

    assert bounds == (10, 20, 110, 220)
    assert autoclicker._android_bounds_center("[10,20][110,220]") == (60, 120)


def test_find_browser_binary_prefers_edge(monkeypatch):
    def fake_exists(self):
        return str(self).lower().endswith("msedge.exe")

    monkeypatch.setattr(autoclicker.Path, "exists", fake_exists, raising=False)

    browser_name, browser_binary = autoclicker._find_browser_binary()

    assert browser_name == "edge"
    assert browser_binary.lower().endswith("msedge.exe")


def test_is_news_like_text_rejects_ad_labels():
    assert autoclicker._is_news_like_text("Anuncio patrocinado del día") is False
    assert autoclicker._is_news_like_text("Titular visible sobre tecnología y economía") is True


def test_pick_android_news_candidate_prefers_clickable_news_like_text():
    xml = """
    <hierarchy>
      <node text="Top stories" clickable="true" bounds="[0,0][100,100]" />
      <node text="Titular destacado de hoy" clickable="true" bounds="[10,200][410,320]" />
      <node text="Otro titular" clickable="true" bounds="[10,350][410,470]" />
    </hierarchy>
    """

    candidate = autoclicker._pick_android_news_candidate(xml)

    assert candidate is not None
    text, center, bounds = candidate
    assert text == "Titular destacado de hoy"
    assert center == (210, 260)
    assert bounds == (10, 200, 410, 320)


def test_pick_android_news_candidate_prefers_larger_clickable_card():
        xml = """
        <hierarchy>
            <node text="Titular principal" clickable="true" bounds="[10,180][200,230]" />
            <node text="Titular principal completo con tarjeta" clickable="true" bounds="[10,150][1030,410]" />
        </hierarchy>
        """

        candidate = autoclicker._pick_android_news_candidate(xml)

        assert candidate is not None
        text, center, bounds = candidate
        assert text == "Titular principal completo con tarjeta"
        assert center == (520, 280)
        assert bounds == (10, 150, 1030, 410)


def test_pick_android_news_candidate_uses_clickable_parent_for_text_node():
        xml = """
        <hierarchy>
            <node text="Titular visible sobre tecnología y economía" clickable="false" bounds="[40,220][220,260]">
                <node text="Titular visible sobre tecnología y economía" clickable="true" bounds="[20,200][1020,420]">
                    <node text="Titular visible sobre tecnología y economía" clickable="false" bounds="[60,230][200,255]" />
                </node>
            </node>
        </hierarchy>
        """

        candidate = autoclicker._pick_android_news_candidate(xml)

        assert candidate is not None
        text, center, bounds = candidate
        assert text == "Titular visible sobre tecnología y economía"
        assert center == (520, 310)
        assert bounds == (20, 200, 1020, 420)


def test_pick_android_news_candidate_ignores_header_area_candidates():
        xml = """
        <hierarchy>
            <node text="Titular de encabezado demasiado alto" clickable="true" bounds="[20,90][1040,170]" />
            <node text="Titular visible sobre tecnología y economía" clickable="true" bounds="[20,260][1040,520]" />
        </hierarchy>
        """

        candidate = autoclicker._pick_android_news_candidate(xml)

        assert candidate is not None
        text, center, bounds = candidate
        assert text == "Titular visible sobre tecnología y economía"
        assert center == (530, 390)
        assert bounds == (20, 260, 1040, 520)


def test_pick_cookie_reject_candidate_prefers_reject_action():
        xml = """
        <hierarchy>
            <node text="Aceptar todo" clickable="true" bounds="[100,1300][480,1380]" />
            <node text="Rechazar" clickable="true" bounds="[600,1300][980,1380]" />
        </hierarchy>
        """

        candidate = autoclicker._pick_cookie_reject_candidate(xml)

        assert candidate is not None
        label, center = candidate
        assert "rechazar" in label.lower()
        assert center == (790, 1340)


def test_pick_android_news_candidate_skips_video_container_with_duration():
        xml = """
        <hierarchy>
            <node text="Titular en video sobre salud y bienestar" clickable="true" bounds="[20,260][1040,520]">
                <node text="02:13" clickable="false" bounds="[900,470][1020,520]" />
            </node>
            <node text="Titular normal sobre ciencia y tecnología" clickable="true" bounds="[20,560][1040,820]" />
        </hierarchy>
        """

        candidate = autoclicker._pick_android_news_candidate(xml)

        assert candidate is not None
        text, center, bounds = candidate
        assert text == "Titular normal sobre ciencia y tecnología"
        assert center == (530, 690)
        assert bounds == (20, 560, 1040, 820)


def test_pick_android_news_candidate_skips_container_with_ad_label():
        xml = """
        <hierarchy>
            <node text="Titular patrocinado sobre economía y mercados" clickable="true" bounds="[20,260][1040,520]">
                <node text="Anuncio" clickable="false" bounds="[40,500][220,540]" />
            </node>
            <node text="Titular normal sobre cultura y ciencia" clickable="true" bounds="[20,560][1040,820]" />
        </hierarchy>
        """

        candidate = autoclicker._pick_android_news_candidate(xml)

        assert candidate is not None
        text, center, bounds = candidate
        assert text == "Titular normal sobre cultura y ciencia"
        assert center == (530, 690)
        assert bounds == (20, 560, 1040, 820)


def test_run_session_android_adb_dispatches_to_adb_mode(monkeypatch):
    called = {}

    def fake_run_android_adb_news_session(
        account: str,
        adb_serial: str = "",
        cycles: int | None = None,
    ) -> None:
        called["account"] = account
        called["adb_serial"] = adb_serial
        called["cycles"] = cycles

    monkeypatch.setattr(autoclicker, "_run_android_adb_news_session", fake_run_android_adb_news_session)

    autoclicker.run_session(
        account="demo@example.com",
        headless=False,
        android_adb=True,
        adb_serial="emulator-5554",
        android_cycles=7,
    )

    assert called == {"account": "demo@example.com", "adb_serial": "emulator-5554", "cycles": 7}


def test_run_session_desktop_forces_visible_browser_when_headless_is_requested(monkeypatch):
    called = {}

    def fake_build_driver(headless: bool):
        called["headless"] = headless

        class DummyDriver:
            def quit(self):
                called["quit"] = True

        return DummyDriver()

    monkeypatch.setattr(autoclicker, "_build_driver", fake_build_driver)
    monkeypatch.setattr(autoclicker, "_do_search", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker, "_searches_per_block", lambda total: [0, 0, total])
    monkeypatch.setattr(autoclicker, "_seconds_until_hour", lambda *args, **kwargs: 0.0)
    monkeypatch.setattr(autoclicker, "_wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker, "_random_wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker, "_say", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker.random, "randint", lambda *args, **kwargs: 1)
    monkeypatch.setattr(autoclicker, "get_random_queries", lambda total: [f"q{i}" for i in range(total)])

    autoclicker.run_session(
        account="demo@example.com",
        headless=True,
        android_adb=False,
    )

    assert called.get("quit") is True


def test_android_adb_news_session_taps_visible_candidate(monkeypatch):
    events: list[tuple[str, tuple[object, ...]]] = []
    xml_responses = iter(
        [
            """
            <hierarchy>
              <node text="Titular destacado de hoy sobre tecnología" clickable="true" bounds="[100,300][980,460]" />
            </hierarchy>
            """,
            """
            <hierarchy>
              <node text="Titular destacado de hoy sobre tecnología" clickable="true" bounds="[100,300][980,460]" />
            </hierarchy>
            """,
            """
            <hierarchy>
            </hierarchy>
            """,
        ]
    )

    monkeypatch.setattr(autoclicker, "_adb_screen_size", lambda *args: (1080, 2400))
    monkeypatch.setattr(autoclicker, "_adb_dump_ui_xml", lambda *args: next(xml_responses))
    monkeypatch.setattr(autoclicker, "_adb_tap", lambda *args: events.append(("tap", args)))
    monkeypatch.setattr(autoclicker, "_adb_swipe", lambda *args, **kwargs: events.append(("swipe", args)))
    monkeypatch.setattr(autoclicker, "_adb_shell", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker, "_wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker, "_say", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker.random, "uniform", lambda *args, **kwargs: 0.0)

    result = autoclicker._adb_news_session_read_one("adb", "device", "account@example.com")

    assert result is True
    tap_events = [event for event in events if event[0] == "tap"]
    assert len(tap_events) == 3
    assert tap_events[0][1][-2:] == (540, 380)


def test_android_adb_news_session_falls_back_to_enter(monkeypatch):
    events: list[tuple[str, tuple[object, ...]]] = []

    monkeypatch.setattr(autoclicker, "_adb_screen_size", lambda *args: (1080, 2400))
    monkeypatch.setattr(
        autoclicker,
        "_adb_dump_ui_xml",
        lambda *args: """
            <hierarchy>
              <node text="Titular destacado de hoy sobre tecnología" clickable="true" bounds="[100,300][980,460]" />
            </hierarchy>
        """,
    )
    monkeypatch.setattr(autoclicker, "_adb_tap", lambda *args: events.append(("tap", args)))
    monkeypatch.setattr(autoclicker, "_adb_shell", lambda *args: events.append(("shell", args)))
    monkeypatch.setattr(autoclicker, "_wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker, "_say", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker.random, "uniform", lambda *args, **kwargs: 0.0)
    monkeypatch.setattr(autoclicker, "_adb_card_opened", lambda *args, **kwargs: False)

    result = autoclicker._adb_news_session_read_one("adb", "device", "account@example.com")

    assert result is True
    assert any(event[0] == "shell" and event[1][-1] == "66" for event in events)


def test_android_adb_news_session_retries_second_tap_when_card_stays_visible(monkeypatch):
    events: list[tuple[str, tuple[object, ...]]] = []
    xml_responses = iter(
        [
            """
            <hierarchy>
              <node text="Titular destacado de hoy sobre tecnología" clickable="true" bounds="[100,300][980,460]" />
            </hierarchy>
            """,
            """
            <hierarchy>
              <node text="Titular destacado de hoy sobre tecnología" clickable="true" bounds="[100,300][980,460]" />
            </hierarchy>
            """,
            """
            <hierarchy>
            </hierarchy>
            """,
        ]
    )

    monkeypatch.setattr(autoclicker, "_adb_screen_size", lambda *args: (1080, 2400))
    monkeypatch.setattr(autoclicker, "_adb_dump_ui_xml", lambda *args: next(xml_responses))
    monkeypatch.setattr(autoclicker, "_adb_tap", lambda *args: events.append(("tap", args)))
    monkeypatch.setattr(autoclicker, "_adb_swipe", lambda *args, **kwargs: events.append(("swipe", args)))
    monkeypatch.setattr(autoclicker, "_adb_shell", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker, "_wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker, "_say", lambda *args, **kwargs: None)
    monkeypatch.setattr(autoclicker.random, "uniform", lambda *args, **kwargs: 0.0)

    result = autoclicker._adb_news_session_read_one("adb", "device", "account@example.com")

    assert result is True
    assert len([event for event in events if event[0] == "tap"]) == 2