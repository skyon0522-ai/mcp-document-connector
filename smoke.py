"""Launch the real stdio server, compare source bytes and check one rejection."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters


async def smoke(root: Path) -> dict:
    root = root.resolve(strict=True)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("connector.py")), "--root", str(root)],
    )
    with anyio.fail_after(20):
        async with Client(parameters) as client:
            tools = sorted(tool.name for tool in (await client.list_tools()).tools)
            assert tools == ["list_documents", "read_document"], tools
            manifest = await client.call_tool("list_documents", {})
            assert not manifest.is_error, manifest
            documents = manifest.structured_content["documents"]
            paths = [document["path"] for document in documents]
            assert paths == sorted(paths) and all("\\" not in path for path in paths)
            assert paths, "The smoke root needs at least one eligible document."
            for metadata in documents:
                result = await client.call_tool("read_document", {"path": metadata["path"]})
                assert not result.is_error, result
                document = result.structured_content
                source = root.joinpath(metadata["path"]).read_bytes()
                assert document["content"] == source.decode("utf-8")
                assert document["sha256"] == hashlib.sha256(source).hexdigest()
                assert document["size_bytes"] == len(source)
                assert {key: document[key] for key in metadata} == metadata
            rejected = await client.call_tool("read_document", {"path": "../outside.md"})
            assert rejected.is_error, "Traversal must be rejected over stdio."
    return {
        "transport": "stdio",
        "tools": tools,
        "documents": documents,
        "source_bytes_verified": len(documents),
        "traversal_rejected": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent / "fixtures/docs")
    print(json.dumps(anyio.run(smoke, parser.parse_args().root), indent=2, ensure_ascii=False))
