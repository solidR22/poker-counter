"""
配置读取与保存。
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from shutil import copyfile
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "REGIONS": {
        "playing_left": [[499, 440], [1067, 671]],
        "playing_middle": [[722, 591], [1538, 720]],
        "playing_right": [[1176, 437], [1716, 653]],
        "my_cards": [[493, 737], [1723, 965]],
        "avatar_left": [[560, 300], [690, 430]],
        "avatar_middle": [[972, 760], [1110, 900]],
        "avatar_right": [[1510, 300], [1640, 430]],
        "game_over": [[900, 240], [1060, 330]],
    },
    "GAME_WINDOW": {
        "OFFSET_X": 0,
        "OFFSET_Y": 0,
    },
    "THRESHOLDS": {
        "card": 0.95,
        "landlord": 0.95,
        "pass": 0.9,
        "wait": 0.9,
        "gameover": 0.9,
    },
    "SCREENSHOT_INTERVAL": 0.1,
    "GAME_START_INTERVAL": 1.0,
    "GUI": {
        "MAIN": {
            "DISPLAY": True,
            "OPACITY": 1.0,
            "FONT_SIZE": 25,
            "CENTER_X": 700,
            "OFFSET_Y": 0,
        },
        "LEFT": {
            "DISPLAY": True,
            "OPACITY": 0.9,
            "FONT_SIZE": 18,
            "CENTER_X": 205,
            "CENTER_Y": 456,
        },
        "RIGHT": {
            "DISPLAY": True,
            "OPACITY": 0.9,
            "FONT_SIZE": 18,
            "OFFSET_X": 1450,
            "CENTER_Y": 456,
        },
        "SWITCH": {
            "FONT_SIZE": 12,
            "OFFSET_X": 1200,
            "OFFSET_Y": 0,
        },
    },
    "HOTKEYS": {
        "QUIT": "q",
        "OPEN_LOG": "l",
        "OPEN_SETTINGS": "c",
        "RESET": "r",
    },
    "LOG_LEVEL": "INFO",
    "LOG_RETENTION": 3,
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def current_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


CONFIG_PATH = current_dir() / "config.yaml"


def load_config(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return _deep_merge(DEFAULT_CONFIG, data)


def save_config(config_data: dict[str, Any]) -> None:
    if CONFIG_PATH.exists():
        copyfile(CONFIG_PATH, CONFIG_PATH.with_suffix(".yaml.bak"))
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        yaml.safe_dump(config_data, file, allow_unicode=True, sort_keys=False)


def reload_config() -> dict[str, Any]:
    global config, REGIONS, GAME_WINDOW, THRESHOLDS, SCREENSHOT_INTERVAL
    global GAME_START_INTERVAL, GUI, HOTKEYS, LOG_LEVEL, LOG_RETENTION

    config = load_config(CONFIG_PATH)
    REGIONS = config["REGIONS"]
    GAME_WINDOW = config["GAME_WINDOW"]
    THRESHOLDS = config["THRESHOLDS"]
    SCREENSHOT_INTERVAL = config["SCREENSHOT_INTERVAL"]
    GAME_START_INTERVAL = config["GAME_START_INTERVAL"]
    GUI = config["GUI"]
    HOTKEYS = config["HOTKEYS"]
    LOG_LEVEL = config["LOG_LEVEL"]
    LOG_RETENTION = config["LOG_RETENTION"]
    return config


config = load_config(CONFIG_PATH)
REGIONS = config["REGIONS"]
GAME_WINDOW = config["GAME_WINDOW"]
THRESHOLDS = config["THRESHOLDS"]
SCREENSHOT_INTERVAL = config["SCREENSHOT_INTERVAL"]
GAME_START_INTERVAL = config["GAME_START_INTERVAL"]
GUI = config["GUI"]
HOTKEYS = config["HOTKEYS"]
LOG_LEVEL = config["LOG_LEVEL"]
LOG_RETENTION = config["LOG_RETENTION"]
