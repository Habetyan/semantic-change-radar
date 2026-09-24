"""Exercise the running demo in a real browser and save desktop/mobile screenshots.

Start `python app.py`, then run this script. Install a browser with
`playwright install chromium`, or pass --chrome /path/to/google-chrome.
"""

import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--chrome", help="Use an existing Chrome executable.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/local/browser"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chrome, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1080})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        # Gradio keeps a server-sent-event connection open; networkidle is not a
        # reliable readiness condition. Wait for the actual interactive controls.
        page.goto(args.url, wait_until="domcontentloaded")
        compare = page.get_by_role("button", name="Compare documents", exact=True)
        expect(compare).to_be_visible()
        compare.click()
        expect(page.locator(".scr-card").first).to_be_visible(timeout=90_000)
        expect(page.locator("#scr-run-status")).to_contain_text("Compared")
        assert page.locator(".scr-card").count() == 4
        expect(page.locator(".scr-map-cell")).to_have_count(11)
        page.screenshot(path=str(args.output / "desktop.png"), full_page=True)

        page.get_by_role("radio", name="All passages", exact=True).check()
        expect(page.locator(".scr-card")).to_have_count(6)
        page.locator(".scr-evidence summary").first.click()
        expect(page.locator(".scr-scores").first).to_be_visible()

        download_link = page.locator('a[download^="semantic-change-radar-"]')
        with page.expect_download() as event:
            download_link.click()
        download = event.value
        report_path = args.output / "download.json"
        download.save_as(report_path)
        report = json.loads(report_path.read_text())
        assert report["engine"] == "semantic" and len(report["changes"]) == 6

        before = page.locator("#scr-inputs textarea").first
        original = before.input_value()
        before.fill(original + "\n\nA newly added sentence.")
        expect(page.locator("#scr-run-status")).to_contain_text("Inputs changed")
        before.fill(original)
        expect(page.locator("#scr-run-status")).to_contain_text("Compared")

        page.get_by_role("radio", name="Material + review", exact=True).check()
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.locator(".scr-card")).to_have_count(4)
        assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        assert page.locator("#scr-inputs").bounding_box()["width"] >= 340
        page.screenshot(path=str(args.output / "mobile.png"), full_page=True)
        page.locator("#scr-example input").click()
        page.get_by_role("option", name="Real document: pip caching", exact=True).click()
        expect(page.locator("#scr-inputs textarea").first).to_have_value(re.compile("Caching"))
        expect(page.locator(".scr-example-note")).to_contain_text("pypa/pip")
        expect(page.locator(".scr-example-note a")).to_have_count(2)
        expect(page.locator("#scr-run-status")).to_contain_text("Inputs changed")
        expect(page.locator(".scr-example-note")).to_contain_text("Historical source")
        real_before = before.input_value()
        before.fill(real_before + "\n\nAn edited example sentence.")
        expect(page.locator(".scr-example-note")).to_contain_text(
            "Edited input; links refer to the original example"
        )
        expect(page.locator(".scr-example-note")).not_to_contain_text("Historical source")
        expect(page.locator(".scr-example-note a")).to_have_count(2)
        compare.click()
        expect(page.locator("#scr-run-status")).to_contain_text("Compared", timeout=90_000)
        expect(page.locator(".scr-example-note")).to_contain_text("Edited input")
        before.fill(real_before)
        expect(page.locator(".scr-example-note")).to_contain_text("Historical source")
        expect(page.locator(".scr-example-note")).not_to_contain_text("Edited input")
        assert not errors, errors
        browser.close()
    print(
        "Browser checks passed: semantic comparison, filters, evidence, JSON download, stale inputs, mobile layout."
    )


if __name__ == "__main__":
    main()
