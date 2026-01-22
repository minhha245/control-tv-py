import customtkinter as ctk
import rtmidi
import threading
import time
import os
import json
import ctypes
import uuid
import hashlib
import datetime
import tkinter.messagebox

# Automation Libs
try:
    import pyautogui
    import pygetwindow as gw
except ImportError:
    print("Warning: Automation libs not found. Auto-Key feature disabled.")

MIDI_PORT_CHECK = "loopMIDI"
CHANNEL = 0 

CC_MAP = {
    "MUSIC_VOL": 21, "MIC_VOL": 20, "REVERB_LONG": 22, "REVERB_SHORT": 23, "TUNE": 27,
    "DELAY": 26,
    "MUTE_MUSIC": 25, "MUTE_MIC": 24, "TONE_VAL_SEND": 28,  # Single CC for Value
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
        self.geometry("850x350")
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
            "listen_x_offset": 0.5,  # 50% of width
            "listen_y_offset": 0.32,  # 32% of height
            "send_x_offset": 0.5,     # 50% of width
            "send_y_from_bottom": 140  # pixels from bottom
        }

        self.setup_left_panel()
        self.setup_center_panel()
        self.setup_right_panel()
        
        self.load_settings()
        self.load_autokey_coords()

    def setup_left_panel(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=10)
        
        btns = [
            ("DÒ TONE", self.col_btn_purple, "DO_TONE"),
            ("LẤY TONE", self.col_btn_purple, "LAY_TONE"),
            ("NHẠC", self.col_btn_green, "MUTE_MUSIC"),
            ("MIC", self.col_btn_green, "MUTE_MIC"),
            ("VANG", self.col_btn_red, "VANG_FX"),
            ("LOFI", self.col_btn_red, "LOFI"),
            ("REMIX", self.col_btn_red, "REMIX"),
            ("CÀI ĐẶT", "#1f77b4", "SETTINGS"),
            ("LƯU", self.col_btn_yellow, "SAVE")
        ]

        # Initialize hidden buttons states
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

        bottom_frame = ctk.CTkFrame(frame, fg_color="transparent")
        bottom_frame.grid(row=len(sliders), column=0, columnspan=3, pady=5)
        
        opt = ctk.CTkOptionMenu(bottom_frame, values=["NHẠC TRẺ", "BOLERO", "REMIX"], fg_color="#1f77b4", height=24, font=("Arial", 11))
        opt.pack(side="left", padx=5)
        
        btn_fix = ctk.CTkButton(bottom_frame, text="Fix Méo", fg_color="#d32f2f", width=60, height=24, font=("Arial", 11), command=lambda: self.on_btn_click("FIX_MEO"))
        btn_fix.pack(side="left", padx=5)

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

        # Extra Knobs
        for i in range(1, 6):
            key = f"EXTRA_KNOB_{i}"
            f = ctk.CTkFrame(frame, fg_color="transparent")
            f.pack(pady=2, fill="x", padx=5)
            ctk.CTkLabel(f, text=f"EX-{i}", font=("Arial", 9), width=30).pack(side="left")
            s = ctk.CTkSlider(f, from_=0, to=127, progress_color="#444", height=14)
            s.pack(side="left", padx=5, fill="x", expand=True)
            s.configure(command=lambda v, k=key: self.on_slider_change(v, k))
            self.slider_widgets[key] = s
        
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
            if new_state: # ON
                btn.configure(fg_color="#F0F0F0", text_color="#000000")
            else: # OFF
                btn.configure(fg_color=orig_color, text_color="#FFFFFF")
        
        # Always send MIDI if CC exists, even if button is hidden
        cc = CC_MAP.get(key)
        if cc:
            midi.send_cc(cc, 127)
            self.after(50, lambda: midi.send_cc(cc, 0))

        if key == "VANG_FX":
            for i in range(1, 6):
                extra_key = f"EXTRA_BTN_{i}"
                if self.btn_states.get(extra_key) != new_state:
                    self.on_btn_toggle(extra_key)

    def on_btn_click(self, key):
        # Default behavior: Flash but NO MIDI for TONE_UP/TONE_DOWN here
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
                
                # Send VALUE to CC 28
                # Map -12..12 -> 0..127
                midi_val = int(64 + new_val * (63.5/12)) # 0 -> 64, 12 -> 127.5, -12 -> 0.5
                midi_val = max(0, min(127, midi_val))
                midi.send_cc(CC_MAP.get("TONE_VAL_SEND"), midi_val)
            except: pass
        elif key == "TONE_DOWN":
            try:
                cur = float(self.tone_val.cget("text"))
                new_val = max(-12.0, cur - 1.0)
                self.tone_val.configure(text=f"{new_val:.1f}")
                
                # Send VALUE to CC 28
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
        # Trigger visual feedback (Flash) but NO MIDI
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
        """Load Auto-Key coordinates from file"""
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
        """Save Auto-Key coordinates to file"""
        try:
            with open("autokey_coords.json", "w", encoding='utf-8') as f:
                json.dump(self.autokey_coords, f, indent=4)
            print("Đã lưu tọa độ Auto-Key vào autokey_coords.json")
            return True
        except Exception as e:
            print(f"Lỗi lưu tọa độ Auto-Key: {e}")
            return False

    def pick_coordinate(self, button_name, x_entry, y_entry, popup):
        """Allow user to click on screen to pick coordinates"""
        try:
            print(f"\n🎯 Bắt đầu đo tọa độ nút {button_name}...")
            
            # [1/3] Focus Cubase first (Like DO TONE does)
            print("   Focus Cubase...")
            cubase_wins = gw.getWindowsWithTitle('Cubase')
            if cubase_wins:
                main_win = cubase_wins[0]
                try:
                    if main_win.isMinimized: main_win.restore()
                    main_win.activate()
                    ctypes.windll.user32.SwitchToThisWindow(main_win._hWnd, True)
                except: pass
                time.sleep(1.0) # Wait for UI to stabilize

            # [2/3] Find Auto-Key window
            target_win = None
            for t in gw.getAllTitles():
                if "Auto-Key" in t:
                    wins = gw.getWindowsWithTitle(t)
                    if wins and wins[0].width > 50:
                        target_win = wins[0]
                        break
            
            if not target_win:
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
            
            # [3/3] Activate Auto-Key window
            try:
                target_win.activate()
            except:
                pass
            
            print(f"📍 Cửa sổ Auto-Key: {target_win.width}x{target_win.height} tại ({target_win.left}, {target_win.top})")
            print(f"👆 Hướng dẫn: Click CHUỘT TRÁI vào nút {button_name} trên màn hình ngay bây giờ!")
            
            # Wait for Left Mouse Click (0x01 = VK_LBUTTON)
            # First, ensure button is released
            while ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                time.sleep(0.05)
            
            # Then wait for it to be pressed
            clicked_pos = None
            while True:
                if ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                    clicked_pos = pyautogui.position()
                    break
                time.sleep(0.01)
            
            print(f"✅ Đã nhận tọa độ tại: ({clicked_pos.x}, {clicked_pos.y})")
            
            # Calculate offsets relative to Auto-Key window
            rel_x = clicked_pos.x - target_win.left
            rel_y = clicked_pos.y - target_win.top
            
            # Calculate percentages
            x_percent = (rel_x / target_win.width) * 100
            y_percent = (rel_y / target_win.height) * 100
            
            # Calculate Y from bottom
            y_from_bottom = target_win.height - rel_y
            
            print(f"📊 Tọa độ tương đối: X={rel_x}px, Y={rel_y}px")
            print(f"📊 Phần trăm: X={x_percent:.1f}%, Y={y_percent:.1f}%")
            print(f"📊 Y từ đáy: {y_from_bottom}px")
            
            # Update entry fields
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
        """Open popup to configure Auto-Key coordinates"""
        # Change SETTINGS button appearance to active
        btn = self.btn_widgets.get("SETTINGS")
        orig_color = "#1f77b4"
        if btn:
            btn.configure(text="ĐANG MỞ...", fg_color="#F0F0F0", text_color="black")

        popup = ctk.CTkToplevel(self)
        popup.title("CÀI ĐẶT TỌA ĐỘ AUTO-KEY")
        popup.geometry("550x450")
        popup.resizable(False, False)
        popup.configure(fg_color=self.col_bg)
        
        # Make popup modal and bring to front
        popup.transient(self)
        popup.grab_set()
        popup.focus_force()
        popup.lift()

        # Labels for binding
        listen_labels = ["LISTEN - X", "LISTEN - Y"]
        send_labels = ["SEND - X", "SEND - Y"]

        def on_close_popup():
            if btn:
                btn.configure(text="CÀI ĐẶT", fg_color=orig_color, text_color="white")
            popup.destroy()

        # Handle closing via "X" button
        popup.protocol("WM_DELETE_WINDOW", on_close_popup)
        
        # Title
        ctk.CTkLabel(
            popup, 
            text="CÀI ĐẶT TỌA ĐỘ NÚT AUTO-KEY",
            font=("Arial", 16, "bold"),
            text_color=self.col_text_green
        ).pack(pady=10)
        
        # Info label
        ctk.CTkLabel(
            popup,
            text="Chuột phải vào ô nhập để lấy tọa độ tự động",
            font=("Arial", 11, "italic"),
            text_color="#ffa726"
        ).pack(pady=(0, 10))
        
        # Settings frame
        settings_frame = ctk.CTkFrame(popup, fg_color="transparent")
        settings_frame.pack(pady=5, padx=20, fill="both", expand=True)
        
        # Listen UI
        listen_x_entry = ctk.CTkEntry(settings_frame, width=80)
        listen_y_entry = ctk.CTkEntry(settings_frame, width=80)
        
        ctk.CTkLabel(settings_frame, text="Nút LISTEN - X (%):", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w", pady=8, padx=5)
        listen_x_entry.insert(0, str(int(self.autokey_coords["listen_x_offset"] * 100)))
        listen_x_entry.grid(row=0, column=1, pady=8, padx=5)
        
        ctk.CTkLabel(settings_frame, text="Nút LISTEN - Y (%):", font=("Arial", 11, "bold")).grid(row=1, column=0, sticky="w", pady=8, padx=5)
        listen_y_entry.insert(0, str(int(self.autokey_coords["listen_y_offset"] * 100)))
        listen_y_entry.grid(row=1, column=1, pady=8, padx=5)
        
        # Pick Listen button
        def pick_listen_coords(e=None):
            popup.withdraw()
            threading.Thread(target=lambda: self.pick_coordinate("LISTEN", listen_x_entry, listen_y_entry, popup), daemon=True).start()
        
        # Bind right click to entries
        listen_x_entry.bind("<Button-3>", pick_listen_coords)
        listen_y_entry.bind("<Button-3>", pick_listen_coords)

        ctk.CTkButton(settings_frame, text="ĐO TỌA ĐỘ", fg_color="#ff9800", width=90, height=28, command=pick_listen_coords).grid(row=0, column=3, rowspan=2, padx=10)

        # Send UI
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

        # Bind right click to entries
        send_x_entry.bind("<Button-3>", pick_send_coords)
        send_y_entry.bind("<Button-3>", pick_send_coords)
        
        ctk.CTkButton(settings_frame, text="ĐO TỌA ĐỘ", fg_color="#ff9800", width=90, height=28, command=pick_send_coords).grid(row=2, column=3, rowspan=2, padx=10)
        
        # Info text
        info_text = ctk.CTkTextbox(popup, height=80, width=500, fg_color="#2a2a2a")
        info_text.pack(pady=10, padx=20)
        info_text.insert("1.0", 
            "💡 Hướng dẫn:\n"
            "1. Mở cửa sổ Auto-Key Plugin trong Cubase\n"
            "2. Click 'ĐO TỌA ĐỘ' bên cạnh nút muốn đo\n"
            "3. Đợi 3 giây, sau đó click vào nút Listen/Send trong Auto-Key\n"
            "4. Tọa độ sẽ tự động được tính và điền vào"
        )
        info_text.configure(state="disabled")
        
        # Buttons frame
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        def save_coords():
            try:
                self.autokey_coords["listen_x_offset"] = float(listen_x_entry.get()) / 100
                self.autokey_coords["listen_y_offset"] = float(listen_y_entry.get()) / 100
                self.autokey_coords["send_x_offset"] = float(send_x_entry.get()) / 100
                self.autokey_coords["send_y_from_bottom"] = int(send_y_entry.get())
                
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
        # Gửi CC ON (127)
        cc = CC_MAP.get("DO_TONE")
        if cc: midi.send_cc(cc, 127)
        
        btn = self.btn_widgets.get("DO_TONE")
        if btn: btn.configure(text="ĐANG DÒ...", fg_color="#F0F0F0", text_color="black")
        
        threading.Thread(target=self.auto_detect_tone_thread, daemon=True).start()

    def auto_detect_tone_thread(self):
        try:
            original_pos = pyautogui.position()

            print("[1/3] Focus Cubase...")
            cubase_wins = gw.getWindowsWithTitle('Cubase')
            if not cubase_wins:
                print("❌ Không thấy Cubase! Hãy mở Cubase.")
                return
            
            main_win = cubase_wins[0]
            try:
                if main_win.isMinimized: main_win.restore()
                main_win.activate()
                import ctypes
                hwnd = main_win._hWnd
                ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            except Exception as e:
                print(f"Warning Focus: {e}")
            
            time.sleep(1.0) 

            target_win = None
            for t in gw.getAllTitles():
                if "Auto-Key" in t:
                    wins = gw.getWindowsWithTitle(t)
                    if wins and wins[0].width > 50: 
                        target_win = wins[0]
                        break
            
            if not target_win:
                print("❌ Không thấy Plugin Auto-Key! Hãy mở Plugin lên màn hình.")
                return

            try: target_win.activate()
            except: pass
            time.sleep(0.5)

            # Use saved coordinates from settings
            listen_x = target_win.left + int(target_win.width * self.autokey_coords["listen_x_offset"])
            listen_y = target_win.top + int(target_win.height * self.autokey_coords["listen_y_offset"])
            send_x = target_win.left + int(target_win.width * self.autokey_coords["send_x_offset"])
            send_y = target_win.top + target_win.height - self.autokey_coords["send_y_from_bottom"]

            print(f"Click Listen ({listen_x}, {listen_y})...")
            pyautogui.click(listen_x, listen_y)
            
            print("Đang nghe (15s)...")
            time.sleep(15)

            print(f"Click Send ({send_x}, {send_y})...")
            pyautogui.click(send_x, send_y)
            
            pyautogui.moveTo(original_pos)
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
        # Gửi CC ON (127)
        cc = CC_MAP.get("LAY_TONE")
        if cc: midi.send_cc(cc, 127)

        btn = self.btn_widgets.get("LAY_TONE")
        if btn: btn.configure(text="ĐANG LẤY...", fg_color="#F0F0F0", text_color="black")

        threading.Thread(target=self.lay_tone_thread, daemon=True).start()

    def lay_tone_thread(self):
        try:
            original_pos = pyautogui.position()

            print("[1/3] Focus Cubase...")
            cubase_wins = gw.getWindowsWithTitle('Cubase')
            if not cubase_wins:
                print("❌ Không thấy Cubase! Hãy mở Cubase.")
                return

            main_win = cubase_wins[0]
            try:
                if main_win.isMinimized: main_win.restore()
                main_win.activate()
                import ctypes
                hwnd = main_win._hWnd
                ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            except Exception as e:
                print(f"Warning Focus: {e}")

            time.sleep(1.0)

            target_win = None
            for t in gw.getAllTitles():
                if "Auto-Key" in t:
                    wins = gw.getWindowsWithTitle(t)
                    if wins and wins[0].width > 50:
                        target_win = wins[0]
                        break

            if not target_win:
                print("❌ Không thấy Plugin Auto-Key! Hãy mở Plugin lên màn hình.")
                return

            try: target_win.activate()
            except: pass
            time.sleep(0.5)

            # Use saved coordinates from settings
            send_x = target_win.left + int(target_win.width * self.autokey_coords["send_x_offset"])
            send_y = target_win.top + target_win.height - self.autokey_coords["send_y_from_bottom"]

            print(f"Click Send ({send_x}, {send_y})...")
            pyautogui.click(send_x, send_y)

            pyautogui.moveTo(original_pos)
            print("✅ Xong quy trình!")

        except Exception as e:
            print(f"Lỗi: {e}")
        finally:
            cc = CC_MAP.get("LAY_TONE")
            if cc: midi.send_cc(cc, 0)

            btn = self.btn_widgets.get("LAY_TONE")
            orig_col = self.btn_colors.get("LAY_TONE", self.col_btn_purple)
            if btn: btn.configure(text="LẤY TONE", fg_color=orig_col, text_color="white")

    def on_closing(self):
        self.destroy()
        os._exit(0)

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
