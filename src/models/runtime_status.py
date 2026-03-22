"""
运行状态快照，供主界面实时展示。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from misc.singleton import singleton


@singleton
@dataclass
class RuntimeStatus:
    _lock: Lock = field(default_factory=Lock)
    _data: dict[str, Any] = field(
        default_factory=lambda: {
            "phase": "未启动",
            "game_started": False,
            "landlord": "未识别",
            "landlord_confidences": {},
            "current_player": "未开始",
            "region_states": {},
            "my_cards": {},
            "last_cards": {},
            "message": "等待启动",
        }
    )

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            self._data.update(kwargs)

    def reset(self) -> None:
        self.update(
            phase="未启动",
            game_started=False,
            landlord="未识别",
            landlord_confidences={},
            current_player="未开始",
            region_states={},
            my_cards={},
            last_cards={},
            message="等待启动",
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "phase": self._data["phase"],
                "game_started": self._data["game_started"],
                "landlord": self._data["landlord"],
                "landlord_confidences": dict(self._data["landlord_confidences"]),
                "current_player": self._data["current_player"],
                "region_states": dict(self._data["region_states"]),
                "my_cards": dict(self._data["my_cards"]),
                "last_cards": dict(self._data["last_cards"]),
                "message": self._data["message"],
            }
