"""Android ADB helper functions for the mobile news flow."""
from __future__ import annotations

import importlib
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple
import xml.etree.ElementTree as ET

from config import (
    ANDROID_NEWS_CYCLES,
    ANDROID_NEWS_MIN_TOP_PX,
    ANDROID_NEWS_RETURN_WAIT_MAX,
    ANDROID_NEWS_RETURN_WAIT_MIN,
    ANDROID_NEWS_SCAN_ATTEMPTS,
    ANDROID_NEWS_SCROLL_PAUSE_MAX,
    ANDROID_NEWS_SCROLL_PAUSE_MIN,
    ANDROID_NEWS_SCROLL_STEPS_MAX,
    ANDROID_NEWS_SCROLL_STEPS_MIN,
    ANDROID_NEWS_TAP_JITTER_PX,
    ARTICLE_DWELL_MAX,
    ARTICLE_DWELL_MIN,
    LOG_DATE_FORMAT,
    LOG_DIR,
    PAGE_LOAD_WAIT_MAX,
    PAGE_LOAD_WAIT_MIN,
)
from logger import log_action


def _proxy(name: str, *args, **kwargs):
    module = importlib.import_module("autoclicker")
    return getattr(module, name)(*args, **kwargs)


def _say(message: str) -> None:
    from datetime import datetime

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {message}")


def _wait(seconds: float, reason: str = "") -> None:
    label = f"Esperando {seconds:.0f} segundos"
    if reason:
        label += f" {reason}"
    _say(label + "…")
    import time

    time.sleep(seconds)


