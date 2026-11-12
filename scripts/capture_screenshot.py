"""Capture a screenshot of the running Streamlit app with Playwright.

Start the app first (python -m streamlit run app.py), then:
    python scripts/capture_screenshot.py [--url URL] [--out PATH] [--width W] [--height H]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8501")
    parser.add_argument("--out", default=str(ROOT / "screenshots" / "streamlit_dashboard.png"))
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--full-page", action="store_true")
    parser.add_argument("--tab", default=None, help="Tab name to open before the capture.")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        page.goto(args.url)
        page.get_by_text("Registered companies").first.wait_for(timeout=60000)
        page.wait_for_selector(".js-plotly-plot", timeout=60000)
        if args.tab:
            page.get_by_role("tab", name=args.tab).click()
        page.wait_for_timeout(2500)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=args.out, full_page=args.full_page)
        browser.close()
    print(args.out)


if __name__ == "__main__":
    main()
