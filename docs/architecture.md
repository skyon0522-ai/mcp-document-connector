# Request flow and source identity

Read the files in this order: `connector.py`, `smoke.py`, then `demo.py`.
The server validates and reads. The client compares. The demo presents those
observed responses; it does not add a different transport or read implementation.

## From a tool call to bytes

1. `create_server()` constructs one `DocumentRoot` from the explicit directory.
2. `list_documents()` enumerates eligible names, calls `DocumentRoot.read()` for
   each, strips content from the manifest and sorts canonical POSIX paths.
3. `read_document(path)` uses the same read function. The SDK containment helper
   checks resolved paths; local checks enforce canonical names and extensions.
4. The bounded read accepts UTF-8 bytes and derives text, byte count and SHA-256
   from that single read. Requests do not use a persistent content cache.
5. `smoke()` launches the real subprocess and reads every listed document through
   MCP. It compares returned content and identities with the fixture bytes, then
   checks that a traversal call returns a tool error.
6. `demo.py` opts into the already verified document content, escapes it for HTML
   and saves JSON beside the report. Its inputs are only the bundled fictional
   fixtures. The default smoke summary still omits document content.

## Boundaries that matter

The configured root is a data-access decision supplied by the MCP host. A
canonical path and hash help a client identify content; they are not user
authorization or evidence that a generated answer is correct. Each request reads
fresh bytes, so the manifest and a later read may observe different versions.

Containment assumes an owner-controlled directory without hostile concurrent
mutation. Report generation writes synthetic results to a new directory; it does
not grant the server a document-write tool. The HTML has no scripts, external
assets or network requests. Text and hashes can be read without JavaScript.
