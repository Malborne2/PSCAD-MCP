# Troubleshooting

## "The simulation process for '<project>' has stopped unexpectedly" with no runtime log at all

**Symptom:** `pscad_run_project` returns `ok: true` (the tool call itself
succeeded), the build completes with no errors in `pscad_get_messages`
(compile, link, and `.exe` creation all show "done"), but then a
`runtime`/`error` message appears immediately, and
`pscad_find_output_file` reports `found: false` -- no `.psout` is ever
written, and no `.log`/`.lis` file appears in the build folder either
(i.e. EMTDC didn't even get far enough to open its own log).

**Actual root cause (confirmed on this machine): the Windows environment
variable `NoDefaultCurrentDirectoryInExePath=1`.** PSCAD launches each
simulation through an auto-generated batch script like:

```bat
call "C:\Program Files\GFortran\8.1\x86\bin\gf81vars.bat"
pushd "<build_folder>\"
mcp_demo.exe -v5 -config mcp_demo_1.config
popd
```

It invokes the compiled `.exe` by **bare name**, relying on `cmd.exe`'s
default behaviour of searching the current directory. If
`NoDefaultCurrentDirectoryInExePath` is set (a security hardening
setting that disables that default), `cmd.exe` cannot find the `.exe`
at all -- `pushd` still succeeds and lands in the right folder, but the
very next line fails with `'mcp_demo.exe' is not recognized as an
internal or external command`. PSCAD's automation layer doesn't surface
that literal text through `pscad_get_messages` / the Automation Library
(it just reports the generic "stopped unexpectedly"); **the real error
is only visible in PSCAD's own GUI message pane**, which is what finally
revealed it here.

**How to confirm it's this:**

```powershell
[Environment]::GetEnvironmentVariable("NoDefaultCurrentDirectoryInExePath","User")
[Environment]::GetEnvironmentVariable("NoDefaultCurrentDirectoryInExePath","Machine")
# a "1" at either scope is the problem
```

Or just reproduce it directly: `cd` into the project's build folder and
run `cmd /c "pushd ""%CD%\"" && mcp_demo.exe -v5 -config mcp_demo_1.config"`
-- if you get the same "not recognized" error despite the file being
right there, this is it.

**Fix:**

```powershell
[Environment]::SetEnvironmentVariable("NoDefaultCurrentDirectoryInExePath", $null, "User")
```

This is a genuine (if minor) security-hardening setting -- it exists to
stop a directory-planting attack where a malicious `cmd.exe`/etc.
dropped into a folder you `cd` into shadows the real one. Removing it
re-enables implicit current-directory executable lookup *system-wide*,
not just for PSCAD, so confirm with the user before changing it.

**Important: the change needs a genuinely fresh process tree to take
effect.** Removing the registry value does not affect any process (or
its children) that was already running when you removed it -- including
a long-lived terminal/automation session. Either reboot, or at minimum
clear it in-process immediately before launching PSCAD so the corrected
value propagates to PSCAD's own child processes:

```powershell
Remove-Item Env:\NoDefaultCurrentDirectoryInExePath -ErrorAction SilentlyContinue
# ...then launch/relaunch PSCAD in the SAME process/session
```

**Red herrings chased before finding this** (don't repeat this detour):
a whole VPN/Tailscale/license-server investigation looked very
compelling at first -- `LicenseConfig.cfg` in the build folder points at
a dynamically-chosen local address/port, which seemed like a classic
"can't reach the license server" story, and even survived disconnecting
the VPN, exiting Tailscale, and a full reboot with no change. All of
that was coincidental: nothing was ever actually listening on that
license port in any of those configurations, for the unrelated reason
above. Compiler bit-ness (GFortran 8.1 vs 13.2), Windows Defender, and
port exclusion ranges were also checked and ruled out along the way.
Skip straight to the `NoDefaultCurrentDirectoryInExePath` check first.

## The run succeeds (no errors anywhere) but `pscad_find_output_file` still reports `found: false`

Check the project's `PlotType` parameter (`pscad_get_project_parameters`).
It defaults to `"NONE"`, which means PSCAD builds and runs the
simulation perfectly but writes no output file at all. Set it to
`"PSOUT"` (what `pscad_get_trace_data`/`mhi.psout` reads) via
`pscad_set_project_parameters(name, {"PlotType": "PSOUT"})` *before*
running.

## PSCAD pops up a login dialog during a tool call and the call hangs

Some automation calls (e.g. refreshing available license certificates)
can trigger a real MyCentre login dialog in the PSCAD window if you
aren't already logged in. `pscad_connect`'s `silence=True` default
suppresses *some* dialogs, but not an actual required login -- that one
needs a human. Tell the user to switch to the PSCAD window and log in;
the blocked tool call will return once they do.

## `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`

You have `mcp>=2.0` installed, which renamed `FastMCP` to `MCPServer` and
changed several APIs. This project already targets 2.x
(`from mcp.server.mcpserver import MCPServer`). If you're adapting
example code from older MCP tutorials that import `FastMCP`, either
update the import or pin `mcp<2`.

## A component's parameters call raises `ValueError: Component has no parameters`

Not every object returned by `canvas.components()` has a parameter set --
wires (`WireOrthogonal`), graph frames, and a few other non-component
canvas objects don't. `pscad_list_components` already guards against
this; if you call `pscad_get_component_parameters` directly on a wire's
`iid`, you'll hit this -- use `pscad_list_components` first to check
`defn_name`.

## A wire doesn't actually connect two components

See the "Component placement gotchas" section in the PSCAD skill
(`.claude/skills/pscad/SKILL.md`). In short: a wire that runs straight
through a component's body (instead of stopping exactly at its port)
creates a short circuit that bypasses it, and the default `orient=0`
is wrong for many in-line components. Copy known-good `location`/`orient`
values from a working PSCAD example rather than guessing.
