"""Build an offline, filterable annotation packet from the real-revision corpus."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_packet() -> Path:
    manifest = json.loads((ROOT / "evaluation/real/manifest.json").read_text())
    sections = []
    choices = []
    for case in manifest["cases"]:
        case_id = case["id"]
        choices.append(f'<option value="{case_id}">{case_id}</option>')
        annotation_path = case["annotation_path"]
        if not annotation_path:
            sections.append(
                f'<section data-case="{case_id}"><h2>{case_id}</h2>'
                "<p>Unannotated coverage stress case. Included in runtime outcomes.</p>"
                "</section>"
            )
            continue
        annotation = json.loads((ROOT / annotation_path).read_text())
        old, new = [
            json.loads((ROOT / case[s]["passages_path"]).read_text()) for s in ("old", "new")
        ]
        rows = []
        for number, event in enumerate(annotation["events"]):
            cells = []
            for side, passages in (("old", old), ("new", new)):
                parts = [
                    f"<p><b>{side}[{index}]</b> {html.escape(passages[index])}</p>"
                    for index in event[f"{side}_indices"]
                ]
                cells.append("<td>" + ("".join(parts) or "<i>Absent</i>") + "</td>")
            status = event["status"]
            rows.append(
                f'<tr data-status="{status}" id="{case_id}-{number}">'
                f'<td><a href="#{case_id}-{number}">{number}</a><br>'
                f"<strong>{status}</strong><p>{html.escape(event['rationale'])}</p></td>"
                + "".join(cells)
                + "</tr>"
            )
        links = " | ".join(
            f'<a href="{html.escape(case[s]["source_url"])}">{s}: {html.escape(case[s]["tag"])}</a>'
            for s in ("old", "new")
        )
        sections.append(
            f'<section data-case="{case_id}"><h2>{case_id}</h2><p>{links}</p>'
            f"<p>{len(old)} old passages; {len(new)} new passages. "
            f"Annotation: <code>{html.escape(annotation_path)}</code></p>"
            "<table><thead><tr><th>Provisional label and rationale</th>"
            "<th>Old prose</th><th>New prose</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></section>"
        )
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Real revision annotation review | Semantic Change Radar</title>
<style>
body{font:16px/1.5 system-ui,sans-serif;margin:2rem;color:#182538;background:#f7f9fc}
h1{font-size:1.7rem}a{color:#165dc0}p{margin:.5rem 0}table{border-collapse:collapse;width:100%;
table-layout:fixed;background:white}th,td{border:1px solid #cbd4e0;padding:.8rem;vertical-align:top;
overflow-wrap:anywhere}th:first-child,td:first-child{width:22%}th{text-align:left;background:#e9eff7}
section{margin:2rem 0}nav{position:sticky;top:0;background:#f7f9fc;padding:1rem 0;border-bottom:2px
solid #cbd4e0}select,label{font:inherit;margin-right:1rem}tr[data-status=uncertain]{background:#fff3d5}
@media(max-width:700px){body{margin:.5rem}table{font-size:13px}th,td{padding:.3rem}}
</style><h1>Real revision annotation review</h1>
<p><strong>AI-authored and AI-reviewed labels. Human validation is still pending.</strong>
These are historical upstream revisions, not current technical advice.</p>
<p>Review correspondence first, then the meaning label. A split or merge may have multiple
passage IDs. Changed substantive detail counts as modified. Uncertain means a decision is
unresolved. Model predictions are intentionally absent from this packet.</p>
<p>To correct a label, cite its case, row and passage IDs, or edit the named annotation JSON.
Annotation edits invalidate the frozen scores and require a new evaluation version.
Original source, extracted prose, omission audits and licenses are stored alongside this file.</p>
<nav><select id="case"><option value="all">All documents</option>CASE_OPTIONS</select>
<label><input type="checkbox" id="hide" checked> Hide unchanged</label>
<span id="count"></span></nav>SECTIONS
<script>
function filter(){let count=0; const chosen=document.querySelector('#case').value;
const hide=document.querySelector('#hide').checked;
document.querySelectorAll('section').forEach(section=>{
section.hidden=chosen!=='all'&&section.dataset.case!==chosen;
section.querySelectorAll('tbody tr').forEach(row=>{
row.hidden=hide&&row.dataset.status==='unchanged';if(!section.hidden&&!row.hidden)count++;
});});document.querySelector('#count').textContent=count+' visible annotation groups';}
document.querySelector('#case').addEventListener('change',filter);
document.querySelector('#hide').addEventListener('change',filter);filter();
</script></html>""".replace("CASE_OPTIONS", "".join(choices)).replace("SECTIONS", "".join(sections))
    output = ROOT / "evaluation/real/review.html"
    output.write_text(page, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(build_packet())
