"""Check grouped source rendering and exports in the running semantic demo."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

SPLIT_OLD = "# Accounts\n\nUsers can read reports. Administrators can delete accounts."
SPLIT_NEW = "# Accounts\n\nUsers can read reports.\n\nAdministrators can delete accounts."
DETAIL_OLD = "Templates support inheritance, use Unicode for all operations, and allow macros."
DETAIL_NEW = "Templates support inheritance, and allow macros."


def compare(page: Page, before: str, after: str) -> None:
    inputs = page.locator("#scr-inputs textarea")
    inputs.nth(0).fill(before)
    inputs.nth(1).fill(after)
    page.get_by_role("button", name="Compare documents", exact=True).click()
    expect(page.locator("#scr-run-status")).to_contain_text("Compared", timeout=90_000)


def download_report(page: Page, path: Path) -> dict:
    with page.expect_download() as event:
        page.locator('a[download^="semantic-change-radar-"]').click()
    event.value.save_as(path)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--chrome", help="Use an existing Chrome executable.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/local/browser"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chrome, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1080})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="domcontentloaded")
        expect(page.get_by_role("radio", name="Semantic models", exact=True)).to_be_checked()
        page.get_by_role("radio", name="All passages", exact=True).check()
        compare(page, SPLIT_OLD, SPLIT_NEW)

        expect(page.locator(".scr-card")).to_have_count(2)
        group_card = page.locator(".scr-card.scr-reworded")
        expect(group_card).to_have_count(1)
        sides = group_card.locator(".scr-side")
        expect(sides.nth(0).locator(".scr-passage-label")).to_contain_text("Passage 2")
        expect(sides.nth(1).locator(".scr-passage-label")).to_contain_text("Passages 2, 3")
        group_card.get_by_text("Group members", exact=True).click()
        expect(sides.nth(1).locator("details p")).to_have_count(2)
        expect(sides.nth(1).locator("details p").nth(0)).to_have_text(
            "Passage 2: Users can read reports."
        )
        expect(sides.nth(1).locator("details p").nth(1)).to_have_text(
            "Passage 3: Administrators can delete accounts."
        )
        report = download_report(page, args.output / "groups-download.json")
        assert report["engine"] == "semantic"
        group = next(change for change in report["changes"] if change["status"] == "reworded")
        assert group["old_indices"] == [1] and group["new_indices"] == [1, 2]
        assert [(part["index"], part["text"]) for part in group["old_parts"]] == [
            (1, "Users can read reports. Administrators can delete accounts.")
        ]
        assert [(part["index"], part["text"]) for part in group["new_parts"]] == [
            (1, "Users can read reports."),
            (2, "Administrators can delete accounts."),
        ]
        for side, count in (("old", 2), ("new", 3)):
            assert sorted(
                index for change in report["changes"] for index in change[f"{side}_indices"]
            ) == list(range(count))
        page.screenshot(path=str(args.output / "groups.png"), full_page=True)

        compare(page, DETAIL_OLD, DETAIL_NEW)
        detail_report = download_report(page, args.output / "detail-download.json")
        assert detail_report["engine"] == "semantic"
        assert len(detail_report["changes"]) == 1
        change = detail_report["changes"][0]
        assert change["status"] in {"modified", "uncertain"}, change["status"]
        page.locator(".scr-evidence summary").first.click()
        expect(page.locator(".scr-scores").first).to_be_visible()
        evidence = change.get("localization_evidence", [])
        if evidence:
            assert any("Unicode" in item.get("old_quote", "") for item in evidence)
            expect(page.get_by_text("Localized verification", exact=True)).to_be_visible()
            expect(page.locator(".scr-evidence")).to_contain_text("Unicode")
        page.screenshot(path=str(args.output / "detail.png"), full_page=True)

        documents = (
            Path(__file__).resolve().parents[1]
            / "evaluation/fresh-v2/documents/httpx-compatibility"
        )
        compare(
            page,
            (documents / "old.txt").read_text(encoding="utf-8"),
            (documents / "new.txt").read_text(encoding="utf-8"),
        )
        expect(page.locator("#scr-run-status")).to_contain_text("30 before and 77 after")
        localized_report = download_report(page, args.output / "localized-download.json")
        assert localized_report["engine"] == "semantic"
        localized_change = next(
            item
            for item in localized_report["changes"]
            if item["old_indices"] == [21] and item["new_indices"] == [56]
        )
        assert localized_change["status"] == "uncertain"
        localized_evidence = localized_change["localization_evidence"]
        assert localized_evidence
        assert any(
            "content" in item["new_quote"] and "content" not in item["old_quote"]
            for item in localized_evidence
        )
        localized_card = page.locator(".scr-card.scr-uncertain").filter(
            has_text="content, files, data, or json arguments."
        )
        expect(localized_card).to_have_count(1)
        expect(localized_card.locator(".scr-passage-label").nth(0)).to_contain_text("Passage 22")
        expect(localized_card.locator(".scr-passage-label").nth(1)).to_contain_text("Passage 57")
        localized_card.locator(".scr-evidence summary").click()
        expect(localized_card.get_by_text("Localized verification", exact=True)).to_be_visible()
        for index, side in enumerate(("old", "new")):
            expect(
                localized_card.locator(".scr-side").nth(index).locator(".scr-passage").first
            ).to_have_text(localized_change[f"{side}_text"])
        for item in localized_evidence:
            # Localized evidence preserves literal source separators.
            for side in ("old", "new"):
                assert item[f"{side}_quote"] in localized_change[f"{side}_text"]
            expect(localized_card.locator(".scr-evidence")).to_contain_text(item["old_quote"])
            expect(localized_card.locator(".scr-evidence")).to_contain_text(item["new_quote"])
        localized_card.screenshot(path=str(args.output / "localized-card.png"))
        page.screenshot(path=str(args.output / "localized-page.png"), full_page=True)
        compare(
            page,
            "# Administrators\n\nYou can export reports.\n\nYou can delete accounts.",
            "# Guests\n\nYou can export reports.\n\nYou can delete accounts.",
        )
        task = page.locator(".scr-scope-task")
        expect(task).to_have_count(1)
        expect(task.locator("summary").first).to_contain_text("2 affected entries · 1 review task")
        expect(page.locator(".scr-summary-note")).to_contain_text("2 affected review entries")
        task.locator("summary").first.click()
        expect(task.locator(".scr-card")).to_have_count(2)
        expect(task.locator(".scr-card").first).to_be_visible()
        scope_report = download_report(page, args.output / "scope-download.json")
        assert sum(item["status"] == "uncertain" for item in scope_report["changes"]) == 2
        page.screenshot(path=str(args.output / "scope-task.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        page.screenshot(path=str(args.output / "scope-mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()
    checks = {
        "grouped_render_and_export": "passed",
        "physical_scope_group_render_and_export": "passed",
        "group_indices": {"old": [1], "new": [1, 2]},
        "detail_status": change["status"],
        "localized_evidence_count": len(evidence),
        "httpx_localized_status": localized_change["status"],
        "httpx_localized_evidence_count": len(localized_evidence),
        "httpx_localized_render_and_export": "passed",
        "httpx_evidence_source_check": "exact source substring",
        "browser_page_errors": errors,
    }
    (args.output / "groups-checks.json").write_text(
        json.dumps(checks, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
