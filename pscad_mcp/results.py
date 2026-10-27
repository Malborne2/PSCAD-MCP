"""
Reads PSCAD simulation output (.psout) files via the mhi.psout library.

Kept separate from session.py because reading results needs no live PSCAD
connection at all -- a .psout file can be inspected long after PSCAD has
closed, which is useful for an agent that just wants the numbers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mhi.psout


def _open(psout_path: str):
    path = Path(psout_path)
    if not path.exists():
        raise FileNotFoundError(f"No .psout file at {path}")
    return mhi.psout.File(str(path))


def list_runs(psout_path: str) -> dict[str, Any]:
    with _open(psout_path) as f:
        runs = []
        for run in f.runs():
            runs.append({"id": run.id, "num_traces": run.num_traces, **run.variables()})
        return {"path": psout_path, "num_runs": f.num_runs, "runs": runs}


def list_channels(psout_path: str, run_index: int = 0) -> dict[str, Any]:
    with _open(psout_path) as f:
        run = f.run(run_index)
        channels = []
        for trace, path in run.trace_paths():
            channels.append(
                {
                    "path": path,
                    "id": trace.id,
                    "size": trace.size,
                    "vars": trace.variables(),
                }
            )
        return {"path": psout_path, "run_id": run.id, "channels": channels}


def get_trace(
    psout_path: str,
    channel_path: str,
    run_index: int = 0,
    max_points: int = 2000,
) -> dict[str, Any]:
    """Fetch a trace's data, downsampled to at most ``max_points`` samples.

    Returns min/max/mean over the full series plus a (possibly decimated)
    list of [t, value] points, so large runs don't flood an agent's context.
    """
    with _open(psout_path) as f:
        run = f.run(run_index)
        trace = run.call(channel_path, sep="/")
        data = list(trace.data)
        domain = trace.domain
        times = list(domain.data) if domain is not None else list(range(len(data)))

        n = len(data)
        if n == 0:
            return {"path": channel_path, "run_id": run.id, "num_samples": 0, "points": []}

        step = max(1, n // max_points)
        points = [[times[i], data[i]] for i in range(0, n, step)]

        return {
            "path": channel_path,
            "run_id": run.id,
            "num_samples": n,
            "min": min(data),
            "max": max(data),
            "mean": sum(data) / n,
            "decimation_step": step,
            "points": points,
        }