def _parse_android_bounds(bounds: str) -> Tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _android_bounds_center(bounds: str) -> Tuple[int, int] | None:
    parsed = _parse_android_bounds(bounds)
    if parsed is None:
        return None
    left, top, right, bottom = parsed
    return ((left + right) // 2, (top + bottom) // 2)


def _is_news_like_text(text: str) -> bool:
    normalized = text.strip().lower()
    if len(normalized) < 18:
        return False
    if any(marker in normalized for marker in ("anuncio", "anuncios", "patrocinado", "publicidad", "sponsored", "advertisement", "ad choice")):
        return False
    blocked = {"news", "search", "sign in", "more", "see all", "top stories", "images", "videos"}
    return normalized not in blocked


def _pick_android_news_candidate(
    xml_text: str,
) -> Tuple[str, Tuple[int, int], Tuple[int, int, int, int]] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    candidates: List[Tuple[int, int, int, str, Tuple[int, int], Tuple[int, int, int, int]]] = []

    def _bounds_contains_center(outer: Tuple[int, int, int, int], inner: Tuple[int, int, int, int]) -> bool:
        left, top, right, bottom = inner
        center_x = (left + right) // 2
        center_y = (top + bottom) // 2
        outer_left, outer_top, outer_right, outer_bottom = outer
        return outer_left <= center_x <= outer_right and outer_top <= center_y <= outer_bottom

    def _container_metadata_tokens(container_bounds: Tuple[int, int, int, int]) -> List[str]:
        tokens: List[str] = []
        for candidate_node in root.iter("node"):
            node_bounds = _parse_android_bounds(candidate_node.attrib.get("bounds", ""))
            if node_bounds is None or not _bounds_contains_center(container_bounds, node_bounds):
                continue
            parts = [
                (candidate_node.attrib.get("text") or "").strip(),
                (candidate_node.attrib.get("content-desc") or "").strip(),
                (candidate_node.attrib.get("resource-id") or "").strip(),
            ]
            combined = " ".join(part for part in parts if part).lower()
            if combined:
                tokens.append(combined)
        return tokens

    def _is_blocked_container(container_bounds: Tuple[int, int, int, int]) -> bool:
        metadata = _container_metadata_tokens(container_bounds)
        if not metadata:
            return False
        if any(any(marker in token for marker in ("anuncio", "anuncios", "patrocinado", "publicidad", "sponsored", "advertisement", "ad choice")) for token in metadata):
            return True
        if any(any(marker in token for marker in ("video", "videos", "reproducir", "play", "duración", "duration", "min watching")) for token in metadata):
            return True
        return any(re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", token) is not None for token in metadata)

    def walk(node: ET.Element, clickable_ancestors: List[Tuple[int, int, int, int]]):
        parsed_bounds = _parse_android_bounds(node.attrib.get("bounds", ""))
        next_clickable_ancestors = clickable_ancestors
        if node.attrib.get("clickable") == "true" and parsed_bounds is not None:
            next_clickable_ancestors = clickable_ancestors + [parsed_bounds]

        text = (node.attrib.get("text") or "").strip()
        if text and _is_news_like_text(text):
            chosen_bounds = next_clickable_ancestors[-1] if next_clickable_ancestors else parsed_bounds
            if chosen_bounds is not None:
                left, top, right, bottom = chosen_bounds
                if top >= ANDROID_NEWS_MIN_TOP_PX and not _is_blocked_container(chosen_bounds):
                    x = (left + right) // 2
                    y = (top + bottom) // 2
                    area = max(0, right - left) * max(0, bottom - top)
                    candidates.append((top, -area, x, text, (x, y), chosen_bounds))

        for child in list(node):
            walk(child, next_clickable_ancestors)

    walk(root, [])
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    _, _, _, text, center, bounds = candidates[0]
    return text, center, bounds


def _pick_cookie_reject_candidate(xml_text: str) -> Tuple[str, Tuple[int, int]] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    reject_markers = ("rechazar", "denegar", "decline", "reject", "no aceptar", "solo necesarias", "only necessary", "necessary only")
    candidates: List[Tuple[int, int, int, str, Tuple[int, int]]] = []

    for node in root.iter("node"):
        text = (node.attrib.get("text") or "").strip()
        content_desc = (node.attrib.get("content-desc") or "").strip()
        resource_id = (node.attrib.get("resource-id") or "").strip()
        combined = " ".join(part for part in [text, content_desc, resource_id] if part).lower()
        if not combined or not any(marker in combined for marker in reject_markers):
            continue
        parsed_bounds = _parse_android_bounds(node.attrib.get("bounds", ""))
        if parsed_bounds is None:
            continue
        left, top, right, bottom = parsed_bounds
        center = ((left + right) // 2, (top + bottom) // 2)
        priority = 0 if ("rechazar" in combined or "reject" in combined or "denegar" in combined) else 1
        candidates.append((priority, top, center[0], text or content_desc or resource_id, center))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    _, _, _, label, center = candidates[0]
    return label, center


def _find_adb_binary() -> str:
    candidates: List[str] = []
    which_adb = shutil.which("adb")
    if which_adb:
        candidates.append(which_adb)

    for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        base = os.environ.get(env_var)
        if base:
            candidates.extend([str(Path(base) / "platform-tools" / "adb.exe"), str(Path(base) / "platform-tools" / "adb")])

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        sdk_base = Path(local_app_data) / "Android" / "Sdk" / "platform-tools"
        candidates.extend([str(sdk_base / "adb.exe"), str(sdk_base / "adb")])

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    raise RuntimeError("No se encontró adb. Instala Android platform-tools y agrega adb al PATH.")


def _adb_run(adb_path: str, serial: str | None, *args: str) -> subprocess.CompletedProcess[str]:
    command = [adb_path]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    return subprocess.run(command, check=True, capture_output=True, text=True)


def _adb_output(adb_path: str, serial: str | None, *args: str) -> str:
    return _adb_run(adb_path, serial, *args).stdout


def _adb_connected_devices(adb_path: str) -> List[str]:
    output = _adb_output(adb_path, None, "devices")
    devices: List[str] = []
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def _resolve_adb_serial(adb_path: str, requested_serial: str = "") -> str:
    devices = _adb_connected_devices(adb_path)
    if requested_serial:
        if requested_serial not in devices:
            raise RuntimeError(
                f"No se encontró el dispositivo ADB '{requested_serial}'. Dispositivos disponibles: {', '.join(devices) or 'ninguno'}."
            )
        return requested_serial

    if not devices:
        raise RuntimeError("No hay dispositivos ADB conectados. Activa USB debugging y verifica `adb devices`.")

    if len(devices) > 1:
        raise RuntimeError(f"Hay más de un dispositivo ADB conectado. Usa --adb-serial para elegir uno: {', '.join(devices)}.")

    return devices[0]


def _adb_shell(adb_path: str, serial: str, *args: str) -> subprocess.CompletedProcess[str]:
    return _adb_run(adb_path, serial, "shell", *args)


def _adb_launch_bing(adb_path: str, serial: str) -> None:
    _adb_shell(adb_path, serial, "monkey", "-p", "com.microsoft.bing", "-c", "android.intent.category.LAUNCHER", "1")


def _adb_screen_size(adb_path: str, serial: str) -> Tuple[int, int]:
    output = _adb_shell(adb_path, serial, "wm", "size").stdout
    match = re.search(r"Physical size:\s*(\d+)x(\d+)", output)
    if match is None:
        match = re.search(r"Override size:\s*(\d+)x(\d+)", output)
    if match is None:
        raise RuntimeError(f"No se pudo leer el tamaño de pantalla desde adb: {output!r}")
    return int(match.group(1)), int(match.group(2))


def _adb_tap(adb_path: str, serial: str, x: int, y: int) -> None:
    _adb_shell(adb_path, serial, "input", "tap", str(x), str(y))


def _adb_swipe(adb_path: str, serial: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 400) -> None:
    _adb_shell(adb_path, serial, "input", "swipe", str(start_x), str(start_y), str(end_x), str(end_y), str(duration_ms))


def _adb_dump_ui_xml(adb_path: str, serial: str) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        remote_path = "/sdcard/window_dump.xml"
        local_path = Path(temp_dir) / "window_dump.xml"
        _adb_shell(adb_path, serial, "uiautomator", "dump", remote_path)
        _adb_run(adb_path, serial, "pull", remote_path, str(local_path))
        return local_path.read_text(encoding="utf-8", errors="ignore")


def _adb_article_tap_points(bounds: Tuple[int, int, int, int], width: int, height: int) -> List[Tuple[int, int]]:
    left, top, right, bottom = bounds
    card_width = max(1, right - left)
    card_height = max(1, bottom - top)
    jitter = max(1, ANDROID_NEWS_TAP_JITTER_PX)
    return [
        (max(1, min(width - 1, left + card_width // 2)), max(1, min(height - 1, top + card_height // 2))),
        (max(1, min(width - 1, left + int(card_width * 0.45) + random.randint(-jitter, jitter))), max(1, min(height - 1, top + int(card_height * 0.44) + random.randint(-jitter, jitter)))),
        (max(1, min(width - 1, left + int(card_width * 0.55) + random.randint(-jitter, jitter))), max(1, min(height - 1, top + int(card_height * 0.56) + random.randint(-jitter, jitter)))),
    ]


def _adb_card_opened(adb_path: str, serial: str, card_text: str) -> bool:
    xml_text = _proxy("_adb_dump_ui_xml", adb_path, serial)
    candidate = _pick_android_news_candidate(xml_text)
    if candidate is None:
        return False
    next_text, _, _ = candidate
    return next_text != card_text


def _adb_gradual_scroll_news_feed(adb_path: str, serial: str, width: int, height: int, longer: bool = False) -> None:
    steps = random.randint(ANDROID_NEWS_SCROLL_STEPS_MIN, ANDROID_NEWS_SCROLL_STEPS_MAX)
    if longer:
        steps += 1

    current_start_y = int(height * random.uniform(0.78, 0.84))
    minimum_end_y = int(height * random.uniform(0.26, 0.38 if longer else 0.42))

    for step in range(steps):
        start_x = width // 2 + random.randint(-width // 25, width // 25)
        step_end_y = max(minimum_end_y, current_start_y - random.randint(int(height * 0.10), int(height * 0.18)))
        _adb_swipe(adb_path, serial, start_x, current_start_y, start_x, step_end_y, duration_ms=random.randint(350, 650))
        current_start_y = max(int(height * 0.20), step_end_y - random.randint(20, 60))
        if step < steps - 1:
            _wait(random.uniform(ANDROID_NEWS_SCROLL_PAUSE_MIN, ANDROID_NEWS_SCROLL_PAUSE_MAX), "entre desplazamientos de noticias")


def _adb_find_visible_news_candidate(adb_path: str, serial: str) -> Tuple[str, Tuple[int, int], Tuple[int, int, int, int]] | None:
    for attempt in range(ANDROID_NEWS_SCAN_ATTEMPTS):
        xml_text = _proxy("_adb_dump_ui_xml", adb_path, serial)
        candidate = _pick_android_news_candidate(xml_text)
        if candidate is not None:
            return candidate
        if attempt < ANDROID_NEWS_SCAN_ATTEMPTS - 1:
            width, height = _adb_screen_size(adb_path, serial)
            _adb_gradual_scroll_news_feed(adb_path, serial, width, height)
            _wait(random.uniform(0.4, 1.0), "para cargar más noticias")
    return None


def _adb_scroll_news_feed_once(adb_path: str, serial: str, longer: bool = False) -> None:
    width, height = _adb_screen_size(adb_path, serial)
    _adb_gradual_scroll_news_feed(adb_path, serial, width, height, longer=longer)


def _adb_news_session_read_one(adb_path: str, serial: str, account: str) -> bool:
    _adb_scroll_news_feed_once(adb_path, serial, longer=True)
    width, height = _adb_screen_size(adb_path, serial)
    candidate = _adb_find_visible_news_candidate(adb_path, serial)

    if candidate is None:
        _say("No se encontró una noticia visible en Android; se omite este ciclo.")
        return False

    card_text, _card_center, card_bounds = candidate
    tap_points = _adb_article_tap_points(card_bounds, width, height)
    _say(f"Abriendo noticia visible: {card_text}…")

    for tap_x, tap_y in tap_points:
        _adb_tap(adb_path, serial, tap_x, tap_y)
        _wait(random.uniform(PAGE_LOAD_WAIT_MIN, PAGE_LOAD_WAIT_MAX), "para abrir la noticia móvil")
        if _adb_card_opened(adb_path, serial, card_text):
            break
        _say("La tarjeta sigue visible; reintentando con otro punto de toque…")
    else:
        _say("El toque no abrió la tarjeta; intentando con Enter…")
        _adb_shell(adb_path, serial, "input", "keyevent", "66")
        _wait(random.uniform(PAGE_LOAD_WAIT_MIN, PAGE_LOAD_WAIT_MAX), "para abrir la noticia móvil")

    dwell = random.uniform(ARTICLE_DWELL_MIN, ARTICLE_DWELL_MAX)
    article_start_y = int(height * 0.78)
    article_end_y = int(height * 0.34)
    elapsed = 0.0
    while elapsed < dwell:
        interval = min(random.uniform(2.0, 3.5), dwell - elapsed)
        _wait(interval, "dentro de la noticia")
        elapsed += interval
        if elapsed < dwell:
            swipe_x = width // 2 + random.randint(-width // 22, width // 22)
            _adb_swipe(adb_path, serial, swipe_x, article_start_y, swipe_x, article_end_y, duration_ms=random.randint(380, 720))
            _say("Desplazando dentro de la noticia en Android…")

    _say(f"Lectura móvil completada durante {dwell:.0f} segundos.")
    log_action(account=account, keyword=card_text, url=f"adb://{serial}", dwell_seconds=dwell)

    _adb_shell(adb_path, serial, "input", "keyevent", "4")
    _adb_scroll_news_feed_once(adb_path, serial)
    _wait(random.uniform(ANDROID_NEWS_RETURN_WAIT_MIN, ANDROID_NEWS_RETURN_WAIT_MAX), "antes del siguiente ciclo Android")
    return True


def _adb_try_reject_cookies(adb_path: str, serial: str) -> bool:
    tapped_any = False
    for _ in range(2):
        try:
            xml_text = _proxy("_adb_dump_ui_xml", adb_path, serial)
        except StopIteration:
            break
        candidate = _pick_cookie_reject_candidate(xml_text)
        if candidate is None:
            break
        label, (x, y) = candidate
        _say(f"Detectado banner de cookies; rechazando: {label}…")
        _adb_tap(adb_path, serial, x, y)
        _wait(random.uniform(0.8, 1.4), "para aplicar preferencia de cookies")
        tapped_any = True
    return tapped_any


def _run_android_adb_news_session(account: str, adb_serial: str = "", cycles: int | None = None) -> None:
    adb_path = _find_adb_binary()
    serial = _resolve_adb_serial(adb_path, adb_serial)
    total_cycles = max(1, cycles if cycles is not None else ANDROID_NEWS_CYCLES)

    _say(f"Sesión Android ADB iniciada para la cuenta '{account}'. Total de ciclos planificados hoy: {total_cycles}.")
    _adb_launch_bing(adb_path, serial)
    _wait(random.uniform(PAGE_LOAD_WAIT_MIN, PAGE_LOAD_WAIT_MAX), "para que cargue Bing en Android")

    try:
        for cycle_idx in range(total_cycles):
            _say(f"Ciclo Android {cycle_idx + 1}/{total_cycles}.")
            _adb_news_session_read_one(adb_path, serial, account)
    finally:
        _say("Sesión Android ADB finalizada.")
