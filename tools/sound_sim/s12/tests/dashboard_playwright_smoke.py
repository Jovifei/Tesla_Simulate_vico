"""Manual Playwright smoke for the static S12 professional dashboard."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[4] / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"


def main() -> int:
    url = (ROOT / "index.html").resolve().as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--allow-file-access-from-files"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector("#trial-nav button")
        assert page.locator("#trial-nav button").count() == 9
        assert page.locator("text=Professional MATLAB").count() >= 1
        assert page.locator("text=Professional MoSQITo").count() >= 1
        assert page.locator("text=Legacy Proxy").count() >= 1
        assert page.locator("audio").count() == 2
        page.wait_for_function("Array.from(document.querySelectorAll('audio')).every((audio) => audio.readyState >= 3 && audio.duration > 0)", timeout=15_000)
        assert page.locator("#export-feedback").is_disabled()
        assert "不能提交" in page.locator("#submit-status").inner_text()
        browser.close()
    print("dashboard_playwright_smoke=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
