"""
模板匹配相关函数。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from cv2 import INTER_LINEAR, TM_CCOEFF_NORMED, matchTemplate, minMaxLoc, resize
from loguru import logger
from PIL import Image

from misc.custom_types import AnyImage, Card, CardIntDict, Mark, MatchResult
from models import config as config_model

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

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
    Card.JOKER: ["JOKER"],
}

MARK_TEMPLATE_NAMES: dict[Mark, list[str]] = {
    Mark.PASS: ["PASS"],
    Mark.LANDLORD: ["boss"],
    Mark.GAME_OVER: ["gameover"],
}


def _candidate_paths(template_name: str) -> list[Path]:
    return [
        TEMPLATE_DIR / f"{template_name}.jpg",
        TEMPLATE_DIR / f"{template_name}.png",
        TEMPLATE_DIR / f"{template_name}.jpeg",
    ]


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
    return target_h > 0 and target_w > 0 and template_h > 1 and template_w > 1 and target_h >= template_h and target_w >= template_w


def _scaled_templates(template: AnyImage) -> list[tuple[float, AnyImage]]:
    results: list[tuple[float, AnyImage]] = []
    for scale in config_model.TEMPLATE_SCALES:
        width = max(1, int(template.shape[1] * scale))
        height = max(1, int(template.shape[0] * scale))
        if width <= 1 or height <= 1:
            continue
        scaled = resize(template, (width, height), interpolation=INTER_LINEAR)
        results.append((float(scale), scaled))
    return results or [(1.0, template)]


def _iou(a: dict[str, int | float | str], b: dict[str, int | float | str]) -> float:
    ax1, ay1 = int(a["x"]), int(a["y"])
    ax2, ay2 = ax1 + int(a["w"]), ay1 + int(a["h"])
    bx1, by1 = int(b["x"]), int(b["y"])
    bx2, by2 = bx1 + int(b["w"]), by1 + int(b["h"])
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter_area / float(area_a + area_b - inter_area)


def _nms(matches: list[dict[str, int | float | str]], iou_threshold: float = 0.2) -> list[dict[str, int | float | str]]:
    kept: list[dict[str, int | float | str]] = []
    for match in sorted(matches, key=lambda item: float(item["confidence"]), reverse=True):
        if any(_iou(match, existing) >= iou_threshold for existing in kept):
            continue
        kept.append(match)
    return kept


def template_match(target: AnyImage, template: AnyImage, threshold: float) -> list[MatchResult]:
    matches: list[MatchResult] = []
    for _, scaled_template in _scaled_templates(template):
        if not _can_match(target, scaled_template):
            continue
        result = matchTemplate(target, scaled_template, TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        matches.extend((float(result[pt[1], pt[0]]), pt) for pt in zip(*locations[::-1]))  # type: ignore[list-item]
    return matches


def best_template_match(target: AnyImage, templates: AnyImage | list[AnyImage]) -> MatchResult:
    template_list = templates if isinstance(templates, list) else [templates]
    best_value = 0.0
    best_loc = (0, 0)
    for template in template_list:
        for _, scaled_template in _scaled_templates(template):
            if not _can_match(target, scaled_template):
                continue
            result = matchTemplate(target, scaled_template, TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = minMaxLoc(result)
            if max_val > best_value:
                best_value = float(max_val)
                best_loc = (int(max_loc[0]), int(max_loc[1]))
    return best_value, best_loc


def identify_cards(target: AnyImage, threshold: float) -> CardIntDict:
    results, _ = identify_cards_with_matches(target, threshold)
    return results


def identify_cards_with_matches(target: AnyImage, threshold: float) -> tuple[CardIntDict, list[dict[str, int | float | str]]]:
    all_matches: list[dict[str, int | float | str]] = []
    for card, templates in CARD_TEMPLATES.items():
        for template in templates:
            for scale, scaled_template in _scaled_templates(template):
                if not _can_match(target, scaled_template):
                    continue
                result = matchTemplate(target, scaled_template, TM_CCOEFF_NORMED)
                locations = np.where(result >= threshold)
                template_h, template_w = _shape_2d(scaled_template)
                for x, y in zip(*locations[::-1]):
                    all_matches.append(
                        {
                            "label": card.value,
                            "x": int(x),
                            "y": int(y),
                            "w": int(template_w),
                            "h": int(template_h),
                            "scale": round(scale, 3),
                            "confidence": round(float(result[y, x]), 4),
                        }
                    )
    merged_matches = _nms(all_matches)
    results: CardIntDict = {}
    for match in merged_matches:
        card = Card(match["label"])
        results[card] = results.get(card, 0) + 1

    for card, count in results.items():
        logger.debug("检测到 {} 张 {}", count, card.value)
    return results, merged_matches
