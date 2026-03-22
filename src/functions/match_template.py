"""
模板匹配相关函数。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from cv2 import TM_CCOEFF_NORMED, matchTemplate, minMaxLoc
from loguru import logger
from PIL import Image

from misc.custom_types import AnyImage, Card, CardIntDict, Mark, MatchResult

TEMPLATE_DIR: Path = Path(__file__).parent.parent / "templates"

CARD_TEMPLATE_NAMES: dict[Card, list[str]] = {
    Card.THREE: ["3"],
    Card.FOUR: ["4"],
    Card.FIVE: ["5"],
    Card.SIX: ["6"],
    Card.SEVEN: ["7"],
    Card.EIGHT: ["8"],
    Card.NINE: ["9"],
    Card.TEN: ["10"],
    Card.J: ["J"],
    Card.Q: ["Q"],
    Card.K: ["K"],
    Card.A: ["A"],
    Card.TWO: ["2"],
    Card.SMALL_JOKER: ["SMALLJOKER"],
    Card.BIG_JOKER: ["BIGJOKER"],
}

MARK_TEMPLATE_NAMES: dict[Mark, list[str]] = {
    Mark.PASS: ["PASS"],
    Mark.LANDLORD: ["Landlord", "LANDLORD", "地主"],
}


def _candidate_paths(template_name: str) -> list[Path]:
    return [TEMPLATE_DIR / f"{template_name}.png", TEMPLATE_DIR / f"{template_name}.jpg", TEMPLATE_DIR / f"{template_name}.jpeg"]


def _load_template(template_name: str) -> AnyImage | None:
    for path in _candidate_paths(template_name):
        if path.exists():
            return np.array(Image.open(path).convert("L"))  # type: ignore[return-value]
    return None


def _load_template_group(template_names: list[str]) -> list[AnyImage]:
    templates = [template for name in template_names if (template := _load_template(name)) is not None]
    if templates:
        return templates
    logger.error("模板缺失: {}", " / ".join(template_names))
    return [np.zeros((1, 1), dtype=np.uint8)]


CARD_TEMPLATES: dict[Card, list[AnyImage]] = {
    card: _load_template_group(names) for card, names in CARD_TEMPLATE_NAMES.items()
}
MARK_TEMPLATES: dict[Mark, list[AnyImage]] = {
    mark: _load_template_group(names) for mark, names in MARK_TEMPLATE_NAMES.items()
}


def _shape_2d(image: AnyImage) -> tuple[int, int]:
    if getattr(image, "ndim", 0) < 2:
        return (0, 0)
    return int(image.shape[0]), int(image.shape[1])


def _can_match(target: AnyImage, template: AnyImage) -> bool:
    target_h, target_w = _shape_2d(target)
    template_h, template_w = _shape_2d(template)
    return (
        target_h > 0
        and target_w > 0
        and template_h > 1
        and template_w > 1
        and target_h >= template_h
        and target_w >= template_w
    )


def template_match(target: AnyImage, template: AnyImage, threshold: float) -> list[MatchResult]:
    if not _can_match(target, template):
        logger.debug("跳过模板匹配，区域尺寸小于模板。target={} template={}", _shape_2d(target), _shape_2d(template))
        return []

    result = matchTemplate(target, template, TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)
    return [(float(result[pt[1], pt[0]]), pt) for pt in zip(*locations[::-1])]  # type: ignore[list-item]


def best_template_match(target: AnyImage, templates: AnyImage | list[AnyImage]) -> MatchResult:
    template_list = templates if isinstance(templates, list) else [templates]

    best_value = 0.0
    best_loc = (0, 0)
    for template in template_list:
        if not _can_match(target, template):
            continue
        result = matchTemplate(target, template, TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = minMaxLoc(result)
        if max_val > best_value:
            best_value = float(max_val)
            best_loc = (int(max_loc[0]), int(max_loc[1]))
    return best_value, best_loc


def identify_cards(image: AnyImage, threshold: float) -> CardIntDict:
    results: CardIntDict = {}

    for card, templates in CARD_TEMPLATES.items():
        amount = 0
        for template in templates:
            amount += len(template_match(image, template, threshold))
        if amount > 0:
            results[card] = amount
            logger.debug("检测到 {} 张 {}", amount, card.value)

    return results
