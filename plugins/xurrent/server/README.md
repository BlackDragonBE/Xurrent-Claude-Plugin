# Xurrent MCP Server

Local stdio MCP server that exposes Xurrent (4me) API tools to Claude Code.

## Required environment variables

| Variable | Required | Description |
|---|---|---|
| `XURRENT_ACCOUNT` | Yes | Default account sent as `X-4me-Account` header (e.g. `provincieantwerpen-dict`). Set this to your most-used account; individual tool calls can override it with the `account` parameter. |
| `XURRENT_PRD_TOKEN` | One of PRD/QA | OAuth bearer token for the production Xurrent API. `XURRENT_API_TOKEN` is accepted as an alias for backward compatibility. |
| `XURRENT_QA_TOKEN` | One of PRD/QA | OAuth bearer token for the QA Xurrent API. |
| `XURRENT_PRD_BASE_URL` | No | Production API base URL. Defaults to `https://api.xurrent.com/v1`. The QA URL is derived automatically by replacing `.com` with `.qa` (e.g. `api.xurrent.qa`). |

At least one of `XURRENT_PRD_TOKEN` / `XURRENT_QA_TOKEN` must be set. The server starts fine with only one; calling a tool with `environment="PRD"` when `XURRENT_PRD_TOKEN` is missing returns a clear error.

Every tool defaults to `environment="QA"` — matching the skill's safe default — so accidental production writes require explicitly passing `environment="PRD"`.

Set these in your shell profile (`.bashrc`, `.zshrc`, PowerShell profile) so they are inherited by Claude Code when it launches the server.

## Running the Inspector for local testing

```powershell
cd plugins\xurrent\server
$env:XURRENT_ACCOUNT="provincieantwerpen"
$env:XURRENT_QA_TOKEN="your_qa_token"
uv run mcp dev server.py
```

This opens the MCP Inspector in your browser where you can call each tool interactively and inspect the typed input schema.

> `--system-certs` is enabled by default via `uv.toml` at the repo root (required on the work network).

## SDK version pin

The server depends on `mcp>=1.27,<2`. The `2.x` line is currently alpha and has breaking changes; the upper bound prevents accidental upgrades. It uses `mcp.server.fastmcp` from the official `mcp` SDK — **not** the separate `fastmcp` PyPI package.

## Tools

| Tool | Skill equivalent | Description |
|---|---|---|
| `get_request` | `Get-XurrentData` on `/requests/{id}` | Fetch one request |
| `list_requests` | `Get-XurrentData` on `/requests` | List/filter requests |
| `create_request` | `New-XurrentData` on `/requests` | Create a new request |
| `update_request` | `Set-XurrentDataPatch` on `/requests/{id}` | Patch any request fields |
| `add_note` | `Add-XurrentNoteToRequest` | Add a note (internal or visible) |
| `update_custom_field` | `Set-XurrentDataPatch` custom_fields | Set one custom field |
| `get_custom_field_value` | `Get-XurrentCustomFieldValue` | Read one custom field |
| `get_person` / `list_people` | `Get-XurrentData` on `/people` | People records |
| `get_organization` / `list_organizations` | `Get-XurrentData` on `/organizations` | Organization records |
| `get_problem` / `list_problems` | `Get-XurrentData` on `/problems` | Problem records |
| `get_rate_limit_status` | `Get-XurrentRateLimitStatus` | Current rate-limit headers |
| `get_attachment_storage` | `Get-XurrentAttachmentStorage` | Get presigned S3 upload URL |
| `add_attachment_to_request` | `Add-XurrentAttachmentToRequest` | Link uploaded file to request |
| `import_csv` | `Import-XurrentCsv` | Start and poll a CSV import job |
| `export_csv` | `Export-XurrentCsv` | Start, poll, and download a CSV export |
