"""Explicit startup for the isolated, patched Hermes read-only pilot.

Arming precedes discovery. A normal installed Hermes process is not accepted as
an equivalent execution environment. This is not an OS containment boundary.
"""

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from owner_setup import SetupError, checked_path, read_isolated_config, settings_for

TOOLS = {"lexecon_list_files", "lexecon_read_file"}


def initialize_required_runtime(home, checkout):
    """Arm, discover, seal, then expose the exact two intended tool handlers."""
    if not Path(home).is_absolute() or not Path(checkout).is_absolute():
        raise SetupError("Absolute profile and candidate checkout paths are required.")
    home, settings = settings_for(home)
    checkout = checked_path(checkout)
    gate_source = checkout / "tools/required_tool_gate.py"
    if not gate_source.is_file():
        raise SetupError("This pilot requires the patched Hermes candidate, not the ordinary installed checkout.")
    config = read_isolated_config(home)
    gate_config = config.get("required_tool_gate")
    plugins_config = config.get("plugins")
    platform_config = config.get("platform_toolsets")
    tools_config = config.get("tools")
    search_config = tools_config.get("tool_search") if isinstance(tools_config, dict) else None
    if (not isinstance(gate_config, dict) or gate_config.get("plugin") != "lexecon-gate"
            or not isinstance(gate_config.get("tools"), list)
            or len(gate_config["tools"]) != 2
            or any(not isinstance(tool, str) for tool in gate_config["tools"])
            or set(gate_config["tools"]) != TOOLS
            or not isinstance(plugins_config, dict) or plugins_config.get("enabled") != ["lexecon-gate"]
            or not isinstance(platform_config, dict) or platform_config.get("cli") != ["lexecon_workspace"]
            or not isinstance(search_config, dict) or search_config.get("enabled") is not False):
        raise SetupError("Profile must require the Lexecon plugin and exactly its two bounded tools.")
    os.environ["HERMES_HOME"] = str(home)
    os.environ["HERMES_RUNTIME_DIR"] = str(home / "private/runtime")
    os.environ["HERMES_ENABLE_PROJECT_PLUGINS"] = "0"
    os.chdir(home / "workspace")
    sys.path.insert(0, str(checkout))
    gate = importlib.import_module("tools.required_tool_gate")
    if Path(gate.__file__).resolve() != gate_source.resolve():
        raise SetupError("Another Hermes checkout was already imported; start a fresh process.")
    if gate.arm_from_config() is not True:
        raise SetupError("Mandatory dispatch was not armed; startup refused.")
    # These imports can discover plugins. Required mode is already armed.
    plugins = importlib.import_module("hermes_cli.plugins")
    model_tools = importlib.import_module("model_tools")
    plugins.discover_plugins(force=True)
    gate.seal_required_gate()
    loaded = plugins.get_plugin_manager()._plugins.get("lexecon-gate")
    if (loaded is None or loaded.module is None
            or Path(loaded.module.__file__).resolve().parent != home / "plugins/lexecon-gate"):
        raise SetupError("The required plugin did not load from the isolated profile.")
    definitions = model_tools.get_tool_definitions(
        enabled_toolsets=["lexecon_workspace"], quiet_mode=True, skip_tool_search_assembly=True,
    )
    if {item["function"]["name"] for item in definitions} != TOOLS:
        raise SetupError("Unexpected tool definitions; required startup refused.")
    if importlib.import_module("tools.tool_search").load_config().enabled != "off":
        raise SetupError("Dynamic tool search must remain disabled for this pilot.")
    return SimpleNamespace(home=home, settings=settings, checkout=checkout,
                           plugin=loaded.module, gate=gate, model_tools=model_tools)
