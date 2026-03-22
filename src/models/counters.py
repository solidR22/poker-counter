"""
记牌计数器。
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

from loguru import logger

from misc.custom_types import Card, CardIntDict, CardIntVarDict, Player
from misc.singleton import singleton


def _create_cardintvar_dict(initial_value: CardIntDict) -> CardIntVarDict:
    return {key: tk.IntVar(value=value) for key, value in initial_value.items()}


def _modify_cardvar_dict(intvar_dict: CardIntVarDict, new_values: CardIntDict) -> None:
    for key, value in new_values.items():
        intvar_dict[key].set(value)


FULL_COUNT = {card: 4 for card in Card}
FULL_COUNT[Card.JOKER] = 2
EMPTY_COUNT = {card: 0 for card in Card}


@singleton
@dataclass
class CardCounter:
    def __post_init__(self) -> None:
        self.remaining_counter = _create_cardintvar_dict(FULL_COUNT)
        self.player1_counter = _create_cardintvar_dict(EMPTY_COUNT)
        self.player3_counter = _create_cardintvar_dict(EMPTY_COUNT)

        self.player1_remaining_var = tk.IntVar(value=17)
        self.player2_remaining_var = tk.IntVar(value=17)
        self.player3_remaining_var = tk.IntVar(value=17)
        self.my_cards_text_var = tk.StringVar(value="手牌识别：暂无")

        self.remaining_count = sum(FULL_COUNT.values())
        self.player1_total = 17
        self.player2_total = 17
        self.player3_total = 17
        self.player1_count = 0
        self.player2_count = 0
        self.player3_count = 0
        self._sync_remaining_vars()
        logger.info("已创建记牌计数器")

    def _sync_remaining_vars(self) -> None:
        self.player1_remaining_var.set(max(0, self.player1_total - self.player1_count))
        self.player2_remaining_var.set(max(0, self.player2_total - self.player2_count))
        self.player3_remaining_var.set(max(0, self.player3_total - self.player3_count))

    def set_totals(self, landlord: Player) -> None:
        self.player1_total = 20 if landlord is Player.LEFT else 17
        self.player2_total = 20 if landlord is Player.MIDDLE else 17
        self.player3_total = 20 if landlord is Player.RIGHT else 17
        self._sync_remaining_vars()

    def set_my_cards_text(self, cards_text: str) -> None:
        self.my_cards_text_var.set(cards_text)

    def reset(self) -> None:
        _modify_cardvar_dict(self.remaining_counter, FULL_COUNT)
        _modify_cardvar_dict(self.player1_counter, EMPTY_COUNT)
        _modify_cardvar_dict(self.player3_counter, EMPTY_COUNT)
        self.remaining_count = sum(FULL_COUNT.values())
        self.player1_total = 17
        self.player2_total = 17
        self.player3_total = 17
        self.player1_count = 0
        self.player2_count = 0
        self.player3_count = 0
        self.my_cards_text_var.set("手牌识别：暂无")
        self._sync_remaining_vars()
        logger.info("已重置记牌计数器")

    def mark(self, card: Card, player: Player) -> None:
        self.remaining_counter[card].set(self.remaining_counter[card].get() - 1)
        match player:
            case Player.LEFT:
                self.player1_counter[card].set(self.player1_counter[card].get() + 1)
                self.player1_count += 1
            case Player.MIDDLE:
                self.player2_count += 1
            case Player.RIGHT:
                self.player3_counter[card].set(self.player3_counter[card].get() + 1)
                self.player3_count += 1
        self.remaining_count -= 1
        self._sync_remaining_vars()
        if self.remaining_counter[card].get() < 0:
            logger.warning("牌 {} 被标记后剩余数量小于 0，可能识别有误", card.value)

    @property
    def player1_remaining(self) -> int:
        return self.player1_remaining_var.get()

    @property
    def player2_remaining(self) -> int:
        return self.player2_remaining_var.get()

    @property
    def player3_remaining(self) -> int:
        return self.player3_remaining_var.get()
