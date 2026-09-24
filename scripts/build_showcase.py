"""Build an offline example explorer from actual, recorded comparison outputs.

This is a static companion to the Gradio app, not browser-side model inference.
Run from the repository root with cached models and HF_HUB_OFFLINE=1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Explore recorded semantic document comparisons, source evidence, and known limitations. Run the open-source Gradio app for your own documents.">
<title>Semantic Change Radar | Recorded examples</title>
<style>STYLE
*{box-sizing:border-box}body{margin:0;font:15px/1.6 system-ui,sans-serif;color:#173439}
a{color:#176d67;text-underline-offset:3px}button,select{font:inherit;color:inherit}
button,select{background:#fffefa;border:1px solid #becdc3;border-radius:7px;padding:10px 14px}
button{cursor:pointer}button:hover{background:#eaf0e9}button[aria-pressed=true]{background:#176d67;color:white}
.recorded{background:#eaf0e9;border-left:3px solid #176d67;padding:12px 16px;font-size:13px;margin:0 0 26px}
.recorded strong{display:block}.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin:20px 0 14px}
.controls label{flex:1;min-width:240px;font-size:12px}.controls select{display:block;width:100%;margin-top:7px}
.source-docs{margin:20px 0;border:1px solid #d9dfd9;background:#fffefa;border-radius:8px;padding:14px 18px}
.source-docs summary{cursor:pointer;font-size:13px}.source-docs pre{font:12px/1.8 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-height:360px;overflow:auto;margin:12px 0}
.docs-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.docs-grid h3{font-size:12px}
.view-controls{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}#provenance{font-size:12px}
.links{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;margin:14px 0 25px}
@media(max-width:760px){.docs-grid{grid-template-columns:1fr}.controls button{width:100%}.view-controls button{font-size:12px;min-height:44px}}
</style></head><body><main class="gradio-container">
HEADER
<div class="recorded" role="note"><strong>Recorded examples · No live inference on this page</strong>
Explore actual saved model outputs, filters, evidence and JSON exports. To compare your own text,
run the <a href="https://github.com/Habetyan/semantic-change-radar#run-locally">Gradio app</a>.
These examples include imperfect predictions; model scores are not calibrated confidence.</div>
<div class="links"><a href="https://github.com/Habetyan/semantic-change-radar">Code &amp; setup</a>
<a href="https://github.com/Habetyan/semantic-change-radar/blob/main/docs/resume-results.md">Evaluation &amp; failures</a>
<a href="NOTICE.md">Source attribution</a></div>
<div class="controls"><label for="scenario">Explore a scenario<select id="scenario"></select></label>
<button id="download">Download recorded JSON</button></div>
<div id="provenance"></div>
<details class="source-docs"><summary>Read the complete input documents</summary>
<div class="docs-grid"><section><h3>Before</h3><pre id="before"></pre></section>
<section><h3>After</h3><pre id="after"></pre></section></div></details>
<div id="summary" aria-live="polite"></div>
<div class="view-controls" role="group" aria-label="Show passages"></div>
<div id="results" aria-live="polite"></div>
<div class="scr-footer"><span>Recorded at RECORDED_AT. English prose · CPU MiniLM pipeline.</span>
<span>Historical source text is not current technical guidance.</span></div>
</main><script id="records" type="application/json">DATA</script>
<script>
const data=JSON.parse(document.querySelector('#records').textContent);
const selector=document.querySelector('#scenario');let view='material';
for(const [i,item] of data.examples.entries()){
 const option=document.createElement('option');option.value=i;option.textContent=item.title;selector.append(option);
}
for(const [label,value] of data.filters){
 const button=document.createElement('button');button.textContent=label;button.dataset.view=value;
 button.addEventListener('click',()=>{view=value;render()});document.querySelector('.view-controls').append(button);
}
function render(){const item=data.examples[Number(selector.value)];
 document.querySelector('#provenance').innerHTML=item.provenance;
 document.querySelector('#before').textContent=item.old;document.querySelector('#after').textContent=item.new;
 document.querySelector('#summary').innerHTML=item.summary;
 document.querySelector('#results').innerHTML=item.views[view];
 document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
}
selector.addEventListener('change',render);
document.querySelector('#download').addEventListener('click',()=>{
 const item=data.examples[Number(selector.value)];const blob=new Blob([JSON.stringify(item.report,null,2)+'\\n'],{type:'application/json'});
 const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='semantic-change-radar-recorded.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});render();
</script></body></html>
"""


def build(output: Path) -> None:
    from app import CSS, EXAMPLES, HEADER, example_context
    from radar.compare import compare_documents
    from radar.presentation import FILTERS, render_results, render_summary

    output.mkdir(parents=True, exist_ok=True)
    recorded = datetime.now(timezone.utc).isoformat()
    records = []
    for example in EXAMPLES:
        report = compare_documents(example["old"], example["new"])
        records.append(
            {
                **example,
                "report": report,
                "summary": render_summary(report),
                "views": {value: render_results(report, value) for _, value in FILTERS},
                "provenance": example_context(example["title"])
                if example.get("source")
                else "Illustrative scenario with prepared inputs and recorded model output.",
            }
        )
    data = json.dumps({"examples": records, "filters": FILTERS}, ensure_ascii=True)
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = PAGE.replace("STYLE", CSS).replace("HEADER", HEADER)
    page = page.replace("RECORDED_AT", recorded).replace("DATA", data)
    (output / "index.html").write_text(page, encoding="utf-8")
    hashes = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [ROOT / "examples.json", ROOT / "app.py", *sorted((ROOT / "radar").glob("*.py"))]
    }
    (output / "recording.json").write_text(
        json.dumps(
            {"recorded_at": recorded, "source_hashes": hashes, "examples": len(records)}, indent=2
        )
        + "\n"
    )
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    notices = [
        "# Sources in the recorded examples\n",
        "App source is MIT licensed. Models are downloaded dependencies; no weights are redistributed.\n",
    ]
    for p in sorted((ROOT / "evaluation/fresh-v2/licenses").glob("*")):
        target = output / "licenses" / p.name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(p, target)
        notices.append(f"- [{p.name}](licenses/{p.name})\n")
    notices.append(
        "\nHTTPX and MkDocs retain their BSD licenses; pip retains MIT. The copied prose is extracted from pinned historical Markdown pages, excluding code blocks and normalizing markup. Exact upstream URLs, revisions and extraction audits are in the [project corpus](https://github.com/Habetyan/semantic-change-radar/tree/main/evaluation/fresh-v2).\n"
    )
    (output / "NOTICE.md").write_text("\n".join(notices))
    (output / "README.md").write_text("""---
title: Semantic Change Radar
colorFrom: green
colorTo: gray
sdk: static
app_file: index.html
license: mit
short_description: Explore recorded document comparisons and source evidence
---

# Semantic Change Radar: recorded examples

This static companion displays actual saved outputs from the CPU Gradio application.
It offers source documents, result filters, evidence and JSON downloads.
It does **not** run models or compare new documents in the browser.

[Full application and setup](https://github.com/Habetyan/semantic-change-radar)
· [Evaluation and limitations](https://github.com/Habetyan/semantic-change-radar/blob/main/docs/resume-results.md)

Evaluation uses versioned reference annotations; see the
[annotation provenance](https://github.com/Habetyan/semantic-change-radar/blob/main/docs/annotation-provenance.md).
Historical documentation examples are not current technical guidance.
See [NOTICE.md](NOTICE.md) and the retained source licenses.
""")
    print(f"Built {len(records)} recorded examples in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "showcase")
    build(parser.parse_args().output)
