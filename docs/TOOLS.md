# PSCAD MCP -- Tool Reference

Auto-generated from the live tool registry (`gen_tool_docs.py`). Every tool returns a JSON object with `ok: true/false`; on failure, `error` and `error_type` describe what went wrong (the real exception from the PSCAD Automation Library, not a generic message).

## Connection & Application

### `pscad_connect`

Connect to PSCAD: attach to a running instance, or launch a new one.

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


| Parameter | Type | Required | Default |
|---|---|---|---|
| `prefer_launch` | boolean | no | True |
| `version` | string \| null | no | None |
| `minimize` | boolean | no | True |
| `silence` | boolean | no | True |
| `timeout` | integer | no | 60 |

### `pscad_status`

Report connection state, license state, and version of PSCAD.

*(no parameters)*

### `pscad_disconnect`

Close our connection to PSCAD, leaving the application running.

*(no parameters)*

### `pscad_quit`

Terminate the PSCAD application process entirely.

Destructive: any unsaved changes in open projects are lost. Confirm
with the user before calling this unless they explicitly asked to
close PSCAD.


*(no parameters)*

### `pscad_license_status`

Report licensing status: logged in, licensed, current certificate.

Call this before anything that needs to actually *run* a simulation
(building/editing generally works on an unlicensed/trial install, but
running does not). If `logged_in` is false, PSCAD needs a MyCentre
account login before it can check out a certificate -- see
`pscad_login`. If `logged_in` is true but `current_certificate` is
null, call `pscad_discover_certificates` then `pscad_acquire_certificate`.


*(no parameters)*

### `pscad_login`

Log in to a PSCAD MyCentre account to enable license checkout.

PSCAD occasionally needs this to validate a license -- without it, a
project can usually still be opened/edited but a simulation *run* can
fail with a generic, unhelpful error. Call `pscad_license_status`
first; if it reports `needs_login: true`, ask the human operating
this agent for their MyCentre username/password (never invent or
reuse credentials from elsewhere) and pass them here. `remember=True`
asks PSCAD to keep the session logged in for next time.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `username` | string | yes |  |
| `password` | string | yes |  |
| `remember` | boolean | no | False |

### `pscad_logout`

Log out of the current PSCAD MyCentre account.

*(no parameters)*

### `pscad_discover_certificates`

List the license certificates available to the logged-in account.

Call this after `pscad_login` (or if already logged in) to see what
can be checked out -- e.g. an EDU or Professional seat. Each result's
`certificate_key` is what `pscad_acquire_certificate` expects.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `refresh` | boolean | no | True |

### `pscad_acquire_certificate`

Check out a license certificate by its key (from pscad_discover_certificates).

This is what actually makes `pscad_run_project` able to run a
simulation rather than just build one. Holding a certificate consumes
one seat of a (possibly seat-limited) license for as long as this
PSCAD process stays open; release it with `pscad_release_certificate`
if the user wants to free that seat for someone else.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `certificate_key` | integer | yes |  |

### `pscad_release_certificate`

Release the currently held license certificate, freeing that seat.

*(no parameters)*

## Workspace

### `pscad_load`

Load a workspace file, or one or more project files, into PSCAD.

Args:
    paths: One or more .pscx/.pslx (project) or .pswx (workspace) file
        paths to load.
    folder: Optional base folder; `paths` are resolved relative to it.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `paths` | array | yes |  |
| `folder` | string \| null | no | None |

### `pscad_list_projects`

List every project (case or library) currently loaded in the workspace.

*(no parameters)*

### `pscad_new_workspace`

Discard the current workspace and start a new, empty one.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `filename` | string | no | NewWorkspace.pswx |

### `pscad_save_workspace`

Save the current workspace (optionally under a new filename).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `filename` | string \| null | no | None |

## Projects

### `pscad_create_project`

Create a new, empty project in the workspace.

Args:
    name: Project name (must follow PSCAD naming rules: starts with a
        letter, letters/digits/underscore only).
    folder: Directory the project file will be saved into.
    project_type: "case" (a runnable simulation, most common) or
        "library" (a reusable component library, no Main canvas run).


| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |
| `folder` | string | yes |  |
| `project_type` | string | no | case |

### `pscad_project_info`

Get metadata about a loaded project: filename, dirty state, scenarios, layers.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |

### `pscad_save_project`

Save a project's unsaved changes to disk.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |

### `pscad_save_project_as`

Save a project under a new name/location, returning the new project.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |
| `new_filename` | string | yes |  |
| `folder` | string \| null | no | None |

### `pscad_unload_project`

Unload (close) a project from the workspace without deleting its file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |

### `pscad_build_project`

Clean and build a project (and its dependencies) without running it.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |

### `pscad_build_all`

Build every project currently loaded in the workspace.

*(no parameters)*

### `pscad_get_messages`

Get the build/load message list (errors, warnings, info) for a project.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |

### `pscad_run_project`

Build and run a project's simulation (its Main canvas).

Args:
    name: Project (case) name to run.
    wait: Block until the run finishes (recommended for agents -- the
        tool call returns only once the simulation is done). If False,
        returns immediately; poll with pscad_get_run_status.
    poll_interval: Seconds between busy-polls while waiting.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |
| `wait` | boolean | no | True |
| `poll_interval` | number | no | 0.5 |

