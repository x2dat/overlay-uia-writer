"""
Overlay UIA Writer
- Draggable always-on-top translucent PyQt6 overlay.
- Capture target with Alt+Shift+U. Quit with Alt+Shift+Q.
- If target control supports UI Automation (Value/Text pattern), the app will set the control's text
  directly (background write) while this overlay remains focused.
- If UIA is not supported for the target, the overlay will notify you and typing must be done with
  the target focused (fallback).
"""

import sys
import time
import random
import threading
from typing import Optional, Tuple

from PyQt6.QtWidgets import (
    QApplication, QWidget, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import pyperclip
import pyautogui
import pygetwindow as gw

from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError

from pynput import keyboard

# ---------- Typing/Set worker ----------
class UIAWriteThread(QThread):
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, get_text, get_target_tuple, get_speed, get_mistake):
        super().__init__()
        self.get_text = get_text
        self.get_target_tuple = get_target_tuple
        self.get_speed = get_speed
        self.get_mistake = get_mistake
        self._stop = threading.Event()
        self._paused = False

    def run(self):
        text = self.get_text()
        if not text:
            self.status_signal.emit("No text provided.")
            return

        target = self.get_target_tuple()
        if not target:
            self.status_signal.emit("No target captured.")
            return

        hwnd, uia_supported, uia_control = target

        # If UIA supported, attempt background set
        if uia_supported and uia_control is not None:
            self.status_signal.emit("Target supports UIA — attempting background set.")
            try:
                ctl = uia_control
                # Try a few safe value-setting approaches (do NOT change focus)
                try:
                    # common method for edit-like controls
                    ctl.set_edit_text(text)
                    self.progress_signal.emit(100)
                    self.status_signal.emit("UIA set_edit_text completed.")
                    return
                except Exception:
                    pass

                try:
                    # try Value pattern if available
                    if hasattr(ctl, 'iface_value'):
                        ctl.iface_value.SetValue(text)
                        self.progress_signal.emit(100)
                        self.status_signal.emit("UIA ValuePattern SetValue completed.")
                        return
                except Exception:
                    pass

                try:
                    # as a final wrapper fallback
                    wrapper = ctl.wrapper_object()
                    wrapper.set_edit_text(text)
                    self.progress_signal.emit(100)
                    self.status_signal.emit("UIA wrapper set_edit_text completed.")
                    return
                except Exception as e:
                    self.status_signal.emit(f"UIA write attempts failed: {e}")
                    # Fall through to fallback typing
            except Exception as e:
                self.status_signal.emit(f"UIA error: {e}")

        # Fallback: foreground typing (only works if target is focused)
        self.status_signal.emit("Falling back to foreground typing. Target must be focused for this to work.")
        self._type_foreground(text, hwnd)

    def _type_foreground(self, text, hwnd):
        total = len(text)
        idx = 0
        while idx < total and not self._stop.is_set():
            if self._paused:
                time.sleep(0.05)
                continue

            active = gw.getActiveWindow()
            active_hwnd = None
            try:
                active_hwnd = active._hWnd
            except Exception:
                active_hwnd = getattr(active, 'handle', None)

            if active_hwnd != hwnd:
                self.status_signal.emit("Paused — target not focused. Focus target to resume.")
                # Wait until target focused or stopped
                while not self._stop.is_set():
                    active = gw.getActiveWindow()
                    try:
                        active_hwnd = active._hWnd
                    except Exception:
                        active_hwnd = getattr(active, 'handle', None)
                    if active_hwnd == hwnd:
                        self.status_signal.emit("Target focused — resuming foreground typing.")
                        break
                    time.sleep(0.12)
                if self._stop.is_set():
                    break

            ch = text[idx]
            mistake_chance = self.get_mistake() / 100.0
            do_mistake = random.random() < mistake_chance and ch.isprintable() and ch != '\n'
            if do_mistake:
                wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                pyautogui.write(wrong_char, interval=0)
                time.sleep(0.02)
                pyautogui.press('backspace')
                time.sleep(0.02)

            speed = max(1.0, self.get_speed())
            delay = 1.0 / speed
            pyautogui.write(ch, interval=0)
            time.sleep(delay)

            idx += 1
            if total > 0:
                self.progress_signal.emit(int(idx / total * 100))

        if self._stop.is_set():
            self.status_signal.emit("Stopped by user.")
        else:
            self.status_signal.emit("Typing finished.")

    def pause(self):
        self._paused = True
        self.status_signal.emit("Paused.")

    def resume(self):
        self._paused = False
        self.status_signal.emit("Resumed.")

    def stop(self):
        self._stop.set()
        self._paused = False

