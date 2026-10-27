"""
PSCAD MCP Server.

Exposes Manitoba Hydro International's PSCAD Automation Library
(``mhi.pscad`` / ``mhi.psout``) as a set of MCP tools, so an agent can
drive a real, licensed, locally-installed PSCAD 5.x instance: open/create
projects, place and wire components, run simulations, and read back
results -- the same way the MATLAB MCP server drives MATLAB.

Run directly for local stdio use (the normal case, e.g. from an MCP
client config):

    python -m pscad_mcp.server

Requires: PSCAD 5.x installed and licensed on this machine, plus the
`mhi-pscad`, `mhi-psout` and `mcp` Python packages (see requirements.txt).
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from . import results as results_mod
from .session import PscadNotConnected, session

mcp = MCPServer(
    name="pscad",
    title="PSCAD Automation",
    instructions=(
        "Tools for driving a locally-installed, licensed PSCAD 5.x power "
        "systems simulator via its official Automation Library. Call "
        "pscad_connect first. Most tools take a project `name` (the name "
        "PSCAD shows in its workspace, not the file path). Use "
        "pscad_run_project to build+run a case, then pscad_find_output_file "
        "and pscad_list_output_channels/pscad_get_trace_data to read results."
    ),
)


def _err(e: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": str(e),
        "error_type": type(e).__name__,
    }


def _ok(**data: Any) -> dict[str, Any]:
    return {"ok": True, **data}


def _safe(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        result = fn(*args, **kwargs)
        if isinstance(result, dict):
            return _ok(**result)
        return _ok(result=result)
    except PscadNotConnected as e:
        return _err(e)
    except Exception as e:  # noqa: BLE001 - surface all PSCAD/COM errors to the agent
        return {**_err(e), "traceback": traceback.format_exc(limit=4)}


# ---------------------------------------------------------------------------
# Connection / application
# ---------------------------------------------------------------------------


@mcp.tool()
def pscad_connect(
    prefer_launch: bool = True,
    version: Optional[str] = None,
    minimize: bool = True,
    silence: bool = True,
    timeout: int = 60,
) -> dict[str, Any]:
    """Connect to PSCAD: attach to a running instance, or launch a new one.

    Always call this before any other pscad_* tool. Safe to call repeatedly;
    it's a no-op if already connected.

    Args:
        prefer_launch: If no running instance is found, launch a new PSCAD
            process. If False, fail instead of launching.
        version: Specific installed PSCAD version to launch (e.g. "5.1.0").
            Omit to use the default/only installed version.
        minimize: Minimize the PSCAD window on launch (keeps it out of the
            way; it still runs normally).
        silence: Suppress PSCAD dialogs that could otherwise block
            automation (e.g. "unsaved changes" prompts).
        timeout: Seconds to wait for PSCAD to start and respond.
    """
    return _safe(
        session.connect_or_launch,
        prefer_launch=prefer_launch,
        version=version,
        minimize=minimize,
        silence=silence,
        timeout=timeout,
    )


@mcp.tool()
def pscad_status() -> dict[str, Any]:
    """Report connection state, license state, and version of PSCAD."""

    def _status() -> dict[str, Any]:
        if not session.is_connected:
            return {"connected": False}
        app = session.app
        return {
            "connected": True,
            "is_alive": app.is_alive(),
            "is_busy": app.is_busy(),
            "licensed": app.licensed(),
            "logged_in": app.logged_in(),
            "version": str(app.version),
            "workspace_name": app.workspace_name,
            "workspace_path": str(app.workspace_path),
            "project_names": app.project_names(),
        }

    return _safe(_status)


@mcp.tool()
def pscad_disconnect() -> dict[str, Any]:
    """Close our connection to PSCAD, leaving the application running."""
    return _safe(session.disconnect)


@mcp.tool()
def pscad_quit() -> dict[str, Any]:
    """Terminate the PSCAD application process entirely.

    Destructive: any unsaved changes in open projects are lost. Confirm
    with the user before calling this unless they explicitly asked to
    close PSCAD.
    """
    return _safe(session.quit_application)


@mcp.tool()
def pscad_license_status() -> dict[str, Any]:
    """Report licensing status: logged in, licensed, current certificate.

    Call this before anything that needs to actually *run* a simulation
    (building/editing generally works on an unlicensed/trial install, but
    running does not). If `logged_in` is false, PSCAD needs a MyCentre
    account login before it can check out a certificate -- see
    `pscad_login`. If `logged_in` is true but `current_certificate` is
    null, call `pscad_discover_certificates` then `pscad_acquire_certificate`.
    """

    def _lic() -> dict[str, Any]:
        app = session.app
        cert = app.get_current_certificate()
        return {
            "licensed": app.licensed(),
            "logged_in": app.logged_in(),
            "current_certificate": str(cert) if cert else None,
            "needs_login": not app.logged_in(),
        }

    return _safe(_lic)


@mcp.tool()
def pscad_login(username: str, password: str, remember: bool = False) -> dict[str, Any]:
    """Log in to a PSCAD MyCentre account to enable license checkout.

    PSCAD occasionally needs this to validate a license -- without it, a
    project can usually still be opened/edited but a simulation *run* can
    fail with a generic, unhelpful error. Call `pscad_license_status`
    first; if it reports `needs_login: true`, ask the human operating
    this agent for their MyCentre username/password (never invent or
    reuse credentials from elsewhere) and pass them here. `remember=True`
    asks PSCAD to keep the session logged in for next time.
    """
    return _safe(session.app.login, username, password, remember=remember)


@mcp.tool()
def pscad_logout() -> dict[str, Any]:
    """Log out of the current PSCAD MyCentre account."""
    return _safe(session.app.logout)


@mcp.tool()
def pscad_discover_certificates(refresh: bool = True) -> dict[str, Any]:
    """List the license certificates available to the logged-in account.

    Call this after `pscad_login` (or if already logged in) to see what
    can be checked out -- e.g. an EDU or Professional seat. Each result's
    `certificate_key` is what `pscad_acquire_certificate` expects.
    """

    def _discover() -> dict[str, Any]:
        certs = session.app.get_available_certificates(refresh=refresh)
        return {
            "certificates": [
                {"certificate_key": key, "description": str(cert)}
                for key, cert in certs.items()
            ]
        }

    return _safe(_discover)


@mcp.tool()
def pscad_acquire_certificate(certificate_key: int) -> dict[str, Any]:
    """Check out a license certificate by its key (from pscad_discover_certificates).

    This is what actually makes `pscad_run_project` able to run a
    simulation rather than just build one. Holding a certificate consumes
    one seat of a (possibly seat-limited) license for as long as this
    PSCAD process stays open; release it with `pscad_release_certificate`
    if the user wants to free that seat for someone else.
    """

    def _acquire() -> dict[str, Any]:
        app = session.app
        certs = app.get_available_certificates(refresh=False)
        if certificate_key not in certs:
            raise KeyError(
                f"certificate_key {certificate_key} not found; call "
                "pscad_discover_certificates again to refresh the list"
            )
        result = app.get_certificate(certs[certificate_key])
        cert = app.get_current_certificate()
        return {"result": result, "current_certificate": str(cert) if cert else None}

    return _safe(_acquire)


@mcp.tool()
def pscad_release_certificate() -> dict[str, Any]:
    """Release the currently held license certificate, freeing that seat."""
    return _safe(session.app.release_certificate)


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------


@mcp.tool()
def pscad_load(paths: list[str], folder: Optional[str] = None) -> dict[str, Any]:
    """Load a workspace file, or one or more project files, into PSCAD.

    Args:
        paths: One or more .pscx/.pslx (project) or .pswx (workspace) file
            paths to load.
        folder: Optional base folder; `paths` are resolved relative to it.
    """
    return _safe(session.app.load, *paths, folder=folder)


@mcp.tool()
def pscad_list_projects() -> dict[str, Any]:
    """List every project (case or library) currently loaded in the workspace."""
    return _safe(lambda: {"projects": session.app.projects()})


@mcp.tool()
def pscad_new_workspace(filename: str = "NewWorkspace.pswx") -> dict[str, Any]:
    """Discard the current workspace and start a new, empty one."""
    return _safe(session.app.new_workspace, filename)


@mcp.tool()
def pscad_save_workspace(filename: Optional[str] = None) -> dict[str, Any]:
    """Save the current workspace (optionally under a new filename)."""
    return _safe(session.app.save_workspace, filename)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

_PROJECT_TYPES = {"case": 1, "library": 2}


@mcp.tool()
def pscad_create_project(name: str, folder: str, project_type: str = "case") -> dict[str, Any]:
    """Create a new, empty project in the workspace.

    Args:
        name: Project name (must follow PSCAD naming rules: starts with a
            letter, letters/digits/underscore only).
        folder: Directory the project file will be saved into.
        project_type: "case" (a runnable simulation, most common) or
            "library" (a reusable component library, no Main canvas run).
    """
    if project_type not in _PROJECT_TYPES:
        return _err(ValueError(f"project_type must be one of {list(_PROJECT_TYPES)}"))
    return _safe(
        session.app.create_project,
        _PROJECT_TYPES[project_type],
        name,
        folder,
    )


@mcp.tool()
def pscad_project_info(name: str) -> dict[str, Any]:
    """Get metadata about a loaded project: filename, dirty state, scenarios, layers."""

    def _info() -> dict[str, Any]:
        prj = session.project(name)
        return {
            "name": prj.name,
            "filename": str(prj.filename),
            "is_dirty": prj.is_dirty(),
            "scenarios": prj.scenarios(),
            "layers": prj.layers(),
            "definitions": prj.definitions(),
        }

    return _safe(_info)


@mcp.tool()
def pscad_save_project(name: str) -> dict[str, Any]:
    """Save a project's unsaved changes to disk."""
    return _safe(session.project(name).save)


