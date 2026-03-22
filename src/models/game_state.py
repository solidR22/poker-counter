"""
游戏状态识别。
"""

from dataclasses import dataclass

from loguru import logger

from functions.match_template import MARK_TEMPLATES, best_template_match
from misc.custom_types import CardIntDict, Mark, Player, RegionState
from misc.singleton import singleton
from models.config import REGIONS, THRESHOLDS

from .regions import Region

card_regions: dict[Player, Region] = {
    Player.LEFT: Region(*REGIONS["playing_left"]),
    Player.MIDDLE: Region(*REGIONS["playing_middle"]),
    Player.RIGHT: Region(*REGIONS["playing_right"]),
}

avatar_regions: dict[Player, Region] = {
    Player.LEFT: Region(*REGIONS["avatar_left"]),
    Player.MIDDLE: Region(*REGIONS["avatar_middle"]),
    Player.RIGHT: Region(*REGIONS["avatar_right"]),
}

my_cards_region: Region = Region(*REGIONS["my_cards"])
my_cards_region.state = RegionState.ACTIVE
logger.success("已创建所有识别区域")


def refresh_regions(region_config: dict[str, list[list[int]]]) -> None:
    card_regions[Player.LEFT].update_coordinates(*region_config["playing_left"])
    card_regions[Player.MIDDLE].update_coordinates(*region_config["playing_middle"])
    card_regions[Player.RIGHT].update_coordinates(*region_config["playing_right"])

    avatar_regions[Player.LEFT].update_coordinates(*region_config["avatar_left"])
    avatar_regions[Player.MIDDLE].update_coordinates(*region_config["avatar_middle"])
    avatar_regions[Player.RIGHT].update_coordinates(*region_config["avatar_right"])

    my_cards_region.update_coordinates(*region_config["my_cards"])
    my_cards_region.state = RegionState.ACTIVE


@singleton
@dataclass
class GameState:
    @property
    def my_cards(self) -> CardIntDict:
        return my_cards_region.recognize_cards()

    @property
    def landlord_confidences(self) -> dict[Player, float]:
        return {
            player: best_template_match(
                avatar_regions[player].region_screenshot,
                MARK_TEMPLATES[Mark.LANDLORD],
            )[0]
            for player in Player
        }

    @property
    def is_game_started(self) -> bool:
        confidences = self.landlord_confidences
        confidence = max(confidences.values())
        logger.debug("头像地主标志识别置信度：{}", confidences)
        return confidence >= THRESHOLDS["landlord"]

    @property
    def landlord_location(self) -> Player:
        confidences = self.landlord_confidences
        return max(confidences, key=confidences.get)