### `pscad_stop_run`

Stop all currently running project simulations.

*(no parameters)*

### `pscad_get_run_status`

Check the run status (e.g. running/stopped, percent complete) of a project.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |

### `pscad_get_project_parameters`

Get a project's simulation-wide parameters (duration, time step, etc).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |

### `pscad_set_project_parameters`

Set a project's simulation-wide parameters.

Common keys: ``time_duration`` (seconds), ``time_step`` (microseconds),
``PlotStep``, ``StartType`` (0=standard, 1=snapshot start),
``SnapTime``, ``description``. Use pscad_get_project_parameters first to
see the current keys/values for this project.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes |  |
| `parameters` | object | yes |  |

## Canvas & Components

### `pscad_list_components`

List every component on a project's canvas (default: the Main page).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `canvas` | string | no | Main |

### `pscad_add_component`

Place a new component instance on a canvas.

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


| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `library` | string | yes |  |
| `name` | string | yes |  |
| `canvas` | string | no | Main |
| `x` | integer | no | 36 |
| `y` | integer | no | 36 |
| `orient` | integer | no | 0 |
| `parameters` | object \| null | no | None |

### `pscad_get_component_parameters`

Get all parameters of one component, by its instance id (iid).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `iid` | integer | yes |  |
| `canvas` | string | no | Main |

### `pscad_set_component_parameters`

Set one or more parameters on a component, by its instance id (iid).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `iid` | integer | yes |  |
| `parameters` | object | yes |  |
| `canvas` | string | no | Main |

### `pscad_find_component`

Find components on a canvas by Name field, definition, and/or parameter values.

Returns every match (use this to locate a component you placed earlier,
e.g. by the "Name" you gave it, instead of tracking its iid yourself).


| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `canvas` | string | no | Main |
| `name` | string \| null | no | None |
| `defn` | string \| null | no | None |
| `params` | object \| null | no | None |

### `pscad_delete_component`

Delete a component from a canvas, by its instance id (iid).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `iid` | integer | yes |  |
| `canvas` | string | no | Main |

### `pscad_move_component`

Move a component to a new (x, y) position on its canvas.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `iid` | integer | yes |  |
| `x` | integer | yes |  |
| `y` | integer | yes |  |
| `canvas` | string | no | Main |

### `pscad_create_wire`

Draw a wire connecting a sequence of (x, y) points on a canvas.

Args:
    vertices: List of [x, y] grid-coordinate pairs, e.g.
        [[36, 36], [72, 36]] for a straight horizontal wire. Each point
        should land on a component's electrical port to actually
        connect it.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `vertices` | array | yes |  |
| `canvas` | string | no | Main |

### `pscad_create_connection`

Connect two points on a canvas directly (PSCAD routes the wire).

Simpler than pscad_create_wire for a straight port-to-port link: give
the two endpoint coordinates and let PSCAD figure out the routing.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `from_point` | array | yes |  |
| `to_point` | array | yes |  |
| `canvas` | string | no | Main |

### `pscad_create_graph`

Create a visible graph frame plotting a PGB (output channel) component.

This adds the same kind of runtime scope PSCAD's GUI shows while a
simulation runs -- useful when a human wants to visually confirm a
run worked in the PSCAD window itself, not just read the numbers back
through pscad_get_trace_data. `pgb_iid` is a master:pgb component's
iid (see pscad_list_components).


| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |
| `pgb_iid` | integer | yes |  |
| `canvas` | string | no | Main |
| `x` | integer | no | 1 |
| `y` | integer | no | 1 |

## Simulation Sets

### `pscad_list_simulation_sets`

List the names of all simulation sets defined in the workspace.

*(no parameters)*

### `pscad_create_simulation_set`

Create a new, empty simulation set (a named group of projects to run together).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `set_name` | string | yes |  |

### `pscad_add_task_to_simulation_set`

Add a project as a task within an existing simulation set.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `set_name` | string | yes |  |
| `project_name` | string | yes |  |

### `pscad_run_simulation_set`

Build and run every task in a simulation set (parallel/batch run).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `set_name` | string | yes |  |
| `wait` | boolean | no | True |
| `poll_interval` | number | no | 0.5 |

## Results (.psout)

### `pscad_find_output_file`

Locate the .psout result file produced by a project's last run.

PSCAD writes results under the project's temp build folder. Call this
after pscad_run_project to get the path to feed into the
pscad_list_output_* / pscad_get_trace_data tools.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `project` | string | yes |  |

### `pscad_list_output_runs`

List the runs stored in a .psout result file (usually just one).

| Parameter | Type | Required | Default |
|---|---|---|---|
| `psout_path` | string | yes |  |

### `pscad_list_output_channels`

List every output channel (trace) recorded in a run, with its path and size.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `psout_path` | string | yes |  |
| `run_index` | integer | no | 0 |

### `pscad_get_trace_data`

Fetch a single output channel's time-series data plus min/max/mean.

Data is decimated to at most `max_points` samples to stay small; the
returned `decimation_step` tells you how many raw samples each point
represents. Get `channel_path` from pscad_list_output_channels.


| Parameter | Type | Required | Default |
|---|---|---|---|
| `psout_path` | string | yes |  |
| `channel_path` | string | yes |  |
| `run_index` | integer | no | 0 |
| `max_points` | integer | no | 2000 |
