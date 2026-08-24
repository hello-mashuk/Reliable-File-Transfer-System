"""
gui.py
======
A clean, modern-looking Tkinter desktop GUI for the Reliable File
Transfer System. One window, two tabs (Sender / Receiver). Tkinter is
part of the Python standard library, so this runs on both computers
with zero extra installs (see README if `python3-tk` needs installing
on Linux).

All the actual networking/encoding work happens in sender.py and
receiver.py -- this file is purely presentation + thread orchestration
so the UI never freezes while a transfer is in progress.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from sender import send_file
from receiver import start_server
from utils import validate_ip, validate_port, get_local_ip

# ---------------------------------------------------------------------------
# Color palette -- a dark, "cool lab console" theme
# ---------------------------------------------------------------------------
BG_DARK = "#0f172a"        # slate-900
BG_PANEL = "#1e293b"       # slate-800
BG_INPUT = "#334155"       # slate-700
ACCENT = "#38bdf8"         # sky-400
ACCENT_2 = "#22d3ee"       # cyan-400
SUCCESS = "#4ade80"        # green-400
DANGER = "#f87171"         # red-400
WARNING = "#facc15"        # yellow-400
TEXT_PRIMARY = "#e2e8f0"   # slate-200
TEXT_MUTED = "#94a3b8"     # slate-400
FONT_MONO = ("Consolas", 10)
FONT_UI = ("Segoe UI", 10)
FONT_HEADING = ("Segoe UI", 16, "bold")


class ConsoleLog(tk.Text):
    """A styled, read-only, auto-scrolling log console with colored tags."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            bg="#020617",
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            font=FONT_MONO,
            relief="flat",
            padx=10,
            pady=8,
            wrap="word",
            state="disabled",
            **kwargs,
        )
        self.tag_configure("info", foreground=TEXT_PRIMARY)
        self.tag_configure("success", foreground=SUCCESS)
        self.tag_configure("error", foreground=DANGER)
        self.tag_configure("warn", foreground=WARNING)
        self.tag_configure("accent", foreground=ACCENT_2)

    def write(self, message: str):
        tag = "info"
        low = message.lower()
        if any(k in message for k in ("\u2713", "VERIFIED", "SUCCESS", "completed successfully")):
            tag = "success"
        elif any(k in message for k in ("\u2717", "MISMATCH", "error", "Error", "failed", "Failed")):
            tag = "error"
        elif "warning" in low:
            tag = "warn"
        elif message.startswith(("Connecting", "Sending", "Receiving", "Applying", "Processing")):
            tag = "accent"

        self.configure(state="normal")
        self.insert("end", message + "\n", tag)
        self.configure(state="disabled")
        self.see("end")

    def clear(self):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")


def styled_entry(parent, textvariable=None, show=None, width=None):
    e = tk.Entry(
        parent,
        textvariable=textvariable,
        show=show,
        width=width,
        bg=BG_INPUT,
        fg=TEXT_PRIMARY,
        insertbackground=TEXT_PRIMARY,
        relief="flat",
        font=FONT_UI,
    )
    return e


def styled_label(parent, text, muted=False, heading=False):
    return tk.Label(
        parent,
        text=text,
        bg=parent["bg"] if "bg" in parent.keys() else BG_PANEL,
        fg=TEXT_MUTED if muted else TEXT_PRIMARY,
        font=FONT_HEADING if heading else FONT_UI,
    )


def accent_button(parent, text, command, danger=False):
    color = DANGER if danger else ACCENT
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=color,
        fg="#020617",
        activebackground=ACCENT_2 if not danger else "#fca5a5",
        activeforeground="#020617",
        relief="flat",
        font=(FONT_UI[0], 10, "bold"),
        padx=14,
        pady=6,
        cursor="hand2",
        bd=0,
    )
    return btn


