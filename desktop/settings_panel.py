"""Settings for provider CLIs and the future API connection."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QProcess, QSettings, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView,
    QPushButton, QRadioButton, QScrollArea, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from vietlayer.ai_api import DEFAULT_MODELS

from .theme import STYLESHEET, application_font


@dataclass(frozen=True)
class CliSelection:
    provider: str
    model: str | None = None
    effort: str | None = None


@dataclass(frozen=True)
class ApiSelection:
    provider: str
    api_key: str = field(repr=False)


def _label(text: str, name: str | None = None) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _button(text: str, name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    if name:
        button.setObjectName(name)
    button.setMinimumHeight(42)
    return button


class _ComboItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(32)
        return size


def _combo(items: list[str]) -> QComboBox:
    combo = QComboBox()
    combo.addItems(items)
    popup = QListView()
    popup.setStyleSheet(
        "QListView { background: #FBF7F2; color: #50362A; border: 1px solid #CFAF98; "
        "outline: none; }"
        "QListView::item { color: #50362A; background: #FBF7F2; padding-left: 9px; }"
        "QListView::item:selected, QListView::item:hover { color: #50362A; "
        "background: #E8D2C0; }"
    )
    popup.setItemDelegate(_ComboItemDelegate(popup))
    combo.setView(popup)
    return combo


class SettingsPanel(QWidget):
    """In-window AI settings; CLI checks run without blocking the window."""

    cli_configuration_changed = Signal(object)
    cli_configuration_cleared = Signal()
    api_configuration_changed = Signal(object)
    api_configuration_cleared = Signal()
    back_requested = Signal()

    def __init__(self, parent=None, connected_selection: CliSelection | None = None):
        super().__init__(parent)
        self.setObjectName("settingsPanel")
        self.setStyleSheet(STYLESHEET)
        self.setFont(application_font())
        self._settings = QSettings("VietLayerOCR", "VietLayerOCR")
        self._process = QProcess(self)
        self._process.started.connect(self._on_process_started)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_check_timeout)
        self._stage: str | None = None
        self._active_provider: str | None = None
        self._check_folder: tempfile.TemporaryDirectory | None = None
        self._pending_input: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.addLayout(self._make_header(), 1)
        back_button = _button("← Trở về tài liệu")
        back_button.clicked.connect(self._request_back)
        header.addWidget(back_button)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setObjectName("settingsScrollViewport")
        content = QWidget()
        content.setObjectName("settingsScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setObjectName("settingsSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)
        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)
        self.cli_card = self._make_cli_column()
        self.api_card = self._make_api_column()
        columns.addWidget(self.cli_card, 1)
        divider = QFrame()
        divider.setObjectName("settingsDivider")
        divider.setFixedWidth(1)
        columns.addWidget(divider)
        columns.addWidget(self.api_card, 1)
        surface_layout.addLayout(columns, 1)
        privacy = QFrame()
        privacy.setObjectName("settingsPrivacy")
        privacy_layout = QVBoxLayout(privacy)
        privacy_layout.setContentsMargins(18, 16, 18, 16)
        privacy_text = _label(
            "Khi bật AI qua Provider CLI hoặc API, ảnh crop và bản đọc OCR có thể được gửi "
            "tới nhà cung cấp đã chọn. Cân nhắc dữ liệu nhạy cảm trước khi sử dụng.",
            "settingsPrivacyText",
        )
        privacy_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        privacy_layout.addWidget(privacy_text)
        privacy_row = QHBoxLayout()
        privacy_row.setContentsMargins(20, 0, 20, 20)
        privacy_row.addWidget(privacy)
        surface_layout.addLayout(privacy_row)
        content_layout.addWidget(surface, 1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self.footer_note = _label("Chọn một cách kết nối AI. API key chỉ giữ trong phiên ứng dụng.", "settingsFooterNote")
        layout.addWidget(self.footer_note)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.cli_radio)
        self.mode_group.addButton(self.api_radio)
        self.cli_radio.setChecked(True)
        saved_provider = connected_selection.provider if connected_selection else self._settings.value("cli/provider", "codex-cli")
        self.cli_provider.setCurrentIndex(0 if saved_provider == "claude-cli" else 1)
        self.cli_provider.currentIndexChanged.connect(self._on_provider_changed)
        self.check_install_button.clicked.connect(self._check_installation)
        self.check_connection_button.clicked.connect(self._check_connection)
        self.cli_model.currentIndexChanged.connect(self._save_cli_selection)
        self.cli_effort.currentIndexChanged.connect(self._save_cli_selection)
        self.api_provider.currentIndexChanged.connect(self._on_api_changed)
        self.api_key_input.textChanged.connect(self._on_api_changed)
        self.save_api_button.clicked.connect(self._save_api_selection)
        if connected_selection:
            self._active_provider = connected_selection.provider
            self.install_status.setText("Đã cài đặt: CLI trong phiên này")
            self.cli_status.setText("Kết nối thành công trong phiên này")
            self.footer_note.setText("CLI đã kết nối; có thể bật Sử dụng AI khi nhận dạng.")
            self.check_connection_button.setEnabled(True)
            self._populate_cli_options(connected_selection)

    def _make_header(self) -> QVBoxLayout:
        header = QVBoxLayout()
        header.setSpacing(4)
        header.addWidget(_label("Cài đặt AI", "settingsTitle"))
        header.addWidget(_label(
            "Chọn cách kết nối để đối chiếu những vùng chữ OCR chưa thống nhất.",
            "settingsDescription",
        ))
        return header

    def _make_cli_column(self) -> QFrame:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.cli_radio = QRadioButton("Provider CLI")
        self.cli_radio.setObjectName("settingsModeRadio")
        layout.addWidget(self.cli_radio)
        layout.addWidget(_label(
            "Dùng công cụ dòng lệnh đã cài và đăng nhập trên máy này.",
            "settingsDescription",
        ))
        layout.addSpacing(8)

        layout.addWidget(_label("Công cụ", "settingsFieldLabel"))
        self.cli_provider = _combo(["Claude CLI", "Codex CLI"])
        self.cli_provider.setCurrentIndex(1)
        layout.addWidget(self.cli_provider)

        self.install_status = _label("Chưa kiểm tra cài đặt", "settingsStatus")
        self.check_install_button = _button("Kiểm tra cài đặt")
        layout.addWidget(self.install_status)
        layout.addWidget(self.check_install_button)

        self.cli_status = _label("Chưa kiểm tra kết nối", "settingsStatus")
        self.check_connection_button = _button("Kiểm tra kết nối")
        self.check_connection_button.setEnabled(False)
        layout.addWidget(self.cli_status)
        layout.addWidget(self.check_connection_button)

        layout.addSpacing(8)
        layout.addWidget(_label("Model", "settingsFieldLabel"))
        self.cli_model = _combo(["Chọn sau khi kết nối"])
        self.cli_model.setEnabled(False)
        layout.addWidget(self.cli_model)

        layout.addWidget(_label("Mức suy luận", "settingsFieldLabel"))
        self.cli_effort = _combo(["Chọn sau khi kết nối"])
        self.cli_effort.setEnabled(False)
        layout.addWidget(self.cli_effort)
        layout.addStretch(1)
        return card

    def _make_api_column(self) -> QFrame:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.api_radio = QRadioButton("API AI")
        self.api_radio.setObjectName("settingsModeRadio")
        layout.addWidget(self.api_radio)
        layout.addWidget(_label(
            "Nhập khóa API của dịch vụ muốn dùng để đối chiếu OCR.",
            "settingsDescription",
        ))
        layout.addSpacing(8)

        layout.addWidget(_label("Dịch vụ", "settingsFieldLabel"))
        self.api_provider = _combo(["OpenAI", "Anthropic", "Google Gemini"])
        layout.addWidget(self.api_provider)
        self.api_model_note = _label(f"Model mặc định: {DEFAULT_MODELS['openai-api']}", "settingsStatus")
        layout.addWidget(self.api_model_note)

        layout.addWidget(_label("API key", "settingsFieldLabel"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Dán API key tại đây")
        self.api_key_input.setMinimumHeight(42)
        layout.addWidget(self.api_key_input)

        self.api_status = _label("Chưa nhập API key", "settingsStatus")
        layout.addWidget(self.api_status)
        self.save_api_button = _button("Dùng API trong phiên này", "primaryButton")
        self.save_api_button.setEnabled(False)
        layout.addWidget(self.save_api_button)
        layout.addStretch(1)
        return card

    @property
    def selected_mode(self) -> str:
        return "api" if self.api_radio.isChecked() else "cli"

    def _request_back(self) -> None:
        self.cancel_pending()
        self.back_requested.emit()

    def _on_api_changed(self) -> None:
        self.api_configuration_cleared.emit()
        providers = ("openai-api", "anthropic-api", "gemini-api")
        self.api_model_note.setText(f"Model mặc định: {DEFAULT_MODELS[providers[self.api_provider.currentIndex()]]}")
        self.api_status.setText("API key chưa được áp dụng")
        self.save_api_button.setEnabled(bool(self.api_key_input.text().strip()))

    def _save_api_selection(self) -> None:
        api_key = self.api_key_input.text().strip()
        if not api_key:
            return
        providers = ("openai-api", "anthropic-api", "gemini-api")
        selection = ApiSelection(providers[self.api_provider.currentIndex()], api_key)
        self.api_configuration_changed.emit(selection)
        self.api_status.setText("Đã áp dụng cho phiên này; sẽ kiểm tra khi nhận dạng")
        self.footer_note.setText("API key chỉ giữ trong bộ nhớ của phiên ứng dụng.")

    def _provider(self) -> str:
        return "claude-cli" if self.cli_provider.currentIndex() == 0 else "codex-cli"

    def _executable(self) -> str:
        return "claude" if self._provider() == "claude-cli" else "codex"

    def _on_provider_changed(self) -> None:
        self._settings.setValue("cli/provider", self._provider())
        self.cli_configuration_cleared.emit()
        self.footer_note.setText("Chọn một cách kết nối AI. API key chỉ giữ trong phiên ứng dụng.")
        self.install_status.setText("Chưa kiểm tra cài đặt")
        self.cli_status.setText("Chưa kiểm tra kết nối")
        self.check_connection_button.setEnabled(False)
        for combo in (self.cli_model, self.cli_effort):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Chọn sau khi kết nối")
            combo.setEnabled(False)
            combo.blockSignals(False)

    def _start_check(self, stage: str, program: str, arguments: list[str],
                     *, timeout_ms: int, workdir: Path | None = None,
                     input_text: str | None = None) -> None:
        self._stage = stage
        self._pending_input = input_text
        self.cli_provider.setEnabled(False)
        self.check_install_button.setEnabled(False)
        self.check_connection_button.setEnabled(False)
        self._process.setWorkingDirectory(str(workdir) if workdir else str(Path.home()))
        self._process.start(program, arguments)
        self._timer.start(timeout_ms)

    def _on_process_started(self) -> None:
        if self._pending_input is not None:
            self._process.write(self._pending_input.encode("utf-8"))
        self._process.closeWriteChannel()
        self._pending_input = None

    def _check_installation(self) -> None:
        executable = shutil.which(self._executable())
        self._active_provider = self._provider()
        if not executable:
            self._check_failed(f"Chưa tìm thấy {self._executable()} trong PATH", stage="version")
            return
        self.install_status.setText("Đang kiểm tra cài đặt…")
        self._start_check("version", executable, ["--version"], timeout_ms=10000)

    def _check_connection(self) -> None:
        executable = shutil.which(self._executable())
        if not executable:
            self._on_provider_changed()
            self.install_status.setText(f"Chưa tìm thấy {self._executable()} trong PATH")
            return
        self._active_provider = self._provider()
        self.cli_status.setText("Đang kiểm tra phiên đăng nhập…")
        arguments = ["auth", "status", "--json"] if self._active_provider == "claude-cli" else ["login", "status"]
        self._start_check("auth", executable, arguments, timeout_ms=15000)

    def _check_live_connection(self) -> None:
        self._check_folder = tempfile.TemporaryDirectory(prefix="vietlayer-cli-check-")
        folder = Path(self._check_folder.name)
        executable = shutil.which("claude" if self._active_provider == "claude-cli" else "codex")
        if not executable:
            self._check_failed("Không tìm thấy CLI để kiểm tra kết nối.")
            return
        self.cli_status.setText("Đang kết nối với provider…")
        if self._active_provider == "codex-cli":
            arguments = ["exec", "-", "--sandbox", "read-only", "--ephemeral",
                         "--skip-git-repo-check", "-C", str(folder),
                         "-o", str(folder / "answer.txt")]
            if self.cli_model.isEnabled() and self.cli_model.currentData():
                arguments += ["--model", self.cli_model.currentData()]
            if self.cli_effort.isEnabled() and self.cli_effort.currentData():
                arguments += ["--config", f"model_reasoning_effort={self.cli_effort.currentData()}"]
            self._start_check("ping", executable, arguments, timeout_ms=60000,
                              workdir=folder, input_text="Reply with exactly OK. Do not use tools.")
        else:
            arguments = ["-p", "Reply with exactly OK. Do not use tools.",
                         "--output-format", "json", "--safe-mode", "--restricted",
                         "--tools", "", "--permission-mode", "dontAsk",
                         "--no-session-persistence"]
            if self.cli_model.isEnabled() and self.cli_model.currentData():
                arguments += ["--model", self.cli_model.currentData()]
            if self.cli_effort.isEnabled() and self.cli_effort.currentData():
                arguments += ["--effort", self.cli_effort.currentData()]
            self._start_check("ping", executable, arguments, timeout_ms=60000, workdir=folder)

    def _on_process_finished(self, exit_code: int, _status) -> None:
        if self._stage is None:
            return
        stage = self._stage
        self._stage = None
        self._timer.stop()
        output = bytes(self._process.readAllStandardOutput()).decode("utf-8", "replace").strip()
        self._process.readAllStandardError()
        if _status != QProcess.ExitStatus.NormalExit:
            self._check_failed("CLI không hoàn thành bước kiểm tra.", stage=stage)
            return
        if stage == "auth" and self._active_provider == "codex-cli":
            if exit_code != 0:
                self._check_failed("Codex CLI chưa đăng nhập. Hãy chạy codex login.")
                return
            self._check_live_connection()
            return
        if exit_code != 0:
            self._check_failed("CLI không hoàn thành bước kiểm tra.", stage=stage)
            return
        if stage == "version":
            self.install_status.setText(f"Đã cài đặt: {output.splitlines()[0] if output else self._executable()}")
            self.check_connection_button.setEnabled(True)
            self.cli_provider.setEnabled(True)
            self.check_install_button.setEnabled(True)
            return
        if stage == "auth":
            if self._active_provider == "claude-cli":
                try:
                    if not json.loads(output).get("loggedIn", False):
                        self._check_failed("Claude CLI chưa đăng nhập. Hãy chạy claude auth login.")
                        return
                except (ValueError, TypeError):
                    self._check_failed("Không đọc được trạng thái đăng nhập Claude CLI.")
                    return
            self._check_live_connection()
            return
        if stage == "ping":
            if self._active_provider == "codex-cli":
                answer = Path(self._check_folder.name, "answer.txt").read_text(encoding="utf-8").strip() \
                    if self._check_folder and Path(self._check_folder.name, "answer.txt").is_file() else ""
            else:
                try:
                    answer = json.loads(output).get("result", "").strip()
                except (ValueError, TypeError, AttributeError):
                    answer = ""
            if answer != "OK":
                self._check_failed("Provider không trả lời hợp lệ. Kiểm tra lại CLI và tài khoản.")
                return
            self.cli_status.setText("Kết nối thành công")
            self.footer_note.setText("CLI đã kết nối; có thể bật Sử dụng AI khi nhận dạng.")
            self._populate_cli_options()
            self._finish_check()
            self._save_cli_selection()

    def _on_process_error(self, _error) -> None:
        if self._stage is not None:
            stage = self._stage
            self._stage = None
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
                self._process.waitForFinished(2000)
            self._check_failed("Không khởi chạy được CLI.", stage=stage)

    def _on_check_timeout(self) -> None:
        if self._stage is not None:
            stage = self._stage
            self._stage = None
            self._process.kill()
            self._process.waitForFinished(2000)
            self._check_failed("Hết thời gian chờ phản hồi từ CLI.", stage=stage)

    def _check_failed(self, message: str, *, stage: str | None = None) -> None:
        self.cli_configuration_cleared.emit()
        self.footer_note.setText("CLI chưa kết nối; OCR cục bộ vẫn dùng được.")
        self._pending_input = None
        for combo in (self.cli_model, self.cli_effort):
            combo.setEnabled(False)
        if (stage or self._stage) == "version":
            self.install_status.setText(message)
            self.cli_status.setText("Chưa kiểm tra kết nối")
        else:
            self.cli_status.setText(message)
        self._stage = None
        self._finish_check()

    def _finish_check(self) -> None:
        self._timer.stop()
        self.cli_provider.setEnabled(True)
        self.check_install_button.setEnabled(True)
        self.check_connection_button.setEnabled("Đã cài đặt:" in self.install_status.text())
        if self._check_folder:
            self._check_folder.cleanup()
            self._check_folder = None

    def _populate_cli_options(self, selection: CliSelection | None = None) -> None:
        models = (["sonnet", "opus", "haiku"] if self._active_provider == "claude-cli"
                  else ["gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna"])
        for combo in (self.cli_model, self.cli_effort):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Mặc định của CLI", None)
        for model in models:
            self.cli_model.addItem(model, model)
        for label, value in (("Thấp", "low"), ("Vừa", "medium"), ("Cao", "high"),
                             ("Rất cao", "xhigh"), ("Tối đa", "max")):
            self.cli_effort.addItem(label, value)
        for combo, key, selected in ((self.cli_model, "cli/model", selection.model if selection else None),
                                     (self.cli_effort, "cli/effort", selection.effort if selection else None)):
            saved = selected if selection else self._settings.value(key, None)
            index = combo.findData(saved)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.setEnabled(True)
            combo.blockSignals(False)

    def _save_cli_selection(self) -> None:
        if not self.cli_model.isEnabled() or not self.cli_effort.isEnabled():
            return
        selection = CliSelection(self._provider(), self.cli_model.currentData(), self.cli_effort.currentData())
        self._settings.setValue("cli/provider", selection.provider)
        self._settings.setValue("cli/model", selection.model)
        self._settings.setValue("cli/effort", selection.effort)
        self.cli_configuration_changed.emit(selection)

    def cancel_pending(self) -> None:
        self._timer.stop()
        pending_stage = self._stage
        self._stage = None
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(2000)
        if pending_stage:
            self._check_failed("Đã hủy kiểm tra. Hãy kiểm tra lại khi cần.", stage=pending_stage)
            return
        if self._check_folder:
            self._check_folder.cleanup()
            self._check_folder = None

    def closeEvent(self, event) -> None:
        self.cancel_pending()
        super().closeEvent(event)
