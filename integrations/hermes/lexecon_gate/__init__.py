"""Bounded local Hermes tools. This plugin is not an OS sandbox."""

import json
from pathlib import Path

from .runtime import TOOLS, GateConfig, GateRuntime

__all__ = ["GateConfig", "GateRuntime", "register", "runtime_for_context"]


def runtime_for_context(ctx):
    """Resolve the calling Hermes profile without caching settings across calls."""
    # Resolve profile-scoped settings per call, never at module import or registration.
    return GateRuntime(GateConfig(
        workspace_root=Path(ctx.get_config("workspace_root", "")),
        username=ctx.get_config("username", ""),
        session_file=Path(ctx.get_config("session_file", "")),
        audit_file=Path(ctx.get_config("audit_file", "")),
        api_port=ctx.get_config("api_port", 8000),
    ))


def pre_tool_call(tool_name, args=None, **kwargs):
    """Reject unmapped tools; mapped tools still authorize inside their handlers."""
    if tool_name not in TOOLS:
        return {"action": "block", "message": "Lexecon: tool is outside the configured workspace toolset."}
    return None  # Authorization happens again inside the actual tool handler.


def _handler_for(ctx, name):
    def handler(args, **kwargs):
        try:
            result = runtime_for_context(ctx).execute(name, args)
        except Exception:
            result = {"ok": False, "error": "gate_configuration_unavailable"}
        return json.dumps(result)
    return handler


def register(ctx):
    """Register bounded tools and the host's default-deny pre-dispatch hook."""
    def hook(tool_name, args=None, **kwargs):
        blocked = pre_tool_call(tool_name, args)
        if blocked:
            try:
                runtime_for_context(ctx).execute(tool_name, args)
            except Exception:
                return {"action": "block", "message": "Lexecon: gate configuration unavailable."}
        return blocked

    ctx.register_hook("pre_tool_call", hook)
    for name in TOOLS:
        ctx.register_tool(
            name=name, toolset="lexecon_workspace", handler=_handler_for(ctx, name),
            schema={"name": name, "description": (
                "List approved text files in the configured Lexecon workspace."
                if name == "lexecon_list_files" else
                "Read a small approved UTF-8 text file in the configured Lexecon workspace."
            ), "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Relative path; use . to list the workspace root."},
            }, "required": ["path"], "additionalProperties": False}},
            description="Lexecon-authorized bounded local workspace access",
        )