# ---------------------------------------------------------------------------
# Sender Tab
# ---------------------------------------------------------------------------
class SenderTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_DARK)
        self.log_queue = queue.Queue()
        self.worker_thread = None

        self._build_ui()
        self.after(80, self._poll_log_queue)

    def _build_ui(self):
        pad = {"padx": 16, "pady": 6}

        header = styled_label(self, "\U0001F4E4  Sender", heading=True)
        header.configure(bg=BG_DARK)
        header.grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 4))

        sub = styled_label(self, "Encode a file with Hamming(7,4) and transmit it over TCP.", muted=True)
        sub.configure(bg=BG_DARK)
        sub.grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 14))

        form = tk.Frame(self, bg=BG_PANEL)
        form.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=6)
        form.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Receiver IP
        tk.Label(form, text="Receiver IP", bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_UI)\
            .grid(row=0, column=0, sticky="w", **pad)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        styled_entry(form, self.ip_var).grid(row=0, column=1, sticky="ew", **pad)

        # Port
        tk.Label(form, text="Port", bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_UI)\
            .grid(row=1, column=0, sticky="w", **pad)
        self.port_var = tk.StringVar(value="5001")
        styled_entry(form, self.port_var).grid(row=1, column=1, sticky="ew", **pad)

        # File path
        tk.Label(form, text="File", bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_UI)\
            .grid(row=2, column=0, sticky="w", **pad)
        file_row = tk.Frame(form, bg=BG_PANEL)
        file_row.grid(row=2, column=1, sticky="ew", **pad)
        file_row.grid_columnconfigure(0, weight=1)
        self.file_var = tk.StringVar(value="")
        styled_entry(file_row, self.file_var).grid(row=0, column=0, sticky="ew")
        tk.Button(
            file_row, text="Browse...", command=self._browse_file,
            bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat", font=FONT_UI, cursor="hand2",
        ).grid(row=0, column=1, padx=(8, 0))

        # Error simulation
        self.error_enabled_var = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(
            form, text="Simulate transmission errors", variable=self.error_enabled_var,
            bg=BG_PANEL, fg=TEXT_PRIMARY, selectcolor=BG_INPUT, activebackground=BG_PANEL,
            activeforeground=TEXT_PRIMARY, font=FONT_UI, command=self._toggle_error_controls,
        )
        chk.grid(row=3, column=0, columnspan=2, sticky="w", padx=16, pady=(10, 0))

        tk.Label(form, text="Error rate (%)", bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_UI)\
            .grid(row=4, column=0, sticky="w", **pad)
        self.error_pct_var = tk.StringVar(value="1.0")
        self.error_pct_entry = styled_entry(form, self.error_pct_var)
        self.error_pct_entry.grid(row=4, column=1, sticky="w", **pad)

        tk.Label(form, text="Random seed (optional)", bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_UI)\
            .grid(row=5, column=0, sticky="w", **pad)
        self.seed_var = tk.StringVar(value="")
        self.seed_entry = styled_entry(form, self.seed_var)
        self.seed_entry.grid(row=5, column=1, sticky="w", **pad)

        self._toggle_error_controls()

        # Send button + progress bar
        action_row = tk.Frame(self, bg=BG_DARK)
        action_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=16, pady=(12, 4))
        action_row.grid_columnconfigure(1, weight=1)

        self.send_btn = accent_button(action_row, "\u25B6  Send File", self._on_send_clicked)
        self.send_btn.grid(row=0, column=0, sticky="w")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Sky.Horizontal.TProgressbar", troughcolor=BG_PANEL,
                         background=ACCENT, bordercolor=BG_PANEL, lightcolor=ACCENT, darkcolor=ACCENT)
        self.progress = ttk.Progressbar(action_row, mode="indeterminate", style="Sky.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=1, sticky="ew", padx=(16, 0))

        # Log console
        log_label = styled_label(self, "Activity Log", muted=True)
        log_label.configure(bg=BG_DARK)
        log_label.grid(row=4, column=0, sticky="w", padx=16, pady=(14, 2))

        self.console = ConsoleLog(self, height=14)
        self.console.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=16, pady=(0, 16))
        self.grid_rowconfigure(5, weight=1)

    def _toggle_error_controls(self):
        state = "normal" if self.error_enabled_var.get() else "disabled"
        self.error_pct_entry.configure(state=state)
        self.seed_entry.configure(state=state)

    def _browse_file(self):
        path = filedialog.askopenfilename(title="Select a file to send")
        if path:
            self.file_var.set(path)

    def _on_send_clicked(self):
        ip = self.ip_var.get().strip()
        port_str = self.port_var.get().strip()
        filepath = self.file_var.get().strip()

        if not validate_ip(ip):
            messagebox.showerror("Invalid IP", f"'{ip}' is not a valid IPv4 address.")
            return
        if not validate_port(port_str):
            messagebox.showerror("Invalid Port", "Port must be a number between 1 and 65535.")
            return
        if not filepath or not os.path.isfile(filepath):
            messagebox.showerror("File Not Found", "Please choose a valid file to send.")
            return

        error_enabled = self.error_enabled_var.get()
        error_prob = 0.0
        seed = None
        if error_enabled:
            try:
                error_prob = float(self.error_pct_var.get()) / 100.0
                if not (0.0 <= error_prob <= 1.0):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Error Rate", "Error rate must be a number between 0 and 100.")
                return
            seed_text = self.seed_var.get().strip()
            if seed_text:
                try:
                    seed = int(seed_text)
                except ValueError:
                    messagebox.showerror("Invalid Seed", "Random seed must be an integer.")
                    return

        self.console.clear()
        self.send_btn.configure(state="disabled", text="Sending...")
        self.progress.start(12)

        def log_cb(msg):
            self.log_queue.put(msg)

        def worker():
            try:
                send_file(
                    ip=ip, port=int(port_str), filepath=filepath,
                    error_enabled=error_enabled, error_probability=error_prob,
                    seed=seed, log=log_cb,
                )
            except Exception as exc:  # noqa: BLE001 -- report any failure to the UI
                log_cb(f"Error: {exc}")
            finally:
                self.log_queue.put("__DONE__")

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg == "__DONE__":
                    self.send_btn.configure(state="normal", text="\u25B6  Send File")
                    self.progress.stop()
                else:
                    self.console.write(msg)
        except queue.Empty:
            pass
        self.after(80, self._poll_log_queue)


