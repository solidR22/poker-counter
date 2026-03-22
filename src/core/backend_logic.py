"""
后端识别逻辑。
"""

from __future__ import annotations

from itertools import cycle
from threading import Event
from time import sleep

from loguru import logger

from misc.custom_types import Card, CardIntDict, Player, RegionState, WindowsType
from misc.singleton import singleton
from models.config import GAME_START_INTERVAL, SCREENSHOT_INTERVAL
from models.counters import CardCounter
from models.game_state import GameState, card_regions
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
            logger.info("已识别到游戏开始")

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
        logger.info("地主是：{}", self._landlord.value)

    def _init_player_cycle(self) -> None:
        self._current_player = next(self._player_cycle)
        while self._current_player is not self._landlord:
            self._current_player = next(self._player_cycle)

    def _mark_my_cards(self) -> None:
        my_cards = self._gs.my_cards
        self._status.update(
            phase="识别手牌",
            my_cards={card.value: count for card, count in my_cards.items()},
            message="已更新自己的手牌识别结果",
        )
        logger.info("识别到自己的手牌：{}", my_cards)
        self._mark_cards(my_cards, Player.MIDDLE)
        self._counter.player2_count = 0
        self._counter._sync_remaining_vars()  # type: ignore[attr-defined]

        not_my_cards = {card for card in Card if card not in my_cards}
        for card in not_my_cards:
            if not self._keep_running:
                return
            self.label_properties.text_color.change_style(card, WindowsType.MAIN, "red")

    def _should_advance_after_marking(self) -> bool:
        cards = card_regions[self._current_player].recognize_cards()
        self._status.update(
            last_cards={card.value: count for card, count in cards.items()},
            current_player=self._current_player.value,
            message=f"最近一次识别：{self._current_player.value}",
        )
        logger.info("识别到 {} 出牌：{}", self._current_player.value, cards)

        if len(cards) > 0:
            self._mark_cards(cards, self._current_player)
            return True
        return False

    def _should_advance(self) -> bool:
        match card_regions[self._current_player].state:
            case RegionState.WAIT:
                sleep(SCREENSHOT_INTERVAL)
                return False
            case RegionState.PASS:
                logger.info("{} 本轮不出", self._current_player.value)
                self._status.update(message=f"{self._current_player.value} 本轮不出")
                return True
            case RegionState.ACTIVE:
                return self._should_advance_after_marking()

    def _is_round_finished(self) -> bool:
        return (
            self._counter.player1_remaining == 0
            or self._counter.player2_remaining == 0
            or self._counter.player3_remaining == 0
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
                logger.info("当前轮到：{}", self._current_player.value)

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
                        logger.info("切换到：{}", self._current_player.value)
                    else:
                        sleep(SCREENSHOT_INTERVAL)

                self._status.update(phase="本局结束", message="等待下一局开始")
                logger.info("本局结束，等待下一局")

            self.label_properties.reset()
            self._status.update(phase="已停止", message="后台线程已停止")
