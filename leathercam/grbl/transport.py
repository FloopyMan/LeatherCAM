"""Synchronous GRBL 1.1 transport.

Implements the standard character-counting flow control:
- GRBL has a 128-byte serial RX buffer (RX_BUFFER_SIZE).
- We track how many bytes are in flight (sent but not yet acknowledged
  by "ok" or "error:N"); we only send the next line if it still fits.
- When GRBL replies "ok"/"error", we pop the oldest line length and try
  to send more.

Realtime commands (~, !, Ctrl-X / 0x18, ?) are written outside the
character-counting accounting — GRBL handles them in interrupt context
and does not buffer them in the line queue.

The transport is Qt-free; the UI wraps it in a QThread worker.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Iterable
from typing import Protocol

GRBL_RX_BUFFER_SIZE = 128
DEFAULT_BAUDRATE = 115200
REALTIME_PAUSE = b"!"
REALTIME_RESUME = b"~"
REALTIME_SOFT_RESET = b"\x18"
REALTIME_STATUS = b"?"


class SerialLike(Protocol):
    """Minimal subset of pyserial.Serial that the transport needs."""

    def write(self, data: bytes) -> int: ...

    def readline(self) -> bytes: ...

    def close(self) -> None: ...

    @property
    def in_waiting(self) -> int: ...


class TransportError(RuntimeError):
    pass


class GrblTransport:
    def __init__(self, serial_factory: Callable[[str, int], SerialLike] | None = None) -> None:
        self._serial: SerialLike | None = None
        self._factory = serial_factory or _default_factory
        self._abort = False

    @property
    def connected(self) -> bool:
        return self._serial is not None

    def connect(self, port: str, baudrate: int = DEFAULT_BAUDRATE) -> None:
        if self._serial is not None:
            raise TransportError("already connected")
        self._serial = self._factory(port, baudrate)
        self._abort = False

    def disconnect(self) -> None:
        if self._serial is None:
            return
        self._serial.close()
        self._serial = None

    def send_command(self, command: str, *, timeout_s: float = 2.0) -> str:
        """Send a single line and block until GRBL replies with ok/error."""
        if self._serial is None:
            raise TransportError("not connected")
        line = _normalize(command)
        self._serial.write(line.encode("ascii"))
        return _read_until_ack(self._serial, timeout_s=timeout_s)

    def request_status(self) -> None:
        """Fire-and-forget realtime status request (?). Reply arrives asynchronously."""
        if self._serial is None:
            raise TransportError("not connected")
        self._serial.write(REALTIME_STATUS)

    def pause(self) -> None:
        self._write_realtime(REALTIME_PAUSE)

    def resume(self) -> None:
        self._write_realtime(REALTIME_RESUME)

    def soft_reset(self) -> None:
        self._abort = True
        self._write_realtime(REALTIME_SOFT_RESET)

    def stream(
        self,
        lines: Iterable[str],
        *,
        on_line_sent: Callable[[int, str], None] | None = None,
        on_ack: Callable[[int, str], None] | None = None,
        poll_interval_s: float = 0.005,
    ) -> None:
        """Stream a sequence of G-code lines using character counting.

        Blocks until every line has been acknowledged by GRBL (or until
        soft_reset() flips the abort flag). Callers usually run this from
        a worker thread.
        """
        if self._serial is None:
            raise TransportError("not connected")
        self._abort = False
        pending: deque[tuple[int, int, str]] = deque()
        bytes_in_buffer = 0
        index = 0
        ack_count = 0
        iterator = iter(lines)
        source_exhausted = False

        while not self._abort:
            while not source_exhausted:
                try:
                    raw = next(iterator)
                except StopIteration:
                    source_exhausted = True
                    break
                line = _normalize(raw)
                if not line.strip():
                    continue
                size = len(line)
                if size > GRBL_RX_BUFFER_SIZE:
                    raise TransportError(f"line too long ({size} > {GRBL_RX_BUFFER_SIZE})")
                if bytes_in_buffer + size > GRBL_RX_BUFFER_SIZE:
                    iterator = _replay(line, iterator)
                    break
                self._serial.write(line.encode("ascii"))
                pending.append((index, size, line))
                bytes_in_buffer += size
                if on_line_sent is not None:
                    on_line_sent(index, line)
                index += 1

            if not pending:
                if source_exhausted:
                    return
                continue

            reply = self._serial.readline().decode("ascii", errors="replace").strip()
            if not reply:
                time.sleep(poll_interval_s)
                continue
            if reply.startswith("ok") or reply.startswith("error"):
                idx, size, _line = pending.popleft()
                bytes_in_buffer -= size
                ack_count += 1
                if on_ack is not None:
                    on_ack(idx, reply)
                if reply.startswith("error"):
                    raise TransportError(f"GRBL reported {reply} on line {idx}")

        if self._abort:
            raise TransportError("stream aborted by soft reset")

    def _write_realtime(self, byte: bytes) -> None:
        if self._serial is None:
            raise TransportError("not connected")
        self._serial.write(byte)


def _normalize(line: str) -> str:
    stripped = line.strip()
    return stripped + "\n" if stripped else "\n"


def _read_until_ack(serial: SerialLike, *, timeout_s: float) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        reply = serial.readline().decode("ascii", errors="replace").strip()
        if not reply:
            continue
        if reply.startswith("ok") or reply.startswith("error"):
            return reply
    raise TransportError("timeout waiting for ok/error")


def _replay(line: str, iterator: Iterable[str]) -> Iterable[str]:
    """Yield `line` first, then drain the remaining iterator."""

    def gen() -> Iterable[str]:
        yield line
        yield from iterator

    return iter(gen())


def _default_factory(port: str, baudrate: int) -> SerialLike:
    import serial  # imported lazily so unit tests don't need pyserial

    return serial.Serial(port=port, baudrate=baudrate, timeout=0.1)
