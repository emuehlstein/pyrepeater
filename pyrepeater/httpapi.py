"""
tiny stdlib-only HTTP control API for pyrepeater

Deliberately dependency-free (asyncio.start_server + a minimal request parser)
so the pi needs no new packages in its pipenv.

Endpoints:
    GET  /status    -> JSON snapshot of controller/repeater/sleep state
    POST /announce  -> queue the repeater info announcement (+ CW ID)
    POST /id        -> queue an immediate CW ID
    GET  /healthz   -> liveness probe

GET is also accepted on /announce and /id for convenience from a browser
or a bare curl, since this listens on a trusted LAN/tailnet only.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Tuple

from .modes import current_mode

logger = logging.getLogger(__name__)

MAX_REQUEST_BYTES = 8192


def _iso(value: Optional[datetime]) -> Optional[str]:
    """serialize a datetime, tolerating None"""
    return value.isoformat(timespec="seconds") if value else None


class ControlApi:
    """serves the control API against a live Controller instance"""

    def __init__(self, controller, settings) -> None:
        self.controller = controller
        self.settings = settings
        self._server: Optional[asyncio.AbstractServer] = None

    # ── lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """bind the listener; logs and continues on failure (API is optional)"""
        host = self.settings.http_host
        port = self.settings.http_port
        try:
            self._server = await asyncio.start_server(
                self._handle_client, host, port
            )
        except OSError as err:
            logger.error(
                "Control API unable to bind %s:%s (%s) - continuing without it",
                host,
                port,
                err,
            )
            return
        logger.info("Control API listening on http://%s:%s", host, port)

    async def stop(self) -> None:
        """close the listener"""
        if not self._server:
            return
        self._server.close()
        try:
            await self._server.wait_closed()
        except Exception:  # pragma: no cover - best-effort shutdown
            pass
        self._server = None

    # ── request handling ───────────────────────────────────────────

    async def _handle_client(self, reader, writer) -> None:
        """read one request, dispatch it, reply, close"""
        try:
            request_line = await asyncio.wait_for(
                reader.readline(), timeout=5.0
            )
            if not request_line:
                return

            # drain headers so the client sees a clean exchange
            consumed = len(request_line)
            while consumed < MAX_REQUEST_BYTES:
                header = await asyncio.wait_for(reader.readline(), timeout=5.0)
                consumed += len(header)
                if header in (b"\r\n", b"\n", b""):
                    break

            try:
                method, raw_path, _ = request_line.decode(
                    "latin-1"
                ).strip().split(" ", 2)
            except ValueError:
                await self._respond(writer, 400, {"error": "malformed request line"})
                return

            path = raw_path.split("?", 1)[0].rstrip("/") or "/"
            status, body = await self._dispatch(method.upper(), path)
            await self._respond(writer, status, body)

        except asyncio.TimeoutError:
            logger.debug("Control API client timed out")
        except Exception as err:  # keep the controller alive no matter what
            logger.error("Control API request error: %s", err)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # pragma: no cover
                pass

    async def _dispatch(self, method: str, path: str) -> Tuple[int, dict]:
        """route a request to its handler"""
        if path == "/healthz" and method in ("GET", "HEAD"):
            return 200, {"ok": True}

        if path == "/status" and method in ("GET", "HEAD"):
            return 200, await self._status()

        if path == "/announce" and method in ("GET", "POST"):
            return 200, await self._announce()

        if path == "/id" and method in ("GET", "POST"):
            return 200, await self._force_id()

        if path == "/net" and method in ("GET", "POST"):
            return 200, await self._net_toggle()

        if path == "/":
            return 200, {
                "service": "pyrepeater",
                "endpoints": ["/status", "/announce", "/id", "/net", "/healthz"],
            }

        return 404, {"error": "not found", "path": path}

    # ── handlers ───────────────────────────────────────────────────

    async def _status(self) -> dict:
        """snapshot of live controller state"""
        ctlr = self.controller
        status = ctlr.status
        sleeping = (
            await ctlr.sleep_mgr.is_sleeping() if ctlr.sleep_mgr else None
        )
        last_rcvd = await ctlr.repeater.check_last_rcvd()
        now = datetime.now()

        return {
            "fcc_id": self.settings.fcc_id,
            "mode": current_mode(self.settings, status.net_mode).value,
            "net_mode": status.net_mode,
            "busy": await ctlr.repeater.is_busy(),
            "sleeping": sleeping,
            "parrot_mode": status.parrot_mode,
            "pending_messages": len(status.pending_messages),
            "last_rcvd": _iso(last_rcvd),
            "secs_since_last_rcvd": round((now - last_rcvd).total_seconds(), 1),
            "last_id": _iso(status.last_id),
            "last_announcement": _iso(status.last_announcement),
            "id_mins": self.settings.id_mins,
            "rpt_info_mins": self.settings.rpt_info_mins,
            "server_time": _iso(now),
        }

    async def _announce(self) -> dict:
        """queue the info announcement plus CW ID, mirroring DTMF 311"""
        ctlr = self.controller
        ctlr.status.pending_messages.append(ctlr.sound("repeater_info.wav"))
        ctlr.status.last_announcement = datetime.now()
        ctlr.status.pending_messages.append(ctlr.sound("cw_id.wav"))
        ctlr.status.last_id = datetime.now()
        logger.info("Control API: announcement queued")
        return {
            "queued": ["repeater_info.wav", "cw_id.wav"],
            "pending_messages": len(ctlr.status.pending_messages),
        }

    async def _force_id(self) -> dict:
        """queue an immediate CW ID, mirroring DTMF 312"""
        ctlr = self.controller
        ctlr.status.pending_messages.append(ctlr.sound("cw_id.wav"))
        ctlr.status.last_id = datetime.now()
        logger.info("Control API: CW ID queued")
        return {
            "queued": ["cw_id.wav"],
            "pending_messages": len(ctlr.status.pending_messages),
        }

    async def _net_toggle(self) -> dict:
        """toggle net mode, mirroring the DTMF net toggle command"""
        ctlr = self.controller
        ctlr.status.net_mode = not ctlr.status.net_mode
        logger.info("Control API: net mode toggled to %s", ctlr.status.net_mode)
        return {"net_mode": ctlr.status.net_mode}

    # ── response ───────────────────────────────────────────────────

    async def _respond(self, writer, status: int, body: dict) -> None:
        """write a JSON response"""
        reasons = {200: "OK", 400: "Bad Request", 404: "Not Found"}
        payload = json.dumps(body, indent=2).encode("utf-8") + b"\n"
        head = (
            f"HTTP/1.1 {status} {reasons.get(status, 'OK')}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Cache-Control: no-store\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("latin-1")
        writer.write(head + payload)
        await writer.drain()
