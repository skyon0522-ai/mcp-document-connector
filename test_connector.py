import hashlib
from pathlib import Path, PureWindowsPath

import pytest
from mcp import Client

from connector import MAX_DOCUMENT_BYTES, MAX_DOCUMENTS, DocumentRoot, create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def write(root, path, data):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


@pytest.mark.anyio
async def test_utf8_and_raw_byte_hash(tmp_path):
    data = "# Synthetic\r\n検証用の文書です。\r\n".encode("utf-8")
    write(tmp_path, "nested/readme.md", data)
    async with Client(create_server(tmp_path), raise_exceptions=True) as client:
        result = await client.call_tool("read_document", {"path": "nested/readme.md"})
        assert not result.is_error
        assert result.structured_content == {
            "path": "nested/readme.md",
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content": data.decode("utf-8"),
        }
        manifest = (await client.call_tool("list_documents", {})).structured_content
        assert manifest["documents"] == [{key: result.structured_content[key] for key in ("path", "size_bytes", "sha256")}]


@pytest.mark.anyio
async def test_manifest_is_independent_of_creation_order(tmp_path):
    names = ["z.md", "nested/b.rst", "a.txt", "nested/a.md"]
    manifests = []
    for directory, order in (("first", names), ("second", list(reversed(names)))):
        root = tmp_path / directory
        for name in order:
            write(root, name, name.encode())
        async with Client(create_server(root), raise_exceptions=True) as client:
            manifests.append((await client.call_tool("list_documents", {})).structured_content)
    assert manifests[0] == manifests[1]
    assert [document["path"] for document in manifests[0]["documents"]] == sorted(names)
    # This checks path serialization semantics, not a Windows runtime claim.
    assert PureWindowsPath("nested", "a.md").as_posix() == "nested/a.md"


@pytest.mark.anyio
@pytest.mark.parametrize("path", [
    "../outside.md", "nested/../../outside.md", "/etc/passwd",
    "C:\\Windows\\file.md", "C:file.md", "\\\\server\\share\\file.md",
    "\\file.md", "nested\\file.md", "a/../safe.md", "./safe.md",
    "a//safe.md", "safe.md\x00", "",
])
async def test_malicious_or_noncanonical_paths_are_rejected(tmp_path, path):
    write(tmp_path, "safe.md", b"synthetic")
    async with Client(create_server(tmp_path), raise_exceptions=True) as client:
        result = await client.call_tool("read_document", {"path": path})
        assert result.is_error
        assert str(tmp_path) not in str(result.content)


@pytest.mark.anyio
async def test_symlink_escape_is_rejected_and_not_listed(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Synthetic outside document", encoding="utf-8")
    (root / "escape.md").symlink_to(outside)
    (root / "directory-link").symlink_to(tmp_path, target_is_directory=True)
    write(root, "inside.md", b"inside")
    async with Client(create_server(root), raise_exceptions=True) as client:
        result = await client.call_tool("read_document", {"path": "escape.md"})
        assert result.is_error
        via_directory = await client.call_tool("read_document", {"path": "directory-link/outside.md"})
        assert via_directory.is_error
        manifest = (await client.call_tool("list_documents", {})).structured_content
        assert [document["path"] for document in manifest["documents"]] == ["inside.md"]


@pytest.mark.anyio
@pytest.mark.parametrize("path,data", [
    ("unsupported.pdf", b"synthetic"),
    ("oversized.md", b"x" * (MAX_DOCUMENT_BYTES + 1)),
    ("invalid.txt", b"\xff\xfe"),
])
async def test_ineligible_documents_are_rejected_and_omitted(tmp_path, path, data):
    write(tmp_path, path, data)
    async with Client(create_server(tmp_path), raise_exceptions=True) as client:
        assert (await client.call_tool("read_document", {"path": path})).is_error
        assert (await client.call_tool("list_documents", {})).structured_content == {"documents": []}


@pytest.mark.anyio
async def test_exact_size_limit_and_no_write_tools(tmp_path):
    write(tmp_path, "limit.TXT", b"a" * MAX_DOCUMENT_BYTES)
    before = (tmp_path / "limit.TXT").read_bytes()
    async with Client(create_server(tmp_path), raise_exceptions=True) as client:
        names = sorted(tool.name for tool in (await client.list_tools()).tools)
        assert names == ["list_documents", "read_document"]
        result = await client.call_tool("read_document", {"path": "limit.TXT"})
        assert not result.is_error and result.structured_content["size_bytes"] == MAX_DOCUMENT_BYTES
    assert (tmp_path / "limit.TXT").read_bytes() == before


@pytest.mark.anyio
async def test_manifest_fails_rather_than_silently_truncating(tmp_path):
    for index in range(MAX_DOCUMENTS + 1):
        write(tmp_path, f"{index:03}.md", b"synthetic")
    async with Client(create_server(tmp_path), raise_exceptions=True) as client:
        assert (await client.call_tool("list_documents", {})).is_error


def test_missing_and_nondirectory_root(tmp_path):
    with pytest.raises(FileNotFoundError):
        DocumentRoot(tmp_path / "missing")
    write(tmp_path, "file.md", b"synthetic")
    with pytest.raises(ValueError):
        DocumentRoot(tmp_path / "file.md")