@mcp.tool()
def pscad_save_project_as(name: str, new_filename: str, folder: Optional[str] = None) -> dict[str, Any]:
    """Save a project under a new name/location, returning the new project."""

    def _save_as() -> dict[str, Any]:
        new_prj = session.project(name).save_as(new_filename, folder=folder)
        return {"new_name": new_prj.name, "new_filename": str(new_prj.filename)}

    return _safe(_save_as)


@mcp.tool()
def pscad_unload_project(name: str) -> dict[str, Any]:
    """Unload (close) a project from the workspace without deleting its file."""
    return _safe(session.project(name).unload)


@mcp.tool()
def pscad_build_project(name: str) -> dict[str, Any]:
    """Clean and build a project (and its dependencies) without running it."""
    return _safe(session.project(name).build)


@mcp.tool()
def pscad_build_all() -> dict[str, Any]:
    """Build every project currently loaded in the workspace."""
    return _safe(session.app.build_all)


@mcp.tool()
def pscad_get_messages(name: str) -> dict[str, Any]:
    """Get the build/load message list (errors, warnings, info) for a project."""

    def _msgs() -> dict[str, Any]:
        prj = session.project(name)
        msgs = [str(m) for m in prj.messages()]
        return {"messages": msgs}

    return _safe(_msgs)


