---
name: xurrent-api
description: Read and write records in Xurrent (formerly 4me), the IT service management platform used at Provincie Antwerpen — requests, people, organizations, problems, custom fields, notes, attachments, rate limit status, and CSV import/export. Use this skill whenever the user asks to look up, list, filter, create, update, or delete Xurrent/4me records, check the API rate limit, add a note or attachment to a request, or import/export data via the Xurrent API, whether on the QA or production environment. Trigger this even if the user just says something like "check those open requests in 4me" or "patch the custom field on this Xurrent ticket" without explicitly naming the API.
---

# Xurrent API

Xurrent (formerly known as 4me) is a REST API-based IT service management platform. This skill is backed by the `xurrent` MCP server (bundled with this plugin, `server/server.py`), which exposes typed tools for reading and writing Xurrent records and handles pagination, retries, and rate limiting automatically. Call those tools directly — this document is the source of truth for *what* to call and *when*, while the tools handle *how*.

## Authentication and configuration

The MCP server reads its credentials from environment variables set in the server's launch config — there is nothing to import or set up per call:

- `XURRENT_QA_TOKEN` — used when `environment="QA"`
- `XURRENT_PRD_TOKEN` (or the legacy alias `XURRENT_API_TOKEN`) — used when `environment="PRD"`
- `XURRENT_ACCOUNT` — the default account, used whenever a tool's `account` argument is omitted

The server refuses to start unless `XURRENT_ACCOUNT` and at least one token are set. If a tool returns **HTTP 401**, the relevant token has expired or been revoked — the user needs a fresh one from their Xurrent administrator. Tokens are credentials: never ask the user to paste one into chat, and never write one into a file.

## Choosing an environment and account

Every tool takes:
- `environment` — `"QA"` or `"PRD"`. Defaults to `"QA"` so an accidental call doesn't hit production. Confirm with the user which they mean if it's not obvious from context ("the live system" / "production" → PRD; "testing" / "QA" → QA).
- `account` — the Xurrent account name to act against, e.g. `provincieantwerpen-dict`, `provincieantwerpen`, `provincieantwerpen-dmco-sp`. Omit it to use `XURRENT_ACCOUNT`. Ask the user which account if they haven't said and the default isn't clearly right — one organization can have several sub-accounts.

## Available tools

**Requests**
- `get_request(request_id)` — fetch one request by numeric ID
- `list_requests(predefined_filter?, filter_params?)` — `predefined_filter` is one of `open`, `completed`, `assigned_to_me`, `assigned_to_my_team`, `waiting_for_me`; `filter_params` is a raw query string like `"team=42&service_instance=111741"`
- `create_request(subject, description?, extra_fields?)` — `extra_fields` is a JSON object string for anything beyond subject/description
- `update_request(request_id, fields)` — `fields` is a JSON object string, e.g. `'{"status":"solved","note":"Fixed by reboot"}'`

**Notes** — `add_note(request_id, text, internal=True)`. `internal=False` makes the note visible to the requester.

**Custom fields**
- `get_custom_field_value(request_id, field_id)` — read one field's value (returns `null` if unset)
- `update_custom_field(request_id, field_id, value)` — set one field; other custom fields are left untouched

**People** — `get_person(person_id)`, `list_people(predefined_filter?, filter_params?)` (filters: `disabled`, `enabled`, `internal`, `directory`, `support_domain`).

**Organizations** — `get_organization(org_id)`, `list_organizations(predefined_filter?, filter_params?)` (filters: `disabled`, `enabled`, `external`, `internal`, `trusted`, `directory`, `support_domain`, `managed_by_me`).

**Problems** — `get_problem(problem_id)`, `list_problems(predefined_filter?, filter_params?)` (filters: `active`, `known_errors`, `solved`, `managed_by_me`, `assigned_to_my_team`, `assigned_to_me`).

**Rate limit** — `get_rate_limit_status()` returns `limit`, `remaining`, and `reset`; check it before any bulk operation.

**Attachments** — two-step flow:
1. `get_attachment_storage()` → returns a presigned `upload_uri` and a `key`. Upload the file with an HTTP PUT to `upload_uri` yourself (e.g. via Bash/`curl`).
2. `add_attachment_to_request(request_id, storage_key, filename, size, content_type?)` — links the uploaded `key` to the request.

**CSV import/export**
- `import_csv(resource_type, csv_content)` — starts an import job and polls until done; strips a leading BOM automatically
- `export_csv(resource_type, filter_params?)` — starts an export and returns the raw CSV/XLSX text; `filter_params` supports `from`, `export_format` (`csv`/`xlsx`), and `line_separator` (`lf`/`crlf`)

For exact field names, filter syntax, and resource types not covered here, see the [Xurrent API reference](https://developer.xurrent.com/v1/) — the tools are a transport layer, not a catalog of every object and field.

## Working with the user's request

1. **Identify the record type and operation.** "Show me open requests assigned to my team" → `list_requests(predefined_filter="assigned_to_my_team")` (or `"open"` plus a team filter); "close request 12345" → `update_request(12345, '{"status":"solved"}')`.
2. **Confirm environment and account** if ambiguous — see above.
3. **For mutating operations** (`create_request`, `update_request`, `add_note`, `update_custom_field`, `add_attachment_to_request`, `import_csv`), state exactly what will change before running it, especially on PRD. There is no preview/dry-run flag — the call commits, so confirm first when it matters. Note this server exposes **no delete tool**; permanent deletion must be done elsewhere.
4. **For bulk reads or anything that might burn through the rate limit**, check `get_rate_limit_status()` first.
5. **Reference the [Xurrent API documentation](https://developer.xurrent.com/v1/)** for endpoint paths, filter syntax, and field names you're unsure about.
