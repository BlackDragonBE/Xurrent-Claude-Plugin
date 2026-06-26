"""Xurrent MCP server — local stdio transport for Claude Code."""

import asyncio
import json
import os
import sys
from typing import Any, Literal, Optional

import httpx
import truststore
from mcp.server.fastmcp import FastMCP

# Use the Windows/OS certificate store so corporate CAs are trusted.
truststore.inject_into_ssl()

mcp: FastMCP = FastMCP("xurrent")

Environment = Literal["QA", "PRD"]
RequestFilter = Literal["open", "completed", "assigned_to_me", "assigned_to_my_team", "waiting_for_me"]
PeopleFilter = Literal["disabled", "enabled", "internal", "directory", "support_domain"]
OrgFilter = Literal["disabled", "enabled", "external", "internal", "trusted", "directory", "support_domain", "managed_by_me"]
ProblemFilter = Literal["active", "known_errors", "solved", "managed_by_me", "assigned_to_my_team", "assigned_to_me"]

# PRD token: XURRENT_PRD_TOKEN, with XURRENT_API_TOKEN as a backward-compat alias.
_PRD_TOKEN: str = os.environ.get("XURRENT_PRD_TOKEN") or os.environ.get("XURRENT_API_TOKEN", "")
_QA_TOKEN: str = os.environ.get("XURRENT_QA_TOKEN", "")
_DEFAULT_ACCOUNT: str = os.environ.get("XURRENT_ACCOUNT", "")

if not _DEFAULT_ACCOUNT:
    print("Missing required environment variable: XURRENT_ACCOUNT", file=sys.stderr)
    sys.exit(1)
if not _PRD_TOKEN and not _QA_TOKEN:
    print(
        "At least one of XURRENT_PRD_TOKEN or XURRENT_QA_TOKEN must be set.",
        file=sys.stderr,
    )
    sys.exit(1)

_PRD_BASE_URL: str = os.environ.get("XURRENT_PRD_BASE_URL", "https://api.xurrent.com/v1")
# QA URL is derived by replacing .com with .qa in the PRD URL (e.g. api.xurrent.com → api.xurrent.qa).
_QA_BASE_URL: str = _PRD_BASE_URL.replace(".com/", ".qa/")


def _env_config(environment: Environment) -> tuple[str, str]:
    """Return (token, base_url) for the requested environment, or raise."""
    if environment == "PRD":
        if not _PRD_TOKEN:
            raise RuntimeError("XURRENT_PRD_TOKEN (or XURRENT_API_TOKEN) is not set.")
        return _PRD_TOKEN, _PRD_BASE_URL
    if not _QA_TOKEN:
        raise RuntimeError("XURRENT_QA_TOKEN is not set.")
    return _QA_TOKEN, _QA_BASE_URL


def _headers(token: str, account: str) -> dict[str, str]:
    """Standard auth headers for every Xurrent request."""
    return {
        "Authorization": f"Bearer {token}",
        "X-4me-Account": account,
        "Content-Type": "application/json",
    }


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    token: str,
    account: str,
    max_retries: int = 3,
    **kwargs: Any,
) -> httpx.Response:
    """HTTP request with retry/backoff for 429 (rate limit) and transient 403."""
    for attempt in range(max_retries):
        headers = _headers(token, account)
        # multipart uploads: let httpx set Content-Type (with boundary)
        if "files" in kwargs:
            headers.pop("Content-Type", None)
        resp = await client.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 429:
            # Respect Retry-After if present, otherwise exponential backoff
            retry_after = int(resp.headers.get("Retry-After", 2**attempt))
            print(f"Rate limited; retrying in {retry_after}s", file=sys.stderr)
            await asyncio.sleep(retry_after)
            continue
        if resp.status_code == 403 and attempt < max_retries - 1:
            # 403 can be transient under heavy load at Provincie Antwerpen
            await asyncio.sleep(2**attempt)
            continue
        if not resp.is_success:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
        return resp
    raise RuntimeError(f"Exhausted {max_retries} retries for {method} {url}")


