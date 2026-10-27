"""Generate docs/TOOLS.md from the live tool registry (so it can't drift)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pscad_mcp.server import mcp  # noqa: E402

GROUPS = [
    ("Connection & Application", ["pscad_connect", "pscad_status", "pscad_disconnect", "pscad_quit",
                                   "pscad_license_status", "pscad_login", "pscad_logout",
                                   "pscad_discover_certificates", "pscad_acquire_certificate",
                                   "pscad_release_certificate"]),
    ("Workspace", ["pscad_load", "pscad_list_projects", "pscad_new_workspace", "pscad_save_workspace"]),
    ("Projects", ["pscad_create_project", "pscad_project_info", "pscad_save_project", "pscad_save_project_as",
                  "pscad_unload_project", "pscad_build_project", "pscad_build_all", "pscad_get_messages",
                  "pscad_run_project", "pscad_stop_run", "pscad_get_run_status",
                  "pscad_get_project_parameters", "pscad_set_project_parameters"]),
    ("Canvas & Components", ["pscad_list_components", "pscad_add_component", "pscad_get_component_parameters",
                              "pscad_set_component_parameters", "pscad_find_component", "pscad_delete_component",
                              "pscad_move_component", "pscad_create_wire", "pscad_create_connection",
                              "pscad_create_graph"]),
    ("Simulation Sets", ["pscad_list_simulation_sets", "pscad_create_simulation_set",
                          "pscad_add_task_to_simulation_set", "pscad_run_simulation_set"]),
    ("Results (.psout)", ["pscad_find_output_file", "pscad_list_output_runs", "pscad_list_output_channels",
                           "pscad_get_trace_data"]),
]


async def main():
    tools = {t.name: t for t in await mcp.list_tools()}
    lines = ["# PSCAD MCP -- Tool Reference", "",
             "Auto-generated from the live tool registry (`gen_tool_docs.py`). "
             "Every tool returns a JSON object with `ok: true/false`; on failure, "
             "`error` and `error_type` describe what went wrong (the real "
             "exception from the PSCAD Automation Library, not a generic message).",
             ""]
    seen = set()
    for group_name, names in GROUPS:
        lines.append(f"## {group_name}")
        lines.append("")
        for name in names:
            t = tools.get(name)
            if t is None:
                continue
            seen.add(name)
            lines.append(f"### `{name}`")
            lines.append("")
            lines.append(t.description or "*(no description)*")
            lines.append("")
            schema = t.input_schema or {}
            props = schema.get("properties", {})
            required = set(schema.get("required", []))
            if props:
                lines.append("| Parameter | Type | Required | Default |")
                lines.append("|---|---|---|---|")
                for pname, pschema in props.items():
                    ptype = pschema.get("type", "any")
                    if "anyOf" in pschema:
                        ptype = " \\| ".join(
                            s.get("type", "null") for s in pschema["anyOf"]
                        )
                    default = pschema.get("default", "")
                    lines.append(f"| `{pname}` | {ptype} | {'yes' if pname in required else 'no'} | {default} |")
                lines.append("")
            else:
                lines.append("*(no parameters)*")
                lines.append("")

    missing = [n for n in tools if n not in seen]
    if missing:
        lines.append("## Other")
        lines.append("")
        for name in missing:
            lines.append(f"- `{name}`")

    Path(__file__).parent.joinpath("docs", "TOOLS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote docs/TOOLS.md with {len(tools)} tools documented.")


if __name__ == "__main__":
    asyncio.run(main())
