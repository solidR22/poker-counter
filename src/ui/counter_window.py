"""
记牌浮窗。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from loguru import logger

from core.backend_thread import BackendThread
from functions.windows_offset import calculate_offset
from misc.custom_types import Card, ConfigDict, WindowsType
from misc.open_file import open_latest_log
from models.config import GUI, HOTKEYS, save_gui_window_position
from models.counters import CardCounter
from models.labels import LabelProperties


class CounterWindow(tk.Toplevel):
    def __init__(self, window_type: WindowsType, parent: tk.Tk) -> None:
        super().__init__(parent) if parent else super().__init__()
        self.PARENT = parent
        self.WINDOW_TYPE = window_type
        config = GUI.get(self.WINDOW_TYPE.name, {})

        self._create_table()
        self._bind_label_style()
        self._setup_window_style(config)
        self._setup_window_position(config)
        self._setup_binding()
        logger.success("{}已创建", window_type.value)

    def _setup_window_style(self, config: ConfigDict) -> None:
        self.title(f"斗地主记牌器 - {self.WINDOW_TYPE.value}")
        self.attributes("-topmost", True)  # type: ignore[attr-defined]
        self.overrideredirect(True)
        self.configure(bg="white")
        self.attributes("-transparentcolor", "white")  # type: ignore[attr-defined]
        self.attributes("-alpha", config.get("OPACITY", 1))  # type: ignore[attr-defined]

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

    def refresh_position(self) -> None:
        self._setup_window_position(GUI.get(self.WINDOW_TYPE.name, {}))

    def _setup_binding(self) -> None:
        self.bind("<Button-1>", self._on_drag_start)  # type: ignore[override]
        self.bind("<B1-Motion>", self._on_drag_move)  # type: ignore[override]
        self.bind("<ButtonRelease-1>", self._on_drag_end)  # type: ignore[override]
        hotkey_dict: dict[str, Callable[[Any], None]] = {
            "QUIT": lambda event: self.PARENT.destroy(),
            "OPEN_LOG": lambda event: open_latest_log(),
            "OPEN_SETTINGS": lambda event: self.PARENT.show_settings(),
            "RESET": lambda event: self._reset(),
        }
        for hotkey, callback in hotkey_dict.items():
            if hotkey in HOTKEYS:
                try:
                    self.bind(f"<KeyPress-{HOTKEYS[hotkey]}>", callback)
                except Exception:
                    logger.error("快捷键绑定失败：{} -> {}", hotkey, HOTKEYS[hotkey])

    def _create_table(self) -> None:
        counter = CardCounter()
        if self.WINDOW_TYPE == WindowsType.MAIN:
            summary = ttk.Frame(self)
            summary.pack(fill="x")
            ttk.Label(summary, text="我的剩余牌数：").pack(side="left", padx=(2, 4))
            ttk.Label(summary, textvariable=counter.player2_remaining_var).pack(side="left")
            hand = ttk.Frame(self)
            hand.pack(fill="x")
            ttk.Label(hand, textvariable=counter.my_cards_text_var, wraplength=420, justify="left").pack(side="left", padx=(2, 4))
        elif self.WINDOW_TYPE == WindowsType.LEFT:
            summary = ttk.Frame(self)
            summary.pack(fill="x")
            ttk.Label(summary, text="上家剩余：").pack(side="left", padx=(2, 4))
            ttk.Label(summary, textvariable=counter.player1_remaining_var).pack(side="left")
        elif self.WINDOW_TYPE == WindowsType.RIGHT:
            summary = ttk.Frame(self)
            summary.pack(fill="x")
            ttk.Label(summary, text="下家剩余：").pack(side="left", padx=(2, 4))
            ttk.Label(summary, textvariable=counter.player3_remaining_var).pack(side="left")

        self._table_frame = ttk.Frame(self)
        if self.WINDOW_TYPE == WindowsType.MAIN:
            self._table_frame.pack()
            rows, cols = 2, len(Card)
        else:
            self._table_frame.pack(fill="both", expand=True)
            rows, cols = len(Card), 2

        get_count: dict[WindowsType, Callable[[Card], tk.Variable]] = {
            WindowsType.MAIN: lambda card: counter.remaining_counter[card],
            WindowsType.LEFT: lambda card: counter.player1_counter[card],
            WindowsType.RIGHT: lambda card: counter.player3_counter[card],
        }
        get_count_text = get_count[self.WINDOW_TYPE]
        self._card_labels: dict[Card, tk.Label] = {}
        self._count_labels: dict[Card, tk.Label] = {}
        font_size = GUI.get(self.WINDOW_TYPE.name, {}).get("FONT_SIZE", 25)

        def create_label(**kwargs: Any) -> tk.Label:
            return tk.Label(self._table_frame, anchor="center", relief="solid", highlightbackground="red", highlightthickness=1, width=2, **kwargs)

        for idx, card in enumerate(Card):
            label_text = "王" if card is Card.JOKER else card.value
            card_label = create_label(text=label_text, font=("Microsoft YaHei UI", font_size), bg="lightblue", fg="black")
            count_label = create_label(textvariable=get_count_text(card), font=("Microsoft YaHei UI", font_size, "bold"), bg="lightyellow", fg="black")
            if self.WINDOW_TYPE == WindowsType.MAIN:
                card_label.grid(row=0, column=idx, sticky="nsew")
                count_label.grid(row=1, column=idx, sticky="nsew")
            else:
                card_label.grid(row=idx, column=0, sticky="nsew")
                count_label.grid(row=idx, column=1, sticky="nsew")
            self._card_labels[card] = card_label
            self._count_labels[card] = count_label

        for i in range(rows):
            self._table_frame.grid_rowconfigure(i, weight=1)
        for j in range(cols):
            self._table_frame.grid_columnconfigure(j, weight=1)

    def _bind_label_style(self) -> None:
        label_properties = LabelProperties()
        binding_labels = self._count_labels if self.WINDOW_TYPE is not WindowsType.MAIN else self._card_labels
        for card, label in binding_labels.items():
            label_properties.text_color.bind_callback(
                self.WINDOW_TYPE,
                card,
                lambda style, label=label: (label.config(fg=style), None)[1],
            )

    def _on_drag_start(self, event: tk.Event) -> None:  # type: ignore[override]
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_move(self, event: tk.Event) -> None:  # type: ignore[override]
        x = self.winfo_x() + (event.x - self._drag_start_x)
        y = self.winfo_y() + (event.y - self._drag_start_y)
        self.geometry(f"+{x}+{y}")

    def _on_drag_end(self, event: tk.Event) -> None:  # type: ignore[override]
        del event
        save_gui_window_position(self.WINDOW_TYPE.name, self.winfo_x(), self.winfo_y())

    def _reset(self) -> None:
        backend = BackendThread()
        backend.terminate()
        backend.start()
