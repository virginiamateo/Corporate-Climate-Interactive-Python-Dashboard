"""Browser smoke tests with Playwright against a live Streamlit server.

Run on demand: python -m pytest -m browser
Needs: python -m playwright install chromium
"""

from __future__ import annotations

import csv
import io
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from climate_targets import config

pytestmark = [pytest.mark.browser, pytest.mark.data]

playwright_sync = pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=config.ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except OSError:
            time.sleep(1)
    else:
        proc.kill()
        pytest.fail("Streamlit did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=15)


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser, server):
    pg = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    pg.goto(server)
    pg.locator('[data-testid="stMetricValue"]').first.wait_for(timeout=60000)
    yield pg
    pg.close()


def _metrics(page) -> list[str]:
    return page.locator('[data-testid="stMetricValue"]').all_inner_texts()


def _pick(page, index: int, text: str) -> None:
    box = page.locator('[data-testid="stSidebar"] [data-testid="stMultiSelect"]').nth(index)
    box.locator("input").click()
    box.locator("input").fill(text)
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")


def test_default_page_shows_cards_and_interactive_charts(page):
    assert _metrics(page) == ["15,961", "77.1%", "18.1%", "113"]
    page.wait_for_selector(".js-plotly-plot", timeout=30000)
    assert page.locator(".js-plotly-plot >> visible=true").count() == 3
    first = page.locator(".js-plotly-plot >> visible=true").first
    first.locator("g.point path").first.hover(force=True)
    page.wait_for_selector(".hoverlayer .hovertext", timeout=10000)
    tooltip = page.locator(".hoverlayer .hovertext").first.text_content()
    assert "Professional Services" in tooltip and "1,620" in tooltip


def test_filter_by_japan_updates_cards(page):
    _pick(page, 0, "Japan")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"stMetricValue\"]')?.innerText === '2,685'",
        timeout=30000,
    )
    assert _metrics(page) == ["2,685", "96.9%", "4.2%", "1"]


def test_no_match_shows_empty_state_and_reset_restores(page, processed):
    companies = processed["companies"]
    in_japan = set(companies.loc[companies["location"] == "Japan", "sector"])
    absent = sorted(set(companies["sector"]) - in_japan)[0]
    _pick(page, 0, "Japan")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"stMetricValue\"]')?.innerText === '2,685'"
    )
    _pick(page, 1, absent)
    page.get_by_text("No records match the selected filters").first.wait_for(timeout=30000)
    assert page.locator('[data-testid="stMetricValue"]').count() == 0
    page.get_by_text("Filters", exact=True).click()  # close any open dropdown first
    page.get_by_role("button", name="Reset filters").click()
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"stMetricValue\"]')?.innerText === '15,961'",
        timeout=30000,
    )
    assert _metrics(page) == ["15,961", "77.1%", "18.1%", "113"]


def test_company_download_matches_selection(page):
    _pick(page, 0, "Japan")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"stMetricValue\"]')?.innerText === '2,685'"
    )
    page.get_by_role("tab", name="Company and target explorer").click()
    page.get_by_role("button", name="Download companies (CSV)").wait_for(timeout=30000)
    with page.expect_download() as info:
        page.get_by_role("button", name="Download companies (CSV)").click()
    content = open(info.value.path(), encoding="utf-8-sig").read()
    rows = list(csv.DictReader(io.StringIO(content)))
    assert len(rows) == 2685
    assert {r["location"] for r in rows} == {"Japan"}


def test_narrow_window_has_no_horizontal_overflow(browser, server):
    pg = browser.new_page(viewport={"width": 700, "height": 900})
    pg.goto(server)
    pg.locator('[data-testid="stMetricValue"]').first.wait_for(timeout=60000)
    pg.wait_for_timeout(1500)
    overflow = pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 1
    pg.close()
