---
name: pscad
description: Drive a locally-installed, licensed PSCAD 5.x power systems simulator through the pscad-mcp MCP server -- create/open projects, place and wire components, set parameters, build and run simulations, and read back .psout results. Use whenever a task mentions PSCAD, EMTDC, power-system transient simulation, or "pscad mcp".
---

# PSCAD (via pscad-mcp)

> **Unofficial.** `pscad-mcp` is an independent, community-built
> integration, not affiliated with or supported by Manitoba Hydro
> International (MHI). You need your own valid, licensed PSCAD install
> -- this skill and its MCP server don't provide, unlock, or bypass a
> license.

This skill drives PSCAD through the `pscad-mcp` MCP server, which wraps
MHI's official PSCAD Automation Library (`mhi.pscad` / `mhi.psout`). It
is the PSCAD equivalent of the MATLAB MCP server: every tool call talks
to a real, running, licensed PSCAD process on the user's machine --
there is no simulated/mock mode.

Full tool reference: see `docs/TOOLS.md` and `README.md` in the
`pscad-mcp` project. This file covers the workflow and the gotchas that
aren't obvious from the API alone.

## Before you do anything

1. Call `pscad_connect` first. It attaches to an already-running PSCAD, or
   launches one if none is running. Every other tool requires this.
2. Check the result's `needs_login` field (also in `pscad_status` /
   `pscad_license_status`). PSCAD can need a logged-in MyCentre account
   before it will actually *run* a simulation (editing/building
   generally works without one) -- when nobody's logged in, this
   normally shows up as a blocking modal dialog in the PSCAD window
   that automation can't see or answer. If `needs_login: true`:
   - Ask the human operating you for their MyCentre username/password
     (never invent, reuse, or guess credentials).
   - Call `pscad_login(username, password)`.
   - Call `pscad_discover_certificates()` to see what licenses that
     account can use, then `pscad_acquire_certificate(certificate_key)`
     to check one out.
   - If the human would rather do this in the GUI themselves, that's
     fine too -- just tell them to, and re-check `pscad_status`
     afterward.
3. **A build that succeeds but a run that instantly reports "the
   simulation process ... has stopped unexpectedly" with zero runtime log**
   is very likely *not* a circuit or licensing problem -- see
   `docs/TROUBLESHOOTING.md`'s `NoDefaultCurrentDirectoryInExePath`
   section first. (A whole licensing/VPN/network rabbit hole looked very
   plausible here and was completely wrong; the real cause was a Windows
   environment variable breaking PSCAD's own generated launcher batch
   script.) Don't re-walk that dead end -- check the actual Windows-level
   cause documented there before assuming it's PSCAD licensing.
4. **Set `PlotType` to `"PSOUT"` (or `"OUT"`) in `pscad_set_project_parameters`
   before running**, or no output file is written at all -- the project
   default is `PlotType: "NONE"`, which means the build and run can both
   succeed perfectly and `pscad_find_output_file` will still report
   `found: false`. This bit us once already; always set it explicitly.

## Workflow for building a circuit from scratch

1. `pscad_create_project(name, folder, project_type="case")`
2. `pscad_set_project_parameters(name, {...})` -- at minimum
   `time_duration` (seconds) and `time_step` (microseconds) if the
   defaults (0.5s / 50us-ish) don't suit the task; also `sample_step` for
   output sampling rate and `description`.
3. `pscad_add_component(project, library, defn_name, x, y, orient, parameters)`
   for every part. `library="master"` is PSCAD's standard component
   library (sources, R/L/C, meters, breakers, machines, controls, etc).
4. `pscad_create_wire(project, [[x1,y1],[x2,y2]])` for every electrical
   connection. **Orthogonal wires only** -- each call's vertices must form
   a sequence of horizontal/vertical segments.
5. `pscad_save_project`, then `pscad_run_project(name, wait=True)`.
6. `pscad_get_messages(name)` to check for build errors/warnings.
7. `pscad_find_output_file(name)` -> `pscad_list_output_channels(path)` ->
   `pscad_get_trace_data(path, channel_path)` to pull results.

## Component placement gotchas (the part that actually trips you up)

PSCAD's canvas uses a grid-unit coordinate system. Components are not
simple boxes with ports exactly at their `(x, y)` location -- port
positions depend on the component's footprint **and its `orient` value**
(0/1/2/3 = rotations, 4-7 = mirrored rotations). Two mistakes will silently
break a circuit without PSCAD ever returning an error from the tool call:

- **A wire drawn straight through a component's body, instead of
  stopping exactly at its port**, creates a short circuit that bypasses
  the component entirely. You'll see build warnings like `Path between
  terminals 'N1' and 'N2' is a short circuit` or `Unresolved current
  path`. Fix: never span a single `pscad_create_wire` call across a
  component's footprint -- always end/start wires exactly at the
  component's port coordinate, and use a second wire call to continue
  past it.
- **Using the default `orient=0` for an in-line series component** (an
  ammeter, breaker, resistor in series, etc.) usually puts its ports on
  the wrong axis for a vertical run, leaving one port floating (`Open
  circuit detected`, `Suspicious floating terminal`). Fix: when unsure of
  a component's exact port geometry, open a known-working PSCAD example
  that uses it (PSCAD ships examples under
  `C:\Users\Public\Documents\PSCAD\<version>\Examples\...`) and read its
  `location` **and** `orient` for that component with
  `pscad_list_components` / direct `mhi.pscad` inspection, then reuse
  those exact values rather than guessing.
- Two components can share an electrical node just by sitting exactly on
  the same wire's path at the same y (or x) -- e.g. a `voltmetergnd` meter
  placed directly on top of a straight wire segment taps that node
  without needing its own wire.

## Recording a signal to an output channel (for `pscad_get_trace_data`)

A meter (`ammeter`, `voltmetergnd`, etc.) with `Name="Foo"` exposes an
*implicit* named signal `"Foo"` -- no wire needed to export it. To record
it to the `.psout` file:

1. Add a `master:datalabel` component with `parameters={"Name": "Foo", ...}`
   near the meter (no wire needed between meter and datalabel; they match
   by `Name`).
2. Add a `master:pgb` ("Output Channel") component.
3. `pscad_create_wire` connecting the datalabel to the pgb (this one *does*
   need a real wire).
4. After a run, that pgb's name/group shows up as a channel in
   `pscad_list_output_channels`.

## Reference data gathered from this machine's PSCAD 5.1.0 install

- Default workspace components live in the `master` library. Common defn
  names: `source_1` (1-phase source), `source3` (3-phase source),
  `resistor`, `inductor`, `capacitor`, `ground`, `ammeter`, `voltmetergnd`,
  `datalabel`, `pgb`.
- Project parameters (via `pscad_get_project_parameters`) include
  `time_duration`, `time_step`, `sample_step`, `output_filename`,
  `description`, `StartType`, `fortran_version`, `threads`.
- `project_type`: 1 = case (runnable), 2 = library.
