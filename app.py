"""Gradio demo. Importing this module never initializes inference models."""

import json
import logging
import os
import tempfile
from html import escape
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr

from radar.presentation import FILTERS, render_results, render_summary

ROOT = Path(__file__).resolve().parent
EXAMPLES = json.loads((ROOT / "examples.json").read_text(encoding="utf-8"))
CSS = (ROOT / "assets" / "style.css").read_text(encoding="utf-8")
LOGGER = logging.getLogger(__name__)

HEADER = """
<div class="scr-topline">
  <span class="scr-brand"><span class="scr-mark" aria-hidden="true"></span>SEMANTIC CHANGE RADAR</span>
  <span>DOCUMENT REVIEW WORKSPACE</span>
</div>
<div class="scr-hero">
  <div><span class="scr-eyebrow">READ THE CHANGE. KEEP THE CONTEXT.</span>
  <h1>What actually changed?</h1>
  <p>A clearer view of document revisions. Compare requirements, limits, and permissions,
  with the source text and evidence side by side.</p></div>
  <div class="scr-hero-note"><span>THE REVIEW FLOW</span><ol><li>Compare two versions</li>
  <li>Separate meaning from wording</li><li>Inspect the evidence</li></ol></div>
</div>
"""


def cleanup_report(state: dict | None) -> None:
    """Remove the original temporary export when a session ends or is replaced."""
    if state and state.get("download_path"):
        Path(state["download_path"]).unlink(missing_ok=True)


def run_comparison(
    old_text: str,
    new_text: str,
    backend: str,
    view: str,
    previous_state: dict | None,
    progress=gr.Progress(),
) -> tuple:
    from radar.compare import compare_documents

    description = (
        "Loading models and comparing passages..."
        if backend == "semantic"
        else "Comparing with the lexical baseline..."
    )
    progress(0.05, desc=description)
    try:
        report = compare_documents(old_text, new_text, backend=backend)
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Document comparison failed")
        message = "Comparison could not finish. Try a shorter document or inspect the server log."
        if backend == "semantic":
            message = (
                "Semantic models could not load or run. First use requires an internet connection "
                "to download the models. Retry, or explicitly select Lexical baseline for an offline comparison."
            )
        raise gr.Error(message) from exc

    progress(0.95, desc="Preparing your report...")
    with tempfile.NamedTemporaryFile(
        mode="w", prefix="semantic-change-radar-", suffix=".json", encoding="utf-8", delete=False
    ) as export:
        json.dump(report, export, ensure_ascii=False, indent=2, allow_nan=False)
        export.write("\n")
        download_path = export.name
    cleanup_report(previous_state)
    name = "semantic models" if backend == "semantic" else "lexical baseline"
    status = f"Compared {report['old_count']} before and {report['new_count']} after passages with the {name}."
    state = {
        "report": report,
        "download_path": download_path,
        "inputs": (old_text, new_text, backend),
        "status": status,
    }
    return (
        state,
        render_summary(report),
        render_results(report, view),
        gr.update(value=download_path, visible=True),
        report,
        status,
    )


def load_example(title: str) -> tuple[str, str]:
    for example in EXAMPLES:
        if example["title"] == title:
            return example["old"], example["new"]
    raise gr.Error("Select an example from the list.")


def example_context(title: str, old_text: str | None = None, new_text: str | None = None) -> str:
    example = next((item for item in EXAMPLES if item["title"] == title), {})
    if not example.get("source"):
        return '<p class="scr-example-note">Illustrative example · Edit either version, or paste your own documents.</p>'
    source = example["source"]
    edited = (old_text is not None and old_text != example["old"]) or (
        new_text is not None and new_text != example["new"]
    )
    label = "Edited input; links refer to the original example" if edited else "Historical source"
    return (
        f'<div class="scr-example-note"><strong>{label} · '
        + escape(source["repository"])
        + "</strong> · "
        + escape(source["dates"])
        + " · "
        + escape(source["license"])
        + f' · <a href="{escape(source["old_url"], quote=True)}" target="_blank" rel="noopener noreferrer">Before source</a>'
        + f' · <a href="{escape(source["new_url"], quote=True)}" target="_blank" rel="noopener noreferrer">After source</a>'
        + "<p>"
        + escape(example["note"])
        + "</p></div>"
    )


def filter_results(state: dict | None, view: str) -> str:
    return render_results(state["report"] if state else None, view)


def mark_stale(state: dict | None, old_text: str, new_text: str, backend: str) -> str:
    if state is None:
        return "Ready to compare."
    if state["inputs"] == (old_text, new_text, backend):
        return state["status"]
    return "Inputs changed. Compare again to refresh the report."


