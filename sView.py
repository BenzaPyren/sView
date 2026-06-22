#!/usr/bin/env python3

import sys
import os
import re
import datetime
import configparser
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QScrollArea, QStatusBar, QComboBox, QHBoxLayout, QWidget, QPushButton, QDialog, QVBoxLayout, QCheckBox
from PyQt6.QtGui import QPixmap, QMouseEvent, QWheelEvent, QTransform, QMovie, QImageReader
from PyQt6.QtCore import Qt, QPoint, QTimer, QEvent, QSize

# sView Minimal Viewer
# Copyright (C) 2026 BenzaPyren
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

def natural_sort_key(s):
    """Zerlegt den String in Text und Zahlen, um eine natürliche Sortierung zu ermöglichen."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

class SimpleImageViewer(QMainWindow):
    def __init__(self, start_path=None):
        super().__init__()
        self.setWindowTitle("sView Minimal Viewer")
        self.setGeometry(100, 100, 1200, 800)

        # Config Setup
        config_dir = os.path.expanduser("~/.config/sView")
        os.makedirs(config_dir, exist_ok=True)
        self.config_file = os.path.join(config_dir, "sView.ini")
        self.config = configparser.ConfigParser()

        # State
        self.image_paths = []
        self.current_index = -1
        self.zoom_factor = 1.0
        self.fit_to_window = True
        self.rotation_angle = 0
        self.flip_horizontal = False
        self.flip_vertical = False
        self.last_mouse_pos = QPoint()

        # UI Setup
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet("background-color: #1a1a1a; border: none;")
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCentralWidget(self.scroll_area)

        # Picture-Label
        self.label = QLabel()
        self.scroll_area.setWidget(self.label)

        # Event-Filters ScrollArea and Viewport
        self.scroll_area.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)

        # Drag & Drop
        self.setAcceptDrops(True)

        # Status bar and Dropdowns
        self.init_status_bar()

        # Load settings before loading first picture
        self.load_settings()

        # Load start-picture
        if start_path:
            if start_path.startswith("file://"):
                start_path = start_path.replace("file://", "")
            self.pending_start_path = os.path.abspath(start_path)
            QTimer.singleShot(100, self.load_initial_image)
        else:
            self.pending_start_path = None

    def init_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("background-color: #222; color: #aaa;")

        right_widget = QWidget()
        layout = QHBoxLayout(right_widget)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(10)

        # Loop Checkbox
        self.check_loop = QCheckBox("Loop")
        self.check_loop.setStyleSheet("""
            QCheckBox {
                color: #aaa;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                background-color: #333;
                border: 1px solid #555;
                border-radius: 2px;
            }
            QCheckBox::indicator:checked {
                background-color: #888;
                border: 1px solid #ccc;
            }
        """)
        self.check_loop.stateChanged.connect(self.save_settings)

        lbl_sort = QLabel("Sort by:")
        lbl_sort.setStyleSheet("color: #aaa; font-weight: bold;")

        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["Date", "Name", "Size", "Type"])
        self.combo_sort.setMinimumWidth(100)
        self.combo_sort.setStyleSheet("background-color: #333; color: #fff; border: 1px solid #555; padding: 2px;")

        self.combo_order = QComboBox()
        self.combo_order.addItems(["Descending", "Ascending"])
        self.combo_order.setMinimumWidth(120)
        self.combo_order.setStyleSheet("background-color: #333; color: #fff; border: 1px solid #555; padding: 2px;")

        # Help Button
        btn_help = QPushButton("?")
        btn_help.setFixedSize(24, 24)
        btn_help.setStyleSheet("""
            QPushButton {
                background-color: #444; color: #fff; border: 1px solid #555; border-radius: 12px; font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        btn_help.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_help.clicked.connect(self.show_help_dialog)

        layout.addWidget(self.check_loop)
        layout.addWidget(lbl_sort)
        layout.addWidget(self.combo_sort)
        layout.addWidget(self.combo_order)
        layout.addWidget(btn_help)

        self.status_bar.addPermanentWidget(right_widget)

        self.combo_sort.currentIndexChanged.connect(self.on_sort_changed)
        self.combo_order.currentIndexChanged.connect(self.on_sort_changed)

    def show_help_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("sView Help & Shortcuts")
        dialog.setFixedSize(450, 370)
        dialog.setStyleSheet("background-color: #222; color: #eee; font-size: 13px;")

        layout = QVBoxLayout(dialog)

        help_text = """
        <h3 style='color: #fff; margin-bottom: 5px;'>Navigation & Viewing</h3>
        <ul style='margin-top: 0px;'>
            <li><b>Mouse Wheel down / up</b>: Next / Previous image</li>
            <li><b>Double Left Click</b>: Toggle 'Fit to Window' / '100% Zoom'</li>
            <li><b>Left Click & Drag</b>: Pan image (when zoomed in)</li>
        </ul>
        <h3 style='color: #fff; margin-bottom: 5px;'>Shortcuts</h3>
        <ul style='margin-top: 0px;'>
            <li><b>Ctrl + Mouse Wheel</b>: Zoom in / out</li>
            <li><b>Alt + Mouse Wheel</b>: Rotate image by 90° (Static only)</li>
            <li><b>Shift + Mouse Wheel</b>: Flip image horizontally/vertically (Static only)</li>
            <li><b>Right Click</b> or <b>Ctrl+C</b>: Copy image to clipboard</li>
            <li><b>F1</b>: Show this help window</li>
        </ul>
        """

        lbl = QLabel(help_text)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #444; border: 1px solid #555; padding: 6px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()

    def load_settings(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            if 'Settings' in self.config:
                sort_val = self.config['Settings'].get('sort', 'Date')
                order_val = self.config['Settings'].get('order', 'Descending')
                loop_val = self.config['Settings'].get('loop', 'False') == 'True'

                self.combo_sort.blockSignals(True)
                self.combo_order.blockSignals(True)
                self.check_loop.blockSignals(True)

                self.combo_sort.setCurrentText(sort_val)
                self.combo_order.setCurrentText(order_val)
                self.check_loop.setChecked(loop_val)

                self.combo_sort.blockSignals(False)
                self.combo_order.blockSignals(False)
                self.check_loop.blockSignals(False)

    def save_settings(self):
        if 'Settings' not in self.config:
            self.config['Settings'] = {}
        self.config['Settings']['sort'] = self.combo_sort.currentText()
        self.config['Settings']['order'] = self.combo_order.currentText()
        self.config['Settings']['loop'] = str(self.check_loop.isChecked())

        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def load_initial_image(self):
        if self.pending_start_path and os.path.isfile(self.pending_start_path):
            self.load_folder(self.pending_start_path)

    def load_folder(self, target_file):
        folder = os.path.dirname(target_file)

        # Dynamically fetch supported image types from PyQt
        supported_formats = [bytes(fmt).decode('utf-8').lower() for fmt in QImageReader.supportedImageFormats()]

        # Add aliases in case system fails to
        aliases = {'jpeg': ['jpg', 'jfif'], 'tiff': ['tif']}
        for base_fmt, alias_list in aliases.items():
            if base_fmt in supported_formats:
                for alias in alias_list:
                    if alias not in supported_formats:
                        supported_formats.append(alias)

        valid_ext = tuple(f".{ext}" for ext in supported_formats)

        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(valid_ext)]

        sort_mode = self.combo_sort.currentText()
        is_descending = self.combo_order.currentText() == "Descending"

        if sort_mode == "Date":
            files.sort(key=os.path.getmtime, reverse=is_descending)
        elif sort_mode == "Size":
            files.sort(key=os.path.getsize, reverse=is_descending)
        elif sort_mode == "Type":
            # Typ (Dateiendung) primär, danach natürliche Sortierung für den Dateinamen
            files.sort(key=lambda x: (os.path.splitext(x)[1].lower(), natural_sort_key(os.path.basename(x))), reverse=is_descending)
        elif sort_mode == "Name":
            # Sortiert natürlich nach Dateinamen (bild2.png vor bild10.png)
            files.sort(key=lambda x: natural_sort_key(os.path.basename(x)), reverse=is_descending)
        else:
            files.sort(key=lambda x: natural_sort_key(os.path.basename(x)), reverse=is_descending)

        self.image_paths = files

        if target_file in self.image_paths:
            self.current_index = self.image_paths.index(target_file)
        elif self.image_paths:
            self.current_index = 0

        self.show_image()

    def on_sort_changed(self):
        self.save_settings()
        if 0 <= self.current_index < len(self.image_paths):
            current_file = self.image_paths[self.current_index]
            self.load_folder(current_file)

    def show_image(self):
        if 0 <= self.current_index < len(self.image_paths):
            path = self.image_paths[self.current_index]

            filename = os.path.basename(path)
            timestamp = os.path.getmtime(path)
            date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            size_bytes = os.path.getsize(path)
            size_mb = size_bytes / (1024 * 1024)

            self.setWindowTitle(f"{filename}  |  Created: {date_str}  |  Size: {size_mb:.2f} MB")

            # Reset transformationen when next picture
            self.zoom_factor = 1.0
            self.fit_to_window = True
            self.rotation_angle = 0
            self.flip_horizontal = False
            self.flip_vertical = False
            self.just_loaded = True

            # Clear movie
            if hasattr(self, 'movie') and self.movie:
                self.movie.stop()
                self.label.setMovie(None)
                self.movie = None

            self.is_animated = path.lower().endswith(('.gif', '.webp'))

            if self.is_animated:
                self.movie = QMovie(path)
                if self.movie.isValid() and self.movie.frameCount() > 1:
                    self.label.setMovie(self.movie)
                    self.movie.start()
                else:
                    self.is_animated = False
                    self.pixmap = QPixmap(path)
                    self.label.setPixmap(self.pixmap)
            else:
                self.pixmap = QPixmap(path)

            QTimer.singleShot(10, self.update_display)

    def update_display(self):
        viewport_size = self.scroll_area.viewport().size()

        is_anim = getattr(self, 'is_animated', False) and hasattr(self, 'movie') and self.movie
        has_pix = hasattr(self, 'pixmap') and not self.pixmap.isNull()

        if not is_anim and not has_pix:
            return

        # --- 1. Determine original size and apply transformation ---
        if is_anim:
            orig_size = self.movie.frameRect().size()
            if orig_size.isEmpty() and self.movie.currentPixmap():
                orig_size = self.movie.currentPixmap().size()
            orig_w, orig_h = orig_size.width(), orig_size.height()
            if orig_w == 0 or orig_h == 0:
                return
        else:
            transform = QTransform()
            if self.flip_horizontal:
                transform.scale(-1, 1)
            if self.flip_vertical:
                transform.scale(1, -1)
            transform.rotate(self.rotation_angle)

            rotated_pixmap = self.pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            orig_w, orig_h = rotated_pixmap.width(), rotated_pixmap.height()

        # --- 2. Smart-Fit on first load ---
        if getattr(self, 'just_loaded', False):
            self.just_loaded = False
            if orig_w <= viewport_size.width() and orig_h <= viewport_size.height():
                self.fit_to_window = False
                self.zoom_factor = 1.0
            else:
                self.fit_to_window = True

        # --- 3. Update display ---
        if is_anim:
            self.label.setScaledContents(True)
            if self.fit_to_window:
                scaled_size = orig_size.scaled(viewport_size, Qt.AspectRatioMode.KeepAspectRatio)
                self.label.resize(scaled_size)
                calc_zoom = int((scaled_size.width() / orig_w) * 100) if orig_w > 0 else 100
                self.status_bar.showMessage(f"Image {self.current_index + 1}/{len(self.image_paths)} | Fit to Window ({calc_zoom}%) | {orig_w} x {orig_h} px [GIF/Video]", 0)
            else:
                w, h = int(orig_w * self.zoom_factor), int(orig_h * self.zoom_factor)
                new_size = QSize(max(1, w), max(1, h))
                self.label.resize(new_size)
                self.status_bar.showMessage(f"Image {self.current_index + 1}/{len(self.image_paths)} | Zoom: {int(self.zoom_factor * 100)}% | {orig_w} x {orig_h} px [GIF/Video]", 0)
        else:
            self.label.setScaledContents(False)
            if self.fit_to_window:
                scaled = rotated_pixmap.scaled(viewport_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.label.setPixmap(scaled)
                self.label.resize(scaled.size())
                calc_zoom = int((scaled.width() / orig_w) * 100) if orig_w > 0 else 100
                self.status_bar.showMessage(f"Image {self.current_index + 1}/{len(self.image_paths)}  |  Fit to Window ({calc_zoom}%)  |  {orig_w} x {orig_h} px", 0)
            else:
                w, h = int(orig_w * self.zoom_factor), int(orig_h * self.zoom_factor)
                scaled = rotated_pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.label.setPixmap(scaled)
                self.label.resize(scaled.size())
                self.status_bar.showMessage(f"Image {self.current_index + 1}/{len(self.image_paths)}  |  Zoom: {int(self.zoom_factor * 100)}%  |  {orig_w} x {orig_h} px", 0)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.Wheel:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.handle_zoom_wheel(event)
                return True
            elif event.modifiers() == Qt.KeyboardModifier.AltModifier:
                self.handle_rotate_wheel(event)
                return True
            elif event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                self.handle_flip_wheel(event)
                return True
            else:
                self.handle_browse_wheel(event)
                return True
        return super().eventFilter(source, event)

    def handle_zoom_wheel(self, event: QWheelEvent):
        is_anim = getattr(self, 'is_animated', False) and hasattr(self, 'movie') and self.movie
        has_pix = hasattr(self, 'pixmap') and not self.pixmap.isNull()

        if not is_anim and not has_pix:
            return

        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()

        mouse_pos_global = event.globalPosition().toPoint()
        mouse_pos_viewport = self.scroll_area.viewport().mapFromGlobal(mouse_pos_global)

        click_x = mouse_pos_viewport.x() + h_bar.value()
        click_y = mouse_pos_viewport.y() + v_bar.value()

        if is_anim:
            orig_size = self.movie.frameRect().size()
            if orig_size.isEmpty() and self.movie.currentPixmap():
                orig_size = self.movie.currentPixmap().size()
            orig_w = orig_size.width()
        else:
            # Consider Transformation when doing zoom-calculation
            transform = QTransform()
            if self.flip_horizontal: transform.scale(-1, 1)
            if self.flip_vertical: transform.scale(1, -1)
            transform.rotate(self.rotation_angle)
            orig_w = self.pixmap.transformed(transform).width()

        if orig_w == 0:
            return

        if self.fit_to_window:
            old_zoom = self.label.width() / orig_w
            self.zoom_factor = old_zoom
            self.fit_to_window = False
        else:
            old_zoom = self.zoom_factor

        adj = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.zoom_factor = old_zoom * adj
        self.zoom_factor = max(0.05, min(self.zoom_factor, 20.0))

        self.update_display()

        zoom_ratio = self.zoom_factor / old_zoom
        new_scroll_x = int(click_x * zoom_ratio - mouse_pos_viewport.x())
        new_scroll_y = int(click_y * zoom_ratio - mouse_pos_viewport.y())

        h_bar.setValue(new_scroll_x)
        v_bar.setValue(new_scroll_y)

    def handle_rotate_wheel(self, event: QWheelEvent):
        if getattr(self, 'is_animated', False):
            self.status_bar.showMessage("Rotation is disabled for animated images.", 2000)
            return

        delta_y = event.angleDelta().y()
        delta_x = event.angleDelta().x()
        scroll_val = delta_y if delta_y != 0 else delta_x

        if scroll_val > 0:
            self.rotation_angle = (self.rotation_angle - 90) % 360
        elif scroll_val < 0:
            self.rotation_angle = (self.rotation_angle + 90) % 360

        self.update_display()

    def handle_flip_wheel(self, event: QWheelEvent):
        if getattr(self, 'is_animated', False):
            self.status_bar.showMessage("Flipping is disabled for animated images.", 2000)
            return

        # Mousewheel up = horizontal, Mousewheel down = vertical
        if event.angleDelta().y() > 0:
            self.flip_horizontal = not self.flip_horizontal
            self.status_bar.showMessage("Flipped horizontally", 1500)
        elif event.angleDelta().y() < 0:
            self.flip_vertical = not self.flip_vertical
            self.status_bar.showMessage("Flipped vertically", 1500)

        self.update_display()

    def handle_browse_wheel(self, event: QWheelEvent):
        if not self.image_paths:
            return

        # Navigation
        if event.angleDelta().y() < 0:  # Scroll down (next image)
            if self.current_index < len(self.image_paths) - 1:
                self.current_index += 1
            elif self.check_loop.isChecked():
                self.current_index = 0
            else:
                return
            self.show_image()

        elif event.angleDelta().y() > 0:  # Scroll up (previous image)
            if self.current_index > 0:
                self.current_index -= 1
            elif self.check_loop.isChecked():
                self.current_index = len(self.image_paths) - 1
            else:
                return
            self.show_image()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = event.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            self.copy_to_clipboard()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.fit_to_window:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()

            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.fit_to_window:
                self.fit_to_window = False
                self.zoom_factor = 1.0
            else:
                self.fit_to_window = True
                self.zoom_factor = 1.0
            self.update_display()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_C:
            self.copy_to_clipboard()
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Space):
            if self.current_index < len(self.image_paths) - 1:
                self.current_index += 1
                self.show_image()
            elif self.check_loop.isChecked() and self.image_paths:
                self.current_index = 0
                self.show_image()
        elif event.key() == Qt.Key.Key_Left:
            if self.current_index > 0:
                self.current_index -= 1
                self.show_image()
            elif self.check_loop.isChecked() and self.image_paths:
                self.current_index = len(self.image_paths) - 1
                self.show_image()
        elif event.key() == Qt.Key.Key_F1:
            self.show_help_dialog()

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        if getattr(self, 'is_animated', False) and hasattr(self, 'movie') and self.movie:
            current_pixmap = self.movie.currentPixmap()
            if not current_pixmap.isNull():
                clipboard.setPixmap(current_pixmap)
                self.status_bar.showMessage("Animation frame copied to clipboard!", 3000)
        elif hasattr(self, 'pixmap') and not self.pixmap.isNull():
            transform = QTransform()
            if self.flip_horizontal: transform.scale(-1, 1)
            if self.flip_vertical: transform.scale(1, -1)
            transform.rotate(self.rotation_angle)

            rotated_pixmap = self.pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            clipboard.setPixmap(rotated_pixmap)
            self.status_bar.showMessage("Image copied to clipboard!", 3000)

        QTimer.singleShot(3000, self.update_display)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                self.load_folder(path)
                break

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_to_window:
            self.update_display()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    start_file = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = SimpleImageViewer(start_file)
    viewer.show()
    sys.exit(app.exec())
