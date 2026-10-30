import math
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import simpledialog


class JarvisWindow:
    COLORS = {
        "background": "#030406",
        "panel": "#0b1017",
        "panel_light": "#101824",
        "panel_input": "#070a0f",
        "border": "#1d2a38",
        "text": "#f4f8ff",
        "muted": "#9aa9bc",
        "dim": "#58677b",
        "cyan": "#00f5ff",
        "ice": "#58bfff",
        "violet": "#8b5cff",
        "plasma": "#b16cff",
        "mint": "#42ffc8",
        "amber": "#ffb84d",
        "red": "#ff4568",
    }

    def __init__(self, events, commands, stop_event, pause_event, ai_enabled=False):
        self.events = events
        self.commands = commands
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.is_paused = pause_event.is_set()
        self.status = "STARTING"
        self.status_detail = "Initializing voice services"
        self.microphone_state = "STARTING"
        self.ai_key_configured = ai_enabled
        self.started_at = time.monotonic()
        self.active_view = "conversation"
        self.messages = []
        self.activity_entries = []
        self.animation_step = 0
        self.motion_enabled = True

        self.root = tk.Tk()
        self.root.title("JARVIS | Crystal Black Command Center")
        self.root.geometry("1360x860")
        self.root.minsize(1000, 700)
        self.root.configure(bg=self.COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._build_layout()
        self._set_status("STARTING", "Initializing voice services")
        self._set_microphone(self.microphone_state)
        self._set_ai_state(ai_enabled)
        self.root.after(100, self._poll_events)
        self.root.after(100, self._animate)
        self.root.after(500, self._update_clock)

    def _build_layout(self):
        colors = self.COLORS
        outer = tk.Frame(self.root, bg=colors["background"])
        outer.pack(fill="both", expand=True, padx=20, pady=16)
        outer.grid_columnconfigure(0, minsize=76)
        outer.grid_columnconfigure(1, weight=5, minsize=360)
        outer.grid_columnconfigure(2, weight=6, minsize=400)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_rowconfigure(2, minsize=88)

        header = tk.Frame(outer, bg=colors["background"])
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(1, weight=1)
        mark = tk.Canvas(header, width=38, height=38, bg=colors["background"], highlightthickness=0)
        mark.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        mark.create_polygon(19, 2, 35, 19, 19, 36, 3, 19, fill="#0a1a22", outline=colors["cyan"], width=1)
        mark.create_line(19, 7, 19, 31, fill=colors["ice"], width=1)
        mark.create_line(8, 19, 30, 19, fill=colors["ice"], width=1)
        tk.Label(
            header,
            text="JARVIS",
            bg=colors["background"],
            fg=colors["text"],
            font=("Bahnschrift SemiBold", 18),
        ).grid(row=0, column=1, sticky="w")
        tk.Label(
            header,
            text="CRYSTAL BLACK  /  PERSONAL COMMAND CENTER",
            bg=colors["background"],
            fg=colors["dim"],
            font=("Bahnschrift", 8),
        ).grid(row=1, column=1, sticky="w", pady=(1, 0))

        self.status_pill = tk.Label(
            header,
            text="STARTING",
            bg=colors["panel_light"],
            fg=colors["ice"],
            font=("Bahnschrift SemiBold", 8),
            padx=12,
            pady=8,
        )
        self.status_pill.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 10))
        self.ai_badge = tk.Label(
            header,
            text="AI / LOCAL MODE",
            bg=colors["background"],
            fg=colors["dim"],
            font=("Bahnschrift SemiBold", 8),
            padx=12,
        )
        self.ai_badge.grid(row=0, column=3, rowspan=2, sticky="e")
        clock_panel = tk.Frame(header, bg=colors["background"])
        clock_panel.grid(row=0, column=4, rowspan=2, sticky="e", padx=(18, 0))
        self.clock_label = tk.Label(
            clock_panel,
            text="--:--:--",
            bg=colors["background"],
            fg=colors["text"],
            font=("Bahnschrift SemiBold", 12),
        )
        self.clock_label.pack(anchor="e")
        self.uptime_label = tk.Label(
            clock_panel,
            text="UP 00:00",
            bg=colors["background"],
            fg=colors["dim"],
            font=("Bahnschrift", 8),
        )
        self.uptime_label.pack(anchor="e", pady=(2, 0))
        self.motion_button = tk.Button(
            header,
            text="MOTION ON",
            command=self._toggle_motion,
            bg=colors["panel"],
            fg=colors["muted"],
            activebackground=colors["panel_light"],
            activeforeground=colors["cyan"],
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=7,
            font=("Bahnschrift SemiBold", 7),
            cursor="hand2",
        )
        self.motion_button.grid(row=0, column=5, rowspan=2, sticky="e", padx=(10, 0))

        nav = tk.Frame(outer, bg=colors["background"], width=76)
        nav.grid(row=1, column=0, sticky="nsw", padx=(0, 12))
        nav.grid_propagate(False)
        tk.Label(
            nav,
            text="SYSTEMS",
            bg=colors["background"],
            fg=colors["dim"],
            font=("Bahnschrift SemiBold", 7),
        ).pack(anchor="center", pady=(5, 12))
        self.nav_buttons = {}
        for code, label, target, enabled in (
            ("CC", "CORE", "conversation", True),
            ("CH", "CHAT", "conversation", True),
            ("EV", "EVENTS", "activity", True),
            ("VC", "VOICE", "voice", True),
            ("TK", "TASKS", "planned", False),
            ("TL", "TOOLS", "planned", False),
            ("MM", "MEMORY", "planned", False),
        ):
            button = tk.Button(
                nav,
                text=f"{code}\n{label}",
                command=lambda view=target: self._navigate(view),
                bg=colors["panel"] if enabled else colors["background"],
                fg=colors["cyan"] if enabled and label == "CORE" else (colors["muted"] if enabled else colors["dim"]),
                activebackground=colors["panel_light"],
                activeforeground=colors["cyan"],
                disabledforeground=colors["dim"],
                relief="flat",
                borderwidth=0,
                padx=4,
                pady=10,
                font=("Bahnschrift SemiBold", 8),
                cursor="hand2" if enabled else "arrow",
                state="normal" if enabled else "disabled",
            )
            button.pack(fill="x", pady=3)
            self.nav_buttons[label] = button

        core_panel = tk.Frame(
            outer,
            bg=colors["panel"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        core_panel.grid(row=1, column=1, sticky="nsew", padx=(0, 12))
        tk.Label(
            core_panel,
            text="HOLOGRAPHIC CORE  /  01",
            bg=colors["panel"],
            fg=colors["cyan"],
            font=("Bahnschrift SemiBold", 9),
        ).pack(anchor="w", padx=18, pady=(18, 4))
        self.orb = tk.Canvas(
            core_panel,
            bg=colors["panel"],
            highlightthickness=0,
            height=390,
        )
        self.orb.pack(fill="both", expand=True, padx=8, pady=(0, 0))
        self.voice_title = tk.Label(
            core_panel,
            text="Starting up",
            bg=colors["panel"],
            fg=colors["text"],
            font=("Bahnschrift SemiBold", 18),
        )
        self.voice_title.pack(pady=(2, 2))
        self.voice_detail = tk.Label(
            core_panel,
            text="Initializing voice services",
            bg=colors["panel"],
            fg=colors["muted"],
            font=("Segoe UI", 10),
            wraplength=340,
        )
        self.voice_detail.pack(padx=18, pady=(0, 6))
        tk.Label(
            core_panel,
            text="AMBIENT SIGNAL  /  DECORATIVE, NOT MEASURED AUDIO",
            bg=colors["panel"],
            fg=colors["dim"],
            font=("Bahnschrift", 7),
        ).pack(pady=(0, 2))
        self.levels = tk.Canvas(
            core_panel,
            width=240,
            height=34,
            bg=colors["panel"],
            highlightthickness=0,
        )
        self.levels.pack(pady=(0, 10))
        self.pause_button = tk.Button(
            core_panel,
            text="PAUSE LISTENING" if not self.is_paused else "RESUME LISTENING",
            command=self.toggle_pause,
            bg="#0c2029",
            fg=colors["cyan"],
            activebackground=colors["panel_light"],
            activeforeground=colors["text"],
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=10,
            font=("Bahnschrift SemiBold", 8),
            cursor="hand2",
        )
        self.pause_button.pack(fill="x", padx=18, pady=(0, 6))
        tk.Button(
            core_panel,
            text="QUIT JARVIS",
            command=self.close,
            bg=colors["panel"],
            fg=colors["muted"],
            activebackground=colors["panel_light"],
            activeforeground=colors["text"],
            relief="flat",
            borderwidth=0,
            pady=8,
            font=("Bahnschrift SemiBold", 8),
            cursor="hand2",
        ).pack(fill="x", padx=18, pady=(0, 14))

        intelligence = tk.Frame(outer, bg=colors["background"])
        intelligence.grid(row=1, column=2, sticky="nsew")
        intelligence.grid_columnconfigure(0, weight=1)
        intelligence.grid_rowconfigure(1, weight=1)
        panel_header = tk.Frame(
            intelligence,
            bg=colors["panel"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        panel_header.grid(row=0, column=0, sticky="ew", pady=(0, 1))
        tk.Label(
            panel_header,
            text="INTELLIGENCE  /  CHANNEL 02",
            bg=colors["panel"],
            fg=colors["text"],
            font=("Bahnschrift SemiBold", 10),
        ).pack(side="left", padx=16, pady=15)
        view_tabs = tk.Frame(panel_header, bg=colors["panel"])
        view_tabs.pack(side="right", padx=8)
        self.view_buttons = {}
        for label, view in (("CONVERSATION", "conversation"), ("EVENTS", "activity")):
            button = tk.Button(
                view_tabs,
                text=label,
                command=lambda target=view: self.show_view(target),
                bg=colors["panel"],
                fg=colors["cyan"] if view == "conversation" else colors["muted"],
                activebackground=colors["panel_light"],
                activeforeground=colors["cyan"],
                relief="flat",
                borderwidth=0,
                padx=8,
                pady=8,
                font=("Bahnschrift SemiBold", 8),
                cursor="hand2",
            )
            button.pack(side="left", padx=2)
            self.view_buttons[view] = button

        transcript_frame = tk.Frame(
            intelligence,
            bg=colors["panel_input"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        transcript_frame.grid(row=1, column=0, sticky="nsew")
        transcript_frame.grid_rowconfigure(0, weight=1)
        transcript_frame.grid_columnconfigure(0, weight=1)
        self.transcript = tk.Text(
            transcript_frame,
            bg=colors["panel_input"],
            fg=colors["text"],
            insertbackground=colors["cyan"],
            selectbackground="#123241",
            relief="flat",
            borderwidth=0,
            padx=18,
            pady=16,
            wrap="word",
            font=("Segoe UI", 10),
            state="disabled",
            spacing1=3,
            spacing3=9,
        )
        self.transcript.grid(row=0, column=0, sticky="nsew")
        scrollbar = tk.Scrollbar(
            transcript_frame,
            command=self.transcript.yview,
            bg=colors["panel"],
            troughcolor=colors["panel_input"],
            activebackground=colors["cyan"],
            relief="flat",
            borderwidth=0,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.transcript.configure(yscrollcommand=scrollbar.set)
        self.transcript.tag_configure("user", foreground=colors["cyan"], font=("Bahnschrift SemiBold", 9))
        self.transcript.tag_configure("assistant", foreground=colors["ice"], font=("Bahnschrift SemiBold", 9))
        self.transcript.tag_configure("activity", foreground=colors["violet"], font=("Bahnschrift SemiBold", 9))
        self.transcript.tag_configure("body", foreground=colors["text"], font=("Segoe UI", 10))
        self.transcript.tag_configure("notice", foreground=colors["muted"], font=("Segoe UI", 9, "italic"))
        self._append_transcript("notice", "JARVIS is ready. Speak naturally, or type a command below.")

        composer = tk.Frame(
            outer,
            bg=colors["panel"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        composer.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(12, 0))
        composer.grid_columnconfigure(1, weight=1)
        self.mic_button = tk.Button(
            composer,
            text=f"MIC {self.microphone_state}",
            command=self.toggle_pause,
            bg="#0c2029",
            fg=colors["dim"],
            activebackground=colors["panel_light"],
            activeforeground=colors["text"],
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=("Bahnschrift SemiBold", 8),
            cursor="hand2",
        )
        self.mic_button.grid(row=0, column=0, padx=(12, 5), pady=10)
        self.command_entry = tk.Text(
            composer,
            height=2,
            wrap="word",
            bg=colors["panel_input"],
            fg=colors["text"],
            insertbackground=colors["cyan"],
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=10,
            font=("Segoe UI", 11),
        )
        self.command_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        self.command_entry.bind("<Return>", self._handle_enter)
        tk.Button(
            composer,
            text="SEND",
            command=self.submit_command,
            bg=colors["cyan"],
            fg=colors["background"],
            activebackground=colors["ice"],
            activeforeground=colors["background"],
            relief="flat",
            borderwidth=0,
            padx=18,
            pady=10,
            font=("Bahnschrift SemiBold", 9),
            cursor="hand2",
        ).grid(row=0, column=2, padx=(5, 12), pady=9)

        tk.Label(
            outer,
            text="VOICE INPUT / GOOGLE SPEECH RECOGNITION     |     SHIFT+ENTER FOR A NEW LINE     |     WINDOW CONTROLS: STANDARD WINDOWS TITLE BAR",
            bg=colors["background"],
            fg=colors["dim"],
            font=("Bahnschrift", 7),
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def _handle_enter(self, event):
        if event.state & 0x0001:
            return None
        self.submit_command()
        return "break"

    def post_event(self, event, value=None):
        self.events.put((event, value))

    def submit_command(self, _event=None):
        command = self.command_entry.get("1.0", "end-1c").strip()
        if not command:
            return "break"
        self.command_entry.delete("1.0", "end")
        self.post_event("user", command)
        self.commands.put(command)
        self._set_status("PROCESSING", "Working on your request")
        return "break"

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_event.set()
            self._set_microphone("PAUSED")
            self._set_status("PAUSED", "Microphone is paused")
            self.pause_button.configure(text="RESUME LISTENING")
            self.mic_button.configure(text="MIC PAUSED")
        else:
            self.pause_event.clear()
            self._set_microphone("READY")
            self._set_status("LISTENING", "Waiting for your voice")
            self.pause_button.configure(text="PAUSE LISTENING")
            self.mic_button.configure(text="MIC ON")

    def close(self):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        self.post_event("status", ("OFFLINE", "Jarvis is shutting down"))
        self.root.after(100, self.root.destroy)

    def run(self):
        self.root.mainloop()

    def ask_input(self, prompt):
        was_paused = self.pause_event.is_set()
        self.pause_event.set()
        self.post_event("status", ("AWAITING_APPROVAL", "Review the requested action"))
        request = {"prompt": prompt, "ready": threading.Event(), "value": None}
        self.post_event("input_request", request)
        if not request["ready"].wait(timeout=600):
            if not was_paused:
                self.pause_event.clear()
            return ""
        if not was_paused:
            self.pause_event.clear()
            self.post_event("status", ("PROCESSING", "Continuing the approved task"))
        return request["value"] or ""

    def _poll_events(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "status":
                    self._set_status(*value)
                elif event == "microphone":
                    self._set_microphone(value)
                elif event == "ai_state":
                    self._set_ai_state(value)
                elif event == "user":
                    self._append_transcript("user", value)
                elif event == "assistant":
                    self._append_transcript("assistant", value)
                elif event == "notice":
                    self._append_transcript("notice", value)
                elif event == "input_request":
                    result = simpledialog.askstring("Jarvis approval", value["prompt"], parent=self.root)
                    value["value"] = result
                    value["ready"].set()
        except queue.Empty:
            pass
        if self.stop_event.is_set():
            if self.root.winfo_exists():
                self.root.destroy()
            return
        if self.root.winfo_exists():
            self.root.after(100, self._poll_events)

    def _append_transcript(self, role, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.messages.append((role, message, timestamp))
        self.activity_entries.append((role.upper(), message, timestamp))
        self._render_active_view()

    def _render_active_view(self):
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        if self.active_view == "conversation":
            entries = self.messages
            for role, message, timestamp in entries:
                label = {"user": "YOU", "assistant": "JARVIS", "notice": "SYSTEM"}.get(role, role.upper())
                tag = role if role in {"user", "assistant", "notice"} else "activity"
                self.transcript.insert("end", f"{label}  /  {timestamp}\n", tag)
                self.transcript.insert("end", f"{message}\n\n", "body")
        else:
            for label, message, timestamp in self.activity_entries:
                self.transcript.insert("end", f"{timestamp}  /  {label}\n", "activity")
                self.transcript.insert("end", f"{message}\n\n", "body")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def show_view(self, view):
        self.active_view = view
        for name, button in self.view_buttons.items():
            button.configure(fg=self.COLORS["cyan"] if name == view else self.COLORS["muted"])
        self._render_active_view()

    def _navigate(self, view):
        if view == "voice":
            self.toggle_pause()
        elif view in {"conversation", "activity"}:
            self.show_view(view)

    def _set_ai_state(self, enabled):
        self.ai_key_configured = bool(enabled)
        if self.ai_key_configured:
            self.ai_badge.configure(text="AI / KEY CONFIGURED", fg=self.COLORS["violet"])
        else:
            self.ai_badge.configure(text="AI / LOCAL MODE", fg=self.COLORS["dim"])

    def _set_microphone(self, state):
        self.microphone_state = state
        state_colors = {
            "LISTENING": self.COLORS["cyan"],
            "READY": self.COLORS["mint"],
            "CALIBRATING": self.COLORS["amber"],
            "PAUSED": self.COLORS["muted"],
            "ERROR": self.COLORS["red"],
        }
        color = state_colors.get(state, self.COLORS["dim"])
        self.mic_button.configure(text=f"MIC {state}", fg=color)

    def _set_status(self, status, detail):
        old_status = self.status
        self.status = status
        self.status_detail = detail
        status_colors = {
            "LISTENING": self.COLORS["cyan"],
            "PROCESSING": self.COLORS["violet"],
            "EXECUTING": self.COLORS["ice"],
            "SPEAKING": self.COLORS["ice"],
            "AWAITING_APPROVAL": self.COLORS["amber"],
            "CALIBRATING": self.COLORS["amber"],
            "PAUSED": self.COLORS["muted"],
            "ERROR": self.COLORS["red"],
            "OFFLINE": self.COLORS["dim"],
        }
        color = status_colors.get(status, self.COLORS["ice"])
        self.status_pill.configure(text=status.replace("_", " "), fg=color)
        titles = {
            "LISTENING": "Listening for commands",
            "PROCESSING": "Analyzing request",
            "EXECUTING": "Executing approved action",
            "SPEAKING": "Responding",
            "AWAITING_APPROVAL": "Approval required",
            "CALIBRATING": "Calibrating microphone",
            "PAUSED": "Voice channel paused",
            "ERROR": "System needs attention",
            "OFFLINE": "Assistant offline",
        }
        self.voice_title.configure(text=titles.get(status, "Initializing system"))
        self.voice_detail.configure(text=detail)
        if old_status != status and hasattr(self, "activity_entries"):
            self.activity_entries.append(("STATE", f"{status.replace('_', ' ')} / {detail}", datetime.now().strftime("%H:%M:%S")))
            if self.active_view == "activity":
                self._render_active_view()

    def _update_clock(self):
        if not self.root.winfo_exists():
            return
        now = datetime.now()
        uptime = int(time.monotonic() - self.started_at)
        minutes, seconds = divmod(uptime, 60)
        hours, minutes = divmod(minutes, 60)
        self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        self.uptime_label.configure(text=f"UP {hours:02d}:{minutes:02d}:{seconds:02d}")
        self.root.after(500, self._update_clock)

    def _toggle_motion(self):
        self.motion_enabled = not self.motion_enabled
        self.motion_button.configure(text="MOTION ON" if self.motion_enabled else "MOTION OFF")
        if self.motion_enabled:
            self.root.after(100, self._animate)

    def _animate(self):
        if not self.root.winfo_exists():
            return
        if self.root.state() == "iconic":
            self.root.after(1200, self._animate)
            return
        self.animation_step += 1
        self._draw_core()
        if self.motion_enabled:
            self.root.after(100, self._animate)

    def _draw_core(self):
        canvas = self.orb
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 300)
        canvas.delete("all")
        colors = self.COLORS
        state_colors = {
            "LISTENING": colors["cyan"],
            "PROCESSING": colors["violet"],
            "EXECUTING": colors["ice"],
            "SPEAKING": colors["ice"],
            "AWAITING_APPROVAL": colors["amber"],
            "CALIBRATING": colors["amber"],
            "ERROR": colors["red"],
        }
        accent = state_colors.get(self.status, colors["dim"])
        cx, cy = width / 2, height / 2
        radius = min(width, height) * 0.37
        pulse_rate = 4 if self.status == "PROCESSING" else 2
        pulse = (math.sin(self.animation_step / 8 * pulse_rate) + 1) / 2

        for x in range(0, width, 32):
            canvas.create_line(x, 0, x, height, fill="#080d14", width=1)
        for y in range(0, height, 32):
            canvas.create_line(0, y, width, y, fill="#080d14", width=1)

        for inset, color in ((0, colors["border"]), (12, "#111c2b"), (26, "#0e1a28")):
            ring = radius - inset
            canvas.create_oval(cx - ring, cy - ring, cx + ring, cy + ring, outline=color, width=1)

        for angle in range(0, 360, 15):
            radians = math.radians(angle)
            inner = radius - (11 if angle % 45 == 0 else 5)
            outer = radius + 1
            canvas.create_line(
                cx + math.cos(radians) * inner,
                cy + math.sin(radians) * inner,
                cx + math.cos(radians) * outer,
                cy + math.sin(radians) * outer,
                fill=accent if angle % 45 == 0 else colors["border"],
                width=1,
            )

        rotation = self.animation_step * (2 if self.status == "LISTENING" else 0.8)
        for orbit_index, orbit_color, squash in ((0, colors["cyan"], 0.46), (1, colors["violet"], 0.64)):
            orbit_angle = math.radians(rotation + orbit_index * 70)
            points = []
            for step in range(41):
                angle = (step / 40) * math.tau
                ox = math.cos(angle) * radius * 0.82
                oy = math.sin(angle) * radius * squash
                rx = ox * math.cos(orbit_angle) - oy * math.sin(orbit_angle)
                ry = ox * math.sin(orbit_angle) + oy * math.cos(orbit_angle)
                points.extend((cx + rx, cy + ry))
            canvas.create_line(*points, fill=orbit_color, width=1, smooth=True, splinesteps=24)
            particle_angle = math.radians((rotation * 2 + orbit_index * 115) % 360)
            px = cx + math.cos(particle_angle) * radius * 0.82
            py = cy + math.sin(particle_angle) * radius * squash
            canvas.create_oval(px - 3, py - 3, px + 3, py + 3, fill=orbit_color, outline="")

        glow = 50 + pulse * (12 if self.status in {"LISTENING", "SPEAKING", "PROCESSING"} else 4)
        canvas.create_oval(cx - glow - 12, cy - glow - 12, cx + glow + 12, cy + glow + 12, outline="#0d2938", width=2)
        canvas.create_oval(cx - glow, cy - glow, cx + glow, cy + glow, fill="#081622", outline=accent, width=2)
        canvas.create_oval(cx - glow * 0.62, cy - glow * 0.62, cx + glow * 0.62, cy + glow * 0.62, fill="#0a1b2a", outline=colors["ice"], width=1)
        canvas.create_text(cx, cy - 5, text="J", fill=colors["text"], font=("Bahnschrift SemiBold", 34))
        canvas.create_text(cx, cy + 34, text=self.status.replace("_", " "), fill=accent, font=("Bahnschrift SemiBold", 7))
        self._draw_levels(pulse)

    def _draw_levels(self, pulse):
        self.levels.delete("all")
        active = self.status in {"LISTENING", "SPEAKING", "PROCESSING", "EXECUTING"}
        bar_count = 31
        bar_width = 4
        gap = 3
        full_width = bar_count * (bar_width + gap) - gap
        start_x = (240 - full_width) / 2
        for index in range(bar_count):
            envelope = 1 - abs(index - (bar_count - 1) / 2) / (bar_count / 2)
            wave = (math.sin(index * 0.8 + self.animation_step / 3) + 1) / 2
            height = 3 + envelope * (7 + wave * 12) * (0.4 + pulse * 0.6 if active else 0.15)
            color = self.COLORS["cyan"] if active else self.COLORS["border"]
            x = start_x + index * (bar_width + gap)
            self.levels.create_line(x, 17 - height, x, 17 + height, fill=color, width=bar_width, capstyle="round")