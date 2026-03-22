from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from misc.custom_types import Card, WindowsType
from models.config import GUI
from models.counters import CardCounter
from models.labels import LabelProperties


class CounterPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=8)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self._build_summary()
        self._build_remaining_grid()
        self._build_played_grids()
        self._build_hand_text()

    def _build_summary(self) -> None:
        counter = CardCounter()
        summary = ttk.Frame(self)
        summary.grid(row=0, column=0, columnspan=2, sticky="ew")
        for column in range(3):
            summary.columnconfigure(column, weight=1)

        self._build_stat(summary, 0, "上家剩余", counter.player1_remaining_var)
        self._build_stat(summary, 1, "我的剩余", counter.player2_remaining_var)
        self._build_stat(summary, 2, "下家剩余", counter.player3_remaining_var)

    def _build_stat(
        self,
        parent: ttk.Frame,
        column: int,
        title: str,
        variable: tk.Variable,
    ) -> None:
        card = ttk.Frame(parent, padding=(0, 0, 6 if column < 2 else 0, 0))
        card.grid(row=0, column=column, sticky="ew")
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=title).grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=variable, font=("Microsoft YaHei UI", 16, "bold")).grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )

    def _build_remaining_grid(self) -> None:
        card = ttk.LabelFrame(self, text="全场剩余", padding=8)
        card.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        card.columnconfigure(0, weight=1)
        CounterGrid(card, WindowsType.MAIN).grid(row=0, column=0, sticky="ew")

    def _build_played_grids(self) -> None:
        left_card = ttk.LabelFrame(self, text="上家已出", padding=8)
        left_card.grid(row=2, column=0, sticky="ew", pady=(8, 0), padx=(0, 4))
        left_card.columnconfigure(0, weight=1)
        CounterGrid(left_card, WindowsType.LEFT).grid(row=0, column=0, sticky="ew")

        right_card = ttk.LabelFrame(self, text="下家已出", padding=8)
        right_card.grid(row=2, column=1, sticky="ew", pady=(8, 0), padx=(4, 0))
        right_card.columnconfigure(0, weight=1)
        CounterGrid(right_card, WindowsType.RIGHT).grid(row=0, column=0, sticky="ew")

    def _build_hand_text(self) -> None:
        hand_card = ttk.LabelFrame(self, text="当前手牌识别", padding=8)
        hand_card.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        hand_card.columnconfigure(0, weight=1)
        ttk.Label(
            hand_card,
            textvariable=CardCounter().my_cards_text_var,
            justify="left",
            wraplength=520,
        ).grid(row=0, column=0, sticky="w")


class CounterGrid(ttk.Frame):
    def __init__(self, parent: tk.Misc, window_type: WindowsType) -> None:
        super().__init__(parent)
        self.window_type = window_type
        self._card_labels: dict[Card, tk.Label] = {}
        self._count_labels: dict[Card, tk.Label] = {}
        self._build()
        self._bind_label_style()

    def _build(self) -> None:
        counter = CardCounter()
        table = ttk.Frame(self)
        table.grid(row=0, column=0, sticky="nsew")

        get_count: dict[WindowsType, Callable[[Card], tk.Variable]] = {
            WindowsType.MAIN: lambda card: counter.remaining_counter[card],
            WindowsType.LEFT: lambda card: counter.player1_counter[card],
            WindowsType.RIGHT: lambda card: counter.player3_counter[card],
        }
        default_font_size = 17 if self.window_type == WindowsType.MAIN else 12
        font_size = int(GUI.get(self.window_type.name, {}).get("FONT_SIZE", default_font_size))

        for idx, card in enumerate(Card):
            label_text = "王" if card is Card.JOKER else card.value
            card_label = self._create_label(
                table,
                text=label_text,
                font=("Microsoft YaHei UI", font_size),
                bg="#dbeafe",
                fg="black",
            )
            count_label = self._create_label(
                table,
                textvariable=get_count[self.window_type](card),
                font=("Microsoft YaHei UI", font_size, "bold"),
                bg="#fef3c7",
                fg="black",
            )
            card_label.grid(row=0, column=idx, sticky="nsew")
            count_label.grid(row=1, column=idx, sticky="nsew")
            table.grid_columnconfigure(idx, weight=1)
            self._card_labels[card] = card_label
            self._count_labels[card] = count_label

        table.grid_rowconfigure(0, weight=1)
        table.grid_rowconfigure(1, weight=1)

    def _create_label(self, parent: tk.Misc, **kwargs: object) -> tk.Label:
        return tk.Label(
            parent,
            anchor="center",
            relief="solid",
            borderwidth=1,
            width=2,
            padx=3,
            pady=2,
            **kwargs,
        )

    def _bind_label_style(self) -> None:
        label_properties = LabelProperties()
        binding_labels = (
            self._card_labels if self.window_type is WindowsType.MAIN else self._count_labels
        )
        for card, label in binding_labels.items():
            label_properties.text_color.bind_callback(
                self.window_type,
                card,
                lambda style, label=label: label.config(fg=style),
            )
