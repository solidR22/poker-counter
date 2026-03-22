"""
公共类型定义。
"""

from __future__ import annotations

import tkinter as tk
from enum import Enum
from typing import Any, TypeVar

import numpy as np


class Card(Enum):
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    J = "J"
    Q = "Q"
    K = "K"
    A = "A"
    TWO = "2"
    JOKER = "JOKER"


class Mark(Enum):
    PASS = "PASS"
    LANDLORD = "boss"
    GAME_OVER = "gameover"


class RegionState(Enum):
    WAIT = 0
    ACTIVE = 1
    PASS = 2


class Player(Enum):
    LEFT = "上家"
    MIDDLE = "自己"
    RIGHT = "下家"


class WindowsType(Enum):
    MAIN = "主记牌窗"
    LEFT = "上家统计窗"
    RIGHT = "下家统计窗"


AnyEnum = TypeVar("AnyEnum", bound=Enum)

RGB = tuple[int, int, int]
AnyImage = np.ndarray[Any, np.dtype[np.uint8]]
GrayscaleImage = np.ndarray[tuple[int, int], np.dtype[np.uint8]]
Confidence = float
Location = tuple[int, int]
MatchResult = tuple[Confidence, Location]
CardIntDict = dict[Card, int]
CardIntVarDict = dict[Card, tk.IntVar]
CardStrDict = dict[Card, str]
CardStrVarDict = dict[Card, tk.StringVar]
EnumTemplateDict = dict[AnyEnum, AnyImage]
ConfigDict = dict[str, Any]
