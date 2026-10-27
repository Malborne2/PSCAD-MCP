# PSCAD MCP Server

> **⚠️ Unofficial project.** This is an independent, community-built
> integration. It is **not affiliated with, endorsed by, or supported
> by Manitoba Hydro International (MHI)**, the maker of PSCAD and its
> Automation Library. "PSCAD" and related names are trademarks of their
> respective owners. Use at your own risk, and see MHI's own licensing
> terms for PSCAD itself and the Automation Library.

An [MCP](https://modelcontextprotocol.io) server that exposes **PSCAD**
(a power systems transient simulator) to AI agents, the same way a
MATLAB MCP server exposes MATLAB. It wraps PSCAD's official
**Automation Library** (`mhi.pscad` for control, `mhi.psout` for reading
results) as 45 MCP tools covering the full workflow: connect, log in and
check out a license certificate, create/open projects, place and wire
components, set parameters, build, run, and read back simulation
results.

There is no mock/simulated mode -- every tool call drives a real, running,
licensed, locally-installed copy of PSCAD 5.x via COM automation.

## Requirements

Nothing here is bundled or downloaded by this repo -- you provide all of
it yourself:

- **A licensed copy of PSCAD 5.x, installed on Windows.** PSCAD is
  commercial (with an educational tier) software from MHI; this repo
  does not include it, unlock it, or provide a license. Get it from
  [pscad.com](https://www.pscad.com/).
- **Python 3.9+ (64-bit, matching PSCAD's 64-bit build).**
- **MHI's own PSCAD Automation Library**, published as ordinary PyPI
  packages -- free to install for anyone with a PSCAD license, no extra
  signup needed for the library itself:
  ```bash
  pip install mhi-pscad mhi-psout pywin32
  ```
- **The official MCP Python SDK:** `pip install mcp` (this project
  targets `mcp>=2.0`, which renamed `FastMCP` to `MCPServer` -- see
  `pscad_mcp/server.py`).
- A **MyCentre account** (MHI's license-management account) if you need
  this server to log in and check out a license certificate
  programmatically -- see "Login & licensing" below. Otherwise, logging
  in once through the PSCAD GUI yourself is enough.

Install the Python side of all this at once:

```bash
pip install -r requirements.txt
```

## Quick start

```bash
# sanity check: list every registered tool
python -c "import asyncio; from pscad_mcp.server import mcp; print([t.name for t in asyncio.run(mcp.list_tools())])"

# run the server (stdio transport -- what MCP clients expect)
python -m pscad_mcp.server
```

### Register it with an MCP client (e.g. Claude Code / Claude Desktop)

Add to your MCP client's server config (adjust the path):

```json
{
  "mcpServers": {
    "pscad": {
      "command": "python",
      "args": ["-m", "pscad_mcp.server"],
      "cwd": "C:\\GitHub\\PSCAD-MCP"
    }
  }
}
```

Once connected, an agent's first call should always be `pscad_connect`.

## What it can do

See [`docs/TOOLS.md`](docs/TOOLS.md) for the full, auto-generated
(`gen_tool_docs.py`) reference of all 45 tools and their parameters.
Grouped overview:

| Group | Examples |
|---|---|
| Connection, login & licensing | `pscad_connect`, `pscad_status`, `pscad_login`, `pscad_discover_certificates`, `pscad_acquire_certificate` |
| Workspace | `pscad_load`, `pscad_list_projects`, `pscad_save_workspace` |
| Projects | `pscad_create_project`, `pscad_run_project`, `pscad_get_messages`, `pscad_set_project_parameters` |
| Canvas / components | `pscad_add_component`, `pscad_set_component_parameters`, `pscad_create_wire`, `pscad_create_graph` |
| Simulation sets | `pscad_create_simulation_set`, `pscad_run_simulation_set` (batch/parallel runs) |
| Results | `pscad_find_output_file`, `pscad_list_output_channels`, `pscad_get_trace_data` (reads `.psout` files via `mhi.psout`) |

Every tool returns a JSON-serializable dict with `ok: true/false`. On
failure it returns the real exception (`error`, `error_type`) from the
PSCAD Automation Library rather than swallowing it, so an agent can tell
a licensing error from a wiring error from a typo'd component name.

## Login & licensing

PSCAD can need a logged-in MyCentre account before it will actually
*run* a simulation (editing/building generally works without one). If
nobody has logged in through the PSCAD GUI yet, that normally surfaces
as a modal login dialog popping up in the PSCAD window -- which blocks
automation calls that can't see or answer it.

This server recognizes that state up front instead of silently hanging:
`pscad_connect` and `pscad_status` both report `logged_in` /
`needs_login` on every call, so an agent sees immediately that a login
is required and can ask its human operator for credentials rather than
discovering it only after some other call times out. The flow:

1. `pscad_connect`, then check `needs_login` in the result (or call
   `pscad_license_status`).
2. If `needs_login: true`, ask the human for their MyCentre
   username/password (never invent, reuse, or guess credentials), then
   call `pscad_login(username, password)`.
3. `pscad_discover_certificates()` to see what license certificates
   that account can use.
4. `pscad_acquire_certificate(certificate_key)` to check one out --
   this is what actually lets `pscad_run_project` run (not just build).
5. `pscad_release_certificate()` when done, if the license is
   seat-limited and the user wants to free it for someone else.

None of this is a substitute for actually having a valid PSCAD license;
it just automates the same login/certificate steps a human would
otherwise click through in the GUI.

## Agent skill

[`../.claude/skills/pscad/SKILL.md`](../.claude/skills/pscad/SKILL.md)
packages the workflow and the non-obvious gotchas (component port
geometry/orientation, how to wire a recorder to a meter, the real cause
behind a "stopped unexpectedly" run, and the `PlotType` setting needed
to actually get an output file) as a Claude Code skill, so an agent
doesn't have to rediscover them by trial and error.

## Verified / tested

Fully tested end-to-end against a real, licensed PSCAD 5.1.0 install
(`test_demo.py` + `plot_result.py`): connect, create a project, add 6
components (`source_1`, `ammeter`, `resistor`, `ground`, `datalabel`,
`pgb`) with correct parameters and orientations, wire them into a closed
loop, add a visible graph (`pscad_create_graph`), save, build, **run**,
and read back real simulation data -- all through the MCP tool layer
exactly as an agent would call them. The resulting `.psout` file
contains 801 real samples of the load current (±1.96 kA sinusoid, as
expected for a 70.71 kV source into a 50 Ω resistor), read back via
`pscad_get_trace_data` and plotted straight from that data.

Getting a clean run took fixing two real bugs along the way, both
written up in `docs/TROUBLESHOOTING.md`:
1. A Windows environment variable (`NoDefaultCurrentDirectoryInExePath`)
   was breaking PSCAD's own auto-generated launch script, which invokes
   the compiled `.exe` by bare name. This produced a generic "stopped
   unexpectedly" error with no useful detail anywhere in the Automation
   Library's messages -- a whole licensing/VPN/network investigation
   looked very plausible at first and was a complete dead end; the real
   error ("'mcp_demo.exe' is not recognized...") was only ever visible
   in PSCAD's own GUI message pane.
2. The project's `PlotType` parameter defaults to `"NONE"`, meaning a
   fully successful build+run still silently produces no output file.
   `pscad_set_project_parameters(name, {"PlotType": "PSOUT"})` before
   running fixes this.

## Project layout

```
PSCAD-MCP/
  pscad_mcp/
    server.py      MCP server + all 45 tool definitions
    session.py      Connection lifecycle (connect/launch/disconnect/quit)
    results.py       .psout reading via mhi.psout
  .claude/skills/pscad/SKILL.md   Agent skill (workflow + gotchas)
  docs/
    TOOLS.md          Full tool reference (auto-generated)
    TROUBLESHOOTING.md
  demo_project/        The real, successfully-run smoke-test circuit
  test_demo.py        End-to-end smoke test (builds + runs a real circuit)
  plot_result.py       Plots real trace data pulled from a produced .psout
  gen_tool_docs.py     Regenerates docs/TOOLS.md from the live tool registry
  requirements.txt
  pyproject.toml
```

## Design notes

- **One connection per process.** `session.py` keeps a process-wide
  singleton; `pscad_connect` attaches to an already-running PSCAD if one
  exists, otherwise launches one. This avoids spawning a new PSCAD
  process on every tool call (slow, and PSCAD may hold a certificate per
  process on a seat-limited license).
- **Errors are data, not exceptions.** Every tool wraps the underlying
  `mhi.pscad`/`mhi.psout` call and returns `{"ok": false, "error": ...,
  "error_type": ...}` on failure instead of letting the MCP transport
  turn it into an opaque tool-call error, so an agent can reason about
  *why* something failed (e.g. `PscadNotConnected` vs. a COM error from
  a bad component name).
- **Trace data is decimated.** `pscad_get_trace_data` caps output at
  `max_points` (default 2000) with a reported `decimation_step`, since a
  full-resolution run can have hundreds of thousands of samples -- enough
  to flood an agent's context for no benefit.
