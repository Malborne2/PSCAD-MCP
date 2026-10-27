"""
End-to-end smoke test for the PSCAD MCP server.

Calls the *actual* tool functions defined in pscad_mcp.server (the same
functions an MCP client would invoke), in order, to build a small demo
circuit from scratch (AC source -> ammeter -> resistor -> ground, with
the load current recorded to an output channel), run it, and read back
results. Not a unit test with mocks -- this drives the real, licensed,
local PSCAD installation.

Component locations/orientations are taken from PSCAD's own installed
"vdiv" tutorial example (Examples/tutorial/vdiv.pscx) to guarantee the
port geometry lines up.

Run with: py test_demo.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pscad_mcp import server as s  # noqa: E402

DEMO_FOLDER = str(Path(__file__).parent / "demo_project")
Path(DEMO_FOLDER).mkdir(exist_ok=True)
PROJECT = "mcp_demo"


def show(label, result):
    print(f"\n--- {label} ---")
    print(json.dumps(result, indent=2, default=str)[:2000])
    if isinstance(result, dict) and not result.get("ok", True):
        raise SystemExit(f"STEP FAILED: {label}")
    return result


def main():
    show("connect", s.pscad_connect(minimize=True, silence=True, timeout=90))
    show("status", s.pscad_status())

    if PROJECT in s.session.app.project_names():
        show("unload stale project", s.pscad_unload_project(PROJECT))

    show("create_project", s.pscad_create_project(PROJECT, DEMO_FOLDER, "case"))

    show(
        "set_project_parameters",
        s.pscad_set_project_parameters(
            PROJECT,
            {
                "time_duration": 0.2,
                "time_step": 50.0,
                "sample_step": 250.0,
                "PlotType": "PSOUT",
                "description": "PSCAD MCP server smoke-test circuit",
            },
        ),
    )

    # -- components: AC source -> ammeter -> resistor -> ground -------------
    # locations/orientations copied from PSCAD's installed vdiv.pscx example
    show(
        "add source_1",
        s.pscad_add_component(
            PROJECT, "master", "source_1", x=10, y=19, orient=1,
            parameters={"Name": "Source1", "Vm": "70.71 [kV]"},
        ),
    )
    show(
        "add ammeter",
        s.pscad_add_component(
            PROJECT, "master", "ammeter", x=17, y=15, orient=6,
            parameters={"Name": "Iload"},
        ),
    )
    show(
        "add resistor",
        s.pscad_add_component(
            PROJECT, "master", "resistor", x=21, y=19, orient=3,
            parameters={"R": "50.0 [ohm]"},
        ),
    )
    show(
        "add ground",
        s.pscad_add_component(PROJECT, "master", "ground", x=21, y=21, orient=1),
    )

    # -- output channel: ammeter's implicit "Iload" signal -> datalabel -> pgb
    show(
        "add datalabel",
        s.pscad_add_component(
            PROJECT, "master", "datalabel", x=18, y=12,
            parameters={"Name": "Iload", "display": "CURRENT", "datatype": "REAL"},
        ),
    )
    show(
        "add pgb",
        s.pscad_add_component(
            PROJECT, "master", "pgb", x=20, y=12,
            parameters={"Name": "Load Current", "Group": "Load Current", "Units": "kA"},
        ),
    )

    # -- wiring, matching vdiv.pscx's known-good port geometry ---------------
    show("wire source->node", s.pscad_create_wire(PROJECT, [[10, 17], [10, 15]]))
    show("wire node->ammeter", s.pscad_create_wire(PROJECT, [[10, 15], [17, 15]]))
    show("wire ammeter->node2", s.pscad_create_wire(PROJECT, [[21, 15], [19, 15]]))
    show("wire node2->resistor", s.pscad_create_wire(PROJECT, [[21, 15], [21, 17]]))
    show("wire resistor->ground", s.pscad_create_wire(PROJECT, [[21, 19], [21, 21]]))
    show("wire datalabel->pgb", s.pscad_create_wire(PROJECT, [[18, 12], [20, 12]]))

    show("list_components", s.pscad_list_components(PROJECT))

    show("save_project", s.pscad_save_project(PROJECT))

    run_result = show("run_project", s.pscad_run_project(PROJECT, wait=True))
    msgs = show("get_messages", s.pscad_get_messages(PROJECT))
    for m in msgs.get("messages", []):
        if "error" in m.lower() or "stopped unexpectedly" in m.lower():
            print("  !! ", m)

    out = show("find_output_file", s.pscad_find_output_file(PROJECT))
    if out.get("found"):
        psout_path = out["path"]
        show("list_output_runs", s.pscad_list_output_runs(psout_path))
        channels = show("list_output_channels", s.pscad_list_output_channels(psout_path))
        chan_list = channels.get("channels", [])
        if chan_list:
            chan_path = chan_list[0]["path"]
            show(f"get_trace_data({chan_path})", s.pscad_get_trace_data(psout_path, chan_path))
    else:
        print("\nNo .psout file produced - build/run likely failed; see run_result/messages above.")

    print("\nRUN RESULT:", run_result)
    print("\nDEMO COMPLETE")


if __name__ == "__main__":
    main()
