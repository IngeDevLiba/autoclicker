"""
Microsoft Rewards autoclicker — main orchestrator.

Usage
-----
    python autoclicker.py [--account ACCOUNT_ID] [--headless]

Arguments
---------
--account   A label for this account (used in log filenames). Default: "default".
--headless  Run the browser without a visible window.

The script distributes the daily searches across morning / afternoon / evening
blocks as defined in config.DAILY_BLOCKS and sleeps between them.
Within each block searches are spaced by a random pause
(BETWEEN_SEARCHES_MIN – BETWEEN_SEARCHES_MAX seconds).
"""

from __future__ import annotations

import argparse
import os
import math
import re
import random
import shutil
import subprocess
import time
import tempfile
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from config import (
    ARTICLE_DWELL_MAX,
    ARTICLE_DWELL_MIN,
    ANDROID_NEWS_CYCLES,
    ANDROID_NEWS_RETURN_WAIT_MAX,
    ANDROID_NEWS_RETURN_WAIT_MIN,
    ANDROID_NEWS_MIN_TOP_PX,
    ANDROID_NEWS_SCAN_ATTEMPTS,
    ANDROID_NEWS_SCROLL_PAUSE_MAX,
    ANDROID_NEWS_SCROLL_PAUSE_MIN,
    ANDROID_NEWS_SCROLL_STEPS_MAX,
    ANDROID_NEWS_SCROLL_STEPS_MIN,
    ANDROID_NEWS_TAP_JITTER_PX,
    BETWEEN_SEARCHES_MAX,
    BETWEEN_SEARCHES_MIN,
    BING_URL,
    BLOCK_GAP_MAX,
    BLOCK_GAP_MIN,
    DAILY_BLOCKS,
    DAILY_SEARCHES_MAX,
    DAILY_SEARCHES_MIN,
    PAGE_LOAD_WAIT_MAX,
    PAGE_LOAD_WAIT_MIN,
    SCROLL_INTERVAL_MAX,
    SCROLL_INTERVAL_MIN,
    SEARCH_BAR_SELECTOR,
)
from logger import log_action
from searches import get_random_queries
from typer import type_naturally

