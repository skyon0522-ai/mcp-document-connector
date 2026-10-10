import json
from pathlib import Path

import anyio
import pytest

from demo import render_html, run_demo, write_report


def test_saved_readback_uses_real_mcp_fixture_bytes(tmp_path):
    result = anyio.run(run_demo)
    root = Path(__file__).parent / "fixtures/docs"
    assert result["source_bytes_verified"] == 2 and result["traversal_rejected"]
    assert [doc["path"] for doc in result["read_documents"]] == ["getting-started.md", "runbooks/recovery.txt"]
    for doc in result["read_documents"]:
        assert doc["content"].encode("utf-8") == (root / doc["path"]).read_bytes()
    output = tmp_path / "fresh"
    write_report(output, result)
    assert json.loads((output / "report.json").read_text(encoding="utf-8")) == result
    assert (output / "report.html").read_text(encoding="utf-8") == render_html(result)
    committed = Path(__file__).parent / "examples/reports"
    assert json.loads((committed / "report.json").read_text(encoding="utf-8")) == result
    assert (committed / "report.html").read_text(encoding="utf-8") == render_html(result)
    before = (output / "report.json").read_bytes()
    with pytest.raises(FileExistsError):
        write_report(output, result)
    assert (output / "report.json").read_bytes() == before


def test_readback_html_escapes_document_text():
    result = {"source_bytes_verified": 1, "traversal_rejected": False, "read_documents": [{"path": '<img src=x onerror="alert(1)">',
        "content": "</pre><script>alert(1)</script>", "size_bytes": 35, "sha256": "a" * 64}]}
    html = render_html(result)
    assert "<script>" not in html and "<img " not in html
    assert "&lt;script&gt;" in html and "&lt;img" in html
    assert "Traversal not rejected" in html
