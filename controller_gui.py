import tkinter as tk
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
        self.geometry("880x280")
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
            "listen_duration": 15,
            "cubase_project_path": "",
            "cubase_exit_action": "dont_save"
        }

        # Auto-Key Detection state
        self.autokey_running = False
        self.auto_do_tone_enabled = False
        self.autokey_analysis_thread = None
        # self.audio_engine = None # Removed legacy engine
        # self.key_detector = None # Removed legacy detector
        self.loopback_devices = []
        self.autokey_loaded = True # Bypassing legacy loader
        
        # Essentia Key Detector state
        self.essentia_server_process = None
        self.essentia_server_port = 5000
        self.youtube_browser = None  # Selenium browser for monitoring
        self.youtube_monitor_thread = None  # URL monitoring thread
        self.youtube_monitor_active = False  # Monitoring flag
        self.youtube_panel = None  # Control panel window
        self.last_youtube_url = None  # Track last detected URL
        self.auto_detect_enabled = False  # Auto-detect flag
        self.youtube_key_timeline = []  # [(start_sec, end_sec, key, scale, conf), ...]
        self.youtube_sync_active = False  # Time sync with YouTube playback
        self.youtube_browser_opening = False  # Prevent double-open while starting
        
        # Marquee UI state
        self.marquee_text = "   BẢNG ĐIỀU KHIỂN TIẾNG VIỆT  ★  HẬU SETUP LIVE STUDIO  ★   "
        self.marquee_canvas = None
        self.marquee_item = None
        self.marquee_speed = 1.5 # Pixels per frame
        self.marquee_width = 0
        
        # We will initialize loopback_devices list separately or lazily
        # For now, we'll try to get devices without loading heavy DSP libs if possible
        # but usually AudioEngine needs to be loaded first. Let's make it fully lazy.

        self.setup_left_panel()
        self.setup_center_panel()
        self.setup_right_panel()

        self.load_settings()
        self.load_autokey_coords()
        self.create_desktop_shortcut() # Create shortcut on first run
        # Start Essentia server immediately with timeout handling
        threading.Thread(target=self.start_essentia_server, daemon=True).start()
        self.update_marquee() # Start marquee animation
        # Delay project opening to reduce startup lag
        self.after(3000, self.open_saved_project)

    def open_saved_project(self):
        path = self.autokey_coords.get("cubase_project_path", "")
        if path and os.path.exists(path):
            try:
                print(f"Opening Cubase project: {path}")
                os.startfile(path)
            except Exception as e:
                print(f"Error opening project: {e}")

    def create_desktop_shortcut(self):
        """Create a desktop shortcut using PowerShell if it doesn't exist."""
        # Run in background thread to avoid blocking UI
        threading.Thread(target=self._create_shortcut_worker, daemon=True).start()
    
    def _create_shortcut_worker(self):
        """Worker thread for creating desktop shortcut."""
        try:
            if not getattr(sys, 'frozen', False):
                return # Only create shortcut for bundled EXE
                
            exe_path = sys.executable
            desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
            # Get the name from the executable or a default
            exe_name = os.path.basename(exe_path).replace(".exe", "")
            shortcut_path = os.path.join(desktop, f"{exe_name}.lnk")
            
            if os.path.exists(shortcut_path):
                return
                
            print(f"[Shortcut] Creating shortcut at: {shortcut_path}")
            
            # PowerShell command to create shortcut
            shell_cmd = (
                f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{shortcut_path}");'
                f'$s.TargetPath="{exe_path}";'
                f'$s.WorkingDirectory="{os.path.dirname(exe_path)}";'
                f'$s.Save()'
            )
            subprocess.run(["powershell", "-Command", shell_cmd], capture_output=True, timeout=5)
            print("[Shortcut] Shortcut created successfully")
        except Exception as e:
            print(f"[Shortcut] Failed to create shortcut: {e}")

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
            ("AUTO DÒ", "#9c27b0", "AUTO_DO_TONE"),
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
            elif cc_key == "AUTO_DO_TONE":
                cmd = self.toggle_auto_do_tone
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
        self.autokey_confidence_bar.pack(pady=(0, 2), padx=10, fill="x")
        self.autokey_confidence_bar.set(0)

        # Playback time display
        self.youtube_time_label = ctk.CTkLabel(
            autokey_frame,
            text="",
            font=("Arial", 9),
            text_color="#888888"
        )
        self.youtube_time_label.pack(pady=(0, 4))

        # Audio source selection removed as requested

        # Audio source selection removed as requested

        marquee_container = ctk.CTkFrame(frame, fg_color="#000", height=30, corner_radius=5, border_width=1, border_color="#333")
        marquee_container.pack(side="bottom", fill="x", padx=5, pady=5)
        marquee_container.pack_propagate(False)

        # Use Canvas for smooth pixel scrolling instead of Label
        self.marquee_canvas = tk.Canvas(
            marquee_container, 
            bg="black", 
            highlightthickness=0,
            height=30
        )
        self.marquee_canvas.pack(fill="both", expand=True)

        # Create text item on canvas
        # We start at the right edge
        self.marquee_item = self.marquee_canvas.create_text(
            200, 15, # Placeholder X, Y=middle
            text=self.marquee_text,
            fill=self.col_text_yellow,
            font=("Arial", 11, "bold"),
            anchor="w"
        )

    def update_marquee(self):
        """Update marquee position by shifting pixels for smoothness."""
        if not self.marquee_canvas or not self.marquee_item:
            self.after(200, self.update_marquee)
            return

        try:
            # Shift text to the left
            self.marquee_canvas.move(self.marquee_item, -self.marquee_speed, 0)
            
            # Get current position
            bbox = self.marquee_canvas.bbox(self.marquee_item)
            if bbox:
                # If text has completely scrolled off the left edge (x2 < 0)
                if bbox[2] < 0:
                    # Reset to right edge
                    canvas_width = self.marquee_canvas.winfo_width()
                    if canvas_width <= 1: canvas_width = 250 # Fallback if not yet rendered
                    self.marquee_canvas.coords(self.marquee_item, canvas_width, 15)
            
            # Schedule next update (approx 50 FPS for smoothness)
            self.after(20, self.update_marquee)
        except Exception as e:
            print(f"[Marquee] Error: {e}")
            self.after(1000, self.update_marquee)

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

            # Load sliders without sending MIDI (faster startup)
            sliders_data = data.get("sliders", {})
            for k, v in sliders_data.items():
                if k in self.slider_widgets:
                    self.slider_widgets[k].set(v)
                    # Update label only, skip MIDI during startup
                    if k in self.slider_labels:
                        percent = int((v / 127) * 100)
                        self.slider_labels[k].configure(text=f"{percent}%")

            # Send all MIDI values at once after UI is ready
            self.after(500, lambda: self._send_startup_midi(sliders_data))

            toggles_data = data.get("toggles", {})
            for k, v in toggles_data.items():
                if k in self.btn_widgets and k not in ["DO_TONE", "SAVE", "AUTO_KEY_DETECT", "AUTO_DO_TONE", "YOUTUBE_BROWSER", "SETTINGS"]:
                    if self.btn_states.get(k, False) != v:
                         self.on_btn_toggle(k)
        except Exception as e:
            print(f"Lỗi load config: {e}")
    
    def _send_startup_midi(self, sliders_data):
        """Send MIDI values after startup to avoid lag."""
        for k, v in sliders_data.items():
            cc = CC_MAP.get(k)
            if cc:
                midi.send_cc(cc, v)

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
        popup.title("CÀI ĐẶT AUTO-KEY & THỜI GIAN")
        popup.geometry("550x750")
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
            text="CÀI ĐẶT AUTO-KEY & THỜI GIAN DETECT",
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

        # Exit Action Selection
        ctk.CTkLabel(settings_frame, text="Khi thoát Cubase:", font=("Arial", 11, "bold")).grid(row=5, column=0, sticky="w", pady=8, padx=5)
        
        # Timing Settings Section
        timing_frame = ctk.CTkFrame(settings_frame, fg_color="#1a1a1a", corner_radius=8)
        timing_frame.grid(row=6, column=0, columnspan=4, pady=15, padx=5, sticky="ew")
        
        ctk.CTkLabel(
            timing_frame, 
            text="⏱️ CÀI ĐẶT THỜI GIAN", 
            font=("Arial", 12, "bold"),
            text_color="#4CAF50"
        ).pack(pady=(10, 5))
        
        timing_inner = ctk.CTkFrame(timing_frame, fg_color="transparent")
        timing_inner.pack(pady=5, padx=10, fill="x")
        
        # Listen duration
        ctk.CTkLabel(timing_inner, text="Thời gian nghe (giây):", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w", pady=8, padx=5)
        listen_duration_entry = ctk.CTkEntry(timing_inner, width=80)
        listen_duration_entry.insert(0, str(self.autokey_coords.get("listen_duration", 15)))
        listen_duration_entry.grid(row=0, column=1, pady=8, padx=5)
        
        ctk.CTkLabel(timing_inner, text="(5-60s)", font=("Arial", 9), text_color="#888888").grid(row=0, column=2, sticky="w", padx=5)
        
        # Analysis duration
        ctk.CTkLabel(timing_inner, text="Thời gian phân tích (giây):", font=("Arial", 11, "bold")).grid(row=1, column=0, sticky="w", pady=8, padx=5)
        analysis_duration_entry = ctk.CTkEntry(timing_inner, width=80)
        analysis_duration_entry.insert(0, str(self.autokey_coords.get("analysis_duration", 30)))
        analysis_duration_entry.grid(row=1, column=1, pady=8, padx=5)
        
        ctk.CTkLabel(timing_inner, text="(5-120s)", font=("Arial", 9), text_color="#888888").grid(row=1, column=2, sticky="w", padx=5)

        exit_action_var = ctk.StringVar(value=self.autokey_coords.get("cubase_exit_action", "dont_save"))
        
        exit_action_switch = ctk.CTkSegmentedButton(
            settings_frame,
            values=["save", "dont_save"],
            command=lambda v: exit_action_var.set(v),
            variable=exit_action_var,
            font=("Arial", 11)
        )
        exit_action_switch.configure(values=["save", "dont_save"]) # Internal values
        # Customizing display names
        exit_action_switch._buttons_dict["save"].configure(text="LƯU (Save)")
        exit_action_switch._buttons_dict["dont_save"].configure(text="KHÔNG LƯU (Don't Save)")
        
        exit_action_switch.grid(row=5, column=1, columnspan=2, pady=8, padx=5, sticky="ew")

        info_text = ctk.CTkTextbox(popup, height=80, width=500, fg_color="#2a2a2a")
        info_text.pack(pady=10, padx=20)
        info_text.insert("1.0",
            "💡 Hướng dẫn sử dụng Auto-Key:\n"
            "1. Mở cửa sổ Auto-Key Plugin trong Cubase\n"
            "2. Click 'ĐO TỌA ĐỘ' để lấy vị trí nút Listen/Send\n"
            "3. Cài đặt thời gian nghe phù hợp (5-60s)\n"
            "4. Cài đặt thời gian phân tích file âm thanh (5-120s)\n"
            "5. Click 'LƯU' để áp dụng cài đặt\n\n"
            "⏱️ Thời gian nghe: Thời gian plugin Auto-Key phân tích\n"
            "🎵 Thời gian phân tích: Thời gian phân tích file âm thanh"
        )
        info_text.configure(state="disabled")

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=15)

        def save_coords():
            try:
                # Validate timing values
                listen_duration = int(listen_duration_entry.get())
                analysis_duration = int(analysis_duration_entry.get())
                
                if not (5 <= listen_duration <= 60):
                    tkinter.messagebox.showerror("Lỗi", "Thời gian nghe phải từ 5-60 giây!")
                    return
                    
                if not (5 <= analysis_duration <= 120):
                    tkinter.messagebox.showerror("Lỗi", "Thời gian phân tích phải từ 5-120 giây!")
                    return

                self.autokey_coords["listen_x_offset"] = float(listen_x_entry.get()) / 100
                self.autokey_coords["listen_y_offset"] = float(listen_y_entry.get()) / 100
                self.autokey_coords["send_x_offset"] = float(send_x_entry.get()) / 100
                self.autokey_coords["send_y_from_bottom"] = int(send_y_entry.get())
                self.autokey_coords["cubase_project_path"] = project_entry.get()
                self.autokey_coords["cubase_exit_action"] = exit_action_var.get()
                self.autokey_coords["listen_duration"] = listen_duration
                self.autokey_coords["analysis_duration"] = analysis_duration

                if self.save_autokey_coords():
                    tkinter.messagebox.showinfo("Thành công", "Đã lưu cài đặt Auto-Key!")
                    on_close_popup()
                else:
                    tkinter.messagebox.showerror("Lỗi", "Không thể lưu cài đặt!")
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
            time.sleep(0.5)  # Fixed delay for window activation

            rect = target_win['rect']
            listen_x = rect['left'] + int(rect['width'] * self.autokey_coords["listen_x_offset"])
            listen_y = rect['top'] + int(rect['height'] * self.autokey_coords["listen_y_offset"])
            send_x = rect['left'] + int(rect['width'] * self.autokey_coords["send_x_offset"])
            send_y = rect['top'] + rect['height'] - self.autokey_coords["send_y_from_bottom"]

            print(f"Click Listen ({listen_x}, {listen_y})...")
            WindowsHelper.click(listen_x, listen_y)

            duration = self.autokey_coords.get("listen_duration", 15)
            print(f"⏱️ Đang nghe và phân tích ({duration}s)...")
            
            # Show countdown in console
            for i in range(duration, 0, -1):
                print(f"⏳ Còn {i}s...", end='\r')
                time.sleep(1)
            print("✅ Hoàn thành phân tích!")

            print(f"Click Send ({send_x}, {send_y})...")
            WindowsHelper.click(send_x, send_y)
            time.sleep(0.3)  # Fixed delay after send

            WindowsHelper.set_cursor_pos(original_pos[0], original_pos[1])
            print("✅ Xong quy trình Auto-Key!")

        except Exception as e:
            print(f"❌ Lỗi Auto-Key: {e}")
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

    # ensure_autokey_loaded removed

    def toggle_autokey_detection(self):
        """Toggle Auto-Key detection on/off."""
        # Toggle monitoring state
        self.autokey_running = not self.autokey_running
        
        if self.autokey_running:
            # STOP AUTO DÒ if running
            if self.auto_do_tone_enabled:
                self.toggle_auto_do_tone()
            
            # STARTED
            print("[Auto-Key] YouTube monitoring enabled")
            self._on_autokey_started()
        else:
            # STOPPED
            print("[Auto-Key] YouTube monitoring disabled")
            self._on_autokey_stopped()

    def toggle_auto_do_tone(self):
        """Toggle Auto Dò Tone on/off."""
        self.auto_do_tone_enabled = not self.auto_do_tone_enabled
        
        btn = self.btn_widgets.get("AUTO_DO_TONE")
        orig_color = self.btn_colors.get("AUTO_DO_TONE", "#9c27b0")
        
        if self.auto_do_tone_enabled:
            # STOP AUTO-KEY if running
            if self.autokey_running:
                self.toggle_autokey_detection()
                
            if btn:
                btn.configure(fg_color="#d32f2f", text="STOP")
            print("[Auto Dò Tone] Enabled")
        else:
            if btn:
                btn.configure(fg_color=orig_color, text="AUTO DÒ")
            print("[Auto Dò Tone] Disabled")
    
    # Legacy detection workers and loop removed
    
    def stop_autokey_detection(self):
        """Compatibility wrapper to stop monitoring."""
        if self.autokey_running:
            self.toggle_autokey_detection()

    def _on_autokey_started(self):
        btn = self.btn_widgets.get("AUTO_KEY_DETECT")
        if btn:
            btn.configure(text="STOP", fg_color="#d32f2f", text_color="white")
        
        self.autokey_status_label.configure(text="● MONITORING", text_color="#4caf50")

    def _on_autokey_stopped(self):
        btn = self.btn_widgets.get("AUTO_KEY_DETECT")
        orig_color = self.btn_colors.get("AUTO_KEY_DETECT", "#00bcd4")
        if btn:
            btn.configure(text="AUTO-KEY", fg_color=orig_color, text_color="white")
        
        self.youtube_sync_active = False
        self.autokey_status_label.configure(text="● OFF", text_color="#d32f2f")
        self.detected_key_label.configure(text="---")
        self.detected_scale_label.configure(text="")
        self.autokey_confidence_bar.set(0)
        self.youtube_time_label.configure(text="")
    
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
        """Start Essentia Python server in a background thread with retry logic."""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"[Essentia] Starting server (attempt {retry_count + 1}/{max_retries})...")
                
                # Detect search path for bundled data
                if getattr(sys, 'frozen', False):
                    # Running as bundled exe
                    base_path = sys._MEIPASS
                    print(f"[Essentia] Running as bundled exe, base path: {base_path}")
                else:
                    # Running as script
                    base_path = os.path.dirname(os.path.abspath(__file__))
                    print(f"[Essentia] Running as script, base path: {base_path}")
                
                essentia_path = os.path.join(base_path, "essentia-key-detector")
                
                # Check if essentia-key-detector folder exists
                if not os.path.exists(essentia_path):
                    print(f"[Essentia] ERROR: Folder not found at {essentia_path}")
                    try:
                        print(f"[Essentia] Contents of base_path: {os.listdir(base_path)}")
                    except:
                        pass
                    raise Exception(f"essentia-key-detector folder not found at {essentia_path}")
                
                # Check if audio_server.py exists
                audio_server_file = os.path.join(essentia_path, "audio_server.py")
                if not os.path.exists(audio_server_file):
                    print(f"[Essentia] ERROR: audio_server.py not found at {audio_server_file}")
                    try:
                        print(f"[Essentia] Contents of essentia folder: {os.listdir(essentia_path)}")
                    except:
                        pass
                    raise Exception(f"audio_server.py not found at {audio_server_file}")
                
                if essentia_path not in sys.path:
                    sys.path.insert(0, essentia_path)
                
                print(f"[Essentia] Loading server from: {essentia_path}")
                
                try:
                    from audio_server import run_server
                    print("[Essentia] Successfully imported audio_server.run_server")
                except ImportError as e:
                    print(f"[Essentia] Direct import failed: {e}")
                    
                    # Try fallback if package name mismatch
                    try:
                        from essentia_key_detector.audio_server import run_server
                        print("[Essentia] Successfully imported via essentia_key_detector package")
                    except Exception as e2:
                        print(f"[Essentia] Package import also failed: {e2}")
                        raise e2
                
                # Run server in background thread
                self.essentia_thread = threading.Thread(
                    target=lambda: run_server(self.essentia_server_port),
                    daemon=True
                )
                self.essentia_thread.start()
                print("[Essentia] Server thread started, waiting for initialization...")
                
                # Wait for server to be ready
                for wait_count in range(20):  # Wait up to 10 seconds
                    time.sleep(0.5)
                    if self.check_essentia_server():
                        print("[Essentia] ✅ Server ready and responding")
                        self.after(1000, self._set_server_default_duration)
                        return
                
                print(f"[Essentia] WARNING: Server started but not responding after 10s")
                return
                    
            except Exception as e:
                retry_count += 1
                print(f"[Essentia] Error (attempt {retry_count}): {e}")
                if retry_count < max_retries:
                    print(f"[Essentia] Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    print(f"[Essentia] ❌ Failed to start after {max_retries} attempts")        
                    import traceback
                    traceback.print_exc()

    def _set_server_default_duration(self):
        """Set default analysis duration on server."""
        try:
            duration = self.autokey_coords.get("analysis_duration", 30)
            response = requests.post(
                f"http://127.0.0.1:{self.essentia_server_port}/set-default-duration",
                json={"duration": duration},
                timeout=5
            )
            if response.status_code == 200:
                print(f"[Essentia] Set default analysis duration to {duration}s")
            else:
                print(f"[Essentia] Failed to set default duration: {response.text}")
        except Exception as e:
            print(f"[Essentia] Error setting default duration: {e}")

    def _check_essentia_startup(self):
        """Check if server started correctly after delay."""
        if self.check_essentia_server():
            print("[Essentia] Threaded server started successfully")
        else:
            print("[Essentia] Threaded server failed to respond on port 5000")
    
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
            
    def check_ffmpeg(self):
        """Check if ffmpeg/ffprobe is available."""
        import shutil
        return shutil.which("ffmpeg") is not None or shutil.which("ffprobe") is not None
    
    def detect_key_essentia(self, file_path, duration=None):
        """Detect key using Essentia server with configurable duration."""
        try:
            # Use duration from autokey_coords or default to 30s
            if duration is None:
                duration = self.autokey_coords.get("analysis_duration", 30)
                
            payload = {
                "filePath": file_path,
                "duration": duration
            }
            
            response = requests.post(
                f"http://127.0.0.1:{self.essentia_server_port}/detect-key",
                json=payload,
                timeout=max(60, duration + 10)  # Timeout based on duration
            )
            
            if response.status_code == 200:
                result = response.json()
                analyzed_duration = result.get("analyzedDuration", duration)
                print(f"[Essentia] Analyzed {analyzed_duration}s of audio")
                return result.get("key"), result.get("scale"), result.get("confidence", 0)
            else:
                print(f"[Essentia] Detection failed: {response.text}")
                return None, None, 0
                
        except Exception as e:
            print(f"[Essentia] Error detecting key: {e}")
            return None, None, 0
    
    # === YOUTUBE BROWSER INTEGRATION ===
    def _is_youtube_browser_alive(self):
        """Check if the Selenium browser window is still open."""
        try:
            if self.youtube_browser is None:
                return False
            _ = self.youtube_browser.current_url
            return True
        except Exception:
            return False

    def _reset_youtube_browser_state(self):
        """Reset all YouTube browser state after browser is closed."""
        self.youtube_monitor_active = False
        self.youtube_sync_active = False
        self.youtube_browser_opening = False
        self.youtube_browser = None
        self.last_youtube_url = None
        self.youtube_key_timeline = []
        self.after(0, lambda: self.youtube_time_label.configure(text=""))
        orig_color = self.btn_colors.get("YOUTUBE_BROWSER", "#ff0000")
        btn = self.btn_widgets.get("YOUTUBE_BROWSER")
        if btn:
            self.after(0, lambda: btn.configure(
                text="YOUTUBE", fg_color=orig_color, state="normal"
            ))
        print("[YouTube Browser] State reset")

    def _find_available_browsers(self):
        """Return list of (name, path) for installed Chrome/Brave."""
        candidates = [
            ("Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            ("Chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            ("Chrome", os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")),
            ("Brave",  r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ("Brave",  r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        found, seen = [], set()
        for name, path in candidates:
            if os.path.exists(path) and name not in seen:
                found.append((name, path))
                seen.add(name)
        return found

    def _ask_browser_choice(self, browsers):
        """Show popup to choose browser. Returns path or None if cancelled."""
        result = [None]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Chọn trình duyệt")
        dialog.geometry("300x140")
        dialog.resizable(False, False)
        dialog.configure(fg_color="#1a1a1a")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        dialog.lift()

        ctk.CTkLabel(dialog, text="Chọn trình duyệt để mở YouTube:",
                     font=("Arial", 11)).pack(pady=(20, 12))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        for name, path in browsers:
            color = "#ff6d00" if "brave" in name.lower() else "#1565c0"
            def on_click(p=path):
                result[0] = p
                dialog.destroy()
            ctk.CTkButton(btn_frame, text=name, fg_color=color, width=110, height=35,
                          font=("Arial", 11, "bold"), command=on_click).pack(side="left", padx=8)

        self.wait_window(dialog)
        return result[0]

    def open_youtube_browser(self):
        """Open YouTube in Selenium browser with auto URL monitoring."""
        if not selenium_available:
            tkinter.messagebox.showerror(
                "Lỗi",
                "Chưa cài đặt Selenium!\n\nVui lòng cài đặt:\npip install selenium"
            )
            return

        # Block if browser is currently being opened
        if self.youtube_browser_opening:
            return

        # If browser was closed by user, reset state so we can reopen
        if self.youtube_browser and not self._is_youtube_browser_alive():
            self._reset_youtube_browser_state()

        # Already running and alive
        if self.youtube_browser and self.youtube_monitor_active:
            tkinter.messagebox.showinfo(
                "Thông báo",
                "YouTube Auto Detector đang chạy!\n\nClick vào video để tự động phát hiện key."
            )
            return

        # Find installed browsers
        browsers = self._find_available_browsers()
        if not browsers:
            tkinter.messagebox.showerror(
                "Lỗi",
                "Không tìm thấy Chrome hoặc Brave!\nHãy cài đặt một trong hai trình duyệt."
            )
            return

        # Ask user if multiple browsers found
        if len(browsers) == 1:
            chrome_binary = browsers[0][1]
        else:
            chrome_binary = self._ask_browser_choice(browsers)
            if not chrome_binary:
                return

        # Lock button while opening
        self.youtube_browser_opening = True
        btn = self.btn_widgets.get("YOUTUBE_BROWSER")
        if btn:
            btn.configure(text="ĐANG MỞ...", fg_color="#555555", state="disabled")

        threading.Thread(target=self._start_youtube_browser_worker,
                         args=(chrome_binary,), daemon=True).start()

    def _start_youtube_browser_worker(self, chrome_binary):
        """Worker thread to start YouTube browser."""
        try:
            browser_name = "Brave" if "brave" in chrome_binary.lower() else "Chrome"
            print(f"[YouTube Browser] Starting {browser_name}: {chrome_binary}")

            chrome_options = Options()
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Separate profile per browser so extensions are saved independently
            profile_folder = "brave_automation_profile" if "brave" in chrome_binary.lower() \
                             else "chrome_automation_profile"
            automation_profile_dir = os.path.join(os.path.dirname(__file__), profile_folder)
            chrome_options.add_argument(f"--user-data-dir={automation_profile_dir}")
            chrome_options.add_argument("--profile-directory=Default")
            chrome_options.binary_location = chrome_binary
            print(f"[YouTube Browser] Profile: {automation_profile_dir}")
            
            # Create driver
            print("[YouTube Browser] Creating WebDriver...")
            self.youtube_browser = webdriver.Chrome(options=chrome_options)
            print("[YouTube Browser] WebDriver created")
            
            # Set small window size immediately (before loading page)
            try:
                window_width = 800
                window_height = 600
                self.youtube_browser.set_window_size(window_width, window_height)
                print(f"[YouTube Browser] Set size: {window_width}x{window_height}")
            except Exception as e:
                print(f"[YouTube Browser] Could not set window size: {e}")
            
            # Open YouTube homepage
            print("[YouTube Browser] Opening YouTube...")
            self.youtube_browser.get("https://www.youtube.com")
            
            # Wait for page load
            time.sleep(3)
            print(f"[YouTube Browser] Current URL: {self.youtube_browser.current_url}")
            
            print("[YouTube Browser] ✅ YouTube opened successfully")
            
            # Auto-enable monitoring
            self.youtube_monitor_active = True
            
            # Start monitoring thread
            self.youtube_monitor_thread = threading.Thread(
                target=self._monitor_youtube_url,
                daemon=True
            )
            self.youtube_monitor_thread.start()
            print("[YouTube Browser] Monitor started")
            
            print("[YouTube Browser] ✅ Ready! Open a video to auto-detect key")

        except Exception as e:
            print(f"[YouTube Browser] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self.youtube_browser = None
            self.after(0, lambda: tkinter.messagebox.showerror(
                "Lỗi",
                f"Không thể mở trình duyệt:\n{e}\n\n"
                "Kiểm tra:\n"
                "1. Đã cài Chrome/Brave\n"
                "2. Đã cài: pip install selenium\n"
                "3. Đóng tất cả Chrome đang mở"
            ))

        finally:
            # Always unlock button after opening attempt (success or fail)
            self.youtube_browser_opening = False
            orig_color = self.btn_colors.get("YOUTUBE_BROWSER", "#ff0000")
            btn = self.btn_widgets.get("YOUTUBE_BROWSER")
            if btn:
                self.after(0, lambda: btn.configure(
                    text="YOUTUBE", fg_color=orig_color, state="normal"
                ))
    
    def _monitor_youtube_url(self):
        """Monitor YouTube URL changes and auto-detect (optimized to reduce lag)."""
        print("[YouTube Monitor] Started")
        
        while self.youtube_monitor_active and self.youtube_browser:
            try:
                # Only proceed if AUTO-KEY is ON (autokey_running) OR AUTO DO TONE is ON
                if not self.autokey_running and not self.auto_do_tone_enabled:
                    time.sleep(2)  # Sleep longer when not active (reduced CPU)
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
                        time.sleep(3)
                        
                        # Start detection or auto do tone
                        if self.autokey_running:
                            self.youtube_sync_active = False  # Stop existing sync
                            self._detect_youtube_url(current_url)
                        elif self.auto_do_tone_enabled:
                            # Tự động kích hoạt Dò Tone (click sequence)
                            print("[Auto Dò Tone] Triggering start_autokey")
                            self.after(0, self.start_autokey)
                        
                        # Wait before next check
                        time.sleep(5)
                        
                time.sleep(2)  # Check every 2 seconds instead of 1 (reduced CPU)
                
            except Exception as e:
                err = str(e).lower()
                if any(k in err for k in ("no such window", "not reachable", "disconnected",
                                          "target window already closed", "session deleted")):
                    print("[YouTube Monitor] Browser closed by user, resetting state")
                    self._reset_youtube_browser_state()
                    return
                print(f"[YouTube Monitor] Error: {e}")
                time.sleep(3)

        print("[YouTube Monitor] Stopped")
    
    def _detect_youtube_url(self, url):
        """Detect key from YouTube URL using Cloud MP3 or Local Download with fallback."""
        try:
            # Update status
            self.after(0, lambda: self.autokey_status_label.configure(text="● CONNECTING...", text_color="#ffa726"))
            self.after(0, lambda: self.detected_key_label.configure(text="..."))
            self.after(0, lambda: self.detected_scale_label.configure(text="Đang xử lý..."))
            
            # Create temp directory
            temp_dir = os.path.join(os.path.dirname(__file__), "temp_youtube")
            os.makedirs(temp_dir, exist_ok=True)
            
            audio_path = None

            def _download_audio_segment(max_seconds, name_prefix):
                """Download a short YouTube audio segment to speed up first detection."""
                print(f"[YouTube] Downloading {max_seconds}s with yt-dlp ({name_prefix})...")

                try:
                    import yt_dlp
                except ImportError:
                    print("[YouTube] ERROR: yt_dlp not installed")
                    self.after(0, lambda: self.autokey_status_label.configure(
                        text="MISSING TOOL", text_color="#d32f2f"
                    ))
                    raise Exception("yt_dlp not installed")

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'extractaudio': True,
                    'audioformat': 'mp3',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '64',
                    }],
                    'postprocessor_args': {
                        'ffmpeg_i': ['-t', str(int(max_seconds))],
                    },
                    'outtmpl': os.path.join(temp_dir, f'{name_prefix}_%(id)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'noplaylist': True,
                }

                # Limit network download to requested range (yt-dlp >= 2022.09)
                try:
                    ydl_opts['download_ranges'] = yt_dlp.utils.download_range_func(None, [(0, int(max_seconds))])
                    ydl_opts['force_keyframes_at_cuts'] = False
                except AttributeError:
                    pass

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    path = ydl.prepare_filename(info)

                # Fix extension if yt_dlp kept webm/m4a
                if not os.path.exists(path):
                    exts = ['.mp3', '.m4a', '.webm', '.opus']
                    base = os.path.splitext(path)[0]
                    for e in exts:
                        if os.path.exists(base + e):
                            path = base + e
                            break

                return path
            
            # --- PHASE 1: QUICK DOWNLOAD (first ~40s) ---
            print("[YouTube] Quick download (first ~40s)...")
            self.after(0, lambda: self.autokey_status_label.configure(text="QUICK DOWNLOAD...", text_color="#ffa726"))
            audio_path = _download_audio_segment(40, "quick")

            if not audio_path or not os.path.exists(audio_path):
                raise Exception("Không thể lấy file âm thanh")

            # --- ANALYSIS ---
            self.youtube_sync_active = False

            # === STEP 1: Quick Essentia scan (30s) — show key immediately ===
            quick_key, quick_scale, quick_conf = None, None, 0
            if self.check_essentia_server():
                self.after(0, lambda: self.autokey_status_label.configure(
                    text="● QUICK SCAN...", text_color="#ffa726"))
                quick_key, quick_scale, quick_conf = self.detect_key_essentia(audio_path, duration=30)
                if quick_key and quick_scale:
                    self.after(0, lambda k=quick_key, s=quick_scale, c=quick_conf:
                        self._update_autokey_display(k, s, c / 100.0, 1.0))
                    self.after(0, lambda: self.autokey_status_label.configure(
                        text="● SCANNING...", text_color="#ffa726"))
                    print(f"[YouTube] Quick key: {quick_key} {quick_scale} ({quick_conf}%)")


            try:
                os.remove(audio_path)
            except Exception:
                pass
            # === STEP 2: Full timeline analysis in background thread ===

            def _bg_timeline(quick_k=quick_key, quick_s=quick_scale, quick_c=quick_conf):
                audio_path_full = None
                try:
                    self.after(0, lambda: self.autokey_status_label.configure(text="DOWNLOADING (FULL)...", text_color="#ffa726"))
                    audio_path_full = _download_audio_segment(155, "full")
                    key_timeline = self._analyze_multi_key(audio_path_full)
                finally:
                    try:
                        if audio_path_full and os.path.exists(audio_path_full):
                            os.remove(audio_path_full)
                    except Exception:
                        pass

                if not key_timeline:
                    # Fallback to quick result if available
                    if quick_k and quick_s:
                        self.after(0, lambda: self.autokey_status_label.configure(
                            text="● DONE (ESSENTIA)", text_color="#4caf50"))
                    else:
                        self.after(0, lambda: self.autokey_status_label.configure(
                            text="● FAILED", text_color="#d32f2f"))
                    return

                distinct_keys = set((seg[2], seg[3]) for seg in key_timeline)
                print(f"[YouTube] Timeline: {len(distinct_keys)} key(s): "
                      f"{', '.join(f'{k} {s}' for k, s in distinct_keys)}")

                if len(distinct_keys) > 1:
                    for seg in key_timeline:
                        print(f"  [{seg[0]:.0f}s-{seg[1]:.0f}s]: {seg[2]} {seg[3]} ({seg[4]:.0f}%)")
                    first = key_timeline[0]
                    self.after(0, lambda k=first[2], s=first[3], c=first[4]:
                        self._update_autokey_display(k, s, c / 100.0, 1.0))
                    n = len(distinct_keys)
                    self.after(0, lambda n=n: self.autokey_status_label.configure(
                        text=f"● SYNC ({n} KEYS)", text_color="#00bcd4"))
                    self._start_youtube_time_sync(key_timeline)
                else:
                    # Single key: Essentia result already shown, just finalize status
                    if quick_k and quick_s:
                        self.after(0, lambda: self.autokey_status_label.configure(
                            text="● DONE (ESSENTIA)", text_color="#4caf50"))
                    else:
                        seg = key_timeline[0]
                        self.after(0, lambda k=seg[2], s=seg[3], c=seg[4]:
                            self._update_autokey_display(k, s, c / 100.0, 1.0))
                        self.after(0, lambda: self.autokey_status_label.configure(
                            text="● DONE (FALLBACK)", text_color="#4caf50"))
                    self._start_youtube_time_sync(key_timeline)

            threading.Thread(target=_bg_timeline, daemon=True).start()
                
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
        """Fallback key detection using librosa and Krumhansl-Schmuckler algorithm."""
        try:
            import librosa
            import numpy as np
            
            print("[Fallback] Using librosa-based key detection...")
            
            # Load audio
            y, sr = librosa.load(audio_path, sr=22050, duration=30)
            
            # Extract chroma features (energy of each pitch class)
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            
            # Compute mean chroma across time
            chroma_mean = np.mean(chroma, axis=1)
            
            # Krumhansl-Kessler key profiles
            KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
            KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
            
            NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            
            # Find best matching key
            best_key = None
            best_scale = None
            best_corr = -1
            
            # Normalize chroma
            chroma_norm = chroma_mean / (np.sum(chroma_mean) + 1e-10)
            
            for tonic in range(12):
                # Test Major
                major_profile = np.roll(KK_MAJOR, tonic)
                major_corr = np.corrcoef(chroma_norm, major_profile)[0, 1]
                
                if major_corr > best_corr:
                    best_corr = major_corr
                    best_key = NOTE_NAMES[tonic]
                    best_scale = 'Major'
                
                # Test Minor
                minor_profile = np.roll(KK_MINOR, tonic)
                minor_corr = np.corrcoef(chroma_norm, minor_profile)[0, 1]
                
                if minor_corr > best_corr:
                    best_corr = minor_corr
                    best_key = NOTE_NAMES[tonic]
                    best_scale = 'Minor'
            
            # Calculate confidence (0-100)
            confidence = max(0, min(100, (best_corr + 1) * 50))  # Convert -1..1 to 0..100
            
            print(f"[Fallback] Detected: {best_key} {best_scale} (confidence: {confidence:.1f}%)")
            return best_key, best_scale, confidence
            
        except Exception as e:
            print(f"[Fallback] Error in fallback detection: {e}")
            import traceback
            traceback.print_exc()
            return None, None, 0

    def _detect_key_from_audio(self, y, sr):
        """Detect key from audio array using HPSS + 3-profile ensemble voting."""
        try:
            import librosa
            import numpy as np
        except ImportError:
            return None, None, 0

        if len(y) < sr * 3:
            return None, None, 0

        # Separate harmonic content to remove drums/bass noise
        y_harmonic, _ = librosa.effects.hpss(y)

        # CQT chroma on harmonic signal
        chroma = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr, hop_length=512)

        # Filter low-energy frames (silence / noise)
        frame_energy = np.sqrt(np.sum(chroma ** 2, axis=0))
        thresh = np.median(frame_energy) * 0.3
        chroma_active = chroma[:, frame_energy > thresh]
        if chroma_active.shape[1] < 10:
            chroma_active = chroma

        chroma_norm = np.mean(chroma_active, axis=1)
        chroma_norm = chroma_norm / (np.sum(chroma_norm) + 1e-10)

        # Three profile sets
        KK_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        KK_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        TM_MAJ = np.array([5.0,  2.0,  3.5,  2.0,  4.5,  4.0,  2.0,  4.5,  2.0,  3.5,  1.5,  4.0])
        TM_MIN = np.array([5.0,  2.0,  3.5,  4.5,  2.0,  4.0,  2.0,  4.5,  3.5,  2.0,  1.5,  4.0])
        AA_MAJ = np.array([17.77, 0.15, 14.93, 0.16, 19.80, 11.36, 0.29, 22.06, 0.15, 8.15, 0.23, 4.95])
        AA_MIN = np.array([18.26, 0.74, 14.05, 16.86, 0.70, 14.44, 0.70, 18.62, 4.57, 1.93, 7.38, 1.76])
        PROFILES = [(KK_MAJ, KK_MIN), (TM_MAJ, TM_MIN), (AA_MAJ, AA_MIN)]

        NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        scores = {}
        for maj, min_ in PROFILES:
            for tonic in range(12):
                for prof, scale in [(maj, 'Major'), (min_, 'Minor')]:
                    corr = float(np.corrcoef(chroma_norm, np.roll(prof, tonic))[0, 1])
                    key = (NOTE_NAMES[tonic], scale)
                    scores[key] = scores.get(key, 0.0) + corr

        best_key = max(scores, key=lambda k: scores[k])
        avg_corr = scores[best_key] / len(PROFILES)
        confidence = max(0, min(100, (avg_corr + 1) * 50))
        return best_key[0], best_key[1], confidence

    def _detect_key_from_chroma(self, chroma):
        """Profile matching on a pre-computed chroma array (no HPSS, no audio loading)."""
        import numpy as np

        if chroma.shape[1] < 5:
            return None, None, 0

        frame_energy = np.sqrt(np.sum(chroma ** 2, axis=0))
        thresh = np.median(frame_energy) * 0.3
        active = chroma[:, frame_energy > thresh]
        if active.shape[1] < 5:
            active = chroma

        chroma_norm = np.mean(active, axis=1)
        chroma_norm = chroma_norm / (np.sum(chroma_norm) + 1e-10)

        KK_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        KK_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        TM_MAJ = np.array([5.0,  2.0,  3.5,  2.0,  4.5,  4.0,  2.0,  4.5,  2.0,  3.5,  1.5,  4.0])
        TM_MIN = np.array([5.0,  2.0,  3.5,  4.5,  2.0,  4.0,  2.0,  4.5,  3.5,  2.0,  1.5,  4.0])
        AA_MAJ = np.array([17.77, 0.15, 14.93, 0.16, 19.80, 11.36, 0.29, 22.06, 0.15, 8.15, 0.23, 4.95])
        AA_MIN = np.array([18.26, 0.74, 14.05, 16.86, 0.70, 14.44, 0.70, 18.62, 4.57, 1.93, 7.38, 1.76])
        PROFILES = [(KK_MAJ, KK_MIN), (TM_MAJ, TM_MIN), (AA_MAJ, AA_MIN)]
        NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        scores = {}
        for maj, min_ in PROFILES:
            for tonic in range(12):
                for prof, scale in [(maj, 'Major'), (min_, 'Minor')]:
                    corr = float(np.corrcoef(chroma_norm, np.roll(prof, tonic))[0, 1])
                    key = (NOTE_NAMES[tonic], scale)
                    scores[key] = scores.get(key, 0.0) + corr

        best = max(scores, key=lambda k: scores[k])
        avg_corr = scores[best] / len(PROFILES)
        confidence = max(0, min(100, (avg_corr + 1) * 50))
        return best[0], best[1], confidence

    def _analyze_multi_key(self, audio_path, max_duration=150, segment_size=30):
        """HPSS + chroma computed ONCE, then sliced per segment.
        Uses dominant-key validation to filter noisy/isolated false detections.
        Returns list of (start_sec, end_sec, key, scale, confidence)."""
        try:
            import librosa
            import numpy as np
        except ImportError:
            print("[MultiKey] librosa not available")
            return []

        try:
            print(f"[MultiKey] Loading audio (max {max_duration}s)...")
            y, sr = librosa.load(audio_path, sr=22050, duration=max_duration)
            total_duration = len(y) / sr
            print(f"[MultiKey] {total_duration:.1f}s loaded, running HPSS...")

            y_harmonic, _ = librosa.effects.hpss(y)
            hop = 512
            chroma_full = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr, hop_length=hop)
            fps = chroma_full.shape[1] / total_duration

            print(f"[MultiKey] Chroma {chroma_full.shape}, slicing {segment_size}s segments...")

            # --- Step 1: raw key per segment ---
            raw = []
            t = 0.0
            while t < total_duration:
                end_t = min(t + segment_size, total_duration)
                seg_chroma = chroma_full[:, int(t * fps):int(end_t * fps)]
                key, scale, conf = self._detect_key_from_chroma(seg_chroma)
                if key and scale:
                    raw.append([t, end_t, key, scale, conf])
                t += segment_size

            if not raw:
                return []

            print(f"[MultiKey] Raw segments: "
                  + " | ".join(f"{s[2]} {s[3]}({s[4]:.0f}%)" for s in raw))

            # --- Step 2: find dominant key (highest total confidence weight) ---
            from collections import defaultdict
            weight = defaultdict(float)
            for s in raw:
                weight[(s[2], s[3])] += s[4]
            dominant = max(weight, key=lambda k: weight[k])
            print(f"[MultiKey] Dominant key: {dominant[0]} {dominant[1]}")

            # --- Step 3: validate each segment ---
            # Rule A: confidence < 45 → unreliable, use dominant
            # Rule B: different from dominant AND isolated (no neighbor confirms it)
            #         EXCEPT last segment with conf >= 60 (possible real end-key-change)
            MIN_CONF = 45
            HIGH_CONF = 60   # last segment kept even without neighbor if conf >= this
            validated = []
            for i, seg in enumerate(raw):
                seg_key = (seg[2], seg[3])

                if seg[4] < MIN_CONF:
                    validated.append([seg[0], seg[1], dominant[0], dominant[1], seg[4]])
                    continue

                if seg_key != dominant:
                    prev_ok = i > 0 and (raw[i-1][2], raw[i-1][3]) == seg_key
                    next_ok = i < len(raw) - 1 and (raw[i+1][2], raw[i+1][3]) == seg_key
                    is_last = (i == len(raw) - 1)

                    if not prev_ok and not next_ok:
                        # Last segment with high confidence → real key change at end
                        if is_last and seg[4] >= HIGH_CONF:
                            print(f"[MultiKey] Last seg {seg_key} conf={seg[4]:.0f}% → kept as end-key-change")
                        else:
                            print(f"[MultiKey] Isolated {seg_key} at {seg[0]:.0f}s → replaced with dominant")
                            validated.append([seg[0], seg[1], dominant[0], dominant[1], seg[4]])
                            continue

                validated.append(seg)

            # --- Step 4: merge consecutive identical ---
            merged = [validated[0]]
            for seg in validated[1:]:
                if merged[-1][2] == seg[2] and merged[-1][3] == seg[3]:
                    merged[-1][1] = seg[1]
                    merged[-1][4] = max(merged[-1][4], seg[4])
                else:
                    merged.append(seg)

            print(f"[MultiKey] Final: {len(merged)} segment(s): "
                  + " | ".join(f"[{s[0]:.0f}s-{s[1]:.0f}s] {s[2]} {s[3]}" for s in merged))
            return [(s[0], s[1], s[2], s[3], s[4]) for s in merged]

        except Exception as e:
            print(f"[MultiKey] Error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_youtube_current_time(self):
        """Get current YouTube video playback time via Selenium JavaScript."""
        try:
            if self.youtube_browser:
                t = self.youtube_browser.execute_script(
                    "var v = document.querySelector('video'); return v ? v.currentTime : -1;"
                )
                val = float(t) if t is not None else -1
                return val if val >= 0 else None
        except Exception:
            return None

    def _start_youtube_time_sync(self, key_timeline):
        """Start background thread that syncs displayed key with YouTube playback time."""
        self.youtube_key_timeline = key_timeline
        self.youtube_sync_active = True

        def sync_loop():
            last_key_pair = None
            print(f"[YouTube Sync] Started — {len(key_timeline)} segment(s)")
            while self.youtube_sync_active and self.youtube_monitor_active:
                try:
                    current_time = self._get_youtube_current_time()
                    if current_time is not None:
                        # Update time label
                        mins = int(current_time) // 60
                        secs = int(current_time) % 60
                        time_str = f"⏱ {mins:02d}:{secs:02d}"
                        self.after(0, lambda t=time_str: self.youtube_time_label.configure(text=t))

                        if self.youtube_key_timeline:
                            current_seg = None
                            for seg in self.youtube_key_timeline:
                                if seg[0] <= current_time < seg[1]:
                                    current_seg = seg
                                    break
                            # Past the last segment → use last
                            if current_seg is None and current_time >= self.youtube_key_timeline[-1][1]:
                                current_seg = self.youtube_key_timeline[-1]

                            if current_seg:
                                key_pair = (current_seg[2], current_seg[3])
                                if key_pair != last_key_pair:
                                    last_key_pair = key_pair
                                    k, s, c = current_seg[2], current_seg[3], current_seg[4]
                                    print(f"[YouTube Sync] {current_time:.0f}s → {k} {s}")
                                    self.after(0, lambda k=k, s=s, c=c:
                                        self._update_autokey_display(k, s, c / 100.0, 1.0))
                except Exception as e:
                    print(f"[YouTube Sync] Error: {e}")
                time.sleep(1)
            self.after(0, lambda: self.youtube_time_label.configure(text=""))
            print("[YouTube Sync] Stopped")

        threading.Thread(target=sync_loop, daemon=True).start()

    def on_closing(self):
        print("\n🛑 Đang bắt đầu quy trình tắt...")
        
        # Stop YouTube monitoring first (stop threads immediately)
        self.youtube_monitor_active = False
        self.auto_detect_enabled = False
        
        # Close YouTube browser quickly (don't wait)
        if self.youtube_browser:
            try:
                print("[YouTube Browser] Closing browser...")
                # Use a thread to close browser so it doesn't block
                def close_browser():
                    try:
                        self.youtube_browser.quit()
                    except:
                        pass
                
                close_thread = threading.Thread(target=close_browser, daemon=True)
                close_thread.start()
                # Don't wait for it, just continue
                print("[YouTube Browser] Close initiated")
            except Exception as e:
                print(f"[YouTube Browser] Error closing: {e}")
        
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

                # 2. Đợi hộp thoại "Save" hiện lên (giảm thời gian chờ)
                print("⏳ Đang đợi hộp thoại xác nhận 'Save' (tối đa 2s)...")
                found_dialog = False
                for i in range(20):  # Giảm từ 50 xuống 20 (2 giây thay vì 5 giây)
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
                            
                            # Decision based on setting
                            exit_action = self.autokey_coords.get("cubase_exit_action", "dont_save")
                            
                            if exit_action == "save":
                                # Click "Save" button (usually on the left side of the dialog)
                                click_x = dlg['rect']['left'] + (w // 4)
                                click_y = dlg['rect']['top'] + h - 25
                                print(f"🖱️ Click vào nút Save tại ({click_x}, {click_y})")
                                WindowsHelper.click(click_x, click_y)
                                
                                # Send phím tắt S for Save
                                user32.keybd_event(VK_S, 0, 0, 0)
                                time.sleep(0.05)
                                user32.keybd_event(VK_S, 0, KEYEVENTF_KEYUP, 0)
                                print("✅ Đã chọn 'Save'")
                            else:
                                # Click "Don't Save" button (usually in the middle/right)
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
                            time.sleep(0.1)  # Giảm từ 0.05 xuống 0.1
                            break
                    if found_dialog: break
                
                if not found_dialog:
                    print("⚠️ Không thấy hộp thoại xác nhận xuất hiện. Có thể Cubase đã đóng luôn hoặc không có gì để lưu.")

        except Exception as e:
            print(f"❌ Lỗi khi đóng Cubase: {e}")

        print("👋 Đang đóng Tool...")
        
        # Force exit immediately without waiting
        try:
            self.destroy()
        except:
            pass
        
        # Force kill process
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
        """Worker thread to process audio file with fallback support."""
        import os
        import tempfile
        import shutil
        filename = os.path.basename(file_path)
        temp_path = None
        
        try:
            self.after(0, lambda: self.autokey_status_label.configure(text="● LOADING FILE...", text_color="#ffa726"))
            self.after(0, lambda: self.detected_key_label.configure(text="..."))
            self.after(0, lambda: self.detected_scale_label.configure(text="Đang xử lý..."))
            
            key, mode, conf = None, None, 0
            method = "UNKNOWN"
            
            # Try Essentia server first
            if self.check_essentia_server():
                print(f"[Auto-Key] Using Essentia server for file: {file_path}")
                self.after(0, lambda: self.autokey_status_label.configure(text="● SERVER ANALYZING...", text_color="#ffa726"))
                
                key, mode, conf = self.detect_key_essentia(file_path)
                method = "ESSENTIA"
            
            # Use fallback if Essentia not available or failed
            if not key or not mode:
                print(f"[Auto-Key] Essentia not available, using fallback for: {file_path}")
                self.after(0, lambda: self.autokey_status_label.configure(text="● FALLBACK ANALYZING...", text_color="#ffa726"))
                
                key, mode, conf = self._detect_key_fallback(file_path)
                method = "FALLBACK"
            
            if key and mode:
                # Update UI
                self.after(0, lambda: self._update_autokey_display(key, mode, conf/100.0, 1.0))
                self.after(0, lambda: self.autokey_status_label.configure(text=f"● DONE ({method})", text_color="#4caf50"))
                
                # Send to MIDI
                self.send_autokey_midi(key, mode)
            else:
                self.after(0, lambda: self.autokey_status_label.configure(text="● FAILED", text_color="#d32f2f"))
                
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
