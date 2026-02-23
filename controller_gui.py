import customtkinter as ctk
import rtmidi
import threading
import time
import os
import json
import ctypes
import uuid
import hashlib
import tkinter.messagebox
import tkinter.filedialog
from ctypes import wintypes
import subprocess
import webbrowser
import requests
import re
from urllib.parse import urlparse, parse_qs

import sys

# Selenium imports for URL monitoring
selenium_available = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    selenium_available = True
except ImportError:
    print("[Selenium] Not installed. Install with: pip install selenium")

# Global flag for Auto-Key
AUTOKEY_AVAILABLE = True # We check availability dynamically later

# Windows API structures and functions
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Window enumeration callback
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG)
    ]

# Windows API functions
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.SetCursorPos.argtypes = [wintypes.INT, wintypes.INT]
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.ULONG]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, wintypes.INT]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, wintypes.INT]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetAsyncKeyState.argtypes = [wintypes.INT]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, wintypes.ULONG]

# Mouse event constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# Keyboard constants
VK_CONTROL = 0x11
VK_Q = 0x51
VK_N = 0x4E
VK_D = 0x44
KEYEVENTF_KEYUP = 0x0002

# Window messages
WM_CLOSE = 0x0010
WM_SYSCOMMAND = 0x0112
SC_CLOSE = 0xF060

# ShowWindow constants
SW_RESTORE = 9

