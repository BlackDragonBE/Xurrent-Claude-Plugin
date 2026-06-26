# xurrent plugin

Claude Code plugin bundling:

- **`xurrent:xurrent-api` skill** — conventions, account structure, and guidance for Provincie Antwerpen's Xurrent/4me environment.
- **`xurrent` MCP server** — typed Python tools for all Xurrent API operations (requests, notes, custom fields, people, organizations, problems, attachments, CSV import/export).

## Prerequisites

- Claude Code
- Python ≥ 3.10
- [`uv`](https://docs.astral.sh/uv/) installed and on your PATH

## Required environment variables

Set these before installing the plugin so Claude Code can pass them to the server:

```bash
export XURRENT_API_TOKEN=your_bearer_token
export XURRENT_ACCOUNT=provincieantwerpen   # or whichever account you target
# Optional but recommended: your Xurrent email — enables whoami() and "requests assigned to me"
# export XURRENT_ME_EMAIL=you@provincieantwerpen.be
# Optional: point at QA instead of production
# export XURRENT_BASE_URL=https://api.4me-demo.com/v1
```

Add to your shell profile (`.bashrc`, `.zshrc`, or PowerShell profile) so they survive reboots.

## What you get

After installation:

- The `xurrent:xurrent-api` skill loads automatically, giving Claude Code your org's Xurrent conventions.
- The `xurrent` MCP server starts on demand and exposes tools Claude Code can call directly.

See [`server/README.md`](server/README.md) for the full tool list and local testing instructions.
