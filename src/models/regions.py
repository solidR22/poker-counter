"""
识别区域定义。
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from functions.color_percentage import color_percentage
from functions.match_template import MARK_TEMPLATES, best_template_match, identify_cards, identify_cards_with_matches
from misc.custom_types import CardIntDict, GrayscaleImage, Mark, RegionState
from models.config import THRESHOLDS

from .screenshot import screenshot


@dataclass
class Region:
    TOP_LEFT: tuple[int, int]
    BOTTOM_RIGHT: tuple[int, int]

    def __post_init__(self) -> None:
        self.state = RegionState.WAIT
        self.update_coordinates(self.TOP_LEFT, self.BOTTOM_RIGHT)

    def update_coordinates(self, top_left: tuple[int, int], bottom_right: tuple[int, int]) -> None:
        x1, x2 = sorted((top_left[0], bottom_right[0]))
        y1, y2 = sorted((top_left[1], bottom_right[1]))
        if x1 == x2:
            x2 += 1
        if y1 == y2:
            y2 += 1
        self.TOP_LEFT = (x1, y1)
        self.BOTTOM_RIGHT = (x2, y2)
        self._X1 = x1
        self._Y1 = y1
        self._X2 = x2
        self._Y2 = y2

    @property
    def region_screenshot(self) -> GrayscaleImage:
        return screenshot.image[self._Y1 : self._Y2, self._X1 : self._X2]  # type: ignore[index]

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return self._X1, self._Y1, self._X2, self._Y2

    def update_state(self) -> None:
        if self._is_pass:
            self.state = RegionState.PASS
            logger.debug("区域状态更新为 PASS")
            return
        if self._is_wait:
            self.state = RegionState.WAIT
            logger.debug("区域状态更新为 WAIT")
            return
        self.state = RegionState.ACTIVE
        logger.debug("区域状态更新为 ACTIVE")

    @property
    def _is_pass(self) -> bool:
        confidence = best_template_match(self.region_screenshot, MARK_TEMPLATES[Mark.PASS])[0]
        return confidence > THRESHOLDS["pass"]

    @property
    def _is_wait(self) -> bool:
        blue_percentage = color_percentage(self.region_screenshot, (118, 40, 75))
        return blue_percentage > THRESHOLDS["wait"]

    def recognize_cards(self) -> CardIntDict:
        if self.state is not RegionState.ACTIVE:
            logger.warning("尝试在非 ACTIVE 区域识别牌面")
        return identify_cards(self.region_screenshot, THRESHOLDS["card"])

    def recognize_cards_with_matches(self) -> tuple[CardIntDict, list[dict[str, int | float | str]]]:
        if self.state is not RegionState.ACTIVE:
            logger.warning("尝试在非 ACTIVE 区域识别牌面")
        return identify_cards_with_matches(self.region_screenshot, THRESHOLDS["card"])