_NEWS_SKIP_WARNED = False


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _say(message: str) -> None:
    """Print a timestamped action description in simple language."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {message}")


def _wait(seconds: float, reason: str = "") -> None:
    label = f"Esperando {seconds:.0f} segundos"
    if reason:
        label += f" {reason}"
    label += "…"
    _say(label)
    time.sleep(seconds)


def _random_wait(lo: int, hi: int, reason: str = "") -> None:
    _wait(random.uniform(lo, hi), reason)


def _driver_location(driver: Any, fallback: str = "") -> str:
    try:
        location = getattr(driver, "current_url", "")
    except WebDriverException:
        location = ""
    return location or fallback


def load_accounts(path: Path) -> dict[str, dict[str, str]]:
    """Load accounts mapping from a CSV file.

    Expected CSV headers: account,email,user_data_dir,profile_directory
    Returns a mapping keyed by email -> {user_data_dir, profile_directory}
    """
    if not path.exists():
        return {}

    mapping: dict[str, dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            email = (row.get("email") or row.get("account") or "").strip()
            if not email:
                continue
            mapping[email] = {
                "user_data_dir": (row.get("user_data_dir") or "").strip(),
                "profile_directory": (row.get("profile_directory") or "").strip(),
            }
    return mapping


def _interactive_profile_check(account: str) -> None:
    """Ask the user to verify or launch the Edge profile before searches.

    This helper is deliberately interactive: it can launch the local
    `edge_profile_launcher.py` to open the requested profile in Edge, but
    requires manual confirmation before continuing. If the user cancels,
    the program exits.
    """
    accounts_path = Path("accounts.csv")
    accounts = load_accounts(accounts_path)

    info = accounts.get(account)
    if not info:
        print(
            f"No existe un mapeo de perfil para la cuenta '{account}' en {accounts_path}."
        )
        ans = input("¿Deseas continuar sin abrir perfil? (y=continuar, c=cancelar) [y]: ")
        if ans.strip().lower().startswith("c"):
            print("Ejecución cancelada por el usuario.")
            raise SystemExit(1)
        return

    user_data_dir = info.get("user_data_dir")
    profile_dir = info.get("profile_directory")

    print("Perfil detectado para la cuenta:")
    print(f"  email: {account}")
    print(f"  user_data_dir: {user_data_dir}")
    print(f"  profile_directory: {profile_dir}")

    while True:
        print("Opciones: [l]anzar perfil  [c]onfirmar abierto  [s]altar/cancelar")
        choice = input("Elige una opción (l/c/s): ").strip().lower()
        if choice == "l":
            launcher = Path(__file__).parent / "edge_profile_launcher.py"
            if not launcher.exists():
                print("No se encontró el lanzador de perfiles (edge_profile_launcher.py).")
                continue
            cmd = [
                sys.executable,
                str(launcher),
                "--user-data-dir",
                user_data_dir,
                "--profile-directory",
                profile_dir,
                "--start-minimized",
            ]
            print("Lanzando Edge con el perfil seleccionado...")
            subprocess.Popen(cmd)
            # After launching, ask user to confirm
        elif choice == "c":
            confirmed = input(
                "Confirma que el perfil está abierto y la sesión iniciada (y/n): "
            ).strip().lower()
            if confirmed == "y":
                return
            else:
                continue
        elif choice == "s":
            print("Saltando verificación de perfil.")
            return
        else:
            print("Opción no válida. Intenta de nuevo.")


def _find_browser_binary() -> tuple[str, str]:
    edge_candidates = [
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]

    for candidate in edge_candidates:
        if candidate.exists():
            return "edge", str(candidate)

    raise RuntimeError(
        "No se encontró Microsoft Edge. Instala Edge o configura su ruta manualmente."
    )


def _build_driver(headless: bool) -> webdriver.Chrome:
    browser_name, browser_binary = _find_browser_binary()
    options = EdgeOptions()
    options.binary_location = browser_binary
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = EdgeService(EdgeChromiumDriverManager().install())
    return webdriver.Edge(service=service, options=options)


def _find_first_element(
    driver: webdriver.Chrome, selectors: list[str]
) -> object | None:
    for selector in selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            return elements[0]
    return None


def _is_news_like_text(text: str) -> bool:
    normalized = text.strip().lower()
    if len(normalized) < 18:
        return False
    ad_markers = {
        "anuncio",
        "anuncios",
        "patrocinado",
        "publicidad",
        "sponsored",
        "advertisement",
        "ad choice",
    }
    if any(marker in normalized for marker in ad_markers):
        return False
    blocked = {
        "news",
        "search",
        "sign in",
        "more",
        "see all",
        "top stories",
        "images",
        "videos",
    }
    return normalized not in blocked


def _parse_android_bounds(bounds: str) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _android_bounds_center(bounds: str) -> tuple[int, int] | None:
    parsed = _parse_android_bounds(bounds)
    if parsed is None:
        return None
    left, top, right, bottom = parsed
    return ((left + right) // 2, (top + bottom) // 2)


def _pick_android_news_candidate(
    xml_text: str,
) -> tuple[str, tuple[int, int], tuple[int, int, int, int]] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    candidates: list[tuple[int, int, int, str, tuple[int, int], tuple[int, int, int, int]]] = []

    ad_markers = (
        "anuncio",
        "anuncios",
        "patrocinado",
        "publicidad",
        "sponsored",
        "advertisement",
        "ad choice",
    )
    video_markers = (
        "video",
        "videos",
        "reproducir",
        "play",
        "duración",
        "duration",
        "min watching",
    )

    def _bounds_contains_center(
        outer: tuple[int, int, int, int],
        inner: tuple[int, int, int, int],
    ) -> bool:
        left, top, right, bottom = inner
        center_x = (left + right) // 2
        center_y = (top + bottom) // 2
        outer_left, outer_top, outer_right, outer_bottom = outer
        return (
            outer_left <= center_x <= outer_right
            and outer_top <= center_y <= outer_bottom
        )

    def _container_metadata_tokens(container_bounds: tuple[int, int, int, int]) -> list[str]:
        tokens: list[str] = []
        for candidate_node in root.iter("node"):
            node_bounds = _parse_android_bounds(candidate_node.attrib.get("bounds", ""))
            if node_bounds is None:
                continue
            if not _bounds_contains_center(container_bounds, node_bounds):
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

    def _is_blocked_container(container_bounds: tuple[int, int, int, int]) -> bool:
        metadata = _container_metadata_tokens(container_bounds)
        if not metadata:
            return False

        if any(any(marker in token for marker in ad_markers) for token in metadata):
            return True

        if any(any(marker in token for marker in video_markers) for token in metadata):
            return True

        has_duration_stamp = any(
            re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", token) is not None
            for token in metadata
        )
        return has_duration_stamp

    def walk(node: ET.Element, clickable_ancestors: list[tuple[int, int, int, int]]):
        parsed_bounds = _parse_android_bounds(node.attrib.get("bounds", ""))
        next_clickable_ancestors = clickable_ancestors
        if node.attrib.get("clickable") == "true" and parsed_bounds is not None:
            next_clickable_ancestors = clickable_ancestors + [parsed_bounds]

        text = (node.attrib.get("text") or "").strip()
        if text and _is_news_like_text(text):
            chosen_bounds = next_clickable_ancestors[-1] if next_clickable_ancestors else parsed_bounds
            if chosen_bounds is not None:
                left, top, right, bottom = chosen_bounds
                if top >= ANDROID_NEWS_MIN_TOP_PX:
                    if not _is_blocked_container(chosen_bounds):
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


def _pick_cookie_reject_candidate(xml_text: str) -> tuple[str, tuple[int, int]] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    reject_markers = (
        "rechazar",
        "denegar",
        "decline",
        "reject",
        "no aceptar",
        "solo necesarias",
        "only necessary",
        "necessary only",
    )
    candidates: list[tuple[int, int, int, str, tuple[int, int]]] = []

    for node in root.iter("node"):
        text = (node.attrib.get("text") or "").strip()
        content_desc = (node.attrib.get("content-desc") or "").strip()
        resource_id = (node.attrib.get("resource-id") or "").strip()
        combined = " ".join(part for part in [text, content_desc, resource_id] if part).lower()
        if not combined:
            continue
        if not any(marker in combined for marker in reject_markers):
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


def _adb_try_reject_cookies(adb_path: str, serial: str) -> bool:
    tapped_any = False
    for _ in range(2):
        xml_text = _adb_dump_ui_xml(adb_path, serial)
        candidate = _pick_cookie_reject_candidate(xml_text)
        if candidate is None:
            break
        label, (x, y) = candidate
        _say(f"Detectado banner de cookies; rechazando: {label}…")
        _adb_tap(adb_path, serial, x, y)
        _wait(random.uniform(0.8, 1.4), "para aplicar preferencia de cookies")
        tapped_any = True
    return tapped_any


def _find_adb_binary() -> str:
    candidates = []
    which_adb = shutil.which("adb")
    if which_adb:
        candidates.append(which_adb)

    for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        base = os.environ.get(env_var)
        if base:
            candidates.extend(
                [
                    str(Path(base) / "platform-tools" / "adb.exe"),
                    str(Path(base) / "platform-tools" / "adb"),
                ]
            )

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        sdk_base = Path(local_app_data) / "Android" / "Sdk" / "platform-tools"
        candidates.extend([str(sdk_base / "adb.exe"), str(sdk_base / "adb")])

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    raise RuntimeError(
        "No se encontró adb. Instala Android platform-tools y agrega adb al PATH."
    )


def _adb_run(adb_path: str, serial: str | None, *args: str) -> subprocess.CompletedProcess[str]:
    command = [adb_path]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    return subprocess.run(command, check=True, capture_output=True, text=True)


def _adb_output(adb_path: str, serial: str | None, *args: str) -> str:
    return _adb_run(adb_path, serial, *args).stdout


def _adb_connected_devices(adb_path: str) -> list[str]:
    output = _adb_output(adb_path, None, "devices")
    devices: list[str] = []
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
                f"No se encontró el dispositivo ADB '{requested_serial}'. "
                f"Dispositivos disponibles: {', '.join(devices) or 'ninguno'}."
            )
        return requested_serial

    if not devices:
        raise RuntimeError(
            "No hay dispositivos ADB conectados. Activa USB debugging y verifica `adb devices`."
        )

    if len(devices) > 1:
        raise RuntimeError(
            "Hay más de un dispositivo ADB conectado. Usa --adb-serial para elegir uno: "
            f"{', '.join(devices)}."
        )

    return devices[0]


def _adb_shell(adb_path: str, serial: str, *args: str) -> subprocess.CompletedProcess[str]:
    return _adb_run(adb_path, serial, "shell", *args)


def _adb_launch_bing(adb_path: str, serial: str) -> None:
    _adb_shell(
        adb_path,
        serial,
        "monkey",
        "-p",
        "com.microsoft.bing",
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    )


def _adb_screen_size(adb_path: str, serial: str) -> tuple[int, int]:
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
    _adb_shell(
        adb_path,
        serial,
        "input",
        "swipe",
        str(start_x),
        str(start_y),
        str(end_x),
        str(end_y),
        str(duration_ms),
    )


def _adb_dump_ui_xml(adb_path: str, serial: str) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        remote_path = "/sdcard/window_dump.xml"
        local_path = Path(temp_dir) / "window_dump.xml"
        _adb_shell(adb_path, serial, "uiautomator", "dump", remote_path)
        _adb_run(adb_path, serial, "pull", remote_path, str(local_path))
        return local_path.read_text(encoding="utf-8", errors="ignore")


def _run_android_adb_news_session(
    account: str,
    adb_serial: str = "",
    cycles: int | None = None,
) -> None:
    adb_path = _find_adb_binary()
    serial = _resolve_adb_serial(adb_path, adb_serial)
    total_cycles = max(1, cycles if cycles is not None else ANDROID_NEWS_CYCLES)

    _say(
        f"Sesión Android ADB iniciada para la cuenta '{account}'. "
        f"Total de ciclos planificados hoy: {total_cycles}."
    )

    _adb_launch_bing(adb_path, serial)
    _wait(random.uniform(PAGE_LOAD_WAIT_MIN, PAGE_LOAD_WAIT_MAX), "para que cargue Bing en Android")
    try:
        for cycle_idx in range(total_cycles):
            _say(f"Ciclo Android {cycle_idx + 1}/{total_cycles}.")
            _adb_news_session_read_one(adb_path, serial, account)
    finally:
        _say("Sesión Android ADB finalizada.")


# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Single search
# ---------------------------------------------------------------------------


def _do_search(driver: webdriver.Chrome, account: str, query: str) -> None:
    """Navigate to Bing and type *query* naturally, then log the result."""
    _say(f"Escribiendo búsqueda: {query}…")

    driver.get(BING_URL)
    _wait(
        random.uniform(PAGE_LOAD_WAIT_MIN, PAGE_LOAD_WAIT_MAX),
        "para que cargue la página",
    )

    _maybe_read_homepage_news(driver, account, query)

    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_BAR_SELECTOR))
        )
    except TimeoutException:
        _say("No se encontró la barra de búsqueda; omitiendo esta búsqueda.")
        return

    search_box.click()
    search_box.clear()
    type_naturally(search_box, query)
    search_box.send_keys(Keys.RETURN)

    try:
        WebDriverWait(driver, 10).until(EC.url_contains("bing.com/search"))
    except TimeoutException:
        pass

    _wait(random.uniform(1.5, 3.0), "para que carguen los resultados")

    current_url = driver.current_url
    _say(f"Resultados cargados: {current_url}")

    # Optionally open the first organic result (article reading)
    _maybe_read_article(driver, account, query)

    log_action(account=account, keyword=query, url=current_url, dwell_seconds=0)


def _read_link_page(
    driver: webdriver.Chrome,
    account: str,
    keyword: str,
    link: object,
    intro_text: str,
) -> None:
    link_text = getattr(link, "text", "").strip() or getattr(
        link, "get_attribute", lambda _name: ""
    )("href")
    _say(f"{intro_text}: {link_text}…")

    driver.execute_script("arguments[0].click();", link)

    dwell = random.uniform(ARTICLE_DWELL_MIN, ARTICLE_DWELL_MAX)
    elapsed = 0.0

    while elapsed < dwell:
        interval = random.uniform(SCROLL_INTERVAL_MIN, SCROLL_INTERVAL_MAX)
        if elapsed + interval > dwell:
            interval = dwell - elapsed
        time.sleep(interval)
        elapsed += interval

        scroll_px = random.randint(200, 600)
        driver.execute_script(f"window.scrollBy(0, {scroll_px});")
        _say(f"Desplazando página {scroll_px}px…")

    final_url = driver.current_url
    _say(f"Lectura completada durante {dwell:.0f} segundos.")
    log_action(
        account=account,
        keyword=keyword,
        url=final_url,
        dwell_seconds=dwell,
    )


def _maybe_read_homepage_news(
    driver: webdriver.Chrome, account: str, keyword: str
) -> None:
    """Desktop Rewards does not credit the mobile news flow, so skip it."""
    global _NEWS_SKIP_WARNED
    if _NEWS_SKIP_WARNED:
        return
    _NEWS_SKIP_WARNED = True
    _say(
        "La lectura de noticias de Microsoft Rewards no se acredita en PC; "
        "se omite esta parte en Windows."
    )


def _adb_article_tap_points(
    bounds: tuple[int, int, int, int],
    width: int,
    height: int,
) -> list[tuple[int, int]]:
    left, top, right, bottom = bounds
    card_width = max(1, right - left)
    card_height = max(1, bottom - top)
    jitter = max(1, ANDROID_NEWS_TAP_JITTER_PX)
    primary = (
        left + int(card_width * 0.50) + random.randint(-jitter, jitter),
        top + int(card_height * 0.50) + random.randint(-jitter, jitter),
    )
    secondary = (
        left + int(card_width * 0.45) + random.randint(-jitter, jitter),
        top + int(card_height * 0.44) + random.randint(-jitter, jitter),
    )
    tertiary = (
        left + int(card_width * 0.55) + random.randint(-jitter, jitter),
        top + int(card_height * 0.56) + random.randint(-jitter, jitter),
    )
    return [
        (max(1, min(width - 1, primary[0])), max(1, min(height - 1, primary[1]))),
        (max(1, min(width - 1, secondary[0])), max(1, min(height - 1, secondary[1]))),
        (max(1, min(width - 1, tertiary[0])), max(1, min(height - 1, tertiary[1]))),
    ]


def _adb_card_opened(adb_path: str, serial: str, card_text: str) -> bool:
    xml_text = _adb_dump_ui_xml(adb_path, serial)
    candidate = _pick_android_news_candidate(xml_text)
    if candidate is None:
        return True
    next_text, _, _ = candidate
    return next_text != card_text


def _adb_gradual_scroll_news_feed(
    adb_path: str,
    serial: str,
    width: int,
    height: int,
    longer: bool = False,
) -> None:
    steps = random.randint(ANDROID_NEWS_SCROLL_STEPS_MIN, ANDROID_NEWS_SCROLL_STEPS_MAX)
    if longer:
        steps += 1

    current_start_y = int(height * random.uniform(0.78, 0.84))
    minimum_end_y = int(height * random.uniform(0.26, 0.38 if longer else 0.42))

    for step in range(steps):
        start_x = width // 2 + random.randint(-width // 25, width // 25)
        step_end_y = max(
            minimum_end_y,
            current_start_y - random.randint(int(height * 0.10), int(height * 0.18)),
        )
        _adb_swipe(
            adb_path,
            serial,
            start_x,
            current_start_y,
            start_x,
            step_end_y,
            duration_ms=random.randint(350, 650),
        )
        current_start_y = max(int(height * 0.20), step_end_y - random.randint(20, 60))

        if step < steps - 1:
            _wait(
                random.uniform(ANDROID_NEWS_SCROLL_PAUSE_MIN, ANDROID_NEWS_SCROLL_PAUSE_MAX),
                "entre desplazamientos de noticias",
            )


def _adb_find_visible_news_candidate(
    adb_path: str,
    serial: str,
) -> tuple[str, tuple[int, int], tuple[int, int, int, int]] | None:
    for attempt in range(ANDROID_NEWS_SCAN_ATTEMPTS):
        xml_text = _adb_dump_ui_xml(adb_path, serial)
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


def _adb_news_session_read_one(
    adb_path: str,
    serial: str,
    account: str,
) -> bool:
    _adb_scroll_news_feed_once(adb_path, serial, longer=True)
    width, height = _adb_screen_size(adb_path, serial)
    candidate = _adb_find_visible_news_candidate(adb_path, serial)

    if candidate is None:
        _say("No se encontró una noticia visible en Android; se omite este ciclo.")
        return False

    card_text, _card_center, card_bounds = candidate
    tap_points = _adb_article_tap_points(card_bounds, width, height)
    _say(f"Abriendo noticia visible: {card_text}…")

    for tap_index, (tap_x, tap_y) in enumerate(tap_points):
        _adb_tap(adb_path, serial, tap_x, tap_y)
        _wait(
            random.uniform(PAGE_LOAD_WAIT_MIN, PAGE_LOAD_WAIT_MAX),
            "para abrir la noticia móvil",
        )
        if _adb_card_opened(adb_path, serial, card_text):
            break
        _say("La tarjeta sigue visible; reintentando con otro punto de toque…")

    else:
        _say("El toque no abrió la tarjeta; intentando con Enter…")
        _adb_shell(adb_path, serial, "input", "keyevent", "66")
        _wait(
            random.uniform(PAGE_LOAD_WAIT_MIN, PAGE_LOAD_WAIT_MAX),
            "para abrir la noticia móvil",
        )
        if not _adb_card_opened(adb_path, serial, card_text):
            _say("La noticia sigue visible tras Enter; se continúa igualmente con la lectura.")

    dwell = random.uniform(ARTICLE_DWELL_MIN, ARTICLE_DWELL_MAX)
    _adb_try_reject_cookies(adb_path, serial)

    article_start_y = int(height * 0.78)
    article_end_y = int(height * 0.34)
    elapsed = 0.0
    while elapsed < dwell:
        interval = min(random.uniform(2.0, 3.5), dwell - elapsed)
        _wait(interval, "dentro de la noticia")
        elapsed += interval

        if elapsed < dwell:
            swipe_x = width // 2 + random.randint(-width // 22, width // 22)
            _adb_swipe(
                adb_path,
                serial,
                swipe_x,
                article_start_y,
                swipe_x,
                article_end_y,
                duration_ms=random.randint(380, 720),
            )
            _say("Desplazando dentro de la noticia en Android…")

    _say(f"Lectura móvil completada durante {dwell:.0f} segundos.")
    log_action(
        account=account,
        keyword=card_text,
        url=f"adb://{serial}",
        dwell_seconds=dwell,
    )

    _adb_shell(adb_path, serial, "input", "keyevent", "4")
    _adb_scroll_news_feed_once(adb_path, serial)
    _wait(
        random.uniform(ANDROID_NEWS_RETURN_WAIT_MIN, ANDROID_NEWS_RETURN_WAIT_MAX),
        "antes del siguiente ciclo Android",
    )
    return True


# ---------------------------------------------------------------------------
# Article reading
# ---------------------------------------------------------------------------


def _maybe_read_article(
    driver: webdriver.Chrome, account: str, query: str
) -> None:
    """
    With a 60 % probability open the first non-ad search result,
    stay on the page for a random dwell time and simulate scrolling.
    """
    if random.random() > 0.60:
        return

    try:
        # Try to find the first organic result link
        link = _find_first_element(driver, ["li.b_algo h2 a", ".b_algo h2 a"])
        if link is None:
            return
        _read_link_page(driver, account, query, link, "Leyendo artículo")
    except (NoSuchElementException, WebDriverException, IndexError):
        pass


# ---------------------------------------------------------------------------
# Block scheduler
# ---------------------------------------------------------------------------


def _searches_per_block(total: int) -> list[int]:
    """
    Split *total* searches among the configured daily blocks.
    The last block absorbs any rounding remainder.
    """
    counts = []
    assigned = 0
    for i, (_, _, fraction) in enumerate(DAILY_BLOCKS):
        if i == len(DAILY_BLOCKS) - 1:
            counts.append(total - assigned)
        else:
            n = math.floor(total * fraction)
            counts.append(n)
            assigned += n
    return counts


def _seconds_until_hour(target_hour: int) -> float:
    """Return seconds from now until *target_hour*:00 today (0 if already past)."""
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    delta = (target - now).total_seconds()
    return max(0.0, delta)


# ---------------------------------------------------------------------------
# Main session runner
# ---------------------------------------------------------------------------


def run_session(
    account: str,
    headless: bool,
    android_adb: bool = False,
    adb_serial: str = "",
    android_cycles: int | None = None,
) -> None:
    if android_adb:
        _run_android_adb_news_session(
            account=account,
            adb_serial=adb_serial,
            cycles=android_cycles,
        )
        return

    if headless:
        _say(
            "Aviso: el modo headless puede no acreditar búsquedas en Microsoft Rewards; "
            "se recomienda ejecutar con ventana visible."
        )
        headless = False

    total = random.randint(DAILY_SEARCHES_MIN, DAILY_SEARCHES_MAX)
    queries = get_random_queries(total)
    block_counts = _searches_per_block(total)

    _say(
        f"Sesión iniciada para la cuenta '{account}'. "
        f"Total de búsquedas planificadas hoy: {total}."
    )

    # Before creating the browser, let the user verify or open the Edge profile
    try:
        _interactive_profile_check(account)
    except SystemExit:
        _say("Usuario canceló la ejecución durante la verificación de perfil.")
        return

    driver = _build_driver(headless)
    try:
        query_idx = 0

        for block_idx, (start_hour, end_hour, _) in enumerate(DAILY_BLOCKS):
            block_n = block_counts[block_idx]
            if block_n == 0:
                continue

            # Wait until the block start hour if needed
            wait_secs = _seconds_until_hour(start_hour)
            if wait_secs > 0:
                _say(
                    f"Bloque {block_idx + 1}: esperando hasta las "
                    f"{start_hour:02d}:00 ({wait_secs / 60:.0f} min)…"
                )
                time.sleep(wait_secs)

            _say(
                f"Bloque {block_idx + 1} ({start_hour:02d}:00–{end_hour:02d}:00): "
                f"{block_n} búsquedas."
            )

            for i in range(block_n):
                if query_idx >= len(queries):
                    break
                q = queries[query_idx]
                query_idx += 1

                _do_search(driver, account, q)

                if i < block_n - 1:
                    _random_wait(
                        BETWEEN_SEARCHES_MIN,
                        BETWEEN_SEARCHES_MAX,
                        "antes de la siguiente búsqueda",
                    )

            # Gap between blocks (skip after last block)
            if block_idx < len(DAILY_BLOCKS) - 1:
                gap = random.randint(BLOCK_GAP_MIN, BLOCK_GAP_MAX)
                _wait(gap, "antes del siguiente bloque")

    finally:
        driver.quit()
        _say("Sesión finalizada. Navegador cerrado.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Microsoft Rewards autoclicker — simula búsquedas naturales."
    )
    parser.add_argument(
        "--account",
        default="default",
        help="Identificador de cuenta (usado en el nombre del log). "
        "Por defecto: 'default'.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ejecutar el navegador en modo headless (sin ventana visible).",
    )
    parser.add_argument(
        "--android-adb",
        action="store_true",
        help="Leer noticias en Android real por USB usando ADB y uiautomator dump.",
    )
    parser.add_argument(
        "--adb-serial",
        default="",
        help="Serial ADB del dispositivo Android cuando hay más de uno conectado.",
    )
    parser.add_argument(
        "--android-cycles",
        type=int,
        default=ANDROID_NEWS_CYCLES,
        help="Número de ciclos de lectura de noticias en Android.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_session(
        account=args.account,
        headless=args.headless,
        android_adb=args.android_adb,
        adb_serial=args.adb_serial,
        android_cycles=args.android_cycles,
    )
