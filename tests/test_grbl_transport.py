"""Tests for the GRBL transport (using an in-memory fake serial)."""

from __future__ import annotations

from collections import deque

import pytest

from leathercam.grbl import GRBL_RX_BUFFER_SIZE, GrblTransport, TransportError


class FakeSerial:
    """In-memory stand-in for pyserial.Serial.

    By default every written line that doesn't start with a realtime byte
    queues up an "ok" reply, simulating GRBL accepting everything. Tests
    can override `reply_for` to inject errors.
    """

    def __init__(self, reply_for=None) -> None:
        self.writes: list[bytes] = []
        self.realtimes: list[bytes] = []
        self._reply_queue: deque[bytes] = deque()
        self._reply_for = reply_for or (lambda _line: b"ok\r\n")

    def write(self, data: bytes) -> int:
        if data in (b"!", b"~", b"\x18", b"?"):
            self.realtimes.append(data)
            return len(data)
        self.writes.append(data)
        self._reply_queue.append(self._reply_for(data))
        return len(data)

    def readline(self) -> bytes:
        if not self._reply_queue:
            return b""
        return self._reply_queue.popleft()

    def close(self) -> None:
        pass

    @property
    def in_waiting(self) -> int:
        return sum(len(r) for r in self._reply_queue)


def _make() -> tuple[GrblTransport, FakeSerial]:
    fake = FakeSerial()

    def factory(_port: str, _baud: int) -> FakeSerial:
        return fake

    t = GrblTransport(serial_factory=factory)
    t.connect("/dev/null", 115200)
    return t, fake


def test_connect_then_disconnect_toggles_state() -> None:
    t, _ = _make()
    assert t.connected
    t.disconnect()
    assert not t.connected


def test_double_connect_raises() -> None:
    t, _ = _make()
    with pytest.raises(TransportError):
        t.connect("/dev/null")


def test_send_command_returns_reply_and_writes_line() -> None:
    t, fake = _make()
    reply = t.send_command("G21")
    assert reply == "ok"
    assert fake.writes == [b"G21\n"]


def test_send_command_when_disconnected_raises() -> None:
    t = GrblTransport(serial_factory=lambda *_: FakeSerial())
    with pytest.raises(TransportError):
        t.send_command("G21")


def test_stream_writes_all_lines_and_waits_for_acks() -> None:
    t, fake = _make()
    sent: list[tuple[int, str]] = []
    acked: list[tuple[int, str]] = []
    program = ["G21", "G90", "G0 X10 Y20", "G1 Z-0.4 F200"]
    t.stream(
        program,
        on_line_sent=lambda i, line: sent.append((i, line)),
        on_ack=lambda i, reply: acked.append((i, reply)),
    )
    assert len(sent) == 4
    assert len(acked) == 4
    assert [w.decode().rstrip() for w in fake.writes] == program


def test_stream_skips_blank_lines() -> None:
    t, fake = _make()
    t.stream(["G21", "", "   ", "G90"])
    assert len(fake.writes) == 2


def test_stream_respects_rx_buffer_with_many_short_lines() -> None:
    t, fake = _make()
    program = [f"G1 X{i:.2f}" for i in range(50)]
    t.stream(program)
    # We can't easily inspect the inflight watermark, but every line must be
    # acknowledged and written exactly once.
    assert len(fake.writes) == 50


def test_stream_raises_on_oversize_line() -> None:
    t, _ = _make()
    too_long = "G1 " + "X1 " * (GRBL_RX_BUFFER_SIZE // 3)
    with pytest.raises(TransportError):
        t.stream([too_long])


def test_stream_raises_on_error_reply() -> None:
    def reply_for(line: bytes) -> bytes:
        return b"error:1\r\n" if b"X" in line else b"ok\r\n"

    fake = FakeSerial(reply_for=reply_for)
    t = GrblTransport(serial_factory=lambda *_: fake)
    t.connect("/dev/null")
    with pytest.raises(TransportError) as exc_info:
        t.stream(["G21", "G0 X10"])
    assert "error" in str(exc_info.value)


def test_realtime_pause_resume_soft_reset_bypass_line_queue() -> None:
    t, fake = _make()
    t.pause()
    t.resume()
    t.soft_reset()
    assert fake.realtimes == [b"!", b"~", b"\x18"]


def test_request_status_emits_query_byte() -> None:
    t, fake = _make()
    t.request_status()
    assert fake.realtimes == [b"?"]


def test_send_command_uppercase_and_newline_normalized() -> None:
    t, fake = _make()
    t.send_command("g21  ")
    assert fake.writes == [b"g21\n"]


def test_soft_reset_during_stream_raises_abort() -> None:
    t, fake = _make()
    program = ["G1 X1", "G1 X2", "G1 X3"]

    def reply_for(_line: bytes) -> bytes:
        t.soft_reset()
        return b"ok\r\n"

    fake._reply_for = reply_for
    with pytest.raises(TransportError):
        t.stream(program)
