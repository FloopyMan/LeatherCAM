"""Send-to-machine dialog for streaming G-code over serial to GRBL.

Streaming runs in a QThread so the UI stays responsive. Pause / resume /
stop call the realtime byte writers on the transport (they bypass the
character-counting queue).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from leathercam.grbl import DEFAULT_BAUDRATE, GrblTransport, TransportError, list_serial_ports

logger = logging.getLogger(__name__)


class StreamWorker(QObject):
    line_sent = Signal(int, str)
    acknowledged = Signal(int, str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, transport: GrblTransport, lines: list[str]) -> None:
        super().__init__()
        self._transport = transport
        self._lines = lines

    def run(self) -> None:
        try:
            self._transport.stream(
                self._lines,
                on_line_sent=lambda i, line: self.line_sent.emit(i, line),
                on_ack=lambda i, reply: self.acknowledged.emit(i, reply),
            )
        except TransportError as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit()


class MachineDialog(QDialog):
    def __init__(self, gcode: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Отправка G-code на станок")
        self.resize(560, 440)
        self._transport = GrblTransport()
        self._lines = [line for line in gcode.splitlines() if line.strip()]
        self._worker: StreamWorker | None = None
        self._thread: QThread | None = None

        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Обновить порты")
        self.refresh_button.clicked.connect(self._refresh_ports)
        self.baud_spin = QSpinBox()
        self.baud_spin.setRange(9600, 1_000_000)
        self.baud_spin.setSingleStep(9600)
        self.baud_spin.setValue(DEFAULT_BAUDRATE)
        self.connect_button = QPushButton("Подключиться")
        self.connect_button.clicked.connect(self._toggle_connection)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Порт:"))
        port_row.addWidget(self.port_combo, stretch=1)
        port_row.addWidget(self.refresh_button)
        port_row.addWidget(QLabel("Скорость:"))
        port_row.addWidget(self.baud_spin)
        port_row.addWidget(self.connect_button)

        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText("Ручная команда (например, G0 X10 или $H)")
        self.command_edit.returnPressed.connect(self._on_send_command)
        self.send_command_button = QPushButton("Отправить")
        self.send_command_button.clicked.connect(self._on_send_command)
        cmd_row = QHBoxLayout()
        cmd_row.addWidget(self.command_edit, stretch=1)
        cmd_row.addWidget(self.send_command_button)

        jog_box = QGridLayout()
        self.jog_step = QSpinBox()
        self.jog_step.setRange(1, 50)
        self.jog_step.setValue(5)
        self.jog_step.setSuffix(" мм")
        self.jog_feed = QSpinBox()
        self.jog_feed.setRange(50, 5000)
        self.jog_feed.setValue(800)
        self.jog_feed.setSuffix(" мм/мин")
        jog_box.addWidget(QLabel("Шаг:"), 0, 0)
        jog_box.addWidget(self.jog_step, 0, 1)
        jog_box.addWidget(QLabel("Подача:"), 0, 2)
        jog_box.addWidget(self.jog_feed, 0, 3)
        for label, dx, dy, dz, row, col in (
            ("Y+", 0, 1, 0, 1, 1),
            ("X-", -1, 0, 0, 2, 0),
            ("X+", 1, 0, 0, 2, 2),
            ("Y-", 0, -1, 0, 3, 1),
            ("Z+", 0, 0, 1, 1, 3),
            ("Z-", 0, 0, -1, 3, 3),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, x=dx, y=dy, z=dz: self._on_jog(x, y, z))
            jog_box.addWidget(btn, row, col)
        self.home_button = QPushButton("Home ($H)")
        self.home_button.clicked.connect(lambda: self._send_safe("$H"))
        self.zero_button = QPushButton("Zero XYZ (G92)")
        self.zero_button.clicked.connect(lambda: self._send_safe("G92 X0 Y0 Z0"))
        jog_box.addWidget(self.home_button, 4, 0, 1, 2)
        jog_box.addWidget(self.zero_button, 4, 2, 1, 2)

        self.progress = QProgressBar()
        self.progress.setMaximum(max(1, len(self._lines)))
        self.progress.setValue(0)
        self.status_label = QLabel(f"Готово к отправке: {len(self._lines)} строк.")
        self.send_button = QPushButton("Старт")
        self.send_button.clicked.connect(self._on_start_stream)
        self.pause_button = QPushButton("Пауза")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self._transport.pause)
        self.resume_button = QPushButton("Продолжить")
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(self._transport.resume)
        self.stop_button = QPushButton("Стоп (soft-reset)")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop)
        stream_row = QHBoxLayout()
        stream_row.addWidget(self.send_button)
        stream_row.addWidget(self.pause_button)
        stream_row.addWidget(self.resume_button)
        stream_row.addWidget(self.stop_button)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        close_box.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(port_row)
        layout.addWidget(QLabel("Ручная команда:"))
        layout.addLayout(cmd_row)
        layout.addWidget(QLabel("Перемещение фрезы (jog):"))
        layout.addLayout(jog_box)
        layout.addWidget(QLabel("Стриминг G-code:"))
        layout.addWidget(self.progress)
        layout.addLayout(stream_row)
        layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(close_box)

        self._refresh_ports()
        self._update_enabled()

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._cleanup()
        super().closeEvent(event)

    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        self.port_combo.clear()
        if not ports:
            self.port_combo.addItem("(нет портов)", None)
        for p in ports:
            self.port_combo.addItem(f"{p.device} — {p.description}", p.device)

    def _toggle_connection(self) -> None:
        if self._transport.connected:
            self._transport.disconnect()
            self.status_label.setText("Отключено.")
            self.connect_button.setText("Подключиться")
            self._update_enabled()
            return
        device = self.port_combo.currentData()
        if not device:
            QMessageBox.warning(self, "Порт", "Сначала выбери порт.")
            return
        try:
            self._transport.connect(device, baudrate=self.baud_spin.value())
        except (TransportError, OSError) as exc:
            QMessageBox.critical(self, "Ошибка подключения", str(exc))
            return
        self.status_label.setText(f"Подключено к {device} @ {self.baud_spin.value()}.")
        self.connect_button.setText("Отключить")
        self._update_enabled()

    def _send_safe(self, command: str) -> None:
        if not self._transport.connected:
            QMessageBox.information(self, "Нет связи", "Подключись к станку.")
            return
        try:
            reply = self._transport.send_command(command)
        except TransportError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        self.status_label.setText(f"{command} → {reply}")

    def _on_send_command(self) -> None:
        text = self.command_edit.text().strip()
        if not text:
            return
        self._send_safe(text)
        self.command_edit.clear()

    def _on_jog(self, dx: int, dy: int, dz: int) -> None:
        step = self.jog_step.value()
        feed = self.jog_feed.value()
        x = dx * step
        y = dy * step
        z = dz * step
        parts = ["$J=G91", "G21"]
        if x:
            parts.append(f"X{x}")
        if y:
            parts.append(f"Y{y}")
        if z:
            parts.append(f"Z{z}")
        parts.append(f"F{feed}")
        self._send_safe(" ".join(parts))

    def _on_start_stream(self) -> None:
        if not self._transport.connected:
            QMessageBox.information(self, "Нет связи", "Подключись к станку.")
            return
        if self._thread is not None:
            return
        self.progress.setValue(0)
        self.status_label.setText("Стрим запущен…")
        self._worker = StreamWorker(self._transport, list(self._lines))
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.acknowledged.connect(self._on_ack)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()
        self._update_enabled()

    def _on_ack(self, index: int, _reply: str) -> None:
        self.progress.setValue(index + 1)

    def _on_finished(self) -> None:
        self.status_label.setText("Готово.")
        self._cleanup_thread()
        self._update_enabled()

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"Ошибка стрима: {message}")
        self._cleanup_thread()
        self._update_enabled()

    def _on_stop(self) -> None:
        try:
            self._transport.soft_reset()
        except TransportError as exc:
            self.status_label.setText(str(exc))

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(1000)
            self._thread = None
            self._worker = None

    def _cleanup(self) -> None:
        import contextlib

        self._cleanup_thread()
        if self._transport.connected:
            with contextlib.suppress(TransportError):
                self._transport.disconnect()

    def _update_enabled(self) -> None:
        connected = self._transport.connected
        streaming = self._thread is not None
        self.send_command_button.setEnabled(connected and not streaming)
        self.send_button.setEnabled(connected and not streaming and bool(self._lines))
        self.pause_button.setEnabled(connected and streaming)
        self.resume_button.setEnabled(connected and streaming)
        self.stop_button.setEnabled(connected and streaming)
        self.home_button.setEnabled(connected and not streaming)
        self.zero_button.setEnabled(connected and not streaming)
        for child in self.findChildren(QPushButton):
            if child.text() in {"X+", "X-", "Y+", "Y-", "Z+", "Z-"}:
                child.setEnabled(connected and not streaming)
