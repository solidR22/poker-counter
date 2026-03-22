"""
后端识别逻辑。
"""

from __future__ import annotations

from io import BytesIO
from itertools import cycle
from threading import Event
from time import sleep

from loguru import logger
from PIL import Image, ImageDraw

from misc.custom_types import Card, CardIntDict, Player, RegionState, WindowsType
from misc.singleton import singleton
from models.config import GAME_START_INTERVAL, SCREENSHOT_INTERVAL
from models.counters import CardCounter
from models.game_state import GameState, card_regions, my_cards_region
from models.labels import LabelProperties
from models.runtime_status import RuntimeStatus
from models.screenshot import screenshot


@singleton
class BackendLogic:
    def __init__(self) -> None:
        self._counter = CardCounter()
        self._gs = GameState()
        self._status = RuntimeStatus()
        self.label_properties = LabelProperties()
        logger.info("后端逻辑初始化完毕")

    def set_stop_event(self, stop_event: Event) -> None:
        self._stop_event = stop_event

    @property
    def _keep_running(self) -> bool:
        return not self._stop_event.is_set()

    def _update_text_color(self, card: Card, count: int, player: Player) -> None:
        if count > 1:
            match player:
                case Player.LEFT:
                    self.label_properties.text_color.change_style(card, WindowsType.LEFT, "red")
                case Player.MIDDLE:
                    pass
                case Player.RIGHT:
                    self.label_properties.text_color.change_style(card, WindowsType.RIGHT, "red")
        self.label_properties.text_color.change_style(card, WindowsType.MAIN, "black")

    def _mark_cards(self, cards: CardIntDict, player: Player) -> None:
        for card, count in cards.items():
            self._update_text_color(card, count, player)
            for _ in range(count):
                self._counter.mark(card, player)

    def _update_preview(
        self,
        title: str,
        region_image,
        matches: list[dict[str, int | float | str]],
    ) -> None:
        if getattr(region_image, "size", 0) == 0:
            return
        preview = Image.fromarray(region_image).convert("RGB")
        draw = ImageDraw.Draw(preview)
        for match in matches:
            x = int(match["x"])
            y = int(match["y"])
            w = int(match["w"])
            h = int(match["h"])
            label = str(match["label"])
            confidence = float(match["confidence"])
            draw.rectangle((x, y, x + w, y + h), outline="#ff3b30", width=2)
            draw.text((x, max(0, y - 14)), f"{label} {confidence:.2f}", fill="#ffd60a")

        max_width = 420
        if preview.width > max_width:
            scale = max_width / preview.width
            preview = preview.resize((int(preview.width * scale), int(preview.height * scale)))

        buffer = BytesIO()
        preview.save(buffer, format="PNG")
        self._status.update(preview_title=title, preview_png=buffer.getvalue())

    def _pregame_init(self) -> None:
        self._counter.reset()
        self.label_properties.text_color.reset()
        self._status.reset()
        self._status.update(phase="准备中", message="已完成开局前初始化")
        self._player_cycle = cycle([Player.LEFT, Player.MIDDLE, Player.RIGHT])
        screenshot.update()
        logger.info("已完成开局前初始化")

    def _wait_for_game_start(self) -> None:
        logger.info("等待游戏开始")
        self._status.update(phase="等待开局", message="等待头像区域出现地主标志")
        while not self._gs.is_game_started and self._keep_running:
            screenshot.update()
            self._status.update(
                game_started=False,
                landlord_confidences={
                    player.value: round(confidence, 3)
                    for player, confidence in self._gs.landlord_confidences.items()
                },
                message="尚未检测到开局地主标志",
            )
            sleep(GAME_START_INTERVAL)
        if self._keep_running:
            self._status.update(phase="已开局", game_started=True, message="已识别到开局")

    def _find_landlord(self) -> None:
        self._landlord = self._gs.landlord_location
        self._counter.set_totals(self._landlord)
        self._status.update(
            landlord=self._landlord.value,
            landlord_confidences={
                player.value: round(confidence, 3)
                for player, confidence in self._gs.landlord_confidences.items()
            },
            message=f"已识别地主：{self._landlord.value}",
        )

    def _init_player_cycle(self) -> None:
        self._current_player = next(self._player_cycle)
        while self._current_player is not self._landlord:
            self._current_player = next(self._player_cycle)

    def _mark_my_cards(self) -> None:
        my_cards, matches = my_cards_region.recognize_cards_with_matches()
        self._update_preview("我的手牌识别预览", my_cards_region.region_screenshot, matches)
        self._status.update(
            phase="识别手牌",
            my_cards={card.value: count for card, count in my_cards.items()},
            message="已更新自己的手牌识别结果",
        )
        self._mark_cards(my_cards, Player.MIDDLE)
        self._counter.player2_count = 0
        self._counter._sync_remaining_vars()  # type: ignore[attr-defined]

        not_my_cards = {card for card in Card if card not in my_cards}
        for card in not_my_cards:
            if not self._keep_running:
                return
            self.label_properties.text_color.change_style(card, WindowsType.MAIN, "red")

    def _should_advance_after_marking(self) -> bool:
        region = card_regions[self._current_player]
        cards, matches = region.recognize_cards_with_matches()
        self._update_preview(f"{self._current_player.value} 出牌识别预览", region.region_screenshot, matches)
        self._status.update(
            last_cards={card.value: count for card, count in cards.items()},
            current_player=self._current_player.value,
            message=f"最近一次识别：{self._current_player.value}",
        )
        if cards:
            self._status.append_recognized_play(
                self._current_player.value,
                {card.value: count for card, count in cards.items()},
            )
            self._mark_cards(cards, self._current_player)
            return True
        return False

    def _should_advance(self) -> bool:
        match card_regions[self._current_player].state:
            case RegionState.WAIT:
                sleep(SCREENSHOT_INTERVAL)
                return False
            case RegionState.PASS:
                self._status.update(message=f"{self._current_player.value} 本轮不出")
                return True
            case RegionState.ACTIVE:
                return self._should_advance_after_marking()

    def _is_round_finished(self) -> bool:
        return (
            self._counter.player1_remaining == 0
            or self._counter.player2_remaining == 0
            or self._counter.player3_remaining == 0
            or self._gs.is_game_over
        )

    def run(self) -> None:
        with logger.catch():
            while self._keep_running:
                self._pregame_init()
                self._wait_for_game_start()
                if not self._keep_running:
                    break

                self._find_landlord()
                self._init_player_cycle()
                self._status.update(
                    phase="记牌中",
                    current_player=self._current_player.value,
                    message=f"当前轮到：{self._current_player.value}",
                )
                self._mark_my_cards()

                while self._keep_running and not self._is_round_finished():
                    screenshot.update()
                    card_regions[self._current_player].update_state()
                    self._status.update(
                        region_states={
                            player.value: card_regions[player].state.name
                            for player in Player
                        },
                        current_player=self._current_player.value,
                    )
                    if self._should_advance():
                        self._current_player = next(self._player_cycle)
                        self._status.update(
                            current_player=self._current_player.value,
                            message=f"切换到：{self._current_player.value}",
                        )
                    else:
                        sleep(SCREENSHOT_INTERVAL)

                if self._gs.is_game_over:
                    self._status.update(message="已识别到游戏结束标志")
                self._status.update(phase="本局结束", message=self._status.snapshot()["message"])

            self.label_properties.reset()
            self._status.update(phase="已停止", message="后台线程已停止")