@mcp.tool()
def pscad_run_project(name: str, wait: bool = True, poll_interval: float = 0.5) -> dict[str, Any]:
    """Build and run a project's simulation (its Main canvas).

    Args:
        name: Project (case) name to run.
        wait: Block until the run finishes (recommended for agents -- the
            tool call returns only once the simulation is done). If False,
            returns immediately; poll with pscad_get_run_status.
        poll_interval: Seconds between busy-polls while waiting.
    """

    def _run() -> dict[str, Any]:
        prj = session.project(name)
        app = session.app
        prj.run()
        if wait:
            app.wait_for_idle(poll_interval=poll_interval)
        status, pct = prj.run_status()
        return {"name": name, "run_status": status, "percent": pct}

    return _safe(_run)


@mcp.tool()
def pscad_stop_run() -> dict[str, Any]:
    """Stop all currently running project simulations."""
    return _safe(session.app.stop_run)


@mcp.tool()
def pscad_get_run_status(name: str) -> dict[str, Any]:
    """Check the run status (e.g. running/stopped, percent complete) of a project."""

    def _status() -> dict[str, Any]:
        status, pct = session.project(name).run_status()
        return {"status": status, "percent": pct}

    return _safe(_status)


@mcp.tool()
def pscad_get_project_parameters(name: str) -> dict[str, Any]:
    """Get a project's simulation-wide parameters (duration, time step, etc)."""
    return _safe(lambda: {"parameters": dict(session.project(name).parameters())})


