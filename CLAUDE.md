# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin marketplace** (`.claude-plugin/marketplace.json`) holding one plugin, `xurrent`, which talks to the Xurrent (formerly 4me) ITSM REST API for Provincie Antwerpen. The plugin has two halves that ship together:

- **Skill** (`plugins/xurrent/skills/xurrent-api/SKILL.md`) — prose that tells Claude *what* tool to call and *when*, plus org conventions (account names, QA-vs-PRD, custom-field meaning). No code.
- **MCP server** (`plugins/xurrent/server/server.py`) — a single-file Python stdio server exposing typed tools that handle *how*: auth, pagination, retries, rate limits. Launched per `plugins/xurrent/.mcp.json` via `uv run --directory ${CLAUDE_PLUGIN_ROOT}/server server.py`.

The division is deliberate: the skill is the catalog and policy, `server.py` is the transport. Behavior changes (e.g. "always confirm before PRD writes") usually belong in SKILL.md; new endpoints or HTTP handling belong in server.py.

## Running the MCP Inspector

```powershell
cd plugins\xurrent\server
$env:XURRENT_ACCOUNT="provincieantwerpen"
$env:XURRENT_QA_TOKEN="your_qa_token"
uv run mcp dev server.py
```

`uv` reads dependencies from `plugins/xurrent/server/pyproject.toml`. There is no build or test suite — verification is manual via the Inspector. `--system-certs` is set by default in `uv.toml` at the repo root (required on the work network — uv's bundled TLS roots don't include the corporate CA; `server.py` also calls `truststore.inject_into_ssl()` for the same reason).

## server.py conventions (read before editing)

- **Every tool defaults to `environment="QA"`** so an accidental call can't hit production. PRD requires explicitly passing `environment="PRD"`.
- **`account` falls back to `XURRENT_ACCOUNT`** via `_acct()`. The same org can have several sub-accounts (`provincieantwerpen`, `-dict`, `-dmco-sp`).
- **Two HTTP read paths:** `_get_all()` auto-paginates by following `Link: rel="next"` headers; `_get_page()` fetches one page. List tools use `_get_all`; `xurrent_get(paginate=False)` uses `_get_page`. When following a next-URL, params **must** be reset to `None`, not `{}` — an empty dict makes httpx overwrite the URL's query string and loop on page 1 forever (see comment at the pagination loop).
- **`_request_with_retry()`** retries 429 (honoring `Retry-After`) and transient 403s (heavy-load quirk at Provincie Antwerpen). For multipart uploads it pops `Content-Type` so httpx sets the boundary.
- **Typed tools vs generic tools:** prefer adding/using a typed tool (`get_request`, `list_people`, …) for better docs/defaults. The generic `xurrent_get/post/patch/delete` exist for any endpoint without a wrapper (teams, sites, services, CIs).
- **Notes have no POST endpoint** — `add_note` PATCHes the request's `note`/`internal_note` field. Custom fields are written by PATCHing a `custom_fields` array with only the target entry.
- **`whoami`** exists because the API token is a *system account*, so predefined `assigned_to_me`-style filters resolve to the token, not the human. It resolves `XURRENT_ME_EMAIL` to a person record (cached per env/account/email); use the returned `id` with `filter_params="member={id}"`.

## When adding or renaming a tool

Keep these in sync — they are hand-maintained mirrors of the tool set:
- the `@mcp.tool()` function in `plugins/xurrent/server/server.py`
- the **Available tools** section of `SKILL.md`
- the **Tools** table in `plugins/xurrent/server/README.md` (and the tool list in the root `README.md`)

## Dependency pin

`mcp[cli]>=1.27,<2`. The 2.x line is alpha with breaking changes. Uses `mcp.server.fastmcp` from the official `mcp` SDK — **not** the separate `fastmcp` PyPI package.