async def _get_all(
    endpoint: str,
    token: str,
    base_url: str,
    account: str,
    params: Optional[dict[str, Any]] = None,
) -> Any:
    """GET an endpoint and auto-paginate via Link headers when the result is a list."""
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{base_url}/{endpoint.lstrip('/')}"
        page_params: dict[str, Any] = dict(params or {})
        page_params.setdefault("per_page", 100)
        results: list[Any] = []

        while url:
            resp = await _request_with_retry(client, "GET", url, token, account, params=page_params)
            data = resp.json()
            if not isinstance(data, list):
                return data  # single-resource endpoint
            results.extend(data)
            total = resp.headers.get("x-pagination-total-entries")
            page = resp.headers.get("x-pagination-current-page")
            pages = resp.headers.get("x-pagination-total-pages")
            print(f"[xurrent] {endpoint} page {page}/{pages}, {len(results)}/{total} records", file=sys.stderr)
            # Follow Link: <url>; rel="next" — the API controls the next URL
            next_url: Optional[str] = None
            for part in resp.headers.get("Link", "").split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    break
            url = next_url  # type: ignore[assignment]
            # next URL already encodes all params; must be None (not {}) — an
            # empty dict makes httpx overwrite the URL's query string, dropping
            # the cursor and looping on page 1 forever.
            page_params = None  # type: ignore[assignment]

        return results


async def _get_page(
    endpoint: str,
    token: str,
    base_url: str,
    account: str,
    params: Optional[dict[str, Any]] = None,
) -> Any:
    """GET a single page — used by list tools to avoid runaway pagination."""
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{base_url}/{endpoint.lstrip('/')}"
        resp = await _request_with_retry(client, "GET", url, token, account, params=params)
        return resp.json()


async def _post(endpoint: str, token: str, base_url: str, account: str, body: dict[str, Any]) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{base_url}/{endpoint.lstrip('/')}"
        resp = await _request_with_retry(client, "POST", url, token, account, json=body)
        return resp.json()


async def _patch(endpoint: str, token: str, base_url: str, account: str, body: dict[str, Any]) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{base_url}/{endpoint.lstrip('/')}"
        resp = await _request_with_retry(client, "PATCH", url, token, account, json=body)
        return resp.json()


def _parse_filter(filter_params: Optional[str]) -> dict[str, Any]:
    """Parse a URL query string into a dict of params."""
    params: dict[str, Any] = {}
    if filter_params:
        for pair in filter_params.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k.strip()] = v.strip()
    return params


def _acct(account: Optional[str]) -> str:
    """Resolve the account to use, falling back to XURRENT_ACCOUNT."""
    return account or _DEFAULT_ACCOUNT


def _list_endpoint(resource: str, predefined_filter: Optional[str]) -> str:
    """Build the list endpoint, optionally with a predefined filter path segment."""
    return f"{resource}/{predefined_filter}" if predefined_filter else resource


