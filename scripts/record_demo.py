"""Record a silent, real Gradio walkthrough with Playwright and ffmpeg.

Start `GRADIO_SERVER_PORT=7864 .venv/bin/python app.py`, then run:
`.venv/bin/python scripts/record_demo.py --chrome /usr/bin/google-chrome`
Requires the project's browser dependencies and ffmpeg on PATH. All comparisons
run through the live UI; no saved predictions are injected. Output is about one minute.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def pause(page: Page, seconds: float = 5) -> None:
    page.wait_for_timeout(seconds * 1000)


def show(page: Page, selector: str) -> None:
    page.locator(selector).first.evaluate(
        "node => node.scrollIntoView({block: 'start', behavior: 'smooth'})"
    )
    pause(page, 0.8)


def run(page: Page) -> None:
    page.get_by_role("button", name="Compare documents", exact=True).click()
    expect(page.locator("#scr-run-status")).to_contain_text("Compared", timeout=90_000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:7864")
    parser.add_argument(
        "--chrome", help="Existing Chrome executable; otherwise Playwright Chromium."
    )
    parser.add_argument("--output", type=Path, default=ROOT / "docs/images")
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        parser.error("ffmpeg must be available on PATH")
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="radar-recording-") as temporary:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.chrome, headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                record_video_dir=temporary,
                record_video_size={"width": 1280, "height": 900},
                device_scale_factor=1,
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.url, wait_until="domcontentloaded")
            expect(page.get_by_role("button", name="Compare documents", exact=True)).to_be_visible()
            pause(page, 4)
            run(page)
            show(page, ".scr-review-heading")
            pause(page, 5)
            page.screenshot(path=str(args.output / "demo.png"))
            page.get_by_role("radio", name="All passages", exact=True).check()
            page.locator(".scr-evidence summary").first.click()
            show(page, "#scr-filters")
            pause(page, 5)
            page.locator("#scr-example input").click()
            page.get_by_role(
                "option", name="Real document: HTTPX compatibility", exact=True
            ).click()
            expect(page.locator("#scr-run-status")).to_contain_text("Inputs changed")
            show(page, "#scr-example")
            pause(page, 5)
            run(page)
            split = page.locator(".scr-card.scr-reworded").filter(has_text="Passages 13, 14")
            expect(split).to_have_count(1)
            split.evaluate("node => node.scrollIntoView({block: 'start', behavior: 'smooth'})")
            split.get_by_text("Group members", exact=True).click()
            pause(page, 7)
            detail = page.locator(".scr-card.scr-uncertain").filter(
                has_text="content, files, data, or json arguments."
            )
            expect(detail).to_have_count(1)
            detail.locator(".scr-evidence summary").click()
            detail.evaluate("node => node.scrollIntoView({block: 'start', behavior: 'smooth'})")
            pause(page, 8)
            page.locator("#scr-example input").click()
            page.get_by_role("option", name="Ambiguous scope: needs review", exact=True).click()
            expect(page.locator("#scr-inputs textarea").first).to_have_value(
                "Support is available during office hours."
            )
            page.locator("#scr-inputs textarea").nth(0).fill(
                "# Administrators\n\nYou can export reports.\n\nYou can delete accounts."
            )
            page.locator("#scr-inputs textarea").nth(1).fill(
                "# Guests\n\nYou can export reports.\n\nYou can delete accounts."
            )
            show(page, "#scr-inputs")
            pause(page, 4)
            run(page)
            show(page, ".scr-review-heading")
            pause(page, 5)
            task = page.locator(".scr-scope-task")
            expect(task).to_have_count(1)
            task.locator("summary").first.click()
            task.evaluate("node => node.scrollIntoView({block: 'start', behavior: 'smooth'})")
            pause(page, 7)
            video = page.video
            context.close()
            source = Path(video.path())
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(source),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "28",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(args.output / "walkthrough.mp4"),
                ],
                check=True,
                capture_output=True,
            )
            # Separate mobile session keeps the desktop recording dimensions fixed.
            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            mobile.goto(args.url, wait_until="domcontentloaded")
            expect(
                mobile.get_by_role("button", name="Compare documents", exact=True)
            ).to_be_visible()
            run(mobile)
            show(mobile, "#scr-filters")
            assert not mobile.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            mobile.screenshot(path=str(args.output / "mobile.png"))
            assert not errors, errors
            browser.close()
    size = (args.output / "walkthrough.mp4").stat().st_size
    assert size < 10_000_000, f"Video exceeds 10 MB: {size} bytes"
    print(
        f"Recorded live UI walkthrough ({size:,} bytes) and desktop/mobile screenshots in {args.output}"
    )


if __name__ == "__main__":
    main()