@mcp.tool()
def pscad_set_project_parameters(name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Set a project's simulation-wide parameters.

    Common keys: ``time_duration`` (seconds), ``time_step`` (microseconds),
    ``PlotStep``, ``StartType`` (0=standard, 1=snapshot start),
    ``SnapTime``, ``description``. Use pscad_get_project_parameters first to
    see the current keys/values for this project.
    """
    return _safe(session.project(name).set_parameters, **parameters)


# ---------------------------------------------------------------------------
# Canvas / components
# ---------------------------------------------------------------------------


def _get_canvas(project_name: str, canvas_name: str = "Main"):
    prj = session.project(project_name)
    return prj.canvas(canvas_name)


@mcp.tool()
def pscad_list_components(project: str, canvas: str = "Main") -> dict[str, Any]:
    """List every component on a project's canvas (default: the Main page)."""

    def _list() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        comps = []
        for c in cv.components():
            try:
                name = dict(c.parameters()).get("Name")
            except Exception:
                name = None  # wires and a few other component kinds have no parameters
            comps.append(
                {
                    "iid": c.iid,
                    "defn_name": c.defn_name,
                    "name": name,
                    "location": c.location,
                }
            )
        return {"components": comps}

    return _safe(_list)


@mcp.tool()
def pscad_add_component(
    project: str,
    library: str,
    name: str,
    canvas: str = "Main",
    x: int = 36,
    y: int = 36,
    orient: int = 0,
    parameters: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Place a new component instance on a canvas.

    Args:
        project: Project name.
        library: Defining library name, e.g. "master" for the standard
            PSCAD master library.
        name: Component definition name within that library, e.g.
            "source3", "resistor", "ground".
        canvas: Canvas (page) name within the project, default "Main".
        x, y: Grid position in PSCAD canvas units.
        orient: Orientation code (0, 90, 180, 270, and mirrored variants).
        parameters: Initial component parameters as key=value pairs, e.g.
            {"R": "50 [ohm]"}.
    """

    def _add() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        comp = cv.add_component(library, name, x, y, orient, **(parameters or {}))
        return {"iid": comp.iid, "defn_name": comp.defn_name, "location": comp.location}

    return _safe(_add)


@mcp.tool()
def pscad_get_component_parameters(project: str, iid: int, canvas: str = "Main") -> dict[str, Any]:
    """Get all parameters of one component, by its instance id (iid)."""

    def _get() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        comp = cv.component(iid)
        return {"parameters": dict(comp.parameters())}

    return _safe(_get)


@mcp.tool()
def pscad_set_component_parameters(
    project: str, iid: int, parameters: dict[str, Any], canvas: str = "Main"
) -> dict[str, Any]:
    """Set one or more parameters on a component, by its instance id (iid)."""

    def _set() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        comp = cv.component(iid)
        comp.set_parameters(**parameters)
        return {"iid": iid, "parameters": dict(comp.parameters())}

    return _safe(_set)


@mcp.tool()
def pscad_find_component(
    project: str,
    canvas: str = "Main",
    name: Optional[str] = None,
    defn: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Find components on a canvas by Name field, definition, and/or parameter values.

    Returns every match (use this to locate a component you placed earlier,
    e.g. by the "Name" you gave it, instead of tracking its iid yourself).
    """

    def _find() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        names = [n for n in (defn, name) if n]
        matches = cv.find_all(*names, **(params or {}))
        return {
            "matches": [
                {"iid": c.iid, "defn_name": c.defn_name, "location": c.location}
                for c in matches
            ]
        }

    return _safe(_find)


@mcp.tool()
def pscad_delete_component(project: str, iid: int, canvas: str = "Main") -> dict[str, Any]:
    """Delete a component from a canvas, by its instance id (iid)."""

    def _delete() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        comp = cv.component(iid)
        ok = cv.delete(comp)
        return {"deleted": ok}

    return _safe(_delete)


@mcp.tool()
def pscad_move_component(project: str, iid: int, x: int, y: int, canvas: str = "Main") -> dict[str, Any]:
    """Move a component to a new (x, y) position on its canvas."""

    def _move() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        comp = cv.component(iid)
        comp.set_location(x, y)
        return {"iid": iid, "location": comp.location}

    return _safe(_move)


@mcp.tool()
def pscad_create_wire(project: str, vertices: list[list[int]], canvas: str = "Main") -> dict[str, Any]:
    """Draw a wire connecting a sequence of (x, y) points on a canvas.

    Args:
        vertices: List of [x, y] grid-coordinate pairs, e.g.
            [[36, 36], [72, 36]] for a straight horizontal wire. Each point
            should land on a component's electrical port to actually
            connect it.
    """

    def _wire() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        pts = [tuple(v) for v in vertices]
        wire = cv.create_wire(*pts)
        return {"created": wire is not None}

    return _safe(_wire)


@mcp.tool()
def pscad_create_connection(
    project: str,
    from_point: list[int],
    to_point: list[int],
    canvas: str = "Main",
) -> dict[str, Any]:
    """Connect two points on a canvas directly (PSCAD routes the wire).

    Simpler than pscad_create_wire for a straight port-to-port link: give
    the two endpoint coordinates and let PSCAD figure out the routing.
    """

    def _connect() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        label = cv.create_connection(tuple(from_point), tuple(to_point))
        return {"label": label}

    return _safe(_connect)


@mcp.tool()
def pscad_create_graph(project: str, pgb_iid: int, canvas: str = "Main", x: int = 1, y: int = 1) -> dict[str, Any]:
    """Create a visible graph frame plotting a PGB (output channel) component.

    This adds the same kind of runtime scope PSCAD's GUI shows while a
    simulation runs -- useful when a human wants to visually confirm a
    run worked in the PSCAD window itself, not just read the numbers back
    through pscad_get_trace_data. `pgb_iid` is a master:pgb component's
    iid (see pscad_list_components).
    """

    def _graph() -> dict[str, Any]:
        cv = _get_canvas(project, canvas)
        pgb = cv.component(pgb_iid)
        frame, overlay, curve = cv.create_graph(pgb, x, y)
        return {"graph_frame_iid": frame.iid}

    return _safe(_graph)


# ---------------------------------------------------------------------------
# Simulation sets (multi-project / batch runs)
# ---------------------------------------------------------------------------


@mcp.tool()
def pscad_list_simulation_sets() -> dict[str, Any]:
    """List the names of all simulation sets defined in the workspace."""
    return _safe(lambda: {"simulation_sets": session.app.simulation_sets()})


@mcp.tool()
def pscad_create_simulation_set(set_name: str) -> dict[str, Any]:
    """Create a new, empty simulation set (a named group of projects to run together)."""
    return _safe(lambda: {"created": session.app.create_simulation_set(set_name).name()})


@mcp.tool()
def pscad_add_task_to_simulation_set(set_name: str, project_name: str) -> dict[str, Any]:
    """Add a project as a task within an existing simulation set."""

    def _add() -> dict[str, Any]:
        sim_set = session.app.simulation_set(set_name)
        task = sim_set.add_task(project_name)
        return {"task_namespace": task.namespace()}

    return _safe(_add)


@mcp.tool()
def pscad_run_simulation_set(set_name: str, wait: bool = True, poll_interval: float = 0.5) -> dict[str, Any]:
    """Build and run every task in a simulation set (parallel/batch run)."""

    def _run() -> dict[str, Any]:
        sim_set = session.app.simulation_set(set_name)
        sim_set.run()
        if wait:
            session.app.wait_for_idle(poll_interval=poll_interval)
        return {"ran": set_name, "tasks": sim_set.list_tasks()}

    return _safe(_run)


# ---------------------------------------------------------------------------
# Results (.psout files)
# ---------------------------------------------------------------------------


@mcp.tool()
def pscad_find_output_file(project: str) -> dict[str, Any]:
    """Locate the .psout result file produced by a project's last run.

    PSCAD writes results under the project's temp build folder. Call this
    after pscad_run_project to get the path to feed into the
    pscad_list_output_* / pscad_get_trace_data tools.
    """

    def _find() -> dict[str, Any]:
        prj = session.project(project)
        temp_folder = Path(str(prj.temp_folder))
        candidates = sorted(temp_folder.glob("*.psout"))
        if not candidates:
            return {"found": False, "temp_folder": str(temp_folder)}
        return {"found": True, "path": str(candidates[-1]), "all": [str(c) for c in candidates]}

    return _safe(_find)


@mcp.tool()
def pscad_list_output_runs(psout_path: str) -> dict[str, Any]:
    """List the runs stored in a .psout result file (usually just one)."""
    return _safe(results_mod.list_runs, psout_path)


@mcp.tool()
def pscad_list_output_channels(psout_path: str, run_index: int = 0) -> dict[str, Any]:
    """List every output channel (trace) recorded in a run, with its path and size."""
    return _safe(results_mod.list_channels, psout_path, run_index)


@mcp.tool()
def pscad_get_trace_data(
    psout_path: str,
    channel_path: str,
    run_index: int = 0,
    max_points: int = 2000,
) -> dict[str, Any]:
    """Fetch a single output channel's time-series data plus min/max/mean.

    Data is decimated to at most `max_points` samples to stay small; the
    returned `decimation_step` tells you how many raw samples each point
    represents. Get `channel_path` from pscad_list_output_channels.
    """
    return _safe(results_mod.get_trace, psout_path, channel_path, run_index, max_points)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
