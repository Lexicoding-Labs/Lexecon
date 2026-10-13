"""Fail-closed model transport for the isolated Solar Mini4 audit process.

This is an application request boundary, not an OS sandbox or a billing guarantee.
The only real network operation performed by construction is NONE: catalog reads
and inference happen only when handle_request is invoked by the owner-run audit.
"""

import http.client
import json
import threading
import time
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from typing import NoReturn

import httpx

MODEL = "upstage/solar-mini4:free"
HOST = "inference-api.nousresearch.com"
BASE_URL = "https://" + HOST + "/v1"
CHAT_URL = BASE_URL + "/chat/completions"
CATALOG_URL = BASE_URL + "/models"
TOOLS = {"lexecon_list_files", "lexecon_read_file"}
MAX_BODY = 4 * 1024 * 1024
MAX_CATALOG = 2 * 1024 * 1024
BODY_KEYS = {
    "model", "messages", "tools", "tool_choice", "parallel_tool_calls", "stream", "stream_options",
    "max_tokens", "max_completion_tokens", "temperature", "top_p", "frequency_penalty", "presence_penalty",
    "reasoning", "reasoning_effort", "stop", "seed", "response_format", "tags", "session_id",
}


class FreeRouteDenied(BaseException):
    """Terminal refusal, intentionally outside SDK/Hermes Exception retry ladders."""


def strict_json(data):
    """Decode JSON while rejecting duplicate keys and nonfinite numbers."""
    def pairs(items) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def invalid_number(_value) -> NoReturn:
        raise ValueError("Nonfinite JSON number")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_number)


def fetch_catalog():
    """Anonymous, TLS-verified, bounded GET; no proxy, auth, redirects or retries."""
    # Use the pinned Hermes public-model client's own identity. Its catalog
    # requests set this header because the provider rejects unidentified Python
    # clients; keep our stricter transport so redirects and oversized bodies
    # still fail closed before any model send.
    from hermes_cli.models import _HERMES_USER_AGENT

    connection = http.client.HTTPSConnection(HOST, timeout=10)
    try:
        connection.request("GET", "/v1/models", headers={
            "Accept": "application/json", "User-Agent": _HERMES_USER_AGENT,
        })
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Catalog unavailable")
        data = response.read(MAX_CATALOG + 1)
        if len(data) > MAX_CATALOG:
            raise ValueError("Catalog too large")
        return strict_json(data)
    finally:
        connection.close()


def require_zero_price(catalog):
    """Every published price must be finite zero; absent/ambiguous SKU is refused."""
    rows = catalog.get("data") if isinstance(catalog, dict) else None
    if not isinstance(rows, list):
        raise TypeError("Invalid catalog")
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == MODEL]
    if len(matches) != 1:
        raise ValueError("Free SKU absent or ambiguous")
    pricing = matches[0].get("pricing")
    if not isinstance(pricing, dict) or not {"prompt", "completion"} <= pricing.keys():
        raise ValueError("Missing prices")
    for value in pricing.values():
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise TypeError("Unknown price")
        try:
            price = Decimal(str(value))
        except InvalidOperation:
            raise ValueError("Unknown price") from None
        if not price.is_finite() or price != 0:
            raise ValueError("Nonzero or unknown price")


class FreeRouteTransport(httpx.BaseTransport):
    """All model sends, including retries and rebuilds, share this run budget."""

    def __init__(self, *, transport=None, catalog_reader=fetch_catalog, max_requests=32,
                 max_tokens=4096, seconds=600, clock=time.monotonic):
        """Create a bounded transport with a fresh catalog reader per request."""
        if (type(max_requests) is not int or not 1 <= max_requests <= 64
                or type(max_tokens) is not int or not 1 <= max_tokens <= 4096
                or type(seconds) is not int or not 1 <= seconds <= 600):
            raise ValueError("Invalid audit bounds")
        self.inner = transport if transport is not None else httpx.HTTPTransport(retries=0)
        self.catalog_reader = catalog_reader
        self.max_requests, self.max_tokens = max_requests, max_tokens
        self.clock, self.deadline = clock, clock() + seconds
        self.sends = 0
        self.preflights = 0
        self.denial = None
        self.lock = threading.RLock()

    def deny(self, reason):
        """Latch a sanitized denial across all clients sharing this transport."""
        # Never include request bodies, URLs, headers, provider errors or credentials.
        self.denial = self.denial or reason
        raise FreeRouteDenied(self.denial)

    def validate(self, request):
        """Refuse requests outside the approved route, body and run budget."""
        if self.denial:
            self.deny(self.denial)
        if self.clock() >= self.deadline or self.sends >= self.max_requests:
            self.deny("Audit request/time bound reached")
        if (request.method != "POST" or str(request.url) != CHAT_URL
                or request.headers.get("host") != HOST
                or request.headers.get("content-encoding") is not None):
            self.deny("Model destination or encoding refused")
        try:
            _require_approved_body(request, self.max_tokens)
        except (ValueError, TypeError, AttributeError, httpx.RequestNotRead):
            self.deny("Model body or tool set refused")

    def handle_request(self, request):
        """Preflight the current price before a single approved inference send."""
        with self.lock:
            self.validate(request)
            try:
                self.preflights += 1
                require_zero_price(self.catalog_reader())
            except Exception:
                self.deny("Fresh zero-price preflight failed")
            # A slow catalog call cannot extend the run budget.
            self.validate(request)
            self.sends += 1
            try:
                response = self.inner.handle_request(request)
            except Exception:
                self.deny("Inference transport failed; no retry or fallback")
            if response.status_code != 200:
                response.close()
                self.deny("Inference refused or redirected; no retry or fallback")
            return response

    def close(self):
        """Leave the shared transport open until the owner finishes the run."""

    def finish(self):
        """Close the underlying transport after the audit ends."""
        self.inner.close()


