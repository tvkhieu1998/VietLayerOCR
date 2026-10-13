"""Desktop interaction checks that run without a visible display."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from desktop.main_window import MainWindow
from desktop.settings_panel import SettingsPanel
from desktop.session import DocumentSession
from vietlayer.core import DigitalSignatureError, OcrResult


class DesktopTests(unittest.TestCase):
    def test_settings_panel_has_two_provider_columns_and_defaults_to_cli(self):
        dialog = SettingsPanel()
        self.assertTrue(dialog.cli_radio.isChecked())
        self.assertFalse(dialog.api_radio.isChecked())
        self.assertEqual(dialog.cli_provider.count(), 2)
        self.assertEqual([dialog.cli_provider.itemText(index) for index in range(2)], ["Claude CLI", "Codex CLI"])
        self.assertEqual(dialog.api_provider.count(), 3)
        self.assertTrue(dialog.api_key_input.echoMode() == dialog.api_key_input.EchoMode.Password)
        self.assertTrue(dialog.check_install_button.isEnabled())
        self.assertFalse(dialog.check_connection_button.isEnabled())
        self.assertFalse(dialog.cli_model.isEnabled())
        self.assertFalse(dialog.cli_effort.isEnabled())
        self.assertFalse(dialog.save_api_button.isEnabled())
        self.assertIn("Chưa kiểm tra", dialog.cli_status.text())
        dialog.close()

    def test_settings_provider_popup_has_separate_readable_rows(self):
        dialog = SettingsPanel()
        dialog.show()
        self.application.processEvents()
        for combo in (dialog.cli_provider, dialog.api_provider):
            combo.showPopup()
            self.application.processEvents()
            view = combo.view()
            boxes = [view.visualRect(view.model().index(index, 0)) for index in range(combo.count())]
            self.assertTrue(all(box.height() >= 30 for box in boxes))
            self.assertTrue(all(first.bottom() < second.top() for first, second in zip(boxes, boxes[1:])))
            combo.hidePopup()
        dialog.close()

    def test_settings_button_shows_page_inside_main_window(self):
        window = MainWindow()
        self.assertTrue(window.settings_button.isEnabled())
        window.settings_button.click()
        self.assertIs(window.central_stack.currentWidget(), window.settings_panel)
        window.settings_panel.back_requested.emit()
        self.assertEqual(window.central_stack.currentIndex(), 0)
        window.close()

    def test_signed_pdf_retry_requires_user_consent(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "signed.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            window = MainWindow()
            window.add_document(source)
            window._running_session = window.active_session
            with patch("desktop.main_window.QMessageBox.warning"), \
                 patch("desktop.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
                 patch.object(window, "start_ocr") as retry:
                window._on_ocr_failed(DigitalSignatureError("Tài liệu có chữ ký số"))
                window._on_thread_finished()
            retry.assert_called_once_with(invalidate_digital_signatures=True)
            window.close()

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_main_actions_match_selected_design(self):
        window = MainWindow()
        self.assertEqual(window.import_button.text(), "Thêm tài liệu")
        self.assertEqual(window.export_pdf_button.text(), "Xuất PDF")
        self.assertEqual(window.export_text_button.text(), "Xuất TXT")
        self.assertFalse(window.export_pdf_button.isEnabled())
        self.assertFalse(window.export_text_button.isEnabled())
        window.close()

    def test_empty_preview_has_document_icon_and_clear_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            Image.new("RGB", (400, 600), "white").save(image_path)
            window = MainWindow()
            window.show()
            self.application.processEvents()
            self.assertTrue(window.preview.empty_state.isVisibleTo(window))
            self.assertFalse(window.preview.empty_icon.pixmap().isNull())
            self.assertIn("Chưa có tài liệu", window.preview.empty_title.text())
            self.assertIn("PDF hoặc ảnh", window.preview.empty_description.text())
            window.add_document(image_path)
            self.application.processEvents()
            self.assertFalse(window.preview.empty_state.isVisibleTo(window))
            self.assertTrue(window.preview._scroll.isVisibleTo(window))
            window.close()

    def test_overview_shows_only_selected_page_and_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "two_pages.tiff"
            Image.new("RGB", (400, 600), "white").save(
                image_path, save_all=True,
                append_images=[Image.new("RGB", (400, 600), "black")],
            )
            window = MainWindow()
            window.add_document(image_path)
            window.active_session.result = OcrResult(
                None, None, 2, 19, 1.0, [], ["Trang đầu", "Trang tiếp theo"]
            )
            window._show_document(0)
            window.overview_button.click()
            self.assertEqual(window.overview_editor.toPlainText(), "Trang đầu")
            self.assertTrue(window.overview_editor.isReadOnly())
            self.assertEqual(window.review_action_button.text(), "Xuất TXT")
            window.page_list.setCurrentRow(1)
            self.assertEqual(window.overview_editor.toPlainText(), "Trang tiếp theo")
            self.assertNotIn("Trang đầu", window.overview_editor.toPlainText())
            window.close()

    def test_overview_export_saves_full_document_txt(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            source_text = Path(directory) / "recognized.txt"
            destination = Path(directory) / "exported.txt"
            Image.new("RGB", (400, 600), "white").save(image_path)
            source_text.write_text("Trang đầu\n\nTrang tiếp", encoding="utf-8")
            window = MainWindow()
            window.add_document(image_path)
            window.active_session.result = OcrResult(
                None, source_text, 2, 20, 1.0, [], ["Trang đầu", "Trang tiếp"]
            )
            window._show_document(0)
            window.overview_button.click()
            with patch("desktop.main_window.QFileDialog.getSaveFileName", return_value=(str(destination), "")):
                window.review_action_button.click()
            self.assertEqual(destination.read_text(encoding="utf-8"), "Trang đầu\n\nTrang tiếp")
            window.close()

    def test_overview_page_navigation_clears_region_highlight(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "two_pages.tiff"
            Image.new("RGB", (400, 600), "white").save(
                image_path, save_all=True,
                append_images=[Image.new("RGB", (400, 600), "black")],
            )
            window = MainWindow()
            window.add_document(image_path)
            window.active_session.result = OcrResult(None, None, 2, 10, 1.0, [{
                "page": 2, "image_size": [400, 600], "review_regions": [{
                    "page": 2, "region": "l01", "bbox": [10, 10, 120, 40],
                    "text": "Trang tiếp", "source": "tesseract", "reasons": [],
                    "candidates": {"tesseract": "Trang tiếp", "vietocr": "Trang tiếp"},
                }],
            }], ["Trang đầu", "Trang tiếp"])
            window._show_document(0)
            window.overview_button.click()
            window.page_list.setCurrentRow(1)
            self.assertIsNone(window.preview._highlight)
            window.close()

    def test_detail_edit_action_unlocks_selected_text_without_candidate_buttons(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            Image.new("RGB", (400, 600), "white").save(image_path)
            window = MainWindow()
            window.add_document(image_path)
            window.active_session.result = OcrResult(None, None, 1, 7, 1.0, [{
                "page": 1, "image_size": [400, 600], "review_regions": [{
                    "page": 1, "region": "l01", "bbox": [10, 10, 120, 40],
                    "text": "Bản gốc", "source": "tesseract", "reasons": [],
                    "candidates": {"tesseract": "Bản gốc", "vietocr": "Bản khác"},
                }],
            }], ["Bản gốc"])
            window._show_document(0)
            self.assertTrue(window.final_editor.isReadOnly())
            self.assertEqual(window.review_action_button.text(), "Chỉnh sửa")
            window.review_action_button.click()
            self.assertFalse(window.final_editor.isReadOnly())
            window.final_editor.setPlainText("Bản sửa")
            self.assertTrue(window.active_session.dirty)
            self.assertEqual(window.review_action_button.text(), "Lưu chỉnh sửa")
            self.assertEqual(window.overview_editor.toPlainText(), "Bản gốc")
            window.close()

    def test_review_footer_buttons_have_equal_sizes_in_both_modes(self):
        window = MainWindow()
        window.resize(1220, 760)
        window.show()
        self.application.processEvents()
        buttons = (window.detail_button, window.overview_button, window.review_action_button)
        self.assertEqual(len({(button.width(), button.height()) for button in buttons}), 1)
        window.overview_button.click()
        self.application.processEvents()
        self.assertEqual(len({(button.width(), button.height()) for button in buttons}), 1)
        window.close()

    def test_ai_warning_is_visible_and_unconfigured_ai_blocks_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            Image.new("RGB", (400, 600), "white").save(image_path)
            window = MainWindow()
            window.add_document(image_path)
            self.assertFalse(window.ai_warning.isVisibleTo(window))
            window.ai_toggle.setChecked(True)
            self.assertTrue(window.ai_warning.isVisibleTo(window))
            self.assertIn("Rủi ro lộ dữ liệu nhạy cảm", window.ai_warning.text())
            with patch("desktop.main_window.QMessageBox.information"):
                window.start_ocr()
            self.assertIsNone(window._thread)
            window.close()

    def test_ai_warning_opens_above_stationary_switch(self):
        window = MainWindow()
        window.resize(1220, 760)
        window.show()
        self.application.processEvents()
        switch_top = window.ai_toggle.y()
        window.ai_toggle.setChecked(True)
        self.application.processEvents()
        self.assertEqual(window.ai_toggle.y(), switch_top)
        self.assertLess(window.ai_warning.geometry().bottom(), window.ai_toggle.y())
        self.assertLess(window.ai_toggle.geometry().bottom(), window.run_button.y())
        window.close()

    def test_clicking_visual_ai_switch_toggles_warning(self):
        window = MainWindow()
        window.show()
        self.application.processEvents()
        switch = window.ai_toggle
        track_center = QPoint(switch.width() - 35, switch.height() // 2)
        QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=track_center)
        self.assertTrue(switch.isChecked())
        self.assertTrue(window.ai_warning.isVisibleTo(window))
        QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=track_center)
        self.assertFalse(switch.isChecked())
        self.assertFalse(window.ai_warning.isVisibleTo(window))
        window.close()

    def test_each_ocr_run_uses_a_new_output_path(self):
        session = DocumentSession(Path("source.pdf"), Path("session.pdf"))
        self.assertNotEqual(session.next_output_path(), session.next_output_path())

    def test_image_import_populates_page_navigation_without_running_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            Image.new("RGB", (400, 600), "white").save(image_path)
            window = MainWindow()
            window.add_document(image_path)
            self.assertEqual(window.page_list.count(), 1)
            self.assertTrue(window.run_button.isEnabled())
            self.assertFalse(window.export_pdf_button.isEnabled())
            window.close()

    def test_multipage_tiff_shows_all_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "two_pages.tiff"
            Image.new("RGB", (400, 600), "white").save(
                image_path, save_all=True,
                append_images=[Image.new("RGB", (400, 600), "black")],
            )
            window = MainWindow()
            window.add_document(image_path)
            self.assertEqual(window.page_list.count(), 2)
            window.close()

    def test_applied_correction_remains_when_editor_returns_to_saved_text(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            Image.new("RGB", (400, 600), "white").save(image_path)
            window = MainWindow()
            window.add_document(image_path)
            session = window.active_session
            session.corrections = {"1": {"l01": "Văn bản đã sửa"}}
            session.result = OcrResult(None, None, 1, 15, 1.0, [{
                "page": 1, "image_size": [400, 600], "review_regions": [{
                    "page": 1, "region": "l01", "bbox": [10, 10, 120, 40],
                    "text": "Văn bản đã sửa", "source": "manual", "reasons": [],
                    "candidates": {"tesseract": "Văn bản", "vietocr": "Văn bản đã sửa"},
                }],
            }])
            window._show_document(0)
            window.final_editor.setPlainText("Văn bản sửa tiếp")
            self.assertTrue(session.dirty)
            window.final_editor.setPlainText("Văn bản đã sửa")
            self.assertFalse(session.dirty)
            self.assertEqual(session.corrections["1"]["l01"],
                             {"text": "Văn bản đã sửa", "bbox": [10, 10, 120, 40]})
            window.close()

    def test_wide_review_crop_is_large_enough_to_read(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            Image.new("RGB", (1200, 1600), "white").save(image_path)
            window = MainWindow()
            window.add_document(image_path)
            session = window.active_session
            session.result = OcrResult(None, None, 1, 5, 1.0, [{
                "page": 1, "image_size": [1200, 1600], "review_regions": [{
                    "page": 1, "region": "l01", "bbox": [100, 200, 1100, 235],
                    "text": "Dòng dài", "source": "vietocr", "reasons": [],
                    "candidates": {"tesseract": "Dòng dài", "vietocr": "Dòng dài"},
                }],
            }])
            window._show_document(0)
            self.assertGreaterEqual(window.crop_label.pixmap().height(), 70)
            window.close()

    def test_editor_saves_bbox_with_manual_text(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            Image.new("RGB", (400, 600), "white").save(image_path)
            window = MainWindow()
            window.add_document(image_path)
            session = window.active_session
            session.result = OcrResult(None, None, 1, 5, 1.0, [{
                "page": 1, "image_size": [400, 600], "review_regions": [{
                    "page": 1, "region": "l01", "bbox": [10, 10, 120, 40],
                    "text": "Bản cũ", "source": "tesseract", "reasons": ["Cần đối chiếu"],
                    "candidates": {"tesseract": "Bản cũ", "vietocr": "Bản khác"},
                }],
            }])
            window._show_document(0)
            window.final_editor.setPlainText("Bản sửa")
            self.assertEqual(session.corrections["1"]["l01"],
                             {"text": "Bản sửa", "bbox": [10, 10, 120, 40]})
            window.close()

    def test_unmatched_correction_blocks_export_and_prompts_review(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            text_path = Path(directory) / "result.txt"
            Image.new("RGB", (400, 600), "white").save(image_path)
            text_path.write_text("Bản gốc", encoding="utf-8")
            window = MainWindow()
            window.add_document(image_path)
            session = window.active_session
            session.corrections = {"1": {"l01": {"text": "Bản sửa", "bbox": [10, 10, 120, 40]}}}
            window._running_session = session
            result = OcrResult(image_path, text_path, 1, 7, 1.0, [{
                "page": 1, "review_regions": [], "unapplied_corrections": ["l01"],
            }])
            window._on_ocr_completed(result)
            self.assertEqual(session.unapplied_count, 1)
            self.assertFalse(window.export_pdf_button.isEnabled())
            self.assertFalse(window.export_text_button.isEnabled())
            self.assertIn("không khớp vùng", window.status_label.text())
            window.close()


if __name__ == "__main__":
    unittest.main()