def create_app() -> gr.Blocks:
    with gr.Blocks(
        title="Semantic Change Radar", analytics_enabled=False, delete_cache=(600, 3600)
    ) as demo:
        state = gr.State(value=None, time_to_live=3600, delete_callback=cleanup_report)
        gr.HTML(HEADER)
        gr.HTML(
            '<div class="scr-section-heading"><span>01</span><h2>Document versions</h2><p>Start with an example or your own text</p></div>'
        )
        example = gr.Dropdown(
            choices=[item["title"] for item in EXAMPLES],
            value=EXAMPLES[0]["title"],
            label="Try a scenario",
            elem_id="scr-example",
            interactive=True,
        )
        example_note = gr.HTML(example_context(EXAMPLES[0]["title"]))
        with gr.Row(elem_id="scr-inputs"):
            old_text = gr.Textbox(
                value=EXAMPLES[0]["old"],
                label="Before",
                info="The original document",
                lines=11,
                max_lines=18,
            )
            new_text = gr.Textbox(
                value=EXAMPLES[0]["new"],
                label="After",
                info="The updated document",
                lines=11,
                max_lines=18,
            )
        with gr.Row(elem_id="scr-controls"):
            backend = gr.Radio(
                choices=[("Semantic models", "semantic"), ("Lexical baseline", "lexical")],
                value="semantic",
                label="Comparison engine",
                scale=3,
            )
            compare = gr.Button(
                "Compare documents", variant="primary", scale=1, elem_id="scr-compare"
            )
        gr.HTML(
            '<p class="scr-helper">English text or Markdown · Up to 30,000 characters and 80 passages per version. '
            "Separate short paragraphs with blank lines (up to 256 model tokens per paragraph). "
            "The semantic engine downloads its models once on first use; the lexical baseline needs no model download.</p>"
        )
        status = gr.Markdown("Ready to compare.", elem_id="scr-run-status")
        gr.HTML(
            '<div class="scr-section-heading scr-review-heading"><span>02</span><h2>Review changes</h2><p>Meaning, wording, and the evidence behind them</p></div>'
        )
        summary = gr.HTML(render_summary(None), elem_id="scr-summary-panel")
        view = gr.Radio(
            choices=FILTERS,
            value="material",
            label="Show passages",
            interactive=True,
            elem_id="scr-filters",
        )
        results = gr.HTML(render_results(None), elem_id="scr-results-panel")
        download = gr.File(
            label="Download comparison report (JSON)",
            interactive=False,
            visible=False,
            elem_id="scr-download",
        )
        with gr.Accordion("How to read the comparison", open=False):
            gr.Markdown(
                "**Material edits** include changed meaning, additions, and removals. **Needs review** means the engine "
                "cannot safely decide. **Reworded** means a likely equivalent paraphrase. **Moved** marks a change in "
                "relative order and can overlap any category.\n\n"
                "The colors inside each passage show literal text edits. Model scores are available under each card; "
                "they are not calibrated confidence. Localized verification preserves source wording and punctuation; "
                "use the full passages above to inspect the surrounding context. "
                "A lexical comparison cannot establish semantic equivalence.\n\n"
                "This is a review aid. It uses headings and list context and can match an adjacent two-paragraph "
                "split or merge. Renamed headings can trigger extra review flags. Larger rewrites, tables, long "
                "context, and subtle exceptions can still need manual review."
            )
        with gr.Accordion("Inspect the complete JSON report", open=False):
            raw_report = gr.JSON(label="Report", value=None, elem_id="scr-raw-report")
        gr.HTML(
            '<div class="scr-footer"><span>Built for inspectable document review.</span>'
            "<span>Text is processed on the app server. Downloads are cleared after about one hour.</span></div>"
        )

        example.change(
            load_example, example, [old_text, new_text], queue=False, api_visibility="private"
        ).then(
            example_context,
            [example, old_text, new_text],
            example_note,
            queue=False,
            show_progress="hidden",
            api_visibility="private",
        )
        gr.on(
            triggers=[old_text.change, new_text.change],
            fn=example_context,
            inputs=[example, old_text, new_text],
            outputs=example_note,
            queue=False,
            trigger_mode="always_last",
            show_progress="hidden",
            api_visibility="private",
        )
        gr.on(
            triggers=[old_text.change, new_text.change, backend.change],
            fn=mark_stale,
            inputs=[state, old_text, new_text, backend],
            outputs=status,
            queue=False,
            show_progress="hidden",
            api_visibility="private",
        )
        compare.click(
            run_comparison,
            inputs=[old_text, new_text, backend, view, state],
            outputs=[state, summary, results, download, raw_report, status],
            concurrency_limit=1,
            api_name="compare",
            api_description="Compare two English document versions. Semantic inference downloads models on first use.",
            show_progress_on=results,
        ).then(
            mark_stale,
            inputs=[state, old_text, new_text, backend],
            outputs=status,
            queue=False,
            show_progress="hidden",
            api_visibility="private",
        )
        view.change(
            filter_results,
            [state, view],
            results,
            queue=False,
            show_progress="hidden",
            api_visibility="private",
        )
    return demo.queue(max_size=16, default_concurrency_limit=1)


def main() -> None:
    theme = gr.themes.Soft(
        primary_hue=gr.themes.Color(
            name="forest",
            c50="#f0f7f2",
            c100="#deeee2",
            c200="#bcdbc7",
            c300="#92bfa4",
            c400="#629a7d",
            c500="#3e7f5f",
            c600="#176d67",
            c700="#195239",
            c800="#163f2e",
            c900="#123426",
            c950="#092017",
        ),
        secondary_hue="stone",
        neutral_hue="stone",
        font=["system-ui", "sans-serif"],
        font_mono=["ui-monospace", "monospace"],
    ).set(
        background_fill_primary="#fffefa",
        background_fill_secondary="#edf0e9",
        body_background_fill="#f6f3ed",
        body_text_color="#173439",
        body_text_color_subdued="#56686a",
        block_label_text_color="#173439",
        block_title_text_color="#173439",
        block_background_fill="#ffffff",
        input_background_fill="#ffffff",
    )
    # The custom UI has one paper palette. Match every Gradio surface and control
    # to it, including file rows and radio states when the browser prefers dark.
    tokens = theme.to_dict()["theme"]
    theme.set(**{key: tokens[key.removesuffix("_dark")] for key in tokens if key.endswith("_dark")})
    create_app().launch(
        server_name=os.getenv(
            "GRADIO_SERVER_NAME", "0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1"
        ),
        share=os.getenv("GRADIO_SHARE") == "1",
        theme=theme,
        css=CSS,
        footer_links=[],
        run_history=False,
        show_error=False,
        max_file_size="1mb",
    )


if __name__ == "__main__":
    main()