def _require_approved_body(request: httpx.Request, max_tokens: int) -> None:
    raw = request.content
    if len(raw) > MAX_BODY:
        raise ValueError
    body = strict_json(raw)
    if not isinstance(body, dict) or body.get("model") != MODEL or set(body) - BODY_KEYS:
        raise ValueError
    tags = body.get("tags")
    if tags is not None and (
        not isinstance(tags, list) or not 2 <= len(tags) <= 3
        or any(not isinstance(tag, str) or len(tag) > 160 for tag in tags)
        or tags[0] != "product=hermes-agent" or not tags[1].startswith("client=hermes-client-v")
        or (len(tags) == 3 and not tags[2].startswith("conversation="))
    ):
        raise ValueError
    session_id = body.get("session_id")
    if session_id is not None and (
        not isinstance(session_id, str) or not 1 <= len(session_id) <= 160
    ):
        raise ValueError
    bounds = [body[key] for key in ("max_tokens", "max_completion_tokens") if key in body]
    if len(bounds) != 1 or type(bounds[0]) is not int or not 1 <= bounds[0] <= max_tokens:
        raise ValueError
    if not isinstance(body.get("messages"), list) or not body["messages"]:
        raise ValueError
    for tool in body.get("tools", []):
        if tool.get("type") != "function" or tool.get("function", {}).get("name") not in TOOLS:
            raise ValueError


@contextmanager
def restrict_model_clients(route, auxiliary):
    """Fresh-process scope: only this transport may use HTTPX; auxiliary calls stop.

    SDK clients use HTTPX. Lexecon's fixed-loopback http.client and the anonymous
    catalog fetch remain separate. This does not constrain arbitrary Python sockets.
    """
    original_send, original_async = httpx.Client.send, httpx.AsyncClient.send
    names = ("call_llm", "async_call_llm", "resolve_provider_client", "get_async_text_auxiliary_client")
    originals = {name: getattr(auxiliary, name) for name in names}

    def denied_aux(*_args: object, **_kwargs: object) -> NoReturn:
        route.deny("Auxiliary model calls disabled for this audit")

    def send(client, request, **kwargs: object) -> httpx.Response:
        # Hermes reads model metadata during initialization. Serve only the exact
        # public catalog through our anonymous reader, never its supplied auth.
        if (request.method == "GET" and str(request.url) == CATALOG_URL
                and request.headers.get("host") == HOST and request.content == b""):
            try:
                catalog = route.catalog_reader()
                require_zero_price(catalog)
            except Exception:
                route.deny("Public model metadata unavailable or not free")
            return httpx.Response(200, json=catalog, request=request)
        if client._transport is not route or any(client._mounts.values()):
            route.deny("Unapproved model client refused")
        # Override both client defaults and per-call preferences before HTTPX sends.
        kwargs["follow_redirects"] = False
        return original_send(client, request, **kwargs)

    async def async_send(_client, _request, **_kwargs: object) -> NoReturn:
        route.deny("Async/auxiliary model clients disabled for this audit")

    httpx.Client.send, httpx.AsyncClient.send = send, async_send
    for name in names:
        setattr(auxiliary, name, denied_aux)
    try:
        yield
    finally:
        httpx.Client.send, httpx.AsyncClient.send = original_send, original_async
        for name, original in originals.items():
            setattr(auxiliary, name, original)
