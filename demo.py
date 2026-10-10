"""Run the real stdio check against fictional fixtures and save its readback."""
import argparse
from html import escape
import json
from pathlib import Path

import anyio

from smoke import smoke


def render_html(result: dict) -> str:
    documents = []
    for document in result["read_documents"]:
        name = escape(document["path"])
        request = escape(json.dumps({"path": document["path"]}))
        documents.append(f'''<section class="panel"><h2>{name}</h2>
<p><code>read_document({request})</code></p>
<pre class="content">{escape(document['content'])}</pre>
<details><summary>Source identity</summary><dl><dt>UTF-8 bytes</dt><dd>{document['size_bytes']}</dd>
<dt>SHA-256</dt><dd><code>{escape(document['sha256'])}</code></dd></dl></details></section>''')
    count = result["source_bytes_verified"]
    traversal = "rejected" if result["traversal_rejected"] else "not rejected"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MCP document readback</title>
<style>
:root{{--ink:#172c3e;--muted:#516678;--line:#d6e0e6;--brand:#16615c;--paper:#fff;--bg:#f3f6f8}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1000px;margin:auto;padding:40px 24px 60px}}a{{color:var(--brand)}}h1{{font-size:clamp(28px,4vw,40px);line-height:1.2;margin:8px 0 14px}}
h2{{font-size:23px;line-height:1.3;margin:0 0 16px}}p{{margin:0 0 14px}}.intro{{max-width:72ch;color:var(--muted)}}
.panel{{padding:24px;margin:24px 0;background:var(--paper);border:1px solid var(--line);border-radius:12px}}
code,pre{{font:15px/1.6 ui-monospace,"Cascadia Code",Consolas,monospace;overflow-wrap:anywhere;white-space:pre-wrap}}.content{{padding:16px;background:#edf3f5;border-radius:6px}}
dd{{margin:0 0 12px}}dt{{font-weight:600}}summary{{cursor:pointer;min-height:44px}}summary:focus-visible,a:focus-visible{{outline:3px solid #197a74;outline-offset:3px}}
.status{{font-weight:700;color:var(--brand)}}@media(max-width:600px){{main{{padding:24px 16px 40px}}.panel{{padding:18px}}}}
@media print{{body{{background:white}}main{{max-width:none;padding:0}}.panel{{break-inside:avoid;border-radius:0}}details>*{{display:block}}}}
</style></head><body><main><h1>MCP document readback</h1>
<p class="intro">A real local stdio exchange with two fictional documents. The client checked the returned content, byte counts and hashes against the fixture files.</p>
<section class="panel"><h2>Observed checks</h2><ol><li><code>list_documents({{}})</code> lists documents in canonical path order.</li>
<li><code>read_document</code> returns the original text and source identity.</li>
<li><code>read_document({{"path":"../outside.md"}})</code> rejects traversal.</li></ol>
<p class="status">{count} source files verified · Traversal {traversal}</p>
<p>Inspect the exact response in <a href="report.json">JSON</a>.</p></section>
{''.join(documents)}
<p class="intro">Synthetic local evidence only. A hash identifies bytes read during a request; it does not authenticate an author, verify an answer or establish a persistent snapshot. No external MCP host or LLM was used.</p>
</main></body></html>'''


def write_report(output: Path, result: dict) -> None:
    # Refuse an existing directory, including an empty one, before creating files.
    payloads = {"report.json": json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                "report.html": render_html(result)}
    output.mkdir(parents=True, exist_ok=False)
    for name, text in payloads.items():
        with (output / name).open("x", encoding="utf-8", newline="\n") as target:
            target.write(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("demo-output"))
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Choose a new output directory; existing paths are not replaced.")
    result = anyio.run(run_demo)
    write_report(args.output_dir, result)
    print(json.dumps({"source_bytes_verified": result["source_bytes_verified"],
        "traversal_rejected": result["traversal_rejected"], "report": str(args.output_dir / "report.html")}))


async def run_demo() -> dict:
    return await smoke(Path(__file__).parent / "fixtures/docs", include_content=True)


if __name__ == "__main__":
    main()
