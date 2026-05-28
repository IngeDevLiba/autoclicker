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
import math
import random
import time
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from config import (
    ARTICLE_DWELL_MAX,
    ARTICLE_DWELL_MIN,
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


# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------


def _build_driver(headless: bool) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    # Realistic user-agent
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


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

    _wait(random.uniform(1.5, 3.0), "para que carguen los resultados")

    current_url = driver.current_url
    _say(f"Resultados cargados: {current_url}")

    # Optionally open the first organic result (article reading)
    _maybe_read_article(driver, account, query)

    log_action(account=account, keyword=query, url=current_url, dwell_seconds=0)


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
        result_links = driver.find_elements(
            By.CSS_SELECTOR, "li.b_algo h2 a, .b_algo h2 a"
        )
        if not result_links:
            return
        link = result_links[0]
        article_url = link.get_attribute("href") or ""
        link_text = link.text.strip() or article_url

        _say(f"Leyendo artículo: {link_text}…")
        driver.execute_script("arguments[0].click();", link)

        dwell = random.uniform(ARTICLE_DWELL_MIN, ARTICLE_DWELL_MAX)
        elapsed = 0.0

        while elapsed < dwell:
            interval = random.uniform(SCROLL_INTERVAL_MIN, SCROLL_INTERVAL_MAX)
            if elapsed + interval > dwell:
                interval = dwell - elapsed
            time.sleep(interval)
            elapsed += interval

            # Simulate scroll
            scroll_px = random.randint(200, 600)
            driver.execute_script(f"window.scrollBy(0, {scroll_px});")
            _say(f"Desplazando página {scroll_px}px…")

        final_url = driver.current_url
        _say(f"Artículo leído durante {dwell:.0f} segundos.")
        log_action(
            account=account,
            keyword=query,
            url=final_url,
            dwell_seconds=dwell,
        )
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


def run_session(account: str, headless: bool) -> None:
    total = random.randint(DAILY_SEARCHES_MIN, DAILY_SEARCHES_MAX)
    queries = get_random_queries(total)
    block_counts = _searches_per_block(total)

    _say(
        f"Sesión iniciada para la cuenta '{account}'. "
        f"Total de búsquedas planificadas hoy: {total}."
    )

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
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_session(account=args.account, headless=args.headless)