# ---------- Overlay UI ----------
class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Overlay UIA Writer")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setWindowOpacity(0.92)
        self.resize(480, 360)

        self._drag_offset = None

        self.target_hwnd: Optional[int] = None
        self.target_uia_supported: bool = False
        self.target_control = None

        self.worker: Optional[UIAWriteThread] = None

        self._hotkey_listener = None
        self.init_ui()
        self.register_hotkeys()

    def init_ui(self):
        v = QVBoxLayout(); v.setContentsMargins(10,10,10,10)

        top = QHBoxLayout()
        title = QLabel("Overlay UIA Writer")
        title.setStyleSheet("font-weight:bold; color:white;")
        top.addWidget(title)
        top.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22,22)
        close_btn.clicked.connect(self.close)
        top.addWidget(close_btn)
        v.addLayout(top)

        self.text_edit = QTextEdit(); self.text_edit.setFixedHeight(150)
        self.text_edit.setStyleSheet("background: rgba(60,60,60,0.7); color: white;")
        self.text_edit.setPlaceholderText("Type text here or press 'Use Clipboard' ...")
        v.addWidget(self.text_edit)

        row1 = QHBoxLayout()
        clipboard_btn = QPushButton("Use Clipboard"); clipboard_btn.clicked.connect(self.use_clipboard)
        row1.addWidget(clipboard_btn)
        select_btn = QPushButton("Select Target (Alt+Shift+U)"); select_btn.clicked.connect(self.show_capture_instructions)
        row1.addWidget(select_btn)
        v.addLayout(row1)

        self.target_label = QLabel("Target: (none)")
        self.target_label.setStyleSheet("color: lightgray;")
        v.addWidget(self.target_label)

        row2 = QHBoxLayout()
        self.start_btn = QPushButton("Start"); self.start_btn.clicked.connect(self.start_write)
        row2.addWidget(self.start_btn)
        self.pause_btn = QPushButton("Pause"); self.pause_btn.clicked.connect(self.pause_write)
        row2.addWidget(self.pause_btn)
        self.stop_btn = QPushButton("Stop"); self.stop_btn.clicked.connect(self.stop_write)
        row2.addWidget(self.stop_btn)
        v.addLayout(row2)

        v.addWidget(QLabel("Speed (chars/sec)"))
        speed_row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Orientation.Horizontal); self.speed_slider.setMinimum(1); self.speed_slider.setMaximum(200); self.speed_slider.setValue(14)
        self.speed_value_label = QLabel("14")
        self.speed_value_label.setStyleSheet("color: white; min-width: 30px;")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_value_label.setText(str(v)))
        speed_row.addWidget(self.speed_slider)
        speed_row.addWidget(self.speed_value_label)
        v.addLayout(speed_row)

        v.addWidget(QLabel("Mistake (%)"))
        mistake_row = QHBoxLayout()
        self.mistake_slider = QSlider(Qt.Orientation.Horizontal); self.mistake_slider.setMinimum(0); self.mistake_slider.setMaximum(100); self.mistake_slider.setValue(2)
        self.mistake_value_label = QLabel("2")
        self.mistake_value_label.setStyleSheet("color: white; min-width: 30px;")
        self.mistake_slider.valueChanged.connect(lambda v: self.mistake_value_label.setText(str(v)))
        mistake_row.addWidget(self.mistake_slider)
        mistake_row.addWidget(self.mistake_value_label)
        v.addLayout(mistake_row)

        self.status_label = QLabel("Status: idle"); self.status_label.setStyleSheet("color: lightgray;")
        v.addWidget(self.status_label)

        self.setLayout(v)
        self.setStyleSheet("""
            QWidget { background: rgba(32,32,32,0.65); border-radius: 10px; }
            QPushButton { background: rgba(220,220,220,0.08); color: white; padding: 6px; }
            QPushButton:pressed { background: rgba(255,255,255,0.06); }
        """)

    # dragging
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def use_clipboard(self):
        try:
            txt = pyperclip.paste()
            if txt:
                self.text_edit.setPlainText(txt); self.update_status("Loaded clipboard.")
            else:
                self.update_status("Clipboard empty.")
        except Exception as e:
            self.update_status(f"Clipboard error: {e}")

    def show_capture_instructions(self):
        QMessageBox.information(self, "Capture target",
            "To capture a target control (for background writing):\n\n"
            "1) Switch to the app and click inside the text field you want to target.\n"
            "2) Press the global hotkey: Alt+Shift+T\n\n"
            "If the control supports UI Automation, this overlay can set its value without giving that window focus."
        )

    # hotkeys: Alt+Shift+T to capture; Alt+Shift+Q to quit
    def register_hotkeys(self):
        def on_capture():
            self.attempt_capture_active_window()

        def on_quit():
            self.update_status("Quit hotkey pressed. Exiting.")
            QApplication.instance().quit()

        hotkeys = {
            '<alt>+<shift>+t': on_capture,
            '<alt>+<shift>+q': on_quit
        }
        self._hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
        self._hotkey_listener.start()

    def attempt_capture_active_window(self):
        active = gw.getActiveWindow()
        if not active:
            self.update_status("No active window to capture.")
            return
        hwnd = None
        try:
            hwnd = active._hWnd
        except Exception:
            hwnd = getattr(active, 'handle', None)
        self.target_hwnd = hwnd
        self.target_uia_supported = False
        self.target_control = None

        # try UIA attach
        if hwnd:
            try:
                app = Application(backend="uia").connect(handle=hwnd)
                dlg = app.window(handle=hwnd)
                ctrl = None
                # try to find Edit or Document controls
                try:
                    ctrl = dlg.child_window(control_type="Edit")
                except Exception:
                    ctrl = None
                if ctrl is None:
                    try:
                        ctrl = dlg.child_window(control_type="Document")
                    except Exception:
                        ctrl = None

                if ctrl is not None:
                    # test element_info to see if accessible
                    try:
                        _ = ctrl.element_info
                        self.target_uia_supported = True
                        self.target_control = ctrl
                        self.target_label.setText(f"Target: (UIA) {active.title[:60]}")
                        self.update_status("Captured target — UIA available for background writing.")
                        return
                    except Exception:
                        self.target_uia_supported = False
                        self.target_control = None
            except ElementNotFoundError:
                pass
            except Exception:
                pass

        # fallback: captured but no UIA control
        self.target_label.setText(f"Target: {active.title[:60]}")
        self.update_status("Captured target, but UIA editable control not found — background write unavailable.")

    def start_write(self):
        if self.worker and self.worker.isRunning():
            self.update_status("Worker already running.")
            return
        text = self.text_edit.toPlainText()
        if not text:
            self.update_status("No text to write.")
            return
        if not self.target_hwnd:
            self.update_status("No target captured. Use Alt+Shift+U while target is focused.")
            return

        def get_text(): return self.text_edit.toPlainText()
        def get_target_tuple(): return (self.target_hwnd, self.target_uia_supported, self.target_control)
        def get_speed(): return self.speed_slider.value()
        def get_mistake(): return self.mistake_slider.value()

        self.worker = UIAWriteThread(get_text, get_target_tuple, get_speed, get_mistake)
        self.worker.status_signal.connect(self.update_status)
        self.worker.progress_signal.connect(lambda p: None)
        self.worker.start()
        self.update_status("Write worker started.")

    def pause_write(self):
        if self.worker and self.worker.isRunning():
            if self.worker._paused:
                self.worker.resume()
            else:
                self.worker.pause()
        else:
            self.update_status("Not typing now.")

    def stop_write(self):
        if self.worker:
            self.worker.stop()
            self.update_status("Stopping worker...")
        else:
            self.update_status("Nothing to stop.")

    def update_status(self, s: str):
        self.status_label.setText(f"Status: {s}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        try:
            if self.worker:
                self.worker.stop(); self.worker.wait(0.5)
        except Exception:
            pass
        try:
            if self._hotkey_listener:
                self._hotkey_listener.stop()
        except Exception:
            pass
        event.accept()

# ---------- main ----------
def main():
    app = QApplication(sys.argv)
    overlay = Overlay()
    overlay.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
