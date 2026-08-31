"""Manual Playwright smoke for the static S12 professional dashboard."""
from __future__ import annotations

from pathlib import Path
import json
import sys

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[4] / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"


def run_rx7_topic_smoke(page) -> None:
    page.wait_for_selector("#pair-nav button")
    assert page.locator("#pair-nav button").count() == 5
    assert page.locator("audio").count() == 2
    assert page.locator("text=Professional MATLAB").count() >= 1
    assert page.locator("text=Professional MoSQITo").count() >= 1
    assert page.locator("text=CC BY-NC-SA 4.0").count() >= 1
    assert page.locator("text=ORDER_COMPARISON_NOT_QUALIFIED").count() >= 1
    page.wait_for_function("Array.from(document.querySelectorAll('audio')).every((audio) => audio.readyState >= 3 && audio.duration > 0)", timeout=15_000)
    page.locator("#pair-nav button").nth(3).click()
    page.wait_for_function("Array.from(document.querySelectorAll('audio')).every((audio) => audio.readyState >= 3 && audio.duration > 0)", timeout=15_000)
    assert "全负荷拉转" in page.locator("#app").inner_text()


def main() -> int:
    page_name = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    url = (ROOT / page_name).resolve().as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--allow-file-access-from-files"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        if page_name == "rx7_topic_r2.html":
            run_rx7_topic_smoke(page)
            browser.close()
            print("dashboard_playwright_smoke=PASS")
            return 0
        page.wait_for_selector("#trial-nav button")
        expected_trials = 18 if "long_window" in page_name else 9
        assert page.locator("#trial-nav button").count() == expected_trials
        assert page.locator("text=Professional MATLAB").count() >= 1
        assert page.locator("text=Professional MoSQITo").count() >= 1
        assert page.locator("text=Legacy Proxy").count() >= 1
        assert page.locator("audio").count() == 2
        page.wait_for_function("Array.from(document.querySelectorAll('audio')).every((audio) => audio.readyState >= 3 && audio.duration > 0)", timeout=15_000)
        assert page.locator("#export-feedback").is_disabled()
        assert "不能提交" in page.locator("#submit-status").inner_text()
        assert page.locator(".problem-chip").count() >= 5
        assert page.locator(".topic-chip").count() == 7
        assert page.locator("select[multiple]").count() == 0
        pair_count = page.locator("#trial-nav button").count()
        vehicle_offsets = [0, 3, 6] if expected_trials == 9 else [0, 6, 12]
        for offset in vehicle_offsets:
            if offset:
                page.locator("#trial-nav button").nth(offset).click()
                page.wait_for_function("Array.from(document.querySelectorAll('audio')).every((audio) => audio.readyState >= 3 && audio.duration > 0)", timeout=15_000)
            page.locator("[data-feedback='software_agreement']").select_option(label="符合")
            page.locator("[data-feedback='identity']").fill("80")
            page.locator("[data-feedback='realism']").fill("70")
            page.locator("[data-feedback='preference']").select_option(label="候选")
            page.locator(".topic-chip").first.click()
            page.locator(".problem-chip").first.click()
            page.locator("[data-feedback='review_ready']").check()
        assert page.locator("#export-feedback").is_enabled()
        assert "三辆车硬门通过" in page.locator("#submit-status").inner_text()
        with page.expect_download() as download_info:
            page.locator("#export-feedback").click()
        payload = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
        assert payload["schema_version"] == "s12-professional-jovi-guided-feedback-v3"
        assert len(payload["rows"]) == 3
        assert all(row["focus_topics"] for row in payload["rows"])
        assert all(isinstance(row["identity"], int) and isinstance(row["realism"], int) for row in payload["rows"])
        browser.close()
    print("dashboard_playwright_smoke=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
