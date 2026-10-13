"""Local reference adapter: verify a grant before one harmless text transform.

This is deliberately a small demonstration of the enforcement boundary. A real
integration must put its tool call behind the same fail-closed verification step.
"""

from typing import Any, Dict


def execute_safe_demo(client: Any, headers: Dict[str, str], grant: Dict[str, Any], text: str) -> str:
    """Return uppercased text only when the online verifier approves this call."""
    response = client.post(
        "/capability/verify",
        json={"capability_token": grant, "action": "read", "tool": "safe_demo"},
        headers=headers,
    )
    if response.status_code != 200 or response.json().get("valid") is not True:
        raise PermissionError("Tool call denied: capability verification failed")
    return text.upper()
