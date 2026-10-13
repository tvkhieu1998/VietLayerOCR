"""Import, inspect, correct, and export documents in one desktop window."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
    QApplication, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from vietlayer.core import DigitalSignatureError, OcrConfig, SUPPORTED_SUFFIXES

from .icons import outline_icon
from .preview import DocumentPreview
from .session import DocumentSession
from .settings_panel import ApiSelection, CliSelection, SettingsPanel
from .switch import AiSwitch
from .theme import STYLESHEET, application_font
from .worker import OcrWorker


def _label(text: str, object_name: str | None = None) -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    return label


def _button(text: str, object_name: str | None = None, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    if object_name:
        button.setObjectName(object_name)
    if icon_name:
        color = "#FFF8F1" if object_name == "primaryButton" else "#65412F"
        button.setIcon(outline_icon(icon_name, color))
        button.setIconSize(QSize(21, 21))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VietLayerOCR — Nhận dạng tài liệu")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry().size() if screen else QSize(1440, 900)
        self.resize(min(1220, available.width() - 80), min(760, available.height() - 80))
        self.setMinimumSize(1020, 640)
        self.setStyleSheet(STYLESHEET)
        self.setFont(application_font())
        self._workspace = tempfile.TemporaryDirectory(prefix="vietlayer-desktop-")
        self._sessions: list[DocumentSession] = []
        self._review_index = 0
        self._filling_editor = False
        self._editing_region = False
        self._thread: QThread | None = None
        self._worker: OcrWorker | None = None
        self._running_session: DocumentSession | None = None
        self._signed_retry_session: DocumentSession | None = None
        self._connected_cli: CliSelection | None = None
        self._connected_api: ApiSelection | None = None
        self._build_ui()
        self._update_actions()

    @property
    def active_session(self) -> DocumentSession | None:
        row = self.document_list.currentRow()
        return self._sessions[row] if 0 <= row < len(self._sessions) else None

    def _build_ui(self) -> None:
        self.central_stack = QStackedWidget(self)
        self.setCentralWidget(self.central_stack)
        root = QWidget(self)
        root.setObjectName("root")
        outer = QHBoxLayout(root)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(13)
        outer.addWidget(self._make_sidebar())
        workspace = QVBoxLayout()
        workspace.setSpacing(13)
        workspace.addWidget(self._make_top_bar())
        columns = QHBoxLayout()
        columns.setSpacing(13)
        columns.addWidget(self._make_preview_panel(), 1)
        columns.addWidget(self._make_review_panel())
        workspace.addLayout(columns, 1)
        outer.addLayout(workspace, 1)
        self.central_stack.addWidget(root)
        self.settings_panel = SettingsPanel(self)
        self.settings_panel.cli_configuration_changed.connect(self._set_cli_configuration)
        self.settings_panel.cli_configuration_cleared.connect(self._clear_cli_configuration)
        self.settings_panel.api_configuration_changed.connect(self._set_api_configuration)
        self.settings_panel.api_configuration_cleared.connect(self._clear_api_configuration)
        self.settings_panel.back_requested.connect(self._show_document_page)
        self.central_stack.addWidget(self.settings_panel)

    def _make_top_bar(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("topBar")
        panel.setFixedHeight(69)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        self.import_button = _button("Thêm tài liệu", "primaryButton", "add")
        self.import_button.setMinimumHeight(45)
        self.import_button.clicked.connect(self._choose_documents)
        layout.addWidget(self.import_button)
        status_column = QVBoxLayout()
        status_column.setSpacing(4)
        self.status_label = _label("Chọn PDF hoặc ảnh để bắt đầu", "statusLabel")
        self.status_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_column.addWidget(self.status_label)
        status_column.addWidget(self.progress_bar)
        layout.addLayout(status_column, 1)
        self.export_pdf_button = _button("Xuất PDF", "primaryButton", "pdf")
        self.export_text_button = _button("Xuất TXT", "primaryButton", "text")
        for button in (self.export_pdf_button, self.export_text_button):
            button.setMinimumHeight(45)
            button.setMinimumWidth(110)
            layout.addWidget(button)
        self.export_pdf_button.clicked.connect(self._export_pdf)
        self.export_text_button.clicked.connect(self._export_text)
        return panel

    def _make_sidebar(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("sidebar")
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 20, 14, 15)
        layout.setSpacing(9)
        title = _label("TÀI LIỆU", "sidebarTitle")
        layout.addWidget(title)
        self.document_list = QListWidget()
        self.document_list.setObjectName("documentList")
        self.document_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.document_list.setMaximumHeight(82)
        self.document_list.setSpacing(2)
        self.document_list.currentRowChanged.connect(self._show_document)
        layout.addWidget(self.document_list)
        self.page_list = QListWidget()
        self.page_list.setObjectName("pageList")
        self.page_list.setViewMode(QListView.ViewMode.IconMode)
        self.page_list.setFlow(QListView.Flow.TopToBottom)
        self.page_list.setWrapping(False)
        self.page_list.setMovement(QListView.Movement.Static)
        self.page_list.setIconSize(QSize(132, 174))
        self.page_list.setSpacing(4)
        self.page_list.currentRowChanged.connect(self._on_page_selected)
        layout.addWidget(self.page_list, 1)
        self.ai_warning = _label(
            "Rủi ro lộ dữ liệu nhạy cảm có trên file pdf, cân nhắc trước khi sử dụng AI",
            "aiWarning",
        )
        self.ai_warning.setWordWrap(True)
        self.ai_warning.hide()
        layout.addWidget(self.ai_warning)
        self.ai_toggle = AiSwitch("Sử dụng AI")
        self.ai_toggle.setObjectName("aiToggle")
        self.ai_toggle.toggled.connect(self._show_ai_warning)
        layout.addWidget(self.ai_toggle)
        self.run_button = _button("Nhận dạng tài liệu", "sidebarButton", "scan")
        self.run_button.setMinimumHeight(43)
        self.run_button.clicked.connect(self.start_ocr)
        layout.addWidget(self.run_button)
        self.settings_button = _button("Cài đặt OCR", "sidebarButton")
        self.settings_button.setMinimumHeight(43)
        self.settings_button.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_button)
        return panel

    def _make_preview_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("previewPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)
        header = QHBoxLayout()
        self.document_title = _label("Tài liệu chưa được chọn", "documentTitle")
        self.document_title.setWordWrap(True)
        header.addWidget(self.document_title, 1)
        self.page_indicator = _label("", "smallLabel")
        header.addWidget(self.page_indicator)
        self.zoom_out_button = _button("−", "iconButton")
        self.zoom_in_button = _button("+", "iconButton")
        self.fit_button = _button("Vừa khung")
        self.zoom_out_button.clicked.connect(lambda: self.preview.change_zoom(0.8))
        self.zoom_in_button.clicked.connect(lambda: self.preview.change_zoom(1.25))
        self.fit_button.clicked.connect(self.preview_fit)
        header.addWidget(self.zoom_out_button)
        header.addWidget(self.zoom_in_button)
        header.addWidget(self.fit_button)
        layout.addLayout(header)
        self.preview = DocumentPreview()
        layout.addWidget(self.preview, 1)
        return panel

    def _make_review_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("reviewPanel")
        panel.setFixedWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 14, 15, 15)
        layout.setSpacing(9)
        header = QHBoxLayout()
        self.review_title = _label("KIỂM TRA CHỮ", "sectionTitle")
        header.addWidget(self.review_title, 1)
        self.review_counter = _label("0 / 0", "smallLabel")
        header.addWidget(self.review_counter)
        self.previous_button = _button("↑", "iconButton")
        self.next_button = _button("↓", "iconButton")
        self.previous_button.clicked.connect(lambda: self._change_review(-1))
        self.next_button.clicked.connect(lambda: self._change_review(1))
        header.addWidget(self.previous_button)
        header.addWidget(self.next_button)
        layout.addLayout(header)
        self.review_stack = QStackedWidget()
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(9)
        crop_card = QFrame()
        crop_card.setObjectName("paperCard")
        crop_layout = QVBoxLayout(crop_card)
        crop_layout.setContentsMargins(10, 10, 10, 10)
        self.crop_label = _label("Chọn một vùng cần kiểm tra", "emptyText")
        self.crop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_label.setMinimumSize(278, 96)
        self.crop_label.setWordWrap(True)
        self.crop_scroll = QScrollArea()
        self.crop_scroll.setFixedHeight(122)
        self.crop_scroll.setWidgetResizable(False)
        self.crop_scroll.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        self.crop_scroll.setWidget(self.crop_label)
        crop_layout.addWidget(self.crop_scroll)
        detail_layout.addWidget(crop_card)
        self.region_meta = _label("Chưa có kết quả nhận dạng", "smallLabel")
        detail_layout.addWidget(self.region_meta)
        detail_layout.addWidget(_label("KẾT QUẢ NHẬN DẠNG", "sectionTitle"))
        reader_card = QFrame()
        reader_card.setObjectName("readerCard")
        reader_layout = QVBoxLayout(reader_card)
        reader_layout.setContentsMargins(0, 0, 0, 0)
        reader_layout.setSpacing(0)
        tesseract_row = QFrame()
        tesseract_row.setObjectName("candidateRow")
        tesseract_layout = QHBoxLayout(tesseract_row)
        tesseract_layout.setContentsMargins(10, 7, 10, 7)
        tesseract_layout.setSpacing(6)
        tesseract_layout.addWidget(_label("Tesseract", "candidateName"))
        self.tesseract_label = _label("—", "candidateText")
        self.tesseract_label.setWordWrap(True)
        tesseract_layout.addWidget(self.tesseract_label, 1)
        vietocr_row = QFrame()
        vietocr_row.setObjectName("candidateRow")
        vietocr_layout = QHBoxLayout(vietocr_row)
        vietocr_layout.setContentsMargins(10, 7, 10, 7)
        vietocr_layout.setSpacing(6)
        vietocr_layout.addWidget(_label("VietOCR", "candidateName"))
        self.vietocr_label = _label("—", "candidateText")
        self.vietocr_label.setWordWrap(True)
        vietocr_layout.addWidget(self.vietocr_label, 1)
        reader_layout.addWidget(tesseract_row)
        reader_layout.addWidget(vietocr_row)
        self.ai_candidate_row = QFrame()
        self.ai_candidate_row.setObjectName("candidateRow")
        ai_candidate_layout = QHBoxLayout(self.ai_candidate_row)
        ai_candidate_layout.setContentsMargins(10, 7, 10, 7)
        ai_candidate_layout.setSpacing(6)
        ai_candidate_layout.addWidget(_label("AI CLI", "candidateName"))
        self.ai_candidate_label = _label("—", "candidateText")
        self.ai_candidate_label.setWordWrap(True)
        ai_candidate_layout.addWidget(self.ai_candidate_label, 1)
        reader_layout.addWidget(self.ai_candidate_row)
        self.ai_candidate_row.hide()
        detail_layout.addWidget(reader_card)
        detail_layout.addWidget(_label("NỘI DUNG CUỐI CÙNG", "sectionTitle"))
        self.final_editor = QPlainTextEdit()
        self.final_editor.setPlaceholderText("Chữ được chọn sẽ hiện ở đây")
        self.final_editor.setReadOnly(True)
        self.final_editor.setFixedHeight(83)
        self.final_editor.textChanged.connect(self._on_text_changed)
        detail_layout.addWidget(self.final_editor)
        warning_card = QFrame()
        warning_card.setObjectName("warningCard")
        warning_layout = QVBoxLayout(warning_card)
        warning_layout.setContentsMargins(14, 11, 14, 11)
        self.warning_label = _label("Đối chiếu với tài liệu gốc trước khi xuất tệp.")
        self.warning_label.setWordWrap(True)
        warning_layout.addWidget(self.warning_label)
        detail_layout.addWidget(warning_card)
        detail_layout.addStretch(1)
        self.review_stack.addWidget(detail)

        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(10)
        self.overview_page_label = _label("Chọn trang để xem văn bản", "smallLabel")
        overview_layout.addWidget(self.overview_page_label)
        self.overview_editor = QPlainTextEdit()
        self.overview_editor.setObjectName("overviewText")
        self.overview_editor.setReadOnly(True)
        self.overview_editor.setPlaceholderText("Nhận dạng tài liệu để xem văn bản của trang")
        overview_layout.addWidget(self.overview_editor, 1)
        self.overview_note = _label("Có thể chọn và sao chép văn bản. Chỉnh sửa trong chế độ Chi tiết.", "smallLabel")
        self.overview_note.setWordWrap(True)
        overview_layout.addWidget(self.overview_note)
        self.review_stack.addWidget(overview)
        layout.addWidget(self.review_stack, 1)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.detail_button = _button("Chi tiết", "modeButton")
        self.overview_button = _button("Tổng thể text", "modeButton")
        for button in (self.detail_button, self.overview_button):
            button.setCheckable(True)
            button.setFixedSize(106, 40)
            actions.addWidget(button)
        self.detail_button.setChecked(True)
        self.detail_button.clicked.connect(lambda: self._set_review_mode(0))
        self.overview_button.clicked.connect(lambda: self._set_review_mode(1))
        self.review_action_button = _button("Chỉnh sửa", "primaryButton")
        self.review_action_button.setFixedSize(106, 40)
        self.review_action_button.clicked.connect(self._review_action)
        actions.addWidget(self.review_action_button)
        layout.addLayout(actions)
        return panel

    def preview_fit(self) -> None:
        self.preview.fit_width()
        self._update_crop()

    def _open_settings(self) -> None:
        self.setWindowTitle("VietLayerOCR — Cài đặt AI")
        self.central_stack.setCurrentWidget(self.settings_panel)

    def _show_document_page(self) -> None:
        self.setWindowTitle("VietLayerOCR — Nhận dạng tài liệu")
        self.central_stack.setCurrentIndex(0)

    def _set_cli_configuration(self, selection: CliSelection) -> None:
        self._connected_cli = selection

    def _clear_cli_configuration(self) -> None:
        self._connected_cli = None

    def _set_api_configuration(self, selection: ApiSelection) -> None:
        self._connected_api = selection

    def _clear_api_configuration(self) -> None:
        self._connected_api = None

    def _show_ai_warning(self, enabled: bool) -> None:
        self.ai_warning.setVisible(enabled)

    def _set_review_mode(self, mode: int) -> None:
        self.review_stack.setCurrentIndex(mode)
        self.detail_button.setChecked(mode == 0)
        self.overview_button.setChecked(mode == 1)
        self.review_title.setText("KIỂM TRA CHỮ" if mode == 0 else "TỔNG THỂ TEXT")
        for widget in (self.review_counter, self.previous_button, self.next_button):
            widget.setVisible(mode == 0)
        if mode == 0:
            region = self._current_region()
            if region is not None:
                self._show_review(self._review_index)
        else:
            self.preview.set_highlight(None, None)
            self._update_overview()
        self._update_actions()

    def _review_action(self) -> None:
        if self.review_stack.currentIndex() == 1:
            self._export_text()
            return
        session = self.active_session
        if session and session.dirty:
            self._save_corrections()
        elif self._current_region() is not None:
            self._editing_region = True
            self.final_editor.setReadOnly(False)
            self.final_editor.setFocus()
            self._update_actions()

    def _update_overview(self) -> None:
        session = self.active_session
        if session is None:
            self.overview_page_label.setText("Chọn trang để xem văn bản")
            self.overview_editor.clear()
            return
        page_index = session.page_index
        self.overview_page_label.setText(f"Văn bản trang {page_index + 1} / {self.preview.page_count}")
        page_texts = session.result.page_texts if session.result else []
        self.overview_editor.setPlainText(page_texts[page_index] if page_index < len(page_texts) else "")
        self.overview_note.setText(
            "Có chỉnh sửa chưa lưu. Lưu trong chế độ Chi tiết để cập nhật văn bản."
            if session.dirty else "Có thể chọn và sao chép văn bản. Chỉnh sửa trong chế độ Chi tiết."
        )

    def _choose_documents(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Thêm tài liệu", str(Path.home()),
            "Tài liệu (*.pdf *.png *.jpg *.jpeg *.tif *.tiff)",
        )
        for path in paths:
            self.add_document(Path(path))

    def add_document(self, path: Path) -> None:
        path = Path(path).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            QMessageBox.warning(self, "Không mở được tài liệu", "Chọn tệp PDF, PNG, JPG hoặc TIFF hợp lệ.")
            return
        for index, session in enumerate(self._sessions):
            if session.source_path == path:
                self.document_list.setCurrentRow(index)
                return
        output_path = Path(self._workspace.name) / f"document_{len(self._sessions) + 1}.pdf"
        self._sessions.append(DocumentSession(path, output_path))
        document_item = QListWidgetItem(path.name)
        document_item.setToolTip(str(path))
        document_item.setIcon(outline_icon("pdf" if path.suffix.lower() == ".pdf" else "text", "#FFF5E9"))
        self.document_list.addItem(document_item)
        self.document_list.setMaximumHeight(min(120, 42 * len(self._sessions) + 12))
        self.document_list.setCurrentRow(len(self._sessions) - 1)

    def _show_document(self, row: int) -> None:
        session = self.active_session
        if session is None:
            return
        if not self.preview.load_document(session.display_path):
            self.status_label.setText("Không xem được tài liệu này. Kiểm tra tệp đầu vào.")
            return
        self.document_title.setText(session.source_path.name)
        self.page_list.blockSignals(True)
        self.page_list.clear()
        for page_index in range(self.preview.page_count):
            item = QListWidgetItem(f"Trang {page_index + 1}")
            thumbnail = self.preview.thumbnail(page_index)
            if not thumbnail.isNull():
                icon = QIcon()
                for mode in (QIcon.Mode.Normal, QIcon.Mode.Selected, QIcon.Mode.Active):
                    icon.addPixmap(thumbnail, mode)
                item.setIcon(icon)
            item.setSizeHint(QSize(178, 212))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.page_list.addItem(item)
        self.page_list.setCurrentRow(min(session.page_index, max(0, self.preview.page_count - 1)))
        self.page_list.blockSignals(False)
        self._on_page_selected(self.page_list.currentRow())
        self._update_actions()

    def _on_page_selected(self, row: int) -> None:
        session = self.active_session
        if session is None or row < 0:
            return
        session.page_index = row
        self.preview.set_page(row)
        self.page_indicator.setText(f"{row + 1} / {self.preview.page_count}")
        self._update_overview()
        index = next((index for index, region in enumerate(session.review_regions) if region.get("page") == row + 1), None)
        if index is None:
            self._clear_review()
        else:
            self._review_index = index
            self._show_review(index)
        if self.review_stack.currentIndex() == 1:
            self.preview.set_highlight(None, None)

    def _current_region(self) -> dict | None:
        session = self.active_session
        regions = session.review_regions if session else []
        return regions[self._review_index] if 0 <= self._review_index < len(regions) else None

    def _show_review(self, index: int) -> None:
        session = self.active_session
        if session is None or not 0 <= index < len(session.review_regions):
            self._clear_review()
            return
        self._review_index = index
        region = session.review_regions[index]
        page_index = region["page"] - 1
        if session.page_index != page_index:
            session.page_index = page_index
            self.page_list.blockSignals(True)
            self.page_list.setCurrentRow(page_index)
            self.page_list.blockSignals(False)
            self.preview.set_page(page_index)
            self.page_indicator.setText(f"{page_index + 1} / {self.preview.page_count}")
        page_report = next((page for page in session.result.report if page.get("page") == region["page"]), {})
        image_size = page_report.get("image_size")
        bbox = region.get("bbox")
        self.preview.set_highlight(bbox, image_size)
        self._update_crop()
        self.review_counter.setText(f"{index + 1} / {len(session.review_regions)}")
        self.region_meta.setText(f"Trang {region['page']} · vùng {region['region']} · {region.get('source', 'ocr')}")
        candidates = region.get("candidates", {})
        self.tesseract_label.setText(candidates.get('tesseract') or '—')
        self.vietocr_label.setText(candidates.get('vietocr') or '—')
        self.ai_candidate_label.setText(candidates.get('ai') or '—')
        self.ai_candidate_row.setVisible(bool(candidates.get('ai')))
        reasons = region.get("reasons") or []
        self.warning_label.setText("Cần đối chiếu: " + "; ".join(reasons) if reasons else
                                   "Đối chiếu với tài liệu gốc trước khi xuất tệp.")
        correction_key = region.get("correction_key") or region["region"]
        draft = session.corrections.get(str(region["page"]), {}).get(correction_key)
        if isinstance(draft, dict):
            draft = draft.get("text")
        self._filling_editor = True
        self.final_editor.setPlainText(draft if draft is not None else region.get("text", ""))
        self._filling_editor = False
        self._editing_region = False
        self.final_editor.setReadOnly(True)
        self._update_actions()

    def _update_crop(self) -> None:
        session = self.active_session
        region = self._current_region()
        if session is None or region is None or session.result is None:
            return
        page_report = next((page for page in session.result.report if page.get("page") == region["page"]), {})
        pixmap = self.preview.crop_region(region.get("bbox"), page_report.get("image_size"))
        if pixmap.isNull():
            self.crop_label.setText("Không có ảnh vùng chữ")
            self.crop_label.setPixmap(QIcon().pixmap(1, 1))
        else:
            scaled = pixmap.scaledToHeight(95, Qt.TransformationMode.SmoothTransformation)
            if scaled.width() > 4000:
                scaled = scaled.scaledToWidth(4000, Qt.TransformationMode.SmoothTransformation)
            self.crop_label.setPixmap(scaled)
            self.crop_label.resize(scaled.size())

    def _clear_review(self) -> None:
        session = self.active_session
        total = len(session.review_regions) if session else 0
        self._review_index = -1
        self.review_counter.setText(f"0 / {total}")
        self.region_meta.setText("Không có vùng cần đối chiếu ở trang này" if session and session.result else
                                 "Chưa có kết quả nhận dạng")
        self.crop_label.clear()
        self.crop_label.setText("Chưa có vùng chữ để xem")
        self.tesseract_label.setText("—")
        self.vietocr_label.setText("—")
        self.ai_candidate_label.setText("—")
        self.ai_candidate_row.hide()
        self._filling_editor = True
        self.final_editor.clear()
        self._filling_editor = False
        self._editing_region = False
        self.final_editor.setReadOnly(True)
        self.warning_label.setText("Đối chiếu với tài liệu gốc trước khi xuất tệp.")
        self.preview.set_highlight(None, None)
        self._update_actions()

    def _change_review(self, delta: int) -> None:
        session = self.active_session
        if not session or not session.review_regions:
            return
        self._show_review((self._review_index + delta) % len(session.review_regions))

    def _on_text_changed(self) -> None:
        if self._filling_editor:
            return
        session = self.active_session
        region = self._current_region()
        if session is None or region is None:
            return
        text = self.final_editor.toPlainText().strip()
        page_key = str(region["page"])
        region_key = region.get("correction_key") or region["region"]
        if text != region.get("text", "").strip():
            session.corrections.setdefault(page_key, {})[region_key] = {
                "text": text, "bbox": region.get("bbox"),
            }
            session.unapplied_count = 0
        else:
            if region.get("source") == "manual":
                existing = session.corrections.get(page_key, {}).get(region_key)
                if existing is None:
                    session.corrections.setdefault(page_key, {})[region_key] = {
                        "text": text, "bbox": region.get("bbox"),
                    }
                elif isinstance(existing, dict):
                    existing["text"] = text
                else:
                    session.corrections[page_key][region_key] = text
            else:
                session.corrections.get(page_key, {}).pop(region_key, None)
        reported_text = {
            (str(item["page"]), item.get("correction_key") or item["region"]): item.get("text", "").strip()
            for item in session.review_regions
        }
        session.dirty = any(
            (value.get("text", "") if isinstance(value, dict) else value).strip()
            != reported_text.get((page, identifier), "")
            for page, changes in session.corrections.items()
            for identifier, value in changes.items()
        )
        self._update_overview()
        self._update_actions()

    def _save_corrections(self) -> None:
        session = self.active_session
        if session is None or not session.dirty:
            return
        if any(not (value.get("text", "") if isinstance(value, dict) else value).strip()
               for page in session.corrections.values() for value in page.values()):
            QMessageBox.warning(self, "Thiếu nội dung", "Vùng chữ đã sửa không được để trống.")
            return
        self.start_ocr()

    def start_ocr(self, invalidate_digital_signatures: bool = False) -> None:
        session = self.active_session
        if session is None or self._thread is not None:
            return
        use_ai = self.ai_toggle.isChecked()
        cli_selection = self._connected_cli if use_ai and self.settings_panel.selected_mode == "cli" else None
        api_selection = self._connected_api if use_ai and self.settings_panel.selected_mode == "api" else None
        if use_ai and cli_selection is None and api_selection is None:
            message = ("Vào Cài đặt OCR và áp dụng API key trước khi dùng AI."
                       if self.settings_panel.selected_mode == "api" else
                       "Vào Cài đặt OCR, kiểm tra cài đặt và kết nối provider CLI trước khi dùng AI.")
            QMessageBox.information(self, "AI chưa được kết nối", message)
            return
        model_dir = os.environ.get("VIETLAYER_MODEL_DIR")
        config = OcrConfig(model_dir=Path(model_dir) if model_dir else None,
                           corrections=session.corrections, export_format="both",
                           invalidate_digital_signatures=invalidate_digital_signatures,
                           ai_provider=(cli_selection.provider if cli_selection else
                                        api_selection.provider if api_selection else None),
                           ai_model=cli_selection.model if cli_selection else None,
                           ai_effort=cli_selection.effort if cli_selection else None,
                           ai_api_key=api_selection.api_key if api_selection else None)
        self._running_session = session
        self.status_label.setText("Đang nhận dạng…")
        self.progress_bar.setRange(0, 0)
        self._update_actions()
        self._thread = QThread(self)
        self._worker = OcrWorker(session.source_path, session.next_output_path(), config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.status_label.setText)
        self._worker.completed.connect(self._on_ocr_completed)
        self._worker.failed.connect(self._on_ocr_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_ocr_completed(self, result) -> None:
        session = self._running_session
        if session is None:
            return
        session.result = result
        unapplied = [(str(page.get("page")), key) for page in result.report
                     for key in page.get("unapplied_corrections", [])]
        session.unapplied_count = len(unapplied)
        for page_key, key in unapplied:
            session.corrections.get(page_key, {}).pop(key, None)
        session.dirty = False
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        review_count = len(session.review_regions)
        ai_error_count = sum(len(page.get("ai_review", {}).get("errors", [])) for page in result.report)
        if unapplied:
            self.status_label.setText(f"{len(unapplied)} bản sửa không khớp vùng; chọn lại vùng chữ để sửa")
        elif ai_error_count:
            self.status_label.setText(
                f"Hoàn thành {result.page_count} trang · AI lỗi ở {ai_error_count} lượt; đã dùng OCR cục bộ"
            )
        else:
            self.status_label.setText(f"Hoàn thành {result.page_count} trang · {review_count} vùng cần đối chiếu")
        if self.active_session is session:
            self._show_document(self.document_list.currentRow())
        self._update_actions()

    def _on_ocr_failed(self, error: Exception) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("Nhận dạng chưa hoàn thành")
        if isinstance(error, DigitalSignatureError):
            answer = QMessageBox.question(
                self, "Tài liệu có chữ ký số",
                "Tạo PDF có lớp chữ sẽ làm chữ ký số trên bản xuất mất hiệu lực. "
                "Tệp gốc vẫn được giữ nguyên. Tiếp tục tạo bản OCR mới?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._signed_retry_session = self._running_session
            return
        QMessageBox.warning(self, "Không nhận dạng được tài liệu", str(error))

    def _on_thread_finished(self) -> None:
        retry_session = self._signed_retry_session
        self._signed_retry_session = None
        self._worker = None
        self._thread = None
        self._running_session = None
        self._update_actions()
        if retry_session is not None and retry_session is self.active_session:
            self.start_ocr(invalidate_digital_signatures=True)

    def _update_actions(self) -> None:
        session = self.active_session
        busy = self._thread is not None
        has_result = session is not None and session.result is not None
        self.import_button.setEnabled(not busy)
        self.ai_toggle.setEnabled(not busy)
        self.settings_button.setEnabled(not busy)
        self.document_list.setEnabled(not busy)
        self.page_list.setEnabled(not busy)
        self.run_button.setEnabled(session is not None and not busy)
        can_export = bool(has_result and not session.dirty and not session.unapplied_count and not busy)
        self.export_pdf_button.setEnabled(bool(can_export and session.result.pdf_path))
        self.export_text_button.setEnabled(bool(can_export and session.result.text_path))
        region = self._current_region()
        self.previous_button.setEnabled(region is not None and not busy)
        self.next_button.setEnabled(region is not None and not busy)
        self.final_editor.setEnabled(region is not None and not busy)
        if self.review_stack.currentIndex() == 0:
            self.review_action_button.setText("Lưu chỉnh sửa" if session and session.dirty else "Chỉnh sửa")
            self.review_action_button.setEnabled(bool((region or session and session.dirty) and not busy))
        else:
            self.review_action_button.setText("Xuất TXT")
            self.review_action_button.setEnabled(bool(can_export and session.result.text_path))

    def _export_pdf(self) -> None:
        session = self.active_session
        if session and session.result and session.result.pdf_path and not session.dirty and not session.unapplied_count:
            self._export_file(session.result.pdf_path, session.source_path.stem + "_searchable.pdf",
                              "PDF (*.pdf)")

    def _export_text(self) -> None:
        session = self.active_session
        if session and session.result and session.result.text_path and not session.dirty and not session.unapplied_count:
            self._export_file(session.result.text_path, session.source_path.stem + "_recognized.txt",
                              "Văn bản (*.txt)")

    def _export_file(self, source: Path, filename: str, file_filter: str) -> None:
        destination, _ = QFileDialog.getSaveFileName(self, "Xuất kết quả", str(Path.home() / filename), file_filter)
        if not destination:
            return
        try:
            shutil.copy2(source, destination)
        except OSError as error:
            QMessageBox.warning(self, "Không xuất được tệp", str(error))
            return
        self.status_label.setText(f"Đã xuất {Path(destination).name}")

    def closeEvent(self, event) -> None:
        if self._thread is not None:
            QMessageBox.information(self, "Đang nhận dạng", "Đợi tài liệu xử lý xong trước khi đóng ứng dụng.")
            event.ignore()
            return
        self.settings_panel.cancel_pending()
        self._workspace.cleanup()
        super().closeEvent(event)
