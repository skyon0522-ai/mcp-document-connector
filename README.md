# Local documentation connector for MCP

Give an MCP client read-only access to one local documentation folder. A document keeps its relative path, original UTF-8 content, byte count and SHA-256, so an integration can compare an answer's source with the actual file. The manifest uses sorted POSIX paths rather than filesystem enumeration order.

The included documents describe an imaginary service. They contain no customer or workspace data.

## Run

The verified environment is Ubuntu 24.04 under WSL2, Python 3.12.3. Run these commands inside this directory in WSL. The lock file records the exact packages used for verification; package installation downloads dependencies but needs no paid service or API key.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pytest -q --basetemp .test-temp
.venv/bin/python smoke.py --root fixtures/docs
```

`smoke.py` starts a separate `connector.py` process with the official SDK's `StdioServerParameters`, exchanges actual MCP messages, verifies every returned document against its source bytes, checks traversal rejection and closes the child process. It does not call an LLM or simulate stdio with an in-memory connection.

To run the server for an existing local MCP host:

```sh
.venv/bin/python connector.py --root /absolute/path/to/approved-docs
```

The host launches that command as a subprocess. No host configuration or credentials are changed by this repository. Server stdout is reserved for MCP messages.

## Interface and boundaries

| Tool | Input | Structured output |
|---|---|---|
| `list_documents` | `{}` | `documents`: sorted entries containing `path`, `size_bytes`, `sha256` |
| `read_document` | `{"path":"runbooks/recovery.txt"}` | The same metadata and the original decoded `content` |

One root is required explicitly. Supported extensions are `.md`, `.txt` and `.rst`, case-insensitively. Each document must be valid UTF-8 and at most 262144 bytes. The manifest omits unsupported, oversized, unreadable, invalid UTF-8 and escaping documents. More than 256 eligible documents produce an error instead of an incomplete manifest. The connector exposes two read tools and has no document-write operation.

Document identities are canonical POSIX relative paths. Absolute paths on POSIX or Windows, null bytes, backslashes, empty components, `.` and `..` components are rejected. The SDK's `safe_join` also checks resolved containment and rejects symlink escapes. Directory symlinks are not traversed when creating the manifest. Filesystem content is read afresh on each request; a hash identifies the bytes read during that request rather than a persistent snapshot.

Use an owner-controlled tree that is stable during requests. Upstream `safe_join` performs point-in-time resolution: it cannot prevent another process from swapping directory links between resolution and opening a file. This connector has not been verified against hostile concurrent filesystem mutation. Direct Windows runtime behavior has not been tested; the path contract is checked with Windows-shaped malicious inputs and POSIX serialization semantics under Linux.

This small local adapter does not supply enterprise authorization, search indexing, a RAG pipeline or an integration platform. Connecting it to a real organization or AI host requires that system's own data-access decisions. No customer deployment, revenue or hosted CI result is claimed.

## Validation

`test_connector.py` uses the SDK's real in-process client for UTF-8 and CRLF preservation, hashes, insertion-order independence, malicious and noncanonical paths, file and directory symlink escapes, unsupported extensions, invalid UTF-8, size boundaries and manifest-count overflow. It does not skip the symlink test if the environment cannot create a link.

Observed on 2026-10-09: `22 passed in 14.68s` with `mcp==2.3.0` and `pytest==9.1.1`. The standalone stdio command exited 0 and printed:

```json
{
  "transport": "stdio",
  "tools": ["list_documents", "read_document"],
  "documents": [
    {
      "path": "getting-started.md",
      "size_bytes": 134,
      "sha256": "a7357007f36c6dbda6379a7c71e0438b5f9574e5b4dc98c8afedbd174d130f49"
    },
    {
      "path": "runbooks/recovery.txt",
      "size_bytes": 129,
      "sha256": "03d092fafb54b00d80576b2751b96673a2e33eeb75db934a12d8b613d2a6cfe9"
    }
  ],
  "source_bytes_verified": 2,
  "traversal_rejected": true
}
```

The expected traversal rejection also logs a tool error to stderr. It is part of the successful negative check. This result covers a real local stdio exchange and synthetic data; no external host connection or remote CI was tested.

## Upstream lineage

Runtime dependency: [`modelcontextprotocol/python-sdk` v2.3.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0), release commit `2118f14f8a19bc158d8a1cf90af58d85d187f849`. The SDK is installed as a pinned dependency; its protocol and path-security implementation are reused rather than recreated here.

Initial source scouting inspected main at `91941ed4d3985d59def99e090baa3f880c626cc8`. Execution used the released v2.3.0 API and package, not that later main revision. The installed `safe_join` module SHA-256 matched the inspected release file exactly: `e9045fa4bddc28e102a50bbbf527fe62995358630b8131a427ea0b2cf2647ca1`.

- [`safe_join` source](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/shared/path_security.py): imported directly for filesystem containment. Its race limitation is retained above.
- [Original testing guide](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/docs/get-started/testing.md): `Client(server, raise_exceptions=True)` and assertions on returned fields.
- [Original stdio client](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/docs_src/client_transports/tutorial004.py): subprocess launch with `StdioServerParameters`.
- [Original directory resource](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/mcpserver/resources/types.py): reference for directory enumeration behavior, rather than copied implementation.
- [Open issue #3589](https://github.com/modelcontextprotocol/python-sdk/issues/3589) reports OS separators and unstable ordering, and already contains another contributor's proposed fix. This repository applies deterministic POSIX identities in a separate application. It does not modify the upstream SDK, claim discovery of the issue or submit a duplicate patch.

The SDK's unmodified MIT notice, including Anthropic attribution, is retained in [`LICENSES/mcp-python-sdk-MIT.txt`](LICENSES/mcp-python-sdk-MIT.txt). Local implementation changes add bounded document eligibility, source-byte metadata, canonical identities and the two read-only tool handlers. See [`LICENSE`](LICENSE) for the local code's MIT terms.
