"""Read-only MCP access to one owner-controlled, stable documentation tree."""

import argparse
import hashlib
import os
from pathlib import Path

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.path_security import PathEscapeError, safe_join
from pydantic import BaseModel

SUPPORTED_EXTENSIONS = frozenset({".md", ".txt", ".rst"})
MAX_DOCUMENT_BYTES = 256 * 1024
MAX_DOCUMENTS = 256


class DocumentMetadata(BaseModel):
    path: str
    size_bytes: int
    sha256: str


class Document(DocumentMetadata):
    content: str


class Manifest(BaseModel):
    documents: list[DocumentMetadata]


class DocumentRoot:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("The configured root must be a directory.")

    def read(self, relative_path: str) -> Document:
        # Reuse the SDK's cross-platform absolute-path and containment checks.
        target = safe_join(self.root, relative_path)
        if (
            not relative_path
            or "\\" in relative_path
            or any(part in {"", ".", ".."} for part in relative_path.split("/"))
        ):
            raise ValueError("Use a canonical POSIX relative document path.")
        if Path(relative_path).suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError("Supported extensions are .md, .txt and .rst.")
        if not target.is_file():
            raise ValueError("Document does not exist or is not a regular file.")
        with target.open("rb") as source:
            data = source.read(MAX_DOCUMENT_BYTES + 1)
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValueError("Document exceeds the 262144-byte limit.")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Document must contain valid UTF-8.") from error
        return Document(
            path=relative_path,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            content=text,
        )

    def manifest(self) -> Manifest:
        documents = []
        # Directory symlinks are not followed; file links still pass safe_join.
        for directory, _, filenames in os.walk(self.root, followlinks=False):
            for filename in filenames:
                path = (Path(directory) / filename).relative_to(self.root).as_posix()
                if Path(path).suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    document = self.read(path)
                except (OSError, ValueError, RuntimeError):
                    continue
                documents.append(DocumentMetadata(**document.model_dump(exclude={"content"})))
                if len(documents) > MAX_DOCUMENTS:
                    raise ValueError("Root contains more than 256 eligible documents.")
        return Manifest(documents=sorted(documents, key=lambda document: document.path))


def create_server(root: Path) -> MCPServer:
    documents = DocumentRoot(root)
    server = MCPServer("Local documentation connector", subscriptions=False)

    @server.tool()
    async def list_documents() -> Manifest:
        """List eligible UTF-8 documents with sorted POSIX paths and SHA-256 hashes."""
        try:
            return await anyio.to_thread.run_sync(documents.manifest)
        except ValueError as error:
            raise ToolError(str(error)) from error

    @server.tool()
    async def read_document(path: str) -> Document:
        """Read one document using its exact relative path from list_documents."""
        try:
            return await anyio.to_thread.run_sync(documents.read, path)
        except PathEscapeError as error:
            raise ToolError("Document path is outside the configured root or is absolute.") from error
        except (OSError, RuntimeError) as error:
            raise ToolError("Document is unavailable.") from error
        except ValueError as error:
            raise ToolError(str(error)) from error

    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    create_server(parser.parse_args().root).run(transport="stdio")