# ---------------------------------------------------------------------------
# Receiver Tab
# ---------------------------------------------------------------------------
class ReceiverTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_DARK)
        self.log_queue = queue.Queue()
        self.worker_thread = None
        self._stop_flag = threading.Event()
        self._server_running = False

        self._build_ui()
        self.after(80, self._poll_log_queue)

    def _build_ui(self):
        pad = {"padx": 16, "pady": 6}

        header = styled_label(self, "\U0001F4E5  Receiver", heading=True)
        header.configure(bg=BG_DARK)
        header.grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 4))

        sub = styled_label(
            self, f"This machine's LAN IP: {get_local_ip()}  (share this with the sender)", muted=True
        )
        sub.configure(bg=BG_DARK)
        sub.grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 14))

        form = tk.Frame(self, bg=BG_PANEL)
        form.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=6)
        form.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tk.Label(form, text="Listen Port", bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_UI)\
            .grid(row=0, column=0, sticky="w", **pad)
        self.port_var = tk.StringVar(value="5001")
        styled_entry(form, self.port_var, width=10).grid(row=0, column=1, sticky="w", **pad)

        tk.Label(form, text="Save Folder", bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_UI)\
            .grid(row=1, column=0, sticky="w", **pad)
        self.save_dir_var = tk.StringVar(value="received_files")
        styled_entry(form, self.save_dir_var).grid(row=1, column=1, sticky="ew", **pad)

        action_row = tk.Frame(self, bg=BG_DARK)
        action_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=16, pady=(12, 4))
        action_row.grid_columnconfigure(2, weight=1)

        self.start_btn = accent_button(action_row, "\u25B6  Start Listening", self._on_start_clicked)
        self.start_btn.grid(row=0, column=0, sticky="w")

        self.stop_btn = accent_button(action_row, "\u25A0  Stop", self._on_stop_clicked, danger=True)
        self.stop_btn.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.stop_btn.configure(state="disabled")

        self.progress = ttk.Progressbar(action_row, mode="indeterminate", style="Sky.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=2, sticky="ew", padx=(16, 0))

        log_label = styled_label(self, "Activity Log", muted=True)
        log_label.configure(bg=BG_DARK)
        log_label.grid(row=4, column=0, sticky="w", padx=16, pady=(14, 2))

        self.console = ConsoleLog(self, height=14)
        self.console.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=16, pady=(0, 16))
        self.grid_rowconfigure(5, weight=1)

    def _on_start_clicked(self):
        port_str = self.port_var.get().strip()
        if not validate_port(port_str):
            messagebox.showerror("Invalid Port", "Port must be a number between 1 and 65535.")
            return
        save_dir = self.save_dir_var.get().strip() or "received_files"

        self.console.clear()
        self._stop_flag.clear()
        self._server_running = True
        self.start_btn.configure(state="disabled", text="Listening...")
        self.stop_btn.configure(state="normal")
        self.progress.start(12)

        def log_cb(msg):
            self.log_queue.put(msg)

        def worker():
            try:
                start_server(
                    port=int(port_str), save_dir=save_dir,
                    log=log_cb, stop_check=lambda: self._stop_flag.is_set(),
                )
            except Exception as exc:  # noqa: BLE001
                log_cb(f"Error: {exc}")
            finally:
                self.log_queue.put("__DONE__")

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _on_stop_clicked(self):
        self._stop_flag.set()

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg == "__DONE__":
                    self._server_running = False
                    self.start_btn.configure(state="normal", text="\u25B6  Start Listening")
                    self.stop_btn.configure(state="disabled")
                    self.progress.stop()
                else:
                    self.console.write(msg)
        except queue.Empty:
            pass
        self.after(80, self._poll_log_queue)


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reliable File Transfer \u2014 Hamming(7,4) Lab")
        self.geometry("760x640")
        self.minsize(680, 560)
        self.configure(bg=BG_DARK)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TNotebook", background=BG_DARK, borderwidth=0
        )
        style.configure(
            "TNotebook.Tab", background=BG_PANEL, foreground=TEXT_MUTED,
            padding=(18, 10), font=(FONT_UI[0], 10, "bold"), borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", BG_DARK)],
            foreground=[("selected", ACCENT)],
        )

        title_bar = tk.Frame(self, bg=BG_DARK)
        title_bar.pack(fill="x", padx=16, pady=(14, 0))
        tk.Label(
            title_bar, text="\U0001F6F0  Reliable File Transfer System",
            bg=BG_DARK, fg=TEXT_PRIMARY, font=(FONT_UI[0], 15, "bold"),
        ).pack(side="left")
        tk.Label(
            title_bar, text="Hamming(7,4) Error Detection & Correction",
            bg=BG_DARK, fg=ACCENT, font=(FONT_UI[0], 10),
        ).pack(side="left", padx=(10, 0))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        sender_tab = SenderTab(notebook)
        receiver_tab = ReceiverTab(notebook)
        notebook.add(sender_tab, text="  \U0001F4E4  Sender  ")
        notebook.add(receiver_tab, text="  \U0001F4E5  Receiver  ")


if __name__ == "__main__":
    app = App()
    app.mainloop()
