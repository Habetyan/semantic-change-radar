"""Exercise the offline review form with synthetic, adversarial source text."""

import argparse
import json
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from evaluation.review_packet import build_packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome", default="/usr/bin/google-chrome")
    parser.add_argument("--output", type=Path, default=Path("artifacts/local/review-browser"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for side in ("old", "new"):
            (root / f"{side}.json").write_text(
                json.dumps(["Safe sentence.", "</script><script>window.injected=1</script>"])
            )
        (root / "annotations.json").write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "old_indices": [0],
                            "new_indices": [0],
                            "status": "unchanged",
                            "rationale": "HIDDEN_RATIONALE",
                        },
                        {
                            "old_indices": [1],
                            "new_indices": [1],
                            "status": "modified",
                            "rationale": "<img src=x onerror=alert(1)>",
                        },
                    ]
                }
            )
        )
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "cases": [
                        {
                            "id": "Synthetic review",
                            "annotation_path": "annotations.json",
                            **{
                                side: {
                                    "passages_path": f"{side}.json",
                                    "tag": None,
                                    "commit": "abc123",
                                    "source_url": "https://example.com/source",
                                }
                                for side in ("old", "new")
                            },
                        }
                    ]
                }
            )
        )
        page_path = build_packet([manifest], root / "review.html", root=root)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.chrome, headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(page_path.as_uri())
            expect(page.locator("#proposed-status")).to_have_text("")
            expect(page.locator("#proposal")).to_be_hidden()
            expect(page.locator("#old-link")).to_have_text("abc123")
            assert page.evaluate("window.injected") is None
            page.locator("#reviewer").fill("Human reviewer")
            page.locator("#correspondence").select_option("accepted")
            page.locator("#human-status").select_option("unchanged")
            page.locator("#notes").fill("Reviewed independently.")
            page.reload()
            expect(page.locator("#notes")).to_have_value("Reviewed independently.")
            expect(page.locator("#human-status")).to_have_value("unchanged")
            page.locator("#reveal").click()
            expect(page.locator("#proposed-rationale")).to_have_text("HIDDEN_RATIONALE")
            with page.expect_download() as downloaded:
                page.locator("#export").click()
            export = args.output / "synthetic-review.json"
            downloaded.value.save_as(export)
            data = json.loads(export.read_text())
            assert data["submission_status"] == "review_submission_pending_adjudication"
            assert data["reviews"][0]["reveal_before_judgment"] is False
            page.close()
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(page_path.as_uri())
            expect(page.locator("#notes")).to_have_value("")
            expect(page.locator("#proposal")).to_be_hidden()
            page.locator("#import").set_input_files(export)
            expect(page.locator("#message")).to_contain_text("Imported pending review")
            expect(page.locator("#notes")).to_have_value("Reviewed independently.")
            with page.expect_download() as downloaded:
                page.locator("#export").click()
            roundtrip = args.output / "roundtrip-review.json"
            downloaded.value.save_as(roundtrip)
            after = json.loads(roundtrip.read_text())
            for key in ("packet_hash", "corpus_hash", "annotation_hash", "reviewer_name"):
                assert after[key] == data[key]
            for left, right in zip(data["reviews"], after["reviews"]):
                assert {k: v for k, v in left.items() if k != "updated_at"} == {
                    k: v for k, v in right.items() if k != "updated_at"
                }
            for mutate in (
                lambda d: d.update(packet_hash="wrong"),
                lambda d: d["reviews"][0].update(old_indices=[True]),
                lambda d: d["reviews"][0].update(old_indices=[999]),
                lambda d: d["reviews"][0].update(human_status="bogus"),
                lambda d: d["reviews"][0].update(revealed_at="tomorrow"),
                lambda d: d["reviews"][0].update(event_id="unknown"),
            ):
                invalid = json.loads(json.dumps(data))
                mutate(invalid)
                page.locator("#import").set_input_files(
                    {
                        "name": "invalid.json",
                        "mimeType": "application/json",
                        "buffer": json.dumps(invalid).encode(),
                    }
                )
                expect(page.locator("#message")).to_contain_text("Import rejected")
                expect(page.locator("#notes")).to_have_value("Reviewed independently.")
            page.locator("#import").set_input_files(
                {"name": "bad.json", "mimeType": "application/json", "buffer": b"not JSON"}
            )
            expect(page.locator("#message")).to_contain_text("Import rejected")
            page.locator("#next").click()
            expect(page.locator("#old-source")).to_contain_text(
                "</script><script>window.injected=1</script>"
            )
            page.locator("#reveal").click()
            expect(page.locator("#proposed-rationale")).to_have_text("<img src=x onerror=alert(1)>")
            assert page.locator("#proposal img").count() == 0
            page.locator("#correspondence").select_option("accepted")
            page.locator("#human-status").select_option("modified")
            with page.expect_download() as downloaded:
                page.locator("#export").click()
            exposure = args.output / "exposure-review.json"
            downloaded.value.save_as(exposure)
            assert json.loads(exposure.read_text())["reviews"][1]["reveal_before_judgment"] is True
            page.evaluate("() => { Storage.prototype.setItem=()=>{throw new Error('blocked')}; }")
            page.locator("#notes").fill("Storage failure test")
            expect(page.locator("#storage-warning")).to_contain_text("storage is unavailable")
            page.screenshot(path=str(args.output / "review-form.png"), full_page=True)
            browser.close()
    assert not errors, errors
    print("Offline review browser checks passed.")


if __name__ == "__main__":
    main()
