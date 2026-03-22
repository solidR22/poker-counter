"""
嵌入主界面的参数设置面板。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from PIL import Image, ImageGrab, ImageTk

from models import config as config_model
from models.game_state import refresh_regions


REGION_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "playing_left",
        "label": "上家出牌区域",
        "usage": "框住上家打出来的牌会出现的位置，只需要覆盖牌面范围。",
        "example": "通常在桌面左侧中间，牌从左往右摊开的位置。",
    },
    {
        "key": "playing_middle",
        "label": "我的出牌区域",
        "usage": "框住自己打出来的牌会出现的位置，只识别你出了哪些牌。",
        "example": "通常在桌面中间偏下，紧挨着你的手牌上方。",
    },
    {
        "key": "playing_right",
        "label": "下家出牌区域",
        "usage": "框住下家打出来的牌会出现的位置，只需要覆盖牌面范围。",
        "example": "通常在桌面右侧中间，牌从右往左摊开的位置。",
    },
    {
        "key": "my_cards",
        "label": "我的手牌区域",
        "usage": "框住自己当前手里的整排牌，程序会用它识别你还剩哪些牌。",
        "example": "通常在屏幕底部，完整覆盖最左和最右的手牌边界。",
    },
    {
        "key": "avatar_left",
        "label": "上家头像区域",
        "usage": "框住上家头像和地主角标出现的位置，用它判断是否开局以及谁是地主。",
        "example": "通常在左侧玩家头像附近，只需包含头像和地主标志。",
    },
    {
        "key": "avatar_middle",
        "label": "我的头像区域",
        "usage": "框住你自己的头像和地主角标出现的位置，用它判断自己是否是地主。",
        "example": "通常在底部中间头像附近，只需包含头像和地主标志。",
    },
    {
        "key": "avatar_right",
        "label": "下家头像区域",
        "usage": "框住下家头像和地主角标出现的位置，用它判断是否开局以及谁是地主。",
        "example": "通常在右侧玩家头像附近，只需包含头像和地主标志。",
    },
]

WINDOW_LABELS = {
    "MAIN": "主记牌窗",
    "LEFT": "上家统计窗",
    "RIGHT": "下家统计窗",
    "SWITCH": "主控制窗",
}


class SettingsPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__(parent, padding=12)
        self.on_saved = on_saved

        self._definitions = REGION_DEFINITIONS
        self._definition_map = {item["key"]: item for item in self._definitions}
        self._regions: dict[str, list[list[int]]] = {}
        self._game_origin = (0, 0)
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._preview_scale = 1.0
        self._screen_size = (1, 1)
        self._selected_name = self._definitions[0]["key"]

        self._interaction_mode = "idle"
        self._drag_start_screen: tuple[int, int] | None = None
        self._move_anchor_screen: tuple[int, int] | None = None
        self._move_origin_region: list[list[int]] | None = None

        self._build_variables()
        self._build_layout()
        self.load_from_config()

    def _build_variables(self) -> None:
        self.coord_vars = {key: tk.IntVar(value=0) for key in ("x1", "y1", "x2", "y2")}
        self.game_origin_vars = {"x": tk.IntVar(value=0), "y": tk.IntVar(value=0)}
        self.threshold_vars = {
            "card": tk.DoubleVar(value=0.95),
            "landlord": tk.DoubleVar(value=0.95),
            "pass": tk.DoubleVar(value=0.9),
            "wait": tk.DoubleVar(value=0.9),
            "screenshot_interval": tk.DoubleVar(value=0.1),
            "game_start_interval": tk.DoubleVar(value=1.0),
        }
        self.log_vars = {"level": tk.StringVar(value="INFO"), "retention": tk.IntVar(value=3)}
        self.hotkey_vars = {
            "QUIT": tk.StringVar(),
            "OPEN_LOG": tk.StringVar(),
            "OPEN_SETTINGS": tk.StringVar(),
            "RESET": tk.StringVar(),
        }
        self.gui_vars: dict[str, dict[str, tk.Variable]] = {}
        for key in WINDOW_LABELS:
            self.gui_vars[key] = {
                "DISPLAY": tk.BooleanVar(value=True),
                "OPACITY": tk.DoubleVar(value=1.0),
                "FONT_SIZE": tk.IntVar(value=12),
                "OFFSET_X": tk.StringVar(),
                "OFFSET_Y": tk.StringVar(),
                "CENTER_X": tk.StringVar(),
                "CENTER_Y": tk.StringVar(),
            }
        self.region_name_var = tk.StringVar()
        self.region_usage_var = tk.StringVar()
        self.region_example_var = tk.StringVar()
        self.region_size_var = tk.StringVar()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.region_tab = ttk.Frame(self.notebook, padding=10)
        self.detect_tab = ttk.Frame(self.notebook, padding=10)
        self.window_tab = ttk.Frame(self.notebook, padding=10)
        self.other_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.region_tab, text="识别区域")
        self.notebook.add(self.detect_tab, text="识别参数")
        self.notebook.add(self.window_tab, text="窗口参数")
        self.notebook.add(self.other_tab, text="快捷键与日志")

        self._build_region_tab()
        self._build_detect_tab()
        self._build_window_tab()
        self._build_other_tab()

        footer = ttk.Frame(self, padding=(0, 10, 0, 0))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(
            footer,
            text="所有参数都可以在这里修改。保存后会立即写回配置并刷新当前识别区域。",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="重新载入当前配置", command=self.load_from_config).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(footer, text="保存全部设置", command=self.save_all).grid(row=0, column=2, padx=(8, 0))

    def _build_region_tab(self) -> None:
        self.region_tab.columnconfigure(0, weight=3)
        self.region_tab.columnconfigure(1, weight=2)
        self.region_tab.rowconfigure(1, weight=1)

        left = ttk.Frame(self.region_tab)
        left.grid(row=0, column=0, rowspan=2, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(left)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(
            toolbar,
            text="先截图，再选择区域名称。点中已有框可以直接拖动，点框外拖拽会重画新的矩形。",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(toolbar, text="刷新屏幕截图", command=self._capture_screen).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(toolbar, text="点选游戏窗口左上角", command=self._start_pick_game_origin).grid(row=0, column=2, padx=(8, 0))

        self.canvas = tk.Canvas(left, bg="#17212b", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        right = ttk.Frame(self.region_tab)
        right.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(12, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        origin_frame = ttk.LabelFrame(right, text="游戏窗口左上角", padding=10)
        origin_frame.grid(row=0, column=0, sticky="ew")
        origin_frame.columnconfigure(1, weight=1)
        origin_frame.columnconfigure(3, weight=1)
        ttk.Label(origin_frame, text="X").grid(row=0, column=0, sticky="w")
        ttk.Entry(origin_frame, textvariable=self.game_origin_vars["x"]).grid(row=0, column=1, sticky="ew", padx=(6, 12))
        ttk.Label(origin_frame, text="Y").grid(row=0, column=2, sticky="w")
        ttk.Entry(origin_frame, textvariable=self.game_origin_vars["y"]).grid(row=0, column=3, sticky="ew", padx=(6, 0))
        ttk.Button(origin_frame, text="按输入值整体平移所有区域", command=self._apply_game_origin_entries).grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0)
        )

        list_frame = ttk.Frame(right)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 12))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)
        ttk.Label(list_frame, text="区域列表").grid(row=0, column=0, sticky="w")
        self.region_list = tk.Listbox(list_frame, exportselection=False, height=8)
        self.region_list.grid(row=1, column=0, sticky="nsew")
        self.region_list.bind("<<ListboxSelect>>", self._on_list_select)

        info_frame = ttk.LabelFrame(right, text="区域说明", padding=10)
        info_frame.grid(row=2, column=0, sticky="ew")
        info_frame.columnconfigure(0, weight=1)
        ttk.Label(info_frame, textvariable=self.region_name_var, font=("Microsoft YaHei UI", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(info_frame, textvariable=self.region_usage_var, wraplength=360, justify="left").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Label(
            info_frame,
            textvariable=self.region_example_var,
            wraplength=360,
            justify="left",
            foreground="#5c6b80",
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(info_frame, textvariable=self.region_size_var).grid(row=3, column=0, sticky="w", pady=(8, 0))

        coord_frame = ttk.LabelFrame(right, text="坐标微调", padding=10)
        coord_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        coord_frame.columnconfigure(1, weight=1)
        coord_frame.columnconfigure(3, weight=1)
        fields = [("x1", 0, 0), ("y1", 0, 2), ("x2", 1, 0), ("y2", 1, 2)]
        for field, row, column in fields:
            ttk.Label(coord_frame, text=field.upper()).grid(row=row, column=column, sticky="w", pady=4)
            ttk.Entry(coord_frame, textvariable=self.coord_vars[field]).grid(
                row=row, column=column + 1, sticky="ew", padx=(6, 12), pady=4
            )
        ttk.Button(coord_frame, text="应用当前区域坐标", command=self._apply_region_entries).grid(
            row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0)
        )

    def _build_detect_tab(self) -> None:
        self.detect_tab.columnconfigure(0, weight=1)
        frame = ttk.LabelFrame(self.detect_tab, text="识别阈值与间隔", padding=12)
        frame.grid(row=0, column=0, sticky="new")
        frame.columnconfigure(1, weight=1)

        rows = [
            ("card", "牌面识别阈值"),
            ("landlord", "地主标志识别阈值"),
            ("pass", "不出识别阈值"),
            ("wait", "等待状态阈值"),
            ("screenshot_interval", "循环截图间隔（秒）"),
            ("game_start_interval", "等待开局检查间隔（秒）"),
        ]
        for idx, (key, label) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=idx, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=self.threshold_vars[key]).grid(row=idx, column=1, sticky="ew", padx=(8, 0), pady=4)

    def _build_window_tab(self) -> None:
        self.window_tab.columnconfigure(0, weight=1)
        notebook = ttk.Notebook(self.window_tab)
        notebook.grid(row=0, column=0, sticky="nsew")

        for key, label in WINDOW_LABELS.items():
            tab = ttk.Frame(notebook, padding=12)
            tab.columnconfigure(1, weight=1)
            notebook.add(tab, text=label)

            row = 0
            if key != "SWITCH":
                ttk.Checkbutton(tab, text="显示这个窗口", variable=self.gui_vars[key]["DISPLAY"]).grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=4
                )
                row += 1

            fields = [
                ("OPACITY", "透明度"),
                ("FONT_SIZE", "字号"),
                ("OFFSET_X", "左上角 X"),
                ("OFFSET_Y", "左上角 Y"),
                ("CENTER_X", "中心点 X"),
                ("CENTER_Y", "中心点 Y"),
            ]
            for field, title in fields:
                ttk.Label(tab, text=title).grid(row=row, column=0, sticky="w", pady=4)
                ttk.Entry(tab, textvariable=self.gui_vars[key][field]).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=4)
                row += 1

    def _build_other_tab(self) -> None:
        self.other_tab.columnconfigure(0, weight=1)

        hotkey_frame = ttk.LabelFrame(self.other_tab, text="快捷键", padding=12)
        hotkey_frame.grid(row=0, column=0, sticky="ew")
        hotkey_frame.columnconfigure(1, weight=1)
        hotkeys = [
            ("QUIT", "退出程序"),
            ("OPEN_LOG", "打开日志"),
            ("OPEN_SETTINGS", "切到设置页"),
            ("RESET", "重置记牌"),
        ]
        for idx, (key, label) in enumerate(hotkeys):
            ttk.Label(hotkey_frame, text=label).grid(row=idx, column=0, sticky="w", pady=4)
            ttk.Entry(hotkey_frame, textvariable=self.hotkey_vars[key]).grid(row=idx, column=1, sticky="ew", padx=(8, 0), pady=4)

        log_frame = ttk.LabelFrame(self.other_tab, text="日志", padding=12)
        log_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        log_frame.columnconfigure(1, weight=1)
        ttk.Label(log_frame, text="日志级别").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            log_frame,
            textvariable=self.log_vars["level"],
            values=["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)
        ttk.Label(log_frame, text="日志保留天数").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(log_frame, textvariable=self.log_vars["retention"]).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)

    def load_from_config(self) -> None:
        config_model.reload_config()
        self._regions = {
            item["key"]: [point[:] for point in config_model.REGIONS[item["key"]]]
            for item in self._definitions
        }
        self._game_origin = (
            int(config_model.GAME_WINDOW["OFFSET_X"]),
            int(config_model.GAME_WINDOW["OFFSET_Y"]),
        )
        self.game_origin_vars["x"].set(self._game_origin[0])
        self.game_origin_vars["y"].set(self._game_origin[1])

        self.threshold_vars["card"].set(config_model.THRESHOLDS["card"])
        self.threshold_vars["landlord"].set(config_model.THRESHOLDS["landlord"])
        self.threshold_vars["pass"].set(config_model.THRESHOLDS["pass"])
        self.threshold_vars["wait"].set(config_model.THRESHOLDS["wait"])
        self.threshold_vars["screenshot_interval"].set(config_model.SCREENSHOT_INTERVAL)
        self.threshold_vars["game_start_interval"].set(config_model.GAME_START_INTERVAL)

        self.log_vars["level"].set(config_model.LOG_LEVEL)
        self.log_vars["retention"].set(config_model.LOG_RETENTION)

        for key, value in config_model.HOTKEYS.items():
            if key in self.hotkey_vars:
                self.hotkey_vars[key].set(value)

        for key in WINDOW_LABELS:
            gui_config = config_model.GUI.get(key, {})
            for field, variable in self.gui_vars[key].items():
                if field in gui_config:
                    variable.set(gui_config[field])
                elif field.startswith(("OFFSET", "CENTER")):
                    variable.set("")

        self.region_list.delete(0, tk.END)
        for item in self._definitions:
            self.region_list.insert(tk.END, item["label"])

        self._select_region(self._definitions[0]["key"])
        self._capture_screen()

    def build_config_dict(self) -> dict:
        config = {
            "REGIONS": {key: [value[0][:], value[1][:]] for key, value in self._regions.items()},
            "GAME_WINDOW": {
                "OFFSET_X": int(self._game_origin[0]),
                "OFFSET_Y": int(self._game_origin[1]),
            },
            "THRESHOLDS": {
                "card": float(self.threshold_vars["card"].get()),
                "landlord": float(self.threshold_vars["landlord"].get()),
                "pass": float(self.threshold_vars["pass"].get()),
                "wait": float(self.threshold_vars["wait"].get()),
            },
            "SCREENSHOT_INTERVAL": float(self.threshold_vars["screenshot_interval"].get()),
            "GAME_START_INTERVAL": float(self.threshold_vars["game_start_interval"].get()),
            "GUI": {},
            "HOTKEYS": {key: self.hotkey_vars[key].get().strip() for key in self.hotkey_vars},
            "LOG_LEVEL": self.log_vars["level"].get(),
            "LOG_RETENTION": int(self.log_vars["retention"].get()),
        }

        for key in WINDOW_LABELS:
            gui_config: dict[str, object] = {}
            if key != "SWITCH":
                gui_config["DISPLAY"] = bool(self.gui_vars[key]["DISPLAY"].get())
            gui_config["OPACITY"] = float(self.gui_vars[key]["OPACITY"].get())
            gui_config["FONT_SIZE"] = int(self.gui_vars[key]["FONT_SIZE"].get())
            for field in ("OFFSET_X", "OFFSET_Y", "CENTER_X", "CENTER_Y"):
                raw_value = str(self.gui_vars[key][field].get()).strip()
                if raw_value:
                    gui_config[field] = int(raw_value)
            config["GUI"][key] = gui_config
        return config

    def save_all(self) -> None:
        try:
            config = self.build_config_dict()
        except Exception as exc:
            messagebox.showerror("保存失败", f"参数格式不正确：{exc}")
            return

        for item in self._definitions:
            name = item["key"]
            (x1, y1), (x2, y2) = config["REGIONS"][name]
            if x2 <= x1 or y2 <= y1:
                messagebox.showerror("保存失败", f"{item['label']} 的区域无效，请重新调整。")
                return

        config_model.save_config(config)
        config_model.reload_config()
        refresh_regions(config["REGIONS"])
        if self.on_saved:
            self.on_saved()
        messagebox.showinfo("保存成功", "全部参数已保存并刷新。")

    def _capture_screen(self) -> None:
        try:
            image = ImageGrab.grab()
        except Exception as exc:
            messagebox.showerror("截图失败", f"无法获取屏幕截图：{exc}")
            return

        self._screen_size = image.size
        canvas_width = max(self.canvas.winfo_width(), 820)
        canvas_height = max(self.canvas.winfo_height(), 500)
        scale = min(canvas_width / image.width, canvas_height / image.height, 1.0)
        preview_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        preview = image.resize(preview_size, Image.Resampling.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(preview)
        self._preview_scale = scale
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, preview_size[0], preview_size[1]))
        self.canvas.create_image(0, 0, image=self._preview_photo, anchor="nw")
        self._draw_regions()

    def _draw_regions(self) -> None:
        self.canvas.delete("region")
        origin_x, origin_y = self._game_origin
        sx, sy = self._scale_point(origin_x, origin_y)
        self.canvas.create_line(sx - 10, sy, sx + 10, sy, fill="#ffd166", width=2, tags="region")
        self.canvas.create_line(sx, sy - 10, sx, sy + 10, fill="#ffd166", width=2, tags="region")
        self.canvas.create_text(sx + 8, sy + 8, text="游戏窗口左上角", fill="#ffd166", anchor="nw", tags="region")

        for item in self._definitions:
            name = item["key"]
            (x1, y1), (x2, y2) = self._regions[name]
            sx1, sy1, sx2, sy2 = self._scale_region(x1, y1, x2, y2)
            color = "#ff6b6b" if name == self._selected_name else "#4cc9f0"
            width = 3 if name == self._selected_name else 2
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline=color, width=width, tags="region")
            self.canvas.create_text(sx1 + 6, max(12, sy1 - 8), text=item["label"], fill=color, anchor="sw", tags="region")

    def _scale_point(self, x: int, y: int) -> tuple[int, int]:
        return int(x * self._preview_scale), int(y * self._preview_scale)

    def _scale_region(self, x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int, int]:
        sx1, sy1 = self._scale_point(x1, y1)
        sx2, sy2 = self._scale_point(x2, y2)
        return sx1, sy1, sx2, sy2

    def _canvas_to_screen(self, x: int, y: int) -> tuple[int, int]:
        width, height = self._screen_size
        px = min(max(int(x / self._preview_scale), 0), width)
        py = min(max(int(y / self._preview_scale), 0), height)
        return px, py

    def _screen_point_in_selected_region(self, x: int, y: int) -> bool:
        (x1, y1), (x2, y2) = self._regions[self._selected_name]
        return x1 <= x <= x2 and y1 <= y <= y2

    def _start_pick_game_origin(self) -> None:
        self._interaction_mode = "pick_origin"

    def _on_canvas_press(self, event: tk.Event) -> None:  # type: ignore[override]
        screen_point = self._canvas_to_screen(event.x, event.y)
        if self._interaction_mode == "pick_origin":
            self._set_game_origin(*screen_point)
            self._interaction_mode = "idle"
            return

        if self._screen_point_in_selected_region(*screen_point):
            self._interaction_mode = "move"
            self._move_anchor_screen = screen_point
            self._move_origin_region = [self._regions[self._selected_name][0][:], self._regions[self._selected_name][1][:]]
        else:
            self._interaction_mode = "draw"
            self._drag_start_screen = screen_point

    def _on_canvas_drag(self, event: tk.Event) -> None:  # type: ignore[override]
        current = self._canvas_to_screen(event.x, event.y)
        if self._interaction_mode == "move":
            self._move_selected_region(current)
        elif self._interaction_mode == "draw":
            self._draw_new_selected_region(current)

    def _on_canvas_release(self, event: tk.Event) -> None:  # type: ignore[override]
        if self._interaction_mode in {"move", "draw"}:
            self._on_canvas_drag(event)
        if self._interaction_mode != "pick_origin":
            self._interaction_mode = "idle"
        self._drag_start_screen = None
        self._move_anchor_screen = None
        self._move_origin_region = None

    def _on_list_select(self, _event: tk.Event) -> None:  # type: ignore[override]
        selected = self.region_list.curselection()
        if selected:
            self._select_region(self._definitions[selected[0]]["key"])

    def _select_region(self, region_name: str) -> None:
        self._selected_name = region_name
        index = next(i for i, item in enumerate(self._definitions) if item["key"] == region_name)
        self.region_list.selection_clear(0, tk.END)
        self.region_list.selection_set(index)
        self.region_list.activate(index)
        self._sync_inputs_from_region()
        self._draw_regions()

    def _sync_inputs_from_region(self) -> None:
        region = self._regions[self._selected_name]
        self.coord_vars["x1"].set(region[0][0])
        self.coord_vars["y1"].set(region[0][1])
        self.coord_vars["x2"].set(region[1][0])
        self.coord_vars["y2"].set(region[1][1])
        self._update_region_info()

    def _update_region_info(self) -> None:
        definition = self._definition_map[self._selected_name]
        x1, y1 = self._regions[self._selected_name][0]
        x2, y2 = self._regions[self._selected_name][1]
        self.region_name_var.set(definition["label"])
        self.region_usage_var.set(f"用途：{definition['usage']}")
        self.region_example_var.set(f"示例：{definition['example']}")
        self.region_size_var.set(f"当前尺寸：{x2 - x1} x {y2 - y1} 像素")

    def _set_game_origin(self, x: int, y: int) -> None:
        old_x, old_y = self._game_origin
        dx = x - old_x
        dy = y - old_y
        self._game_origin = (x, y)
        self.game_origin_vars["x"].set(x)
        self.game_origin_vars["y"].set(y)

        for name in self._regions:
            self._regions[name][0][0] += dx
            self._regions[name][0][1] += dy
            self._regions[name][1][0] += dx
            self._regions[name][1][1] += dy

        self._shift_window_positions(dx, dy)
        self._sync_inputs_from_region()
        self._draw_regions()

    def _shift_window_positions(self, dx: int, dy: int) -> None:
        for key in WINDOW_LABELS:
            for field, delta in (("OFFSET_X", dx), ("OFFSET_Y", dy), ("CENTER_X", dx), ("CENTER_Y", dy)):
                raw = str(self.gui_vars[key][field].get()).strip()
                if raw:
                    self.gui_vars[key][field].set(str(int(raw) + delta))

    def _apply_game_origin_entries(self) -> None:
        self._set_game_origin(self.game_origin_vars["x"].get(), self.game_origin_vars["y"].get())

    def _move_selected_region(self, current: tuple[int, int]) -> None:
        if self._move_anchor_screen is None or self._move_origin_region is None:
            return
        dx = current[0] - self._move_anchor_screen[0]
        dy = current[1] - self._move_anchor_screen[1]
        (x1, y1), (x2, y2) = self._move_origin_region
        width = x2 - x1
        height = y2 - y1
        screen_width, screen_height = self._screen_size
        new_x1 = min(max(0, x1 + dx), max(0, screen_width - width))
        new_y1 = min(max(0, y1 + dy), max(0, screen_height - height))
        self._regions[self._selected_name] = [[new_x1, new_y1], [new_x1 + width, new_y1 + height]]
        self._sync_inputs_from_region()
        self._draw_regions()

    def _draw_new_selected_region(self, current: tuple[int, int]) -> None:
        if self._drag_start_screen is None:
            return
        self._set_region_from_points(self._drag_start_screen[0], self._drag_start_screen[1], current[0], current[1])

    def _set_region_from_points(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        x1, x2 = sorted((start_x, end_x))
        y1, y2 = sorted((start_y, end_y))
        if x1 == x2:
            x2 += 1
        if y1 == y2:
            y2 += 1
        self._regions[self._selected_name] = [[x1, y1], [x2, y2]]
        self._sync_inputs_from_region()
        self._draw_regions()

    def _apply_region_entries(self) -> None:
        self._set_region_from_points(
            self.coord_vars["x1"].get(),
            self.coord_vars["y1"].get(),
            self.coord_vars["x2"].get(),
            self.coord_vars["y2"].get(),
        )
