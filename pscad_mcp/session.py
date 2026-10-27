"""
Manages the single, lazily-created connection to a PSCAD application instance.

PSCAD's Automation Library (``mhi.pscad``) talks to a running PSCAD process
over a local COM/RPC bridge. There is one PSCAD process per Python session
in practice, so this module keeps a process-wide singleton connection that
every MCP tool call reuses, instead of relaunching PSCAD on every call
(which would be slow and would spawn many copies of the app).
"""

from __future__ import annotations

import threading
from typing import Any, Optional

import mhi.pscad


class PscadNotConnected(RuntimeError):
    """Raised when a tool needs a live PSCAD connection and none exists yet."""


class PscadSession:
    """Owns the lazily-created connection to the PSCAD application."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pscad: Optional[mhi.pscad.PSCAD] = None
        self._launched_by_us = False

    # -- connection lifecycle -------------------------------------------------

    @property
    def is_connected(self) -> bool:
        if self._pscad is None:
            return False
        try:
            return self._pscad.is_alive()
        except Exception:
            return False

    def connect_or_launch(
        self,
        *,
        prefer_launch: bool = True,
        version: Optional[str] = None,
        minimize: bool = True,
        silence: bool = True,
        splash: bool = False,
        timeout: int = 60,
        port: Optional[int] = None,
    ) -> dict[str, Any]:
        """Attach to a running PSCAD instance, or launch a new one.

        Returns a status dict describing what happened.
        """
        with self._lock:
            if self.is_connected:
                return {"action": "already_connected", **self._describe()}

            # First, try to attach to an already-running PSCAD (fast, and
            # avoids spawning duplicate processes / certificate grabs).
            try:
                pscad = mhi.pscad.connect(timeout=2)
                self._pscad = pscad
                self._launched_by_us = False
                return {"action": "connected_existing", **self._describe()}
            except Exception:
                pass

            if not prefer_launch:
                raise PscadNotConnected(
                    "No running PSCAD instance found, and prefer_launch=False."
                )

            kwargs: dict[str, Any] = {
                "minimize": minimize,
                "silence": silence,
                "splash": splash,
                "timeout": timeout,
            }
            if version:
                kwargs["version"] = version
            if port:
                kwargs["port"] = port

            pscad = mhi.pscad.launch(**kwargs)
            self._pscad = pscad
            self._launched_by_us = True
            return {"action": "launched_new", **self._describe()}

    def disconnect(self) -> dict[str, Any]:
        """Close our connection, leaving the PSCAD application running."""
        with self._lock:
            if self._pscad is None:
                return {"action": "noop", "connected": False}
            try:
                self._pscad.close_connection()
            finally:
                self._pscad = None
                self._launched_by_us = False
            return {"action": "disconnected", "connected": False}

    def quit_application(self) -> dict[str, Any]:
        """Terminate the PSCAD application process itself."""
        with self._lock:
            if self._pscad is None:
                return {"action": "noop", "connected": False}
            try:
                self._pscad.quit()
            finally:
                self._pscad = None
                self._launched_by_us = False
            return {"action": "quit", "connected": False}

    # -- accessors --------------------------------------------------------

    @property
    def app(self) -> mhi.pscad.PSCAD:
        if not self.is_connected:
            raise PscadNotConnected(
                "Not connected to PSCAD. Call pscad_connect first."
            )
        assert self._pscad is not None
        return self._pscad

    def project(self, name: str):
        return self.app.project(name)

    def _describe(self) -> dict[str, Any]:
        p = self._pscad
        if p is None:
            return {"connected": False}
        info: dict[str, Any] = {"connected": True, "launched_by_mcp": self._launched_by_us}
        try:
            info["version"] = str(p.version)
        except Exception:
            pass
        try:
            info["licensed"] = p.licensed()
        except Exception:
            pass
        try:
            logged_in = p.logged_in()
            info["logged_in"] = logged_in
            if not logged_in:
                # Surfaced here so an agent immediately "sees" that a
                # MyCentre login is needed, instead of discovering it only
                # after some other call hangs on a login dialog it can't
                # see or answer. Use pscad_login to resolve this.
                info["needs_login"] = True
        except Exception:
            pass
        try:
            info["workspace_path"] = str(p.workspace_path)
        except Exception:
            pass
        return info


# Process-wide singleton used by every tool in server.py
session = PscadSession()
