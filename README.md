# xurrent-tools

Claude Code plugin marketplace containing the `xurrent` plugin — a skill and local Python MCP server for the Xurrent (4me) IT service management API, tailored for Provincie Antwerpen.

## What it is

A Claude Code plugin that gives Claude:

1. The **`xurrent:xurrent-api` skill** — org-specific conventions: account names, custom field meanings, QA vs production guidance, and the PowerShell module reference.
2. The **`xurrent` MCP server** — typed Python tools for all Xurrent API operations (requests, notes, custom fields, people, organizations, problems, attachments, CSV import/export) running as a local subprocess over stdio.

## Quick setup

Run this one-liner in PowerShell — it installs `uv` if missing, provisions Python via `uv`, and tells you what to do next:

```powershell
irm https://raw.githubusercontent.com/BlackDragonBE/Xurrent-Claude-Plugin/main/setup.ps1 | iex
```

Then:

```text
claude plugin marketplace add BlackDragonBE/Xurrent-Claude-Plugin
claude plugin install xurrent@xurrent-tools
```

## Updating

To pull the latest version:

```text
claude plugin marketplace update xurrent-tools
```

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- [`uv`](https://docs.astral.sh/uv/) installed and on your PATH (the setup script installs it; `uv` then provides Python ≥ 3.10)

## Required environment variables

The MCP server reads credentials from your environment — they are never stored in any file in this repo.

| Variable | Required | Description |
|---|---|---|
| `XURRENT_ACCOUNT` | Yes | `X-4me-Account` header value (e.g. `provincieantwerpen`) |
| `XURRENT_PRD_TOKEN` | One of PRD/QA | Bearer token for production. `XURRENT_API_TOKEN` accepted as alias. |
| `XURRENT_QA_TOKEN` | One of PRD/QA | Bearer token for QA. |
| `XURRENT_ME_EMAIL` | Recommended | Your Xurrent email. Enables `whoami` and "requests assigned to me" (the API token is a system account, so the built-in `assigned_to_me` filter resolves to it, not you). Optional, but set it unless you have a reason not to. |
| `XURRENT_PRD_BASE_URL` | No | Production base URL. Defaults to `https://api.xurrent.com/v1`. QA URL is derived automatically by replacing `.com` with `.qa`. |

`XURRENT_ACCOUNT` is your default account — the one used when no `account` parameter is passed to a tool. Set it to your most-used account (e.g. `provincieantwerpen-dict`). Individual tool calls can always override it.

Set these as **user-level** environment variables so they are inherited by Claude Code and the MCP Inspector:

```powershell
[System.Environment]::SetEnvironmentVariable("XURRENT_ACCOUNT", "provincieantwerpen-dict", "User")
[System.Environment]::SetEnvironmentVariable("XURRENT_PRD_TOKEN", "your_prd_token", "User")
[System.Environment]::SetEnvironmentVariable("XURRENT_QA_TOKEN", "your_qa_token", "User")
# Optional — enables whoami / "requests assigned to me":
[System.Environment]::SetEnvironmentVariable("XURRENT_ME_EMAIL", "you@provincieantwerpen.be", "User")
```

Restart your terminal (or the Inspector) after setting them — session-level `$env:` variables are not inherited by subprocesses spawned by other apps.

## What you get after install

- `xurrent:xurrent-api` skill loaded in every session.
- `xurrent` MCP server available with tools: `get_request`, `list_requests`, `create_request`, `update_request`, `add_note`, `update_custom_field`, `get_custom_field_value`, `get_person`, `list_people`, `get_organization`, `list_organizations`, `get_problem`, `list_problems`, `get_rate_limit_status`, `get_attachment_storage`, `add_attachment_to_request`, `import_csv`, `export_csv`, `xurrent_get`, `xurrent_post`, `xurrent_patch`, `xurrent_delete`, `whoami`.

See [`plugins/xurrent/server/README.md`](plugins/xurrent/server/README.md) for details on each tool.