# ---------------------------------------------------------------------------
# Requests — skill: Get-XurrentData, Set-XurrentDataPatch, New-XurrentData
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_request(
    request_id: int,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Fetch a single Xurrent request by its numeric ID.

    Args:
        request_id: Numeric ID of the request.
        environment: "QA" (default, safe) or "PRD" for production.
        account: Xurrent account name (e.g. "provincieantwerpen-dict"). Defaults to XURRENT_ACCOUNT.

    Returns the full request record as a JSON string.
    """
    token, base_url = _env_config(environment)
    data = await _get_all(f"requests/{request_id}", token, base_url, _acct(account))
    return json.dumps(data, indent=2)


@mcp.tool()
async def list_requests(
    predefined_filter: Optional[RequestFilter] = None,
    filter_params: Optional[str] = None,
    page_size: int = 100,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """List Xurrent requests using predefined filters and/or query parameters.

    Args:
        predefined_filter: One of the API's predefined filter paths:
            "open", "completed", "assigned_to_me", "assigned_to_my_team", "waiting_for_me".
            Maps to GET /requests/{predefined_filter}. Omit to query all requests.
        filter_params: URL query string of additional filter parameters, e.g.
            "team_id=42&service_instance_id=111741". Reference fields filter by
            numeric id with an _id suffix.
            See https://developer.xurrent.com/v1/requests/ for all supported fields.
        page_size: Number of records per page (max 100). Defaults to 100.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns a JSON array of request records.
    """
    token, base_url = _env_config(environment)
    params = _parse_filter(filter_params)
    params["per_page"] = min(page_size, 100)
    endpoint = _list_endpoint("requests", predefined_filter)
    data = await _get_all(endpoint, token, base_url, _acct(account), params)
    return json.dumps(data, indent=2)


@mcp.tool()
async def create_request(
    subject: str,
    description: Optional[str] = None,
    extra_fields: Optional[str] = None,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Create a new Xurrent request.

    Args:
        subject: Short summary of the request (required, max 255 chars).
        description: Longer description or body text (sent as the initial note).
        extra_fields: Additional fields as a JSON object string, e.g.
            '{"category": "incident", "impact": "medium", "team_id": 42}'.
            To set a reference to another record, append _id to the field name and
            pass its numeric id (e.g. team_id, member_id, service_instance_id); use
            _ids for collections. See https://developer.xurrent.com/v1/requests/ for
            all accepted fields.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns the created request record as a JSON string.
    """
    token, base_url = _env_config(environment)
    body: dict[str, Any] = {"subject": subject}
    if description:
        body["note"] = description
    if extra_fields:
        body.update(json.loads(extra_fields))
    data = await _post("requests", token, base_url, _acct(account), body)
    return json.dumps(data, indent=2)


@mcp.tool()
async def update_request(
    request_id: int,
    fields: str,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Update fields on an existing Xurrent request (HTTP PATCH).

    Args:
        request_id: Numeric ID of the request to update.
        fields: JSON object string of fields to patch, e.g.
            '{"status": "completed", "completion_reason": "solved", "note": "Fixed by reboot"}'.
            status is one of: declined, on_backlog, assigned, accepted, in_progress,
            waiting_for, waiting_for_customer, completed (and the *_pending states).
            See https://developer.xurrent.com/v1/requests/ for all writable fields.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns the updated request record as a JSON string.
    """
    token, base_url = _env_config(environment)
    data = await _patch(f"requests/{request_id}", token, base_url, _acct(account), json.loads(fields))
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Notes — skill: Add-XurrentNoteToRequest
# ---------------------------------------------------------------------------


@mcp.tool()
async def add_note(
    request_id: int,
    text: str,
    internal: bool = True,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Add a note to a Xurrent request.

    The v1 API has no POST endpoint for notes; a note is written by patching the
    request's `note` (public) or `internal_note` field.

    Args:
        request_id: Numeric ID of the request.
        text: Note body text (max 64KB).
        internal: True (default) writes to `internal_note` — visible only to people
            with the Auditor, Specialist or Account Administrator role;
            False writes to `note`, which is also visible to the requester.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns the updated request record as a JSON string.
    """
    token, base_url = _env_config(environment)
    field = "internal_note" if internal else "note"
    data = await _patch(
        f"requests/{request_id}", token, base_url, _acct(account), {field: text},
    )
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Custom fields — skill: Get-XurrentCustomFieldValue, Set-XurrentDataPatch
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_custom_field(
    request_id: int,
    field_id: str,
    value: str,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Set a single custom field on a Xurrent request.

    Args:
        request_id: Numeric ID of the request.
        field_id: The custom field identifier (e.g. "custom_field_1").
        value: New value for the field.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns the updated request record as a JSON string.
    """
    token, base_url = _env_config(environment)
    # Xurrent custom fields are patched by posting the full custom_fields array
    # with just the target entry; existing fields not listed are left unchanged.
    body = {"custom_fields": [{"id": field_id, "value": value}]}
    data = await _patch(f"requests/{request_id}", token, base_url, _acct(account), body)
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_custom_field_value(
    request_id: int,
    field_id: str,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Read the value of a single custom field from a Xurrent request.

    Args:
        request_id: Numeric ID of the request.
        field_id: The custom field identifier (e.g. "custom_field_1").
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns the field value as a JSON string, or "null" if not set.
    """
    token, base_url = _env_config(environment)
    data = await _get_all(f"requests/{request_id}", token, base_url, _acct(account))
    for cf in data.get("custom_fields", []):
        if cf.get("id") == field_id:
            return json.dumps(cf.get("value"))
    return "null"


# ---------------------------------------------------------------------------
# People — skill: Get-XurrentData on /people
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_person(
    person_id: int,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Fetch a single Xurrent person record by numeric ID.

    Args:
        person_id: Numeric ID of the person.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.
    """
    token, base_url = _env_config(environment)
    data = await _get_all(f"people/{person_id}", token, base_url, _acct(account))
    return json.dumps(data, indent=2)


@mcp.tool()
async def list_people(
    predefined_filter: Optional[PeopleFilter] = None,
    filter_params: Optional[str] = None,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """List Xurrent people using predefined filters and/or query parameters.

    Args:
        predefined_filter: One of: "disabled", "enabled", "internal", "directory",
            "support_domain". Maps to GET /people/{predefined_filter}.
        filter_params: URL query string, e.g. "primary_email=jane@example.com&organization_id=5".
            See https://developer.xurrent.com/v1/people/ for supported fields.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.
    """
    token, base_url = _env_config(environment)
    endpoint = _list_endpoint("people", predefined_filter)
    data = await _get_all(endpoint, token, base_url, _acct(account), _parse_filter(filter_params))
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Organizations — skill: Get-XurrentData on /organizations
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_organization(
    org_id: int,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Fetch a single Xurrent organization record by numeric ID.

    Args:
        org_id: Numeric ID of the organization.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.
    """
    token, base_url = _env_config(environment)
    data = await _get_all(f"organizations/{org_id}", token, base_url, _acct(account))
    return json.dumps(data, indent=2)


@mcp.tool()
async def list_organizations(
    predefined_filter: Optional[OrgFilter] = None,
    filter_params: Optional[str] = None,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """List Xurrent organizations using predefined filters and/or query parameters.

    Args:
        predefined_filter: One of: "disabled", "enabled", "external", "internal",
            "trusted", "directory", "support_domain", "managed_by_me".
            Maps to GET /organizations/{predefined_filter}.
        filter_params: URL query string, e.g. "parent_id=123&name=Antwerpen".
            See https://developer.xurrent.com/v1/organizations/ for supported fields.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.
    """
    token, base_url = _env_config(environment)
    endpoint = _list_endpoint("organizations", predefined_filter)
    data = await _get_all(endpoint, token, base_url, _acct(account), _parse_filter(filter_params))
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Problems — skill: Get-XurrentData on /problems
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_problem(
    problem_id: int,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Fetch a single Xurrent problem record by numeric ID.

    Args:
        problem_id: Numeric ID of the problem.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.
    """
    token, base_url = _env_config(environment)
    data = await _get_all(f"problems/{problem_id}", token, base_url, _acct(account))
    return json.dumps(data, indent=2)


@mcp.tool()
async def list_problems(
    predefined_filter: Optional[ProblemFilter] = None,
    filter_params: Optional[str] = None,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """List Xurrent problems using predefined filters and/or query parameters.

    Args:
        predefined_filter: One of: "active", "known_errors", "solved",
            "managed_by_me", "assigned_to_my_team", "assigned_to_me".
            Maps to GET /problems/{predefined_filter}.
        filter_params: URL query string, e.g. "service_id=456&impact=high".
            See https://developer.xurrent.com/v1/problems/ for supported fields.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.
    """
    token, base_url = _env_config(environment)
    endpoint = _list_endpoint("problems", predefined_filter)
    data = await _get_all(endpoint, token, base_url, _acct(account), _parse_filter(filter_params))
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Rate limit — skill: Get-XurrentRateLimitStatus
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_rate_limit_status(
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Return the current Xurrent API rate-limit status.

    Reads the x-ratelimit-* headers from a lightweight GET on /me and returns
    a JSON object with 'limit', 'remaining', and 'reset' (Unix timestamp).

    Args:
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.
    """
    token, base_url = _env_config(environment)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await _request_with_retry(client, "GET", f"{base_url}/me", token, _acct(account))
    return json.dumps({
        "environment": environment,
        "account": _acct(account),
        "limit": resp.headers.get("x-ratelimit-limit"),
        "remaining": resp.headers.get("x-ratelimit-remaining"),
        "reset": resp.headers.get("x-ratelimit-reset"),
    }, indent=2)


# ---------------------------------------------------------------------------
# Attachments — skill: Get-XurrentAttachmentStorage / Add-XurrentAttachmentToRequest
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_attachment_storage(
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Request a presigned S3 upload location for attaching a file to a request.

    Returns a JSON object with 'upload_uri', 'key', and any other fields the
    Xurrent API returns. Use the upload_uri to PUT the file directly to S3,
    then pass the returned 'key' to add_attachment_to_request.

    Args:
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.
    """
    token, base_url = _env_config(environment)
    data = await _get_page("attachments/storage", token, base_url, _acct(account))
    return json.dumps(data, indent=2)


@mcp.tool()
async def add_attachment_to_request(
    request_id: int,
    storage_key: str,
    size: int,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Link an already-uploaded file to a Xurrent request as a note attachment.

    Call get_attachment_storage first, upload the file to the returned location,
    then pass the resulting key here. The API accepts only `key` and `filesize`
    per attachment (the original filename and content type come from the upload).

    Args:
        request_id: Numeric ID of the request.
        storage_key: The storage key returned by get_attachment_storage (the
            <Key> value from the upload response).
        size: File size in bytes.
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns the updated request record as a JSON string.
    """
    token, base_url = _env_config(environment)
    body = {"note_attachments": [{"key": storage_key, "filesize": str(size)}]}
    data = await _patch(f"requests/{request_id}", token, base_url, _acct(account), body)
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# CSV import/export — skill: Import-XurrentCsv / Export-XurrentCsv
# ---------------------------------------------------------------------------


@mcp.tool()
async def import_csv(
    resource_type: str,
    csv_content: str,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Start a Xurrent CSV import job and poll until it completes.

    Args:
        resource_type: The Xurrent resource type, e.g. "people", "organizations", "cis".
            See https://developer.xurrent.com/v1/import/ for accepted types.
        csv_content: Full CSV text (UTF-8, with header row).
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns a JSON object with the final import job status and any error details.
    """
    token, base_url = _env_config(environment)
    acct = _acct(account)
    # Strip BOM if present (Excel habit)
    csv_content = csv_content.lstrip("﻿")

    async with httpx.AsyncClient(timeout=60) as client:
        # POST multipart: file field + type field; omit Content-Type so httpx sets the boundary.
        files = {"file": (f"{resource_type}.csv", csv_content.encode("utf-8"), "text/csv")}
        data = {"type": resource_type}
        resp = await _request_with_retry(
            client, "POST", f"{base_url}/import", token, acct,
            files=files, data=data,
        )
        token_val: str = resp.json()["token"]

    # Poll GET /import/{token} until terminal state
    poll_url = f"{base_url}/import/{token_val}"
    job: dict[str, Any] = {}
    for _ in range(60):  # up to ~5 min
        await asyncio.sleep(5)
        async with httpx.AsyncClient(timeout=30) as client:
            poll_resp = await _request_with_retry(client, "GET", poll_url, token, acct)
        job = poll_resp.json()
        if job.get("state") in ("done", "error"):
            break

    return json.dumps(job, indent=2)


@mcp.tool()
async def export_csv(
    resource_type: str,
    filter_params: Optional[str] = None,
    environment: Environment = "QA",
    account: Optional[str] = None,
) -> str:
    """Start a Xurrent CSV export job and return the resulting CSV text.

    Args:
        resource_type: Comma-separated resource type(s) to export, e.g. "requests" or "people,organizations".
            See https://developer.xurrent.com/v1/export/ for accepted types.
        filter_params: Optional extra parameters as a query string, e.g.
            "from=2024-01-01&export_format=xlsx&line_separator=crlf".
            Supported: "from" (date, limits to records updated since), "export_format" (csv/xlsx),
            "line_separator" (lf/crlf).
        environment: "QA" (default) or "PRD".
        account: Xurrent account name. Defaults to XURRENT_ACCOUNT.

    Returns the raw CSV text, or a JSON error object if the export failed.
    """
    token, base_url = _env_config(environment)
    acct = _acct(account)
    body: dict[str, Any] = {"type": resource_type}
    body.update(_parse_filter(filter_params))

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await _request_with_retry(client, "POST", f"{base_url}/export", token, acct, json=body)
        token_val: str = resp.json()["token"]

    # Poll GET /export/{token} until terminal state
    poll_url = f"{base_url}/export/{token_val}"
    download_url: Optional[str] = None
    job: dict[str, Any] = {}
    for _ in range(60):
        await asyncio.sleep(5)
        async with httpx.AsyncClient(timeout=30) as client:
            poll_resp = await _request_with_retry(client, "GET", poll_url, token, acct)
        job = poll_resp.json()
        if job.get("state") in ("done", "failed"):
            download_url = job.get("url")
            break

    if not download_url:
        return json.dumps({"error": "Export did not complete", "job": job})

    async with httpx.AsyncClient(timeout=60) as client:
        dl_resp = await client.get(download_url)
        dl_resp.raise_for_status()
    return dl_resp.text


if __name__ == "__main__":
    # Default transport is stdio — exactly what Claude Code launches.
    mcp.run()