class WindowsHelper:
    """Helper class for Windows API operations"""

    @staticmethod
    def get_cursor_pos():
        """Get current cursor position"""
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)

    @staticmethod
    def set_cursor_pos(x, y):
        """Set cursor position"""
        user32.SetCursorPos(int(x), int(y))

    @staticmethod
    def click(x, y):
        """Click at position"""
        WindowsHelper.set_cursor_pos(x, y)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    @staticmethod
    def get_window_title(hwnd):
        """Get window title"""
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value

    @staticmethod
    def get_window_rect(hwnd):
        """Get window rectangle"""
        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {
            'left': rect.left,
            'top': rect.top,
            'right': rect.right,
            'bottom': rect.bottom,
            'width': rect.right - rect.left,
            'height': rect.bottom - rect.top
        }

    @staticmethod
    def find_windows_by_title(title_substring):
        """Find windows containing title substring"""
        windows = []

        def enum_callback(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                window_title = WindowsHelper.get_window_title(hwnd)
                if title_substring.lower() in window_title.lower():
                    rect = WindowsHelper.get_window_rect(hwnd)
                    if rect['width'] > 50:  # Filter out tiny windows
                        windows.append({
                            'hwnd': hwnd,
                            'title': window_title,
                            'rect': rect
                        })
            return True

        enum_proc = EnumWindowsProc(enum_callback)
        user32.EnumWindows(enum_proc, 0)
        return windows

    @staticmethod
    def activate_window(hwnd):
        """Activate and bring window to foreground"""
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        user32.SwitchToThisWindow(hwnd, True)

    @staticmethod
    def wait_for_left_click():
        """Wait for left mouse button click"""
        VK_LBUTTON = 0x01

        # Wait for button release
        while user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
            time.sleep(0.05)

        # Wait for button press
        while True:
            if user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
                return WindowsHelper.get_cursor_pos()
            time.sleep(0.01)

MIDI_PORT_CHECK = "loopMIDI"
CHANNEL = 0

CC_MAP = {
    "MUSIC_VOL": 21, "MIC_VOL": 20, "REVERB_LONG": 22, "REVERB_SHORT": 23, "TUNE": 27,
    "DELAY": 26,
    "MUTE_MUSIC": 25, "MUTE_MIC": 24, "TONE_VAL_SEND": 28,
    "DO_TONE": 30, "LAY_TONE": 31, "VANG_FX": 32, "FIX_MEO": 36,
    "EXTRA_BTN_1": 40, "EXTRA_BTN_2": 41, "EXTRA_BTN_3": 42, "EXTRA_BTN_4": 43, "EXTRA_BTN_5": 44,
    "EXTRA_KNOB_1": 45, "EXTRA_KNOB_2": 46, "EXTRA_KNOB_3": 47, "EXTRA_KNOB_4": 48, "EXTRA_KNOB_5": 49
}

class MidiHandler:
    def __init__(self):
        self.midiout = rtmidi.MidiOut()
        self.port_name = None
        self.is_connected = False
        self.last_sent = {}
        self.connect()

    def connect(self):
        ports = self.midiout.get_ports()
        for i, name in enumerate(ports):
            if MIDI_PORT_CHECK in name:
                self.midiout.open_port(i)
                self.port_name = name
                self.is_connected = True
                print(f"Connected to {name}")
                return True
        print(f"{MIDI_PORT_CHECK} not found!")
        return False

    def send_cc(self, cc, value):
        if self.is_connected and cc is not None:
            c = int(cc)
            val = max(0, min(127, int(value)))
            if self.last_sent.get(c) == val:
                return
            self.last_sent[c] = val
            self.midiout.send_message([0xB0 | CHANNEL, c, val])

midi = MidiHandler()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("Dark")
        self.col_bg = "#1a1a1a"
        self.col_btn_purple = "#6a4c9c"
        self.col_btn_green = "#4caf50"
        self.col_btn_red = "#d32f2f"
        self.col_btn_orange = "#f57c00"
        self.col_btn_yellow = "#fbc02d"
        self.col_text_green = "#4caf50"
        self.col_text_yellow = "#fbc02d"

        # LICENSE CHECK
        if self.validate_license():
            self.init_main_app()
        else:
            self.init_activation_screen()

    # --- LICENSE LOGIC ---
    def get_hwid(self):
        return str(uuid.getnode())

    def get_expected_key(self):
        return "HAU_SETUP_STUDIO_2025"

    def generate_token(self):
        raw = f"{self.get_expected_key()}|{self.get_hwid()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def validate_license(self):
        if not os.path.exists("license.dat"): return False
        try:
            with open("license.dat", "r") as f:
                saved_token = f.read().strip()
            return saved_token == self.generate_token()
        except: return False

    def init_activation_screen(self):
        self.title("KÍCH HOẠT BẢN QUYỀN")
        self.geometry("400x250")
        self.resizable(False, False)

        frame = ctk.CTkFrame(self, fg_color=self.col_bg)
        frame.pack(expand=True, fill="both")

        ctk.CTkLabel(frame, text="NHẬP KEY KÍCH HOẠT", font=("Arial", 18, "bold"), text_color="#4caf50").pack(pady=(40, 20))

        self.entry_key = ctk.CTkEntry(frame, placeholder_text="Nhập Key (Ví dụ: HAU_SETUP...)", width=300, justify="center", show="*")
        self.entry_key.pack(pady=10)

        ctk.CTkButton(frame, text="KÍCH HOẠT", fg_color="#4caf50", width=120, height=35, command=self.activate_license).pack(pady=20)

        ctk.CTkLabel(frame, text="Hậu Setup Live Studio © 2025", font=("Arial", 10), text_color="#555").pack(side="bottom", pady=10)

    def activate_license(self):
        user_key = self.entry_key.get().strip()
        expected = self.get_expected_key()

        if user_key == expected:
            try:
                token = self.generate_token()
                with open("license.dat", "w") as f:
                    f.write(token)

                tkinter.messagebox.showinfo("Thành công", "Kích hoạt bản quyền theo máy thành công!")

                for widget in self.winfo_children():
                    widget.destroy()
                self.init_main_app()

            except Exception as e:
                tkinter.messagebox.showerror("Lỗi", f"Không thể lưu license: {e}")
        else:
            tkinter.messagebox.showerror("Lỗi", "Key không đúng!")

    # --- MAIN APP LOGIC ---
    def init_main_app(self):
        self.title("BẢNG ĐIỀU KHIỂN TIẾNG VIỆT - Hậu Setup Live Studio")
        self.geometry("880x320")
        self.resizable(False, False)
        self.configure(fg_color=self.col_bg)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)

        self.btn_widgets = {}
        self.btn_states = {}
        self.btn_colors = {}

        self.slider_widgets = {}
        self.slider_labels = {}

        # Auto-Key coordinates configuration
        self.autokey_coords = {
            "listen_x_offset": 0.5,
            "listen_y_offset": 0.32,
            "send_x_offset": 0.5,
            "send_y_from_bottom": 140,
            "cubase_project_path": ""
        }

        # Auto-Key Detection state
        self.autokey_running = False
        self.autokey_analysis_thread = None
        self.audio_engine = None
        self.key_detector = None
        self.loopback_devices = []
        self.autokey_loaded = False
        
        # Essentia Key Detector state
        self.essentia_server_process = None
        self.essentia_server_port = 5000
        self.youtube_browser = None  # Selenium browser for monitoring
        self.youtube_monitor_thread = None  # URL monitoring thread
        self.youtube_monitor_active = False  # Monitoring flag
        self.youtube_panel = None  # Control panel window
        self.last_youtube_url = None  # Track last detected URL
        self.auto_detect_enabled = False  # Auto-detect flag
        
        # We will initialize loopback_devices list separately or lazily
        # For now, we'll try to get devices without loading heavy DSP libs if possible
        # but usually AudioEngine needs to be loaded first. Let's make it fully lazy.

        self.setup_left_panel()
        self.setup_center_panel()
        self.setup_right_panel()

        self.load_settings()
        self.load_autokey_coords()
        self.start_essentia_server()
        self.after(1000, self.open_saved_project)

    def open_saved_project(self):
        path = self.autokey_coords.get("cubase_project_path", "")
        if path and os.path.exists(path):
            try:
                print(f"Opening Cubase project: {path}")
                os.startfile(path)
            except Exception as e:
                print(f"Error opening project: {e}")

    def setup_left_panel(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=10)

        btns = [
            ("DÒ TONE", self.col_btn_purple, "DO_TONE"),
            ("LẤY TONE", self.col_btn_purple, "LAY_TONE"),
            ("NHẠC", self.col_btn_green, "MUTE_MUSIC"),
            ("MIC", self.col_btn_green, "MUTE_MIC"),
            ("VANG", self.col_btn_red, "VANG_FX"),
            ("AUTO-KEY", "#00bcd4", "AUTO_KEY_DETECT"),
            ("YOUTUBE", "#ff0000", "YOUTUBE_BROWSER"),  # Nút YouTube mới
            ("CÀI ĐẶT", "#1f77b4", "SETTINGS"),
            ("LƯU", self.col_btn_yellow, "SAVE")
        ]

        for i in range(1, 6):
            self.btn_states[f"EXTRA_BTN_{i}"] = False

        for i, (text, color, cc_key) in enumerate(btns):
            self.btn_states[cc_key] = False
            self.btn_colors[cc_key] = color

            cmd = lambda k=cc_key: self.on_btn_toggle(k)

            if cc_key == "DO_TONE":
                cmd = self.start_autokey
            elif cc_key == "LAY_TONE":
                cmd = self.start_lay_tone
            elif cc_key == "SAVE":
                cmd = self.save_settings
            elif cc_key == "SETTINGS":
                cmd = self.open_settings_popup
            elif cc_key == "AUTO_KEY_DETECT":
                cmd = self.toggle_autokey_detection
            elif cc_key == "YOUTUBE_BROWSER":
                cmd = self.open_youtube_browser

            btn = ctk.CTkButton(
                frame, text=text, fg_color=color,
                font=("Arial", 11, "bold"), height=28, width=75,
                hover_color=self.adjust_color(color),
                command=cmd
            )
            self.btn_widgets[cc_key] = btn

            r = i // 2
            c = i % 2
            btn.grid(row=r, column=c, padx=3, pady=4, sticky="ew")

    def setup_center_panel(self):
        frame = ctk.CTkFrame(self, fg_color="transparent", border_width=1, border_color="#333")
        frame.grid(row=0, column=1, sticky="nsew", padx=2, pady=10)

        sliders = [
            ("ÂM NHẠC", "MUSIC_VOL", self.col_btn_green),
            ("ÂM MIC", "MIC_VOL", self.col_btn_orange),
            ("VANG DÀI", "REVERB_LONG", "#888"),
            ("VANG NGẮN", "REVERB_SHORT", "#888"),
            ("Delay", "DELAY", "#888"),
        ]

        for i, (label_text, cc_key, color) in enumerate(sliders):
            lbl = ctk.CTkLabel(frame, text=label_text, font=("Arial", 10, "bold"), text_color=self.col_btn_yellow, width=70, anchor="w")
            lbl.grid(row=i, column=0, padx=5, pady=5)

            slider = ctk.CTkSlider(
                frame, from_=0, to=127, number_of_steps=127,
                progress_color=color, height=16,
                command=lambda val, k=cc_key: self.on_slider_change(val, k)
            )
            slider.set(100)
            slider.grid(row=i, column=1, padx=2, pady=5, sticky="ew")
            self.slider_widgets[cc_key] = slider

            val_lbl = ctk.CTkLabel(frame, text="79%", font=("Arial", 10), width=35)
            val_lbl.grid(row=i, column=2, padx=2, pady=5)
            self.slider_labels[cc_key] = val_lbl

        # bottom_frame = ctk.CTkFrame(frame, fg_color="transparent")
        # bottom_frame.grid(row=len(sliders), column=0, columnspan=3, pady=5)

        # opt = ctk.CTkOptionMenu(bottom_frame, values=["NHẠC TRẺ", "BOLERO", "REMIX"], fg_color="#1f77b4", height=24, font=("Arial", 11))
        # opt.pack(side="left", padx=5)

        # btn_fix = ctk.CTkButton(bottom_frame, text="Fix Méo", fg_color="#d32f2f", width=60, height=24, font=("Arial", 11), command=lambda: self.on_btn_click("FIX_MEO"))
        # btn_fix.pack(side="left", padx=5)

    def setup_right_panel(self):
        frame = ctk.CTkFrame(self, fg_color="#101010", corner_radius=10, border_color="#444", border_width=2)
        frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=10)

        ctk.CTkLabel(frame, text="TONE / TUNE", font=("Arial", 12, "bold"), text_color="white").pack(pady=5)

        tone_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tone_frame.pack(pady=2)

        ctk.CTkButton(tone_frame, text="TONE", fg_color=self.col_btn_green, width=50, height=24, font=("Arial", 11)).pack(side="left", padx=3)
        ctk.CTkButton(tone_frame, text="-", width=30, height=24, fg_color="#333", command=lambda: self.on_btn_click("TONE_DOWN")).pack(side="left", padx=1)

        self.tone_val = ctk.CTkLabel(tone_frame, text="0.0", font=("Arial", 14, "bold"), width=40, text_color="#00e676")
        self.tone_val.pack(side="left", padx=3)

        ctk.CTkButton(tone_frame, text="+", width=30, height=24, fg_color="#333", command=lambda: self.on_btn_click("TONE_UP")).pack(side="left", padx=1)

        tune_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tune_frame.pack(pady=10, fill="x", padx=5)

        ctk.CTkButton(tune_frame, text="TUNE", fg_color=self.col_btn_green, width=50, height=24, font=("Arial", 11)).pack(side="left")

        self.tune_slider = ctk.CTkSlider(tune_frame, from_=0, to=127, progress_color="#d32f2f", height=16)
        self.tune_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.tune_slider.configure(command=lambda v: self.on_slider_change(v, "TUNE"))
        self.slider_widgets["TUNE"] = self.tune_slider

        # === AUTO-KEY DETECTION DISPLAY ===
        autokey_frame = ctk.CTkFrame(frame, fg_color="#1a1a1a", corner_radius=8, border_color="#00bcd4", border_width=1)
        autokey_frame.pack(pady=5, padx=5, fill="x")

        autokey_header = ctk.CTkFrame(autokey_frame, fg_color="transparent")
        autokey_header.pack(fill="x", padx=5, pady=(3, 0))
        
        ctk.CTkLabel(autokey_header, text="🎵 AUTO-KEY", font=("Arial", 9, "bold"), text_color="#00bcd4").pack(side="left")
        
        self.autokey_status_label = ctk.CTkLabel(autokey_header, text="● OFF", font=("Arial", 8), text_color="#d32f2f")
        self.autokey_status_label.pack(side="right")
        
        # Audio file upload button
        self.upload_audio_btn = ctk.CTkButton(
            autokey_header, 
            text="📁", 
            width=20, 
            height=20, 
            fg_color="transparent",
            text_color="#00bcd4",
            hover_color="#333",
            font=("Arial", 12),
            command=self.detect_audio_file
        )
        self.upload_audio_btn.pack(side="right", padx=5)

        key_display_frame = ctk.CTkFrame(autokey_frame, fg_color="transparent")
        key_display_frame.pack(pady=2)

        # Key label (large)
        self.detected_key_label = ctk.CTkLabel(
            key_display_frame, 
            text="---", 
            font=("Arial", 24, "bold"), 
            text_color="#00e676"
        )
        self.detected_key_label.pack(side="left", padx=5)

        # Scale label
        self.detected_scale_label = ctk.CTkLabel(
            key_display_frame, 
            text="", 
            font=("Arial", 12), 
            text_color="#ffa726"
        )
        self.detected_scale_label.pack(side="left", padx=2)

        # Confidence bar
        self.autokey_confidence_bar = ctk.CTkProgressBar(autokey_frame, height=6, progress_color="#00bcd4")
        self.autokey_confidence_bar.pack(pady=(0, 4), padx=10, fill="x")
        self.autokey_confidence_bar.set(0)

        # Device selector
        dev_frame = ctk.CTkFrame(autokey_frame, fg_color="transparent")
        dev_frame.pack(fill="x", padx=5, pady=(0, 3))
        
        self.autokey_device_var = ctk.StringVar(value="Chọn nguồn âm thanh...")
        self.autokey_device_select = ctk.CTkOptionMenu(
            dev_frame, 
            values=["Chọn nguồn âm thanh..."],
            variable=self.autokey_device_var,
            font=("Arial", 8),
            height=20,
            width=160,
            fg_color="#333",
            dropdown_fg_color="#2a2a2a"
        )
        self.autokey_device_select.pack(fill="x")

        ctk.CTkLabel(frame, text="BẢNG ĐIỀU KHIỂN TIẾNG VIỆT", font=("Arial", 11, "bold"), text_color=self.col_text_yellow).pack(side="bottom", pady=2)
        ctk.CTkLabel(frame, text="Hậu Setup Live Studio", font=("Arial", 10, "bold"), text_color=self.col_text_green).pack(side="bottom", pady=2)

    def adjust_color(self, hex_color, factor=0.8):
        return hex_color

    def on_btn_toggle(self, key):
        cur_state = self.btn_states.get(key, False)
        new_state = not cur_state
        self.btn_states[key] = new_state

        btn = self.btn_widgets.get(key)
        orig_color = self.btn_colors.get(key)

        if btn:
            if new_state:
                btn.configure(fg_color="#F0F0F0", text_color="#000000")
            else:
                btn.configure(fg_color=orig_color, text_color="#FFFFFF")

        cc = CC_MAP.get(key)
        if cc:
            midi.send_cc(cc, 127)
            self.after(50, lambda: midi.send_cc(cc, 0))

        if key == "VANG_FX":
            for i in range(1, 6):
                extra_key = f"EXTRA_BTN_{i}"
                if self.btn_states.get(extra_key) != new_state:
                    self.on_btn_toggle(extra_key)

        if key == "LOFI" and new_state:
            # Cấu hình giọng Lofi: Tune 27, Flex 45, Vib 46, Human 47
            # Setup preset Lofi: Retune 20 (Soft), Flex 0, Vib 0, Human 0
            settings = [
                ("TUNE", 20),           # Retune Speed (CC 27)
                ("EXTRA_KNOB_1", 0),    # FlexTune (CC 45)
                ("EXTRA_KNOB_2", 0),    # Natural Vibrato (CC 46)
                ("EXTRA_KNOB_3", 0)     # Humanize (CC 47)
            ]
            for param, val in settings:
                if param in self.slider_widgets:
                    self.slider_widgets[param].set(val)
                    self.on_slider_change(val, param)

    def on_btn_click(self, key):
        if key not in ["TONE_UP", "TONE_DOWN"]:
            cc = CC_MAP.get(key)
            if cc:
                midi.send_cc(cc, 127)
                self.after(50, lambda: midi.send_cc(cc, 0))

        btn = self.btn_widgets.get(key)
        if btn:
            orig = self.btn_colors.get(key, "#333")
            btn.configure(fg_color="#ffffff", text_color="black")
            self.after(150, lambda: btn.configure(fg_color=orig, text_color="white"))

        if key == "TONE_UP":
            try:
                cur = float(self.tone_val.cget("text"))
                new_val = min(12.0, cur + 1.0)
                self.tone_val.configure(text=f"{new_val:.1f}")

                midi_val = int(64 + new_val * (63.5/12))
                midi_val = max(0, min(127, midi_val))
                midi.send_cc(CC_MAP.get("TONE_VAL_SEND"), midi_val)
            except: pass
        elif key == "TONE_DOWN":
            try:
                cur = float(self.tone_val.cget("text"))
                new_val = max(-12.0, cur - 1.0)
                self.tone_val.configure(text=f"{new_val:.1f}")

                midi_val = int(64 + new_val * (63.5/12))
                midi_val = max(0, min(127, midi_val))
                midi.send_cc(CC_MAP.get("TONE_VAL_SEND"), midi_val)
            except: pass

    def on_slider_change(self, value, key):
        cc = CC_MAP.get(key)
        if cc:
            midi.send_cc(cc, value)

        if key in self.slider_labels:
            percent = int((value / 127) * 100)
            self.slider_labels[key].configure(text=f"{percent}%")

    def save_settings(self):
        btn = self.btn_widgets.get("SAVE")
        if btn:
            orig = self.btn_colors.get("SAVE", "#333")
            btn.configure(fg_color="#ffffff", text_color="black")
            self.after(150, lambda: btn.configure(fg_color=orig, text_color="white"))

        data = {
            "toggles": self.btn_states,
            "sliders": {k: v.get() for k, v in self.slider_widgets.items()}
        }
        try:
            with open("config.json", "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print("Đã lưu cấu hình vào config.json")
        except Exception as e:
            print(f"Lỗi lưu file: {e}")

    def load_settings(self):
        if not os.path.exists("config.json"): return
        try:
            print("Đang tải cấu hình...")
            with open("config.json", "r", encoding='utf-8') as f:
                data = json.load(f)

            sliders_data = data.get("sliders", {})
            for k, v in sliders_data.items():
                if k in self.slider_widgets:
                    self.slider_widgets[k].set(v)
                    self.on_slider_change(v, k)

            toggles_data = data.get("toggles", {})
            for k, v in toggles_data.items():
                if k in self.btn_widgets and k not in ["DO_TONE", "SAVE"]:
                    if self.btn_states.get(k, False) != v:
                         self.on_btn_toggle(k)
        except Exception as e:
            print(f"Lỗi load config: {e}")

    def load_autokey_coords(self):
        if not os.path.exists("autokey_coords.json"):
            return
        try:
            with open("autokey_coords.json", "r", encoding='utf-8') as f:
                saved_coords = json.load(f)
                self.autokey_coords.update(saved_coords)
            print("Đã tải tọa độ Auto-Key từ autokey_coords.json")
        except Exception as e:
            print(f"Lỗi load tọa độ Auto-Key: {e}")

    def save_autokey_coords(self):
        try:
            with open("autokey_coords.json", "w", encoding='utf-8') as f:
                json.dump(self.autokey_coords, f, indent=4)
            print("Đã lưu tọa độ Auto-Key vào autokey_coords.json")
            return True
        except Exception as e:
            print(f"Lỗi lưu tọa độ Auto-Key: {e}")
            return False

    def pick_coordinate(self, button_name, x_entry, y_entry, popup):
        try:
            print(f"\n🎯 Bắt đầu đo tọa độ nút {button_name}...")

            # Focus Cubase
            print("   Focus Cubase...")
            cubase_wins = WindowsHelper.find_windows_by_title('Cubase')
            if cubase_wins:
                WindowsHelper.activate_window(cubase_wins[0]['hwnd'])
                time.sleep(1.0)

            # Find Auto-Key window
            autokey_wins = WindowsHelper.find_windows_by_title('Auto-Key')

            if not autokey_wins:
                print("❌ Không tìm thấy cửa sổ Auto-Key!")
                def show_err():
                    tkinter.messagebox.showerror(
                        "Lỗi",
                        "Không tìm thấy cửa sổ Auto-Key!\nVui lòng mở Plugin trong Cubase."
                    )
                    popup.deiconify()
                    popup.lift()
                    popup.focus_force()

                self.after(100, show_err)
                return

            target_win = autokey_wins[0]
            WindowsHelper.activate_window(target_win['hwnd'])

            rect = target_win['rect']
            print(f"📍 Cửa sổ Auto-Key: {rect['width']}x{rect['height']} tại ({rect['left']}, {rect['top']})")
            print(f"👆 Hướng dẫn: Click CHUỘT TRÁI vào nút {button_name} trên màn hình ngay bây giờ!")

            # Wait for click
            clicked_pos = WindowsHelper.wait_for_left_click()
            print(f"✅ Đã nhận tọa độ tại: {clicked_pos}")

            # Calculate offsets
            rel_x = clicked_pos[0] - rect['left']
            rel_y = clicked_pos[1] - rect['top']

            x_percent = (rel_x / rect['width']) * 100
            y_percent = (rel_y / rect['height']) * 100
            y_from_bottom = rect['height'] - rel_y

            print(f"📊 Tọa độ tương đối: X={rel_x}px, Y={rel_y}px")
            print(f"📊 Phần trăm: X={x_percent:.1f}%, Y={y_percent:.1f}%")
            print(f"📊 Y từ đáy: {y_from_bottom}px")

            def update_fields():
                x_entry.delete(0, "end")
                x_entry.insert(0, str(int(round(x_percent))))

                if button_name == "LISTEN":
                    y_entry.delete(0, "end")
                    y_entry.insert(0, str(int(round(y_percent))))
                else:  # SEND
                    y_entry.delete(0, "end")
                    y_entry.insert(0, str(int(round(y_from_bottom))))

                popup.deiconify()
                popup.lift()
                popup.focus_force()

                tkinter.messagebox.showinfo(
                    "Thành công",
                    f"Đã đo tọa độ nút {button_name}!\n\n"
                    f"X: {int(round(x_percent))}%\n"
                    f"Y: {int(round(y_percent if button_name == 'LISTEN' else y_from_bottom))}{'%' if button_name == 'LISTEN' else 'px'}"
                )

            self.after(100, update_fields)

        except Exception as e:
            print(f"❌ Lỗi khi đo tọa độ: {e}")
            def restore_on_err():
                tkinter.messagebox.showerror("Lỗi", f"Không thể đo tọa độ:\n{e}")
                popup.deiconify()
                popup.lift()
                popup.focus_force()
            self.after(100, restore_on_err)

    def open_settings_popup(self):
        btn = self.btn_widgets.get("SETTINGS")
        orig_color = "#1f77b4"
        if btn:
            btn.configure(text="ĐANG MỞ...", fg_color="#F0F0F0", text_color="black")

        popup = ctk.CTkToplevel(self)
        popup.title("CÀI ĐẶT TỌA ĐỘ AUTO-KEY")
        popup.geometry("550x520")
        popup.resizable(False, False)
        popup.configure(fg_color=self.col_bg)

        popup.transient(self)
        popup.grab_set()
        popup.focus_force()
        popup.lift()

        def on_close_popup():
            if btn:
                btn.configure(text="CÀI ĐẶT", fg_color=orig_color, text_color="white")
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_close_popup)

        ctk.CTkLabel(
            popup,
            text="CÀI ĐẶT TỌA ĐỘ NÚT AUTO-KEY",
            font=("Arial", 16, "bold"),
            text_color=self.col_text_green
        ).pack(pady=10)

        ctk.CTkLabel(
            popup,
            text="Chuột phải vào ô nhập để lấy tọa độ tự động",
            font=("Arial", 11, "italic"),
            text_color="#ffa726"
        ).pack(pady=(0, 10))

        settings_frame = ctk.CTkFrame(popup, fg_color="transparent")
        settings_frame.pack(pady=5, padx=20, fill="both", expand=True)

        listen_x_entry = ctk.CTkEntry(settings_frame, width=80)
        listen_y_entry = ctk.CTkEntry(settings_frame, width=80)

        ctk.CTkLabel(settings_frame, text="Nút LISTEN - X (%):", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w", pady=8, padx=5)
        listen_x_entry.insert(0, str(int(self.autokey_coords["listen_x_offset"] * 100)))
        listen_x_entry.grid(row=0, column=1, pady=8, padx=5)

        ctk.CTkLabel(settings_frame, text="Nút LISTEN - Y (%):", font=("Arial", 11, "bold")).grid(row=1, column=0, sticky="w", pady=8, padx=5)
        listen_y_entry.insert(0, str(int(self.autokey_coords["listen_y_offset"] * 100)))
        listen_y_entry.grid(row=1, column=1, pady=8, padx=5)

        def pick_listen_coords(e=None):
            popup.withdraw()
            threading.Thread(target=lambda: self.pick_coordinate("LISTEN", listen_x_entry, listen_y_entry, popup), daemon=True).start()

        listen_x_entry.bind("<Button-3>", pick_listen_coords)
        listen_y_entry.bind("<Button-3>", pick_listen_coords)

        ctk.CTkButton(settings_frame, text="ĐO TỌA ĐỘ", fg_color="#ff9800", width=90, height=28, command=pick_listen_coords).grid(row=0, column=3, rowspan=2, padx=10)

        send_x_entry = ctk.CTkEntry(settings_frame, width=80)
        send_y_entry = ctk.CTkEntry(settings_frame, width=80)

        ctk.CTkLabel(settings_frame, text="Nút SEND - X (%):", font=("Arial", 11, "bold")).grid(row=2, column=0, sticky="w", pady=8, padx=5)
        send_x_entry.insert(0, str(int(self.autokey_coords["send_x_offset"] * 100)))
        send_x_entry.grid(row=2, column=1, pady=8, padx=5)

        ctk.CTkLabel(settings_frame, text="Nút SEND - Y (px):", font=("Arial", 11, "bold")).grid(row=3, column=0, sticky="w", pady=8, padx=5)
        send_y_entry.insert(0, str(self.autokey_coords["send_y_from_bottom"]))
        send_y_entry.grid(row=3, column=1, pady=8, padx=5)

        def pick_send_coords(e=None):
            popup.withdraw()
            threading.Thread(target=lambda: self.pick_coordinate("SEND", send_x_entry, send_y_entry, popup), daemon=True).start()

        send_x_entry.bind("<Button-3>", pick_send_coords)
        send_y_entry.bind("<Button-3>", pick_send_coords)

        ctk.CTkButton(settings_frame, text="ĐO TỌA ĐỘ", fg_color="#ff9800", width=90, height=28, command=pick_send_coords).grid(row=2, column=3, rowspan=2, padx=10)

        # File Project Selection
        ctk.CTkLabel(settings_frame, text="File Project:", font=("Arial", 11, "bold")).grid(row=4, column=0, sticky="w", pady=8, padx=5)
        project_entry = ctk.CTkEntry(settings_frame, width=150)
        project_entry.insert(0, self.autokey_coords.get("cubase_project_path", ""))
        project_entry.grid(row=4, column=1, columnspan=2, pady=8, padx=5, sticky="ew")

        def choose_project():
            path = tkinter.filedialog.askopenfilename(filetypes=[("Cubase Project", "*.cpr"), ("All Files", "*.*")])
            if path:
                project_entry.delete(0, "end")
                project_entry.insert(0, path)
                popup.lift()
                popup.focus_force()

        ctk.CTkButton(settings_frame, text="CHỌN FILE", fg_color="#1f77b4", width=90, height=28, command=choose_project).grid(row=4, column=3, padx=10)

        info_text = ctk.CTkTextbox(popup, height=80, width=500, fg_color="#2a2a2a")
        info_text.pack(pady=10, padx=20)
        info_text.insert("1.0",
            "💡 Hướng dẫn:\n"
            "1. Mở cửa sổ Auto-Key Plugin trong Cubase\n"
            "2. Click 'ĐO TỌA ĐỘ' bên cạnh nút muốn đo\n"
            "3. Đợi cửa sổ Auto-Key hiện lên, sau đó click vào nút Listen/Send\n"
            "4. Tọa độ sẽ tự động được tính và điền vào"
        )
        info_text.configure(state="disabled")

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=15)

        def save_coords():
            try:
                self.autokey_coords["listen_x_offset"] = float(listen_x_entry.get()) / 100
                self.autokey_coords["listen_y_offset"] = float(listen_y_entry.get()) / 100
                self.autokey_coords["send_x_offset"] = float(send_x_entry.get()) / 100
                self.autokey_coords["send_y_from_bottom"] = int(send_y_entry.get())
                self.autokey_coords["cubase_project_path"] = project_entry.get()

                if self.save_autokey_coords():
                    tkinter.messagebox.showinfo("Thành công", "Đã lưu tọa độ Auto-Key!")
                    on_close_popup()
                else:
                    tkinter.messagebox.showerror("Lỗi", "Không thể lưu tọa độ!")
            except ValueError:
                tkinter.messagebox.showerror("Lỗi", "Vui lòng nhập số hợp lệ!")

        ctk.CTkButton(
            btn_frame,
            text="LƯU",
            fg_color=self.col_btn_green,
            width=100,
            height=35,
            font=("Arial", 12, "bold"),
            command=save_coords
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="HỦY",
            fg_color=self.col_btn_red,
            width=100,
            height=35,
            font=("Arial", 12, "bold"),
            command=on_close_popup
        ).pack(side="left", padx=10)

    def start_autokey(self):
        print("Bắt đầu Dò Tone...")
        cc = CC_MAP.get("DO_TONE")
        if cc: midi.send_cc(cc, 127)

        btn = self.btn_widgets.get("DO_TONE")
        if btn: btn.configure(text="ĐANG DÒ...", fg_color="#F0F0F0", text_color="black")

        threading.Thread(target=self.auto_detect_tone_thread, daemon=True).start()

    def auto_detect_tone_thread(self):
        try:
            original_pos = WindowsHelper.get_cursor_pos()

            print("[1/3] Focus Cubase...")
            cubase_wins = WindowsHelper.find_windows_by_title('Cubase')
            if not cubase_wins:
                print("❌ Không thấy Cubase! Hãy mở Cubase.")
                return

            WindowsHelper.activate_window(cubase_wins[0]['hwnd'])
            time.sleep(0.3)

            autokey_wins = WindowsHelper.find_windows_by_title('Auto-Key')
            if not autokey_wins:
                print("❌ Không thấy Plugin Auto-Key! Hãy mở Plugin lên màn hình.")
                return

            target_win = autokey_wins[0]
            WindowsHelper.activate_window(target_win['hwnd'])
            time.sleep(0.5)

            rect = target_win['rect']
            listen_x = rect['left'] + int(rect['width'] * self.autokey_coords["listen_x_offset"])
            listen_y = rect['top'] + int(rect['height'] * self.autokey_coords["listen_y_offset"])
            send_x = rect['left'] + int(rect['width'] * self.autokey_coords["send_x_offset"])
            send_y = rect['top'] + rect['height'] - self.autokey_coords["send_y_from_bottom"]

            print(f"Click Listen ({listen_x}, {listen_y})...")
            WindowsHelper.click(listen_x, listen_y)

            print("Đang nghe (15s)...")
            time.sleep(15)

            print(f"Click Send ({send_x}, {send_y})...")
            WindowsHelper.click(send_x, send_y)

            WindowsHelper.set_cursor_pos(original_pos[0], original_pos[1])
            print("✅ Xong quy trình!")

        except Exception as e:
            print(f"Lỗi: {e}")
        finally:
            cc = CC_MAP.get("DO_TONE")
            if cc: midi.send_cc(cc, 0)

            btn = self.btn_widgets.get("DO_TONE")
            orig_col = self.btn_colors.get("DO_TONE", self.col_btn_purple)
            if btn: btn.configure(text="DÒ TONE", fg_color=orig_col, text_color="white")

    def start_lay_tone(self):
        print("Bắt đầu Lấy Tone...")
        cc = CC_MAP.get("LAY_TONE")
        if cc: midi.send_cc(cc, 127)

        btn = self.btn_widgets.get("LAY_TONE")
        if btn: btn.configure(text="ĐANG LẤY...", fg_color="#F0F0F0", text_color="black")

        threading.Thread(target=self.lay_tone_thread, daemon=True).start()

    def lay_tone_thread(self):
        try:
            original_pos = WindowsHelper.get_cursor_pos()

            print("[1/3] Focus Cubase...")
            cubase_wins = WindowsHelper.find_windows_by_title('Cubase')
            if not cubase_wins:
                print("❌ Không thấy Cubase! Hãy mở Cubase.")
                return

            WindowsHelper.activate_window(cubase_wins[0]['hwnd'])
            time.sleep(0.1)

            autokey_wins = WindowsHelper.find_windows_by_title('Auto-Key')
            if not autokey_wins:
                print("❌ Không thấy Plugin Auto-Key! Hãy mở Plugin lên màn hình.")
                return

            target_win = autokey_wins[0]
            WindowsHelper.activate_window(target_win['hwnd'])
            time.sleep(0.5)

            rect = target_win['rect']
            send_x = rect['left'] + int(rect['width'] * self.autokey_coords["send_x_offset"])
            send_y = rect['top'] + rect['height'] - self.autokey_coords["send_y_from_bottom"]

            print(f"Click Send ({send_x}, {send_y})...")
            WindowsHelper.click(send_x, send_y)

            WindowsHelper.set_cursor_pos(original_pos[0], original_pos[1])
            print("✅ Xong quy trình!")

        except Exception as e:
            print(f"Lỗi: {e}")
        finally:
            cc = CC_MAP.get("LAY_TONE")
            if cc: midi.send_cc(cc, 0)

            btn = self.btn_widgets.get("LAY_TONE")
            orig_col = self.btn_colors.get("LAY_TONE", self.col_btn_purple)
            if btn: btn.configure(text="LẤY TONE", fg_color=orig_col, text_color="white")

    # === AUTO-KEY DETECTION METHODS ===
    def ensure_autokey_loaded(self):
        """Lazy load heavy Auto-Key libraries and initialize components."""
        if self.autokey_loaded:
            return True
            
        if getattr(self, "autokey_loading", False):
            return False
            
        self.autokey_loading = True
        print("[Auto-Key] Loading heavy libraries (librosa, numpy, etc.)...")
        self.autokey_status_label.configure(text="● LOADING...", text_color="#ffa726")
        self.update_idletasks() # Refresh UI colors
        
        try:
            # Determine base path
            if getattr(sys, 'frozen', False):
                BASE_PATH = os.path.dirname(sys.executable)
            else:
                BASE_PATH = os.path.dirname(os.path.abspath(__file__))

            # Add to path
            if BASE_PATH not in sys.path:
                sys.path.insert(0, BASE_PATH)

            # Lazy Imports
            import numpy as np
            from autokey_tool.audio_engine import AudioEngine
            from autokey_tool.key_detector_improved import KeyDetector
            
            # Initialize components
            self.audio_engine = AudioEngine(
                sample_rate=44100,
                buffer_seconds=1.5,
                chunk_size=2048,
            )
            self.key_detector = KeyDetector(
                sample_rate=44100,
                smoothing_history=12,  # Faster response
                confidence_threshold=0.1,
                use_hpss=True,
            )
            
            # Pre-warm detector (initializes librosa filters to avoid first-run delay)
            print("[Auto-Key] Pre-warming detector...")
            dummy_audio = np.zeros(44100, dtype=np.float32)
            self.key_detector.detect_key(dummy_audio)
            self.key_detector.reset()
            
            # Load devices
            self.loopback_devices = self.audio_engine.get_loopback_devices()
            device_names = [d['name'][:40] for d in self.loopback_devices] # Increased length for better visibility
            
            if device_names:
                self.autokey_device_select.configure(values=device_names)
                
                # Intelligent Auto-Select Logic
                best_device = device_names[0]
                priority_keywords = ["default", "speaker", "stereo mix", "what u hear", "loopback"]
                
                found_priority = False
                for keyword in priority_keywords:
                    for name in device_names:
                        if keyword.lower() in name.lower():
                            best_device = name
                            found_priority = True
                            print(f"[Auto-Key] Auto-selected device: {best_device}")
                            break
                    if found_priority: break
                
                self.autokey_device_var.set(best_device)
            
            self.autokey_loaded = True
            print(f"[Auto-Key] Successfully loaded. Found {len(self.loopback_devices)} devices.")
            return True
        except Exception as e:
            print(f"[Auto-Key] Error during lazy load: {e}")
            import traceback
            traceback.print_exc()
            tkinter.messagebox.showerror("Lỗi", f"Không thể tải Auto-Key: {e}")
            self.autokey_status_label.configure(text="● ERROR", text_color="#d32f2f")
            return False
        finally:
            self.autokey_loading = False

    def toggle_autokey_detection(self):
        """Toggle Auto-Key detection on/off."""
        # Check if already processing a start/stop action
        if getattr(self, "autokey_processing", False) or getattr(self, "autokey_loading", False):
            return
            
        if not self.autokey_loaded:
            # First load might be slow, let's keep it synchronous 
            # or could be moved to thread if really needed
            if not self.ensure_autokey_loaded():
                return
        
        self.autokey_processing = True
        btn = self.btn_widgets.get("AUTO_KEY_DETECT")
        
        if self.autokey_running:
            # STOPPING
            if btn: btn.configure(text="STOP...", fg_color="#888")
            threading.Thread(target=self.stop_autokey_worker, daemon=True).start()
        else:
            # STARTING
            if btn: btn.configure(text="START...", fg_color="#888")
            threading.Thread(target=self.start_autokey_worker, daemon=True).start()
    
    def start_autokey_worker(self):
        """Worker thread for starting detection."""
        try:
            print("[Auto-Key] Starting detection worker...")
            
            if self.autokey_running:
                self.after(0, self._finish_processing)
                return
            
            # Get selected device (must be done in thread safely, 
            # but reading Tkinter var should be done via after or is str var thread safe? 
            # Tkvar.get() is usually fine if mainloop running, but better safe.)
            # We'll assume self.autokey_device_var.get() is safe enough or was cached.
            # Actually, let's get it before thread start? Too late now, let's use a cached property or try get.
            try:
                selected_name = self.autokey_device_var.get()
            except:
                selected_name = ""

            device_id = None
            if self.loopback_devices:
                for dev in self.loopback_devices:
                    if dev['name'][:40] == selected_name:
                        device_id = dev['id']
                        break
            
            # Start audio engine
            if self.audio_engine.start(device_id=device_id):
                # Update KeyDetector sample rate
                actual_rate = getattr(self.audio_engine, '_actual_sample_rate', 44100)
                print(f"[Auto-Key] Sample rate: {actual_rate}Hz")
                
                self.key_detector.sample_rate = actual_rate
                self.key_detector.reset()
                
                self.autokey_running = True
                
                # Start analysis thread
                if self.autokey_analysis_thread is None or not self.autokey_analysis_thread.is_alive():
                    self.autokey_analysis_thread = threading.Thread(
                        target=self._autokey_analysis_loop, 
                        daemon=True
                    )
                    self.autokey_analysis_thread.start()
                
                self.after(0, self._on_autokey_started)
            else:
                self.after(0, lambda: tkinter.messagebox.showerror("Lỗi", "Không thể bắt đầu capture audio loopback!"))
                self.after(0, self._on_autokey_stopped)

        except Exception as e:
            print(f"Error starting autokey: {e}")
            self.after(0, self._on_autokey_stopped)
        finally:
            self.after(0, self._finish_processing)

    def stop_autokey_worker(self):
        """Worker thread for stopping detection."""
        try:
            print("[Auto-Key] Stopping detection worker...")
            self.autokey_running = False
            
            if self.audio_engine:
                self.audio_engine.stop()
                
        except Exception as e:
            print(f"[Auto-Key] Error stopping audio engine: {e}")
        finally:
            self.after(0, self._on_autokey_stopped)
            self.after(0, self._finish_processing)

    def _finish_processing(self):
        self.autokey_processing = False

    def _on_autokey_started(self):
        btn = self.btn_widgets.get("AUTO_KEY_DETECT")
        if btn:
            btn.configure(text="STOP", fg_color="#d32f2f", text_color="white")
        
        self.autokey_status_label.configure(text="● LISTENING", text_color="#4caf50")
        if hasattr(self, 'autokey_device_select'):
            self.autokey_device_select.configure(state="disabled")

    def _on_autokey_stopped(self):
        btn = self.btn_widgets.get("AUTO_KEY_DETECT")
        orig_color = self.btn_colors.get("AUTO_KEY_DETECT", "#00bcd4")
        if btn:
            btn.configure(text="AUTO-KEY", fg_color=orig_color, text_color="white")
        
        self.autokey_status_label.configure(text="● OFF", text_color="#d32f2f")
        self.detected_key_label.configure(text="---")
        self.detected_scale_label.configure(text="")
        self.autokey_confidence_bar.set(0)
        
        if hasattr(self, 'autokey_device_select'):
            self.autokey_device_select.configure(state="normal")
            
    # Kept for compatibility if called directly, but should use toggle
    def start_autokey_detection(self):
        self.toggle_autokey_detection()
            
    def stop_autokey_detection(self):
        if self.autokey_running and not getattr(self, "autokey_processing", False):
            self.autokey_processing = True
            threading.Thread(target=self.stop_autokey_worker, daemon=True).start()
    
    def _autokey_analysis_loop(self):
        """Main analysis loop running in separate thread."""
        import numpy as np
        import traceback
        
        error_count = 0
        
        while self.autokey_running:
            try:
                # Get audio buffer
                audio = self.audio_engine.get_buffer()
                rms = self.audio_engine.get_buffer_rms()
                
                if len(audio) > 0:
                    # Detect key
                    try:
                        key, mode, confidence = self.key_detector.detect_key(audio)
                        error_count = 0  # Reset error count on success
                    except Exception as detect_err:
                        error_count += 1
                        if error_count <= 3:  # Only log first 3 errors
                            print(f"[Auto-Key] Detection error: {detect_err}")
                            traceback.print_exc()
                        key, mode, confidence = None, None, 0.0
                    
                    # Update UI (thread-safe)
                    self.after(0, self._update_autokey_display, key, mode, confidence, rms)
                
                # Analysis rate
                time.sleep(0.15)
                
            except Exception as e:
                print(f"[Auto-Key] Analysis loop error: {e}")
                traceback.print_exc()
                time.sleep(0.5)
    
    def send_autokey_midi(self, key_str, scale_str):
        if not key_str or not scale_str: return

        # Auto-Tune Keys Mapping (12 keys)
        KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        FLAT_MAP = {"Db":"C#", "Eb":"D#", "Gb":"F#", "Ab":"G#", "Bb":"A#"}

        # Auto-Tune Scales Mapping (29 scales)
        SCALES = [
            "Major", "Minor", "Chromatic", "Ling Lun", "Scholar's Lute", "Greek Diatonic",
            "Greek Chromatic", "Greek Enharmonic", "Pythagorean", "Just (Major)", "Just (Minor)",
            "Meantone Chromatic", "Werckmeister I (III)", "Vallotti & Young", "Barnes-Bach",
            "Indian", "Slendro", "Pelog", "Arabic 1", "Arabic 2", "19 Tone", "24 Tone",
            "31 Tone", "53 Tone", "Partch", "Carlos A", "Carlos B", "Carlos G", "Harmonic"
        ]

        # 1. Handle Key
        k = key_str.strip()
        # Handle normalization
        if k not in KEYS:
            # Check flat map
            if k in FLAT_MAP:
                k = FLAT_MAP[k]
            else:
                # Case-insensitive check
                found = False
                for fl, sh in FLAT_MAP.items():
                    if k.lower() == fl.lower():
                        k = sh
                        found = True
                        break
                if not found:
                    for ref in KEYS:
                        if k.lower() == ref.lower():
                            k = ref
                            found = True
                            break
        
        if k in KEYS:
            idx = KEYS.index(k)
            # Map index 0-11 to 0-127
            val = int(idx * (127 / (len(KEYS) - 1)))
            midi.send_cc(CC_MAP["EXTRA_KNOB_1"], val)
            # Debug
            # print(f"Sent Key {k} (validx {idx}) -> CC {val}")

        # 2. Handle Scale
        s_in = scale_str.strip().lower()
        scale_idx = -1
        
        for i, s_ref in enumerate(SCALES):
            if s_in == s_ref.lower():
                scale_idx = i
                break
        
        if scale_idx != -1:
            val = int(scale_idx * (127 / (len(SCALES) - 1)))
            midi.send_cc(CC_MAP["EXTRA_KNOB_2"], val)
            # Debug
            # print(f"Sent Scale {scale_str} (validx {scale_idx}) -> CC {val}")

    def _update_autokey_display(self, key, mode, confidence, rms):
        """Update the Auto-Key UI with detected key (called from main thread)."""
        if key and mode:
            self.detected_key_label.configure(text=key)
            self.detected_scale_label.configure(text=mode)
            
            # Send detected Key/Scale to MIDI
            self.send_autokey_midi(key, mode)
            
            # Update confidence bar
            self.autokey_confidence_bar.set(confidence)
            
            # Color based on confidence
            if confidence > 0.7:
                self.autokey_confidence_bar.configure(progress_color="#4caf50")  # Green
            elif confidence > 0.5:
                self.autokey_confidence_bar.configure(progress_color="#ffa726")  # Orange
            else:
                self.autokey_confidence_bar.configure(progress_color="#d32f2f")  # Red
        else:
            # No valid detection
            if rms < 0.005:
                self.detected_scale_label.configure(text="Chờ âm thanh...")
            else:
                self.detected_scale_label.configure(text="Đang phân tích...")

    # === ESSENTIA KEY DETECTOR INTEGRATION ===
    def start_essentia_server(self):
        """Start Essentia Python server in background."""
        try:
            server_path = os.path.join("essentia-key-detector", "audio_server.py")
            if not os.path.exists(server_path):
                print("[Essentia] Server script not found, skipping...")
                return
            
            print("[Essentia] Starting audio server...")
            self.essentia_server_process = subprocess.Popen(
                ["python", server_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Wait for server to start
            time.sleep(2)
            
            # Check if server is running
            if self.check_essentia_server():
                print("[Essentia] Server started successfully")
            else:
                print("[Essentia] Server failed to start")
                
        except Exception as e:
            print(f"[Essentia] Error starting server: {e}")
    
    def stop_essentia_server(self):
        """Stop Essentia Python server."""
        if self.essentia_server_process:
            try:
                print("[Essentia] Stopping audio server...")
                self.essentia_server_process.terminate()
                self.essentia_server_process.wait(timeout=5)
                print("[Essentia] Server stopped")
            except Exception as e:
                print(f"[Essentia] Error stopping server: {e}")
                try:
                    self.essentia_server_process.kill()
                except:
                    pass
    
    def check_essentia_server(self):
        """Check if Essentia server is running."""
        try:
            response = requests.get(f"http://127.0.0.1:{self.essentia_server_port}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def detect_key_essentia(self, file_path):
        """Detect key using Essentia server."""
        try:
            response = requests.post(
                f"http://127.0.0.1:{self.essentia_server_port}/detect-key",
                json={"filePath": file_path},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("key"), result.get("scale"), result.get("confidence", 0)
            else:
                print(f"[Essentia] Detection failed: {response.text}")
                return None, None, 0
                
        except Exception as e:
            print(f"[Essentia] Error detecting key: {e}")
            return None, None, 0
    
    # === YOUTUBE BROWSER INTEGRATION ===
    def open_youtube_browser(self):
        """Open YouTube in Selenium browser with auto URL monitoring."""
        if not selenium_available:
            tkinter.messagebox.showerror(
                "Lỗi",
                "Chưa cài đặt Selenium!\n\nVui lòng cài đặt:\npip install selenium"
            )
            return
        
        # Check if already running
        if self.youtube_browser and self.youtube_monitor_active:
            tkinter.messagebox.showinfo(
                "Thông báo",
                "YouTube Auto Detector đang chạy!\n\nClick vào video để tự động phát hiện key."
            )
            return
        
        # Start browser in thread
        threading.Thread(target=self._start_youtube_browser_worker, daemon=True).start()
    
    def _start_youtube_browser_worker(self):
        """Worker thread to start YouTube browser."""
        try:
            if self.youtube_browser:
                return
            
            print("[YouTube Browser] Starting Chrome...")
            
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', True)
            
            # Try to find Chrome/Brave
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
            ]
            
            chrome_binary = None
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_binary = path
                    break
            
            if chrome_binary:
                chrome_options.binary_location = chrome_binary
                print(f"[YouTube Browser] Using browser: {chrome_binary}")
            
            # Create driver
            self.youtube_browser = webdriver.Chrome(options=chrome_options)
            
            # Open YouTube homepage
            self.youtube_browser.get("https://www.youtube.com")
            
            print("[YouTube Browser] Opened YouTube")
            
            # Auto-enable monitoring
            self.auto_detect_enabled = True
            self.youtube_monitor_active = True
            
            # Start monitoring thread
            self.youtube_monitor_thread = threading.Thread(
                target=self._monitor_youtube_url,
                daemon=True
            )
            self.youtube_monitor_thread.start()
            
            # Show notification
            self.after(0, lambda: tkinter.messagebox.showinfo(
                "YouTube Auto Detector",
                "✅ Đã bật tự động phát hiện!\n\n"
                "Click vào video YouTube để tự động phát hiện key.\n\n"
                "Kết quả sẽ hiển thị trên panel AUTO-KEY."
            ))
            
        except Exception as e:
            print(f"[YouTube Browser] Error: {e}")
            import traceback
            traceback.print_exc()
            
            self.after(0, lambda: tkinter.messagebox.showerror(
                "Lỗi",
                f"Không thể mở trình duyệt:\n{e}\n\nVui lòng cài đặt:\npip install selenium"
            ))
    
    def _monitor_youtube_url(self):
        """Monitor YouTube URL changes and auto-detect."""
        print("[YouTube Monitor] Started")
        
        while self.youtube_monitor_active and self.youtube_browser:
            try:
                if not self.auto_detect_enabled:
                    time.sleep(1)
                    continue
                
                current_url = self.youtube_browser.current_url
                
                # Check if it's a video URL and different from last
                if ("youtube.com/watch" in current_url or "youtu.be/" in current_url):
                    if current_url != self.last_youtube_url:
                        print(f"[YouTube Monitor] New video detected: {current_url}")
                        self.last_youtube_url = current_url
                        
                        # Update status
                        self.after(0, lambda: self.autokey_status_label.configure(
                            text="● YOUTUBE DETECTED",
                            text_color="#ff0000"
                        ))
                        
                        # Wait a bit for video to load
                        time.sleep(2)
                        
                        # Start detection
                        self._detect_youtube_url(current_url)
                        
                        # Wait before next check
                        time.sleep(5)
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"[YouTube Monitor] Error: {e}")
                time.sleep(2)
        
        print("[YouTube Monitor] Stopped")
    
    def _detect_youtube_url(self, url):
        """Detect key from YouTube URL."""
        try:
            # Update status
            self.after(0, lambda: self.autokey_status_label.configure(text="● DOWNLOADING...", text_color="#ffa726"))
            self.after(0, lambda: self.detected_key_label.configure(text="..."))
            self.after(0, lambda: self.detected_scale_label.configure(text="Đang tải..."))
            
            # Check if yt-dlp is available
            try:
                import yt_dlp
            except ImportError:
                self.after(0, lambda: tkinter.messagebox.showerror(
                    "Lỗi", 
                    "Chưa cài đặt yt-dlp!\n\nVui lòng cài đặt:\npip install yt-dlp"
                ))
                self.after(0, lambda: self.autokey_status_label.configure(text="● ERROR", text_color="#d32f2f"))
                return
            
            # Create temp directory
            temp_dir = os.path.join(os.path.dirname(__file__), "temp_youtube")
            os.makedirs(temp_dir, exist_ok=True)
            
            print(f"[YouTube] Downloading audio: {url}")
            
            # Download audio directly using yt-dlp CLI (simple and reliable)
            output_template = os.path.join(temp_dir, "%(id)s.%(ext)s")
            
            try:
                # Use CLI with timeout - Download opus/webm (native YouTube format, no conversion)
                result = subprocess.run([
                    sys.executable, "-m", "yt_dlp",
                    "--format", "bestaudio",
                    "--no-playlist",
                    "--output", output_template,
                    "--no-warnings",
                    url
                ], capture_output=True, text=True, timeout=120)  # 2 minutes timeout
                
                if result.returncode != 0:
                    raise Exception(f"Download failed: {result.stderr}")
                
                print("[YouTube] Download completed")
                
            except subprocess.TimeoutExpired:
                raise Exception("Download timeout (quá 2 phút)")
            except Exception as e:
                raise Exception(f"Download error: {e}")
            
            # Find downloaded file
            audio_files = []
            for ext in ['.m4a', '.webm', '.mp3', '.opus', '.ogg']:
                audio_files.extend([f for f in os.listdir(temp_dir) if f.endswith(ext)])
            
            if not audio_files:
                raise Exception("Không tìm thấy file audio đã tải")
            
            audio_path = os.path.join(temp_dir, audio_files[0])
            print(f"[YouTube] Audio file: {audio_path}")
            
            self.after(0, lambda: self.autokey_status_label.configure(text="● ANALYZING...", text_color="#ffa726"))
            self.after(0, lambda: self.detected_scale_label.configure(text="Đang phân tích..."))
            
            # Detect key - Try Essentia first, fallback to librosa
            key = None
            scale = None
            confidence = 0
            
            if self.check_essentia_server():
                print("[YouTube] Trying Essentia server...")
                key, scale, confidence = self.detect_key_essentia(audio_path)
            
            # If Essentia failed or not available, use fallback
            if not key or not scale:
                print("[YouTube] Using librosa fallback...")
                key, scale, confidence = self._detect_key_fallback(audio_path)
            
            # Clean up
            try:
                os.remove(audio_path)
                print(f"[YouTube] Cleaned up: {audio_path}")
            except:
                pass
            
            if key and scale:
                self.after(0, lambda: self._update_autokey_display(key, scale, confidence / 100, 1.0))
                self.after(0, lambda: self.autokey_status_label.configure(text="● YOUTUBE DONE", text_color="#4caf50"))
                self.send_autokey_midi(key, scale)
                
                print(f"[YouTube] Detected: {key} {scale} ({confidence}%)")
            else:
                self.after(0, lambda: self.autokey_status_label.configure(text="● FAILED", text_color="#d32f2f"))
                print("[YouTube] Detection failed")
                
        except Exception as e:
            print(f"[YouTube] Error: {e}")
            import traceback
            traceback.print_exc()
            
            self.after(0, lambda: self.autokey_status_label.configure(text="● ERROR", text_color="#d32f2f"))
    
    def save_youtube_tabs(self):
        """Deprecated - kept for compatibility."""
        pass
    
    def load_youtube_tabs(self):
        """Deprecated - kept for compatibility."""
        pass
    
    def _detect_key_fallback(self, audio_path):
        """Fallback key detection using librosa."""
        try:
            import librosa
            import numpy as np
            
            # Load audio
            y, sr = librosa.load(audio_path, sr=22050, duration=30)
            
            # Extract chroma
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=2048)
            chroma_avg = np.mean(chroma, axis=1)
            
            # Simple key detection (Krumhansl-Kessler)
            NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
            KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
            
            max_corr = -1
            detected_key = 'C'
            detected_scale = 'Major'
            
            for tonic in range(12):
                major_profile = np.roll(KK_MAJOR, tonic)
                major_corr = np.corrcoef(chroma_avg, major_profile)[0, 1]
                
                if major_corr > max_corr:
                    max_corr = major_corr
                    detected_key = NOTE_NAMES[tonic]
                    detected_scale = 'Major'
                
                minor_profile = np.roll(KK_MINOR, tonic)
                minor_corr = np.corrcoef(chroma_avg, minor_profile)[0, 1]
                
                if minor_corr > max_corr:
                    max_corr = minor_corr
                    detected_key = NOTE_NAMES[tonic]
                    detected_scale = 'Minor'
            
            confidence = int(max(0, min(100, (max_corr + 1) * 50)))
            
            return detected_key, detected_scale, confidence
            
        except Exception as e:
            print(f"[Fallback] Error: {e}")
            return None, None, 0

    def on_closing(self):
        print("\n🛑 Đang bắt đầu quy trình tắt...")
        
        # Stop YouTube monitoring
        self.youtube_monitor_active = False
        self.auto_detect_enabled = False
        
        # Close YouTube browser
        if self.youtube_browser:
            try:
                print("[YouTube Browser] Closing...")
                self.youtube_browser.quit()
            except:
                pass
        
        # Stop Essentia server
        self.stop_essentia_server()
        
        # Stop Auto-Key detection if running
        if self.autokey_running:
            print("[Auto-Key] Stopping detection before exit...")
            self.stop_autokey_detection()
        
        print("🔍 Đang tìm cửa sổ Cubase...")
        try:
            # 1. Tìm tất cả cửa sổ liên quan đến Cubase
            all_wins = WindowsHelper.find_windows_by_title('Cubase')
            print(f"🔍 Tìm thấy {len(all_wins)} cửa sổ liên quan đến Cubase.")

            if all_wins:
                # Tìm cửa sổ có khả năng là cửa sổ Project nhất (thường có tên file .cpr)
                main_hwnd = None
                for w in all_wins:
                    title = w['title']
                    print(f"   - Window: {title}")
                    if '.cpr' in title.lower() or 'cubase pro' in title.lower():
                        main_hwnd = w['hwnd']
                        break
                
                if not main_hwnd:
                    main_hwnd = all_wins[0]['hwnd']

                print(f"🚀 Đang gửi lệnh Ctrl+Q tới HWND: {main_hwnd}")
                WindowsHelper.activate_window(main_hwnd)
                time.sleep(0.5)
                
                # Giả lập Ctrl + Q
                user32.keybd_event(VK_CONTROL, 0, 0, 0) # Ctrl down
                user32.keybd_event(VK_Q, 0, 0, 0)       # Q down
                time.sleep(0.05)
                user32.keybd_event(VK_Q, 0, KEYEVENTF_KEYUP, 0) # Q up
                user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0) # Ctrl up

                # 2. Đợi hộp thoại "Save" hiện lên
                print("⏳ Đang đợi hộp thoại xác nhận 'Save' (tối đa 5s)...")
                found_dialog = False
                for i in range(50):
                    time.sleep(0.1)
                    # Tìm cửa sổ có tiêu đề "Cubase Pro" hoặc "Cubase" mà không phải cửa sổ chính
                    dialogs = WindowsHelper.find_windows_by_title('Cubase')
                    for dlg in dialogs:
                        # Hộp thoại thường có kích thước cố định và nhỏ
                        w, h = dlg['rect']['width'], dlg['rect']['height']
                        if dlg['hwnd'] != main_hwnd and 300 < w < 650 and 100 < h < 350:
                            print(f"🎯 Đã phát hiện hộp thoại: '{dlg['title']}' ({w}x{h})")
                            WindowsHelper.activate_window(dlg['hwnd'])
                            time.sleep(0.5)
                            
                            # Tính toán vị trí nút "Don't Save" (nằm chính giữa hàng nút dưới cùng)
                            click_x = dlg['rect']['left'] + (w // 2)
                            click_y = dlg['rect']['top'] + h - 25 # Cách đáy khoảng 25 pixel
                            
                            print(f"🖱️ Click vào nút Don't Save tại ({click_x}, {click_y})")
                            WindowsHelper.click(click_x, click_y)
                            
                            # Gửi thêm phím tắt cho chắc chắn (N hoặc D)
                            for vk in [VK_N, VK_D]:
                                user32.keybd_event(vk, 0, 0, 0) 
                                time.sleep(0.05)
                                user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                                time.sleep(0.05)
                            
                            print("✅ Đã chọn 'Don't Save'")
                            found_dialog = True
                            time.sleep(0.05) # Đợi Cubase đóng hẳn
                            break
                    if found_dialog: break
                
                if not found_dialog:
                    print("⚠️ Không thấy hộp thoại xác nhận xuất hiện. Có thể Cubase đã đóng luôn hoặc không có gì để lưu.")

        except Exception as e:
            print(f"❌ Lỗi khi đóng Cubase: {e}")

        print("👋 Đang đóng Tool...")
        self.destroy()
        os._exit(0)

    def detect_audio_file(self):
        """Open file dialog and detect key from audio file."""
        if not self.autokey_loaded:
            if not self.ensure_autokey_loaded():
                return
        
        if self.autokey_running:
            self.stop_autokey_detection()
            
        file_path = tkinter.filedialog.askopenfilename(
            title="Chọn file âm thanh",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav *.flac *.m4a *.ogg *.aac"),
                ("All Files", "*.*")
            ]
        )
        
        if file_path:
            threading.Thread(target=self._process_audio_file_worker, args=(file_path,), daemon=True).start()

    def _process_audio_file_worker(self, file_path):
        """Worker thread to process audio file."""
        import os
        import tempfile
        import shutil
        import librosa
        filename = os.path.basename(file_path)
        temp_path = None
        
        try:
            self.after(0, lambda: self.autokey_status_label.configure(text="● LOADING FILE...", text_color="#ffa726"))
            self.after(0, lambda: self.detected_key_label.configure(text="..."))
            self.after(0, lambda: self.detected_scale_label.configure(text="Đang xử lý..."))
            
            # Load audio using a more robust binary stream approach
            # This bypasses many Unicode path and backend issues on Windows
            import soundfile
            import io
            
            self.after(0, lambda: self.autokey_status_label.configure(text="● DECODING...", text_color="#ffa726"))
            
            try:
                # Try reading directly with soundfile first (handles most MP3s in newer versions)
                # We use a binary stream to ensure file handles are handled correctly
                with open(file_path, 'rb') as f:
                    # Note: soundfile.read can take a file-like object
                    # We limit to approx 3 mins (sr * 180 samples)
                    # But we need sr first, so we use soundfile.info
                    info = soundfile.info(f)
                    sr = info.samplerate
                    f.seek(0)
                    y, _ = soundfile.read(f, frames=int(sr * 180))
                    
                    # If it's multi-channel, convert to mono
                    if len(y.shape) > 1:
                        y = y.mean(axis=1)
            except Exception as sf_err:
                print(f"[Auto-Key] Soundfile failed: {sf_err}, falling back to librosa...")
                # Fallback to librosa logic (which might still fail but we try)
                y, sr = librosa.load(file_path, sr=None, duration=180)
            
            self.after(0, lambda: self.autokey_status_label.configure(text="● ANALYZING...", text_color="#ffa726"))
            
            # Use the static detection method
            self.key_detector.sample_rate = sr
            self.key_detector.reset()
            
            key, mode, conf, proc_time = self.key_detector.detect_static_audio(y)
            
            if key and mode:
                self.after(0, lambda: self._update_autokey_display(key, mode, conf, 1.0))
                self.after(0, lambda: self.autokey_status_label.configure(text=f"● DONE ({proc_time:.1f}s)", text_color="#4caf50"))
                # Send to MIDI
                self.send_autokey_midi(key, mode)
            else:
                self.after(0, lambda: self.autokey_status_label.configure(text="● FAILED", text_color="#d32f2f"))
                self.after(0, lambda: self.detected_scale_label.configure(text="Không tìm thấy tone"))
                
        except Exception as e:
            print(f"[Auto-Key] File error: {e}")
            import traceback
            traceback.print_exc()
            self.after(0, lambda: tkinter.messagebox.showerror("Lỗi", f"Không thể xử lý file:\n{e}"))
            self.after(0, lambda: self.autokey_status_label.configure(text="● ERROR", text_color="#d32f2f"))
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
