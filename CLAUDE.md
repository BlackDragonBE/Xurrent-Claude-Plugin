# CLAUDE.md — xurrent-tools

## Running the MCP Inspector

```powershell
cd plugins\xurrent\server
$env:XURRENT_ACCOUNT="provincieantwerpen"
$env:XURRENT_QA_TOKEN="your_qa_token"
uv run mcp dev server.py
```

> `--system-certs` is set by default in `uv.toml` at the repo root (required on the work network — uv's bundled TLS roots don't include the corporate CA).
