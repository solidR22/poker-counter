from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from functions.windows_offset import calculate_offset
from misc.custom_types import ConfigDict
from models.config import GUI, HOTKEYS, save_gui_window_position

from .counter_panel import CounterPanel


class CounterDisplayWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.parent = parent
        self._save_after_id: str | None = None

        self._build_ui()
        self._setup_window_style()
        self.refresh_position()
        self._setup_binding()

    def _build_ui(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        CounterPanel(container).grid(row=0, column=0, sticky="nsew")

    def _setup_window_style(self) -> None:
        self.title("记牌窗口")
        self.attributes("-topmost", True)  # type: ignore[attr-defined]
        self.minsize(640, 240)

    def refresh_position(self) -> None:
        self._setup_window_position(GUI.get("MAIN", {}))

    def apply_runtime_config(self) -> None:
        current_x = self.winfo_x()
        current_y = self.winfo_y()
        self._build_ui()
        self.update_idletasks()
        self.geometry(f"+{current_x}+{current_y}")

    def _setup_window_position(self, config: ConfigDict) -> None:
        self.update_idletasks()
        x_offset, y_offset = calculate_offset(
            self.winfo_width(),
            self.winfo_height(),
            config.get("OFFSET_X"),
            config.get("OFFSET_Y"),
            config.get("CENTER_X"),
            config.get("CENTER_Y"),
        )
        self.geometry(f"+{x_offset}+{y_offset}")

    def _setup_binding(self) -> None:
        self.bind("<Configure>", self._on_configure)  # type: ignore[override]
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        for hotkey, action in {
            "QUIT": lambda event: self.parent.destroy(),
            "OPEN_SETTINGS": lambda event: self.parent.show_settings(),
        }.items():
            if hotkey in HOTKEYS:
                self.bind(f"<KeyPress-{HOTKEYS[hotkey]}>", action)

    def _on_configure(self, event: tk.Event) -> None:  # type: ignore[override]
        if event.widget is not self or self.state() != "normal":
            return
        if self._save_after_id:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(200, self._save_position)

    def _save_position(self) -> None:
        self._save_after_id = None
        save_gui_window_position("MAIN", self.winfo_x(), self.winfo_y())

    def _on_close(self) -> None:
        self.parent._close_counter_window()
