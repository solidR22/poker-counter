"""
主控制窗口。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk
from loguru import logger

from core.backend_thread import BackendThread
from functions.match_template import identify_cards_with_matches
from functions.windows_offset import calculate_offset
from misc.custom_types import ConfigDict, WindowsType
from models.config import GUI, THRESHOLDS, reload_config
from models.runtime_status import RuntimeStatus

from .counter_window import CounterWindow
from .region_editor import SettingsPanel


class MasterWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.backend = BackendThread()
        self.runtime_status = RuntimeStatus()
        self.windows: list[CounterWindow] = []
        self.status_var = tk.StringVar(value="状态：未启动")
        self.preview_title_var = tk.StringVar(value="识别预览：等待识别")
        self.preview_zoom_var = tk.StringVar(value="100%")
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._preview_zoom = 1.0

        self._setup_window()
        self._build_layout()
        self.refresh_layout_from_config()
        self._schedule_status_refresh()
        logger.success("主控制窗口已创建")

    def _setup_window(self) -> None:
        self.title("斗地主记牌器")
        self.configure(bg="#edf2f7")
        self.minsize(1240, 780)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#edf2f7")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#edf2f7", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Sub.TLabel", background="#edf2f7", foreground="#52606d", font=("Microsoft YaHei UI", 10))
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Status.TLabel", background="#ffffff", font=("Microsoft YaHei UI", 11))
        style.configure("Section.TLabelframe", background="#ffffff")
        style.configure("Section.TLabelframe.Label", background="#ffffff", font=("Microsoft YaHei UI", 10, "bold"))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="斗地主记牌器", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="在同一个窗口里启动记牌、看识别状态、调全部参数。", style="Sub.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )

        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.control_tab = ttk.Frame(self.notebook, padding=16, style="App.TFrame")
        self.settings_tab = ttk.Frame(self.notebook, padding=8, style="App.TFrame")
        self.notebook.add(self.control_tab, text="记牌器")
        self.notebook.add(self.settings_tab, text="参数设置")
        self._build_control_tab()
        self._build_settings_tab()

    def _build_control_tab(self) -> None:
        self.control_tab.columnconfigure(0, weight=3)
        self.control_tab.columnconfigure(1, weight=2)
        self.control_tab.rowconfigure(1, weight=1)

        hero = ttk.Frame(self.control_tab, style="Card.TFrame", padding=18)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        hero.columnconfigure(0, weight=1)
        ttk.Label(hero, text="当前操作", background="#ffffff", font=("Microsoft YaHei UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            hero,
            text="先在“参数设置”中框选头像区、出牌区和手牌区，再回到这里启动记牌。",
            background="#ffffff",
            foreground="#52606d",
            font=("Microsoft YaHei UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(6, 14))

        actions = ttk.Frame(hero, style="Card.TFrame")
        actions.grid(row=2, column=0, sticky="w")
        self.start_button = ttk.Button(actions, text="打开记牌器", style="Primary.TButton", command=self._switch_on)
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button = ttk.Button(actions, text="关闭记牌器", command=self._switch_off, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="本地图像调试", command=self._debug_local_image).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="切到参数设置", command=self.show_settings).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(actions, text="退出软件", command=self.destroy).grid(row=0, column=4)

        status_card = ttk.LabelFrame(self.control_tab, text="运行状态", style="Section.TLabelframe", padding=16)
        status_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        status_card.columnconfigure(0, weight=1)
        status_card.rowconfigure(2, weight=1)
        ttk.Label(status_card, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            status_card,
            text="这里会实时显示识别阶段、最近结果、成功历史和本地图像调试结果。",
            background="#ffffff",
            foreground="#52606d",
            font=("Microsoft YaHei UI", 10),
            wraplength=460,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.debug_text = tk.Text(
            status_card,
            height=18,
            wrap="word",
            font=("Consolas", 10),
            bg="#f8fafc",
            relief="solid",
            borderwidth=1,
        )
        self.debug_text.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self.debug_text.insert("1.0", "等待启动")
        self.debug_text.configure(state="disabled")

        preview_card = ttk.LabelFrame(self.control_tab, text="识别预览图", style="Section.TLabelframe", padding=16)
        preview_card.grid(row=1, column=1, sticky="nsew")
        preview_card.columnconfigure(0, weight=1)
        preview_card.rowconfigure(2, weight=1)

        preview_header = ttk.Frame(preview_card)
        preview_header.grid(row=0, column=0, sticky="ew")
        preview_header.columnconfigure(0, weight=1)
        ttk.Label(preview_header, textvariable=self.preview_title_var, background="#ffffff").grid(row=0, column=0, sticky="w")
        ttk.Button(preview_header, text="-", width=3, command=lambda: self._change_preview_zoom(0.8)).grid(row=0, column=1, padx=(8, 4))
        ttk.Button(preview_header, text="+", width=3, command=lambda: self._change_preview_zoom(1.25)).grid(row=0, column=2, padx=4)
        ttk.Button(preview_header, text="重置", command=self._reset_preview_zoom).grid(row=0, column=3, padx=(4, 8))
        ttk.Label(preview_header, textvariable=self.preview_zoom_var, background="#ffffff").grid(row=0, column=4, sticky="e")

        ttk.Label(
            preview_card,
            text="可用按钮或鼠标滚轮放大缩小预览图。",
            background="#ffffff",
            foreground="#52606d",
            font=("Microsoft YaHei UI", 9),
        ).grid(row=1, column=0, sticky="w", pady=(8, 10))

        self.preview_label = tk.Label(preview_card, bg="#f8fafc", relief="solid", borderwidth=1)
        self.preview_label.grid(row=2, column=0, sticky="nsew")
        self.preview_label.bind("<MouseWheel>", self._on_preview_mousewheel)  # type: ignore[override]

    def _build_settings_tab(self) -> None:
        self.settings_tab.columnconfigure(0, weight=1)
        self.settings_tab.rowconfigure(0, weight=1)
        self.settings_panel = SettingsPanel(self.settings_tab, on_saved=self.refresh_layout_from_config)
        self.settings_panel.grid(row=0, column=0, sticky="nsew")

    def refresh_layout_from_config(self) -> None:
        reload_config()
        self._setup_window_position(GUI.get("SWITCH", {}))
        for window in list(self.windows):
            if window.winfo_exists():
                window.refresh_position()

    def _setup_window_position(self, config: ConfigDict) -> None:
        self.update_idletasks()
        x_offset, y_offset = calculate_offset(
            self.winfo_width(),
            self.winfo_height(),
            config.get("OFFSET_X"),
            config.get("OFFSET_Y"),
            config.get("CENTER_X"),
            config.get("CENTER_Y"),
        )
        self.geometry(f"+{x_offset}+{y_offset}")

    def show_settings(self) -> None:
        self.notebook.select(self.settings_tab)

    def _change_preview_zoom(self, factor: float) -> None:
        self._preview_zoom = min(4.0, max(0.25, self._preview_zoom * factor))
        self.preview_zoom_var.set(f"{int(self._preview_zoom * 100)}%")
        self._refresh_runtime_status()

    def _reset_preview_zoom(self) -> None:
        self._preview_zoom = 1.0
        self.preview_zoom_var.set("100%")
        self._refresh_runtime_status()

    def _on_preview_mousewheel(self, event: tk.Event) -> None:  # type: ignore[override]
        self._change_preview_zoom(1.1 if event.delta > 0 else 0.9)

    def _schedule_status_refresh(self) -> None:
        self._refresh_runtime_status()
        self.after(300, self._schedule_status_refresh)

    def _refresh_runtime_status(self) -> None:
        snapshot = self.runtime_status.snapshot()
        self.status_var.set(f"状态：{snapshot['phase']}")
        region_state_names = {"WAIT": "等待", "ACTIVE": "可识别", "PASS": "不出"}

        text_lines = [
            f"阶段：{snapshot['phase']}",
            f"开局判定：{'已开始' if snapshot['game_started'] else '未开始'}",
            f"地主：{snapshot['landlord']}",
            f"当前轮到：{snapshot['current_player']}",
            f"提示：{snapshot['message']}",
            "",
            "地主置信度：",
        ]
        confidences = snapshot["landlord_confidences"]
        text_lines.extend([f"  {name}: {value}" for name, value in confidences.items()] or ["  暂无"])
        text_lines.append("")
        text_lines.append("出牌区状态：")
        region_states = snapshot["region_states"]
        text_lines.extend([f"  {name}: {region_state_names.get(value, value)}" for name, value in region_states.items()] or ["  暂无"])
        text_lines.append("")
        text_lines.append(f"我的手牌识别：{snapshot['my_cards'] or '暂无'}")
        text_lines.append(f"最近一次出牌识别：{snapshot['last_cards'] or '暂无'}")
        text_lines.append("")
        text_lines.append("识别成功历史：")
        history = snapshot.get("recognized_history", [])
        if history:
            for index, record in enumerate(reversed(history[-10:]), start=1):
                text_lines.append(f"  {index}. {record['player']} -> {record['cards']}")
        else:
            text_lines.append("  暂无")

        self.debug_text.configure(state="normal")
        self.debug_text.delete("1.0", tk.END)
        self.debug_text.insert("1.0", "\n".join(text_lines))
        self.debug_text.configure(state="disabled")

        self.preview_title_var.set(f"识别预览：{snapshot['preview_title']}")
        preview_png = snapshot.get("preview_png")
        if preview_png:
            image = Image.open(BytesIO(preview_png))
            zoomed = image.resize(
                (max(1, int(image.width * self._preview_zoom)), max(1, int(image.height * self._preview_zoom))),
                Image.Resampling.NEAREST,
            )
            self._preview_photo = ImageTk.PhotoImage(zoomed)
            self.preview_label.config(image=self._preview_photo, text="")
        else:
            self.preview_label.config(image="", text="暂无图像", font=("Microsoft YaHei UI", 10))

    def _render_debug_preview(
        self,
        title: str,
        image: Image.Image,
        matches: list[dict[str, int | float | str]],
        cards_result: dict[str, int],
    ) -> None:
        preview = image.convert("RGB")
        draw = ImageDraw.Draw(preview)
        for match in matches:
            x = int(match["x"])
            y = int(match["y"])
            w = int(match["w"])
            h = int(match["h"])
            label = str(match["label"])
            confidence = float(match["confidence"])
            scale = match.get("scale")
            draw.rectangle((x, y, x + w, y + h), outline="#ff3b30", width=2)
            note = f"{label} {confidence:.2f}"
            if scale is not None:
                note += f" x{scale}"
            draw.text((x, max(0, y - 14)), note, fill="#ffd60a")

        max_width = 420
        if preview.width > max_width:
            ratio = max_width / preview.width
            preview = preview.resize((int(preview.width * ratio), int(preview.height * ratio)))

        buffer = BytesIO()
        preview.save(buffer, format="PNG")
        self.runtime_status.update(
            phase="本地图像调试",
            preview_title=title,
            preview_png=buffer.getvalue(),
            last_cards=cards_result,
            message="已完成本地图像调试识别",
        )

    def _debug_local_image(self) -> None:
        file_path = filedialog.askopenfilename(
            title="选择要调试的本地图像",
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp"), ("所有文件", "*.*")],
        )
        if not file_path:
            return

        image_path = Path(file_path)
        image = Image.open(image_path).convert("L")
        array = np.array(image)
        cards, matches = identify_cards_with_matches(array, THRESHOLDS["card"])
        cards_result = {card.value: count for card, count in cards.items()}
        self._render_debug_preview(f"本地图像调试：{image_path.name}", image, matches, cards_result)
        messagebox.showinfo("调试完成", f"识别结果：{cards_result or '暂无'}")

    def _switch_on(self) -> None:
        if self.backend.is_running:
            return
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("状态：正在运行")
        if GUI["MAIN"].get("DISPLAY", True):
            self.windows.append(CounterWindow(WindowsType.MAIN, self))
        if GUI["LEFT"].get("DISPLAY", True):
            self.windows.append(CounterWindow(WindowsType.LEFT, self))
        if GUI["RIGHT"].get("DISPLAY", True):
            self.windows.append(CounterWindow(WindowsType.RIGHT, self))
        self.backend.start()
        logger.info("记牌器已启动")

    def _switch_off(self) -> None:
        if not self.backend.is_running and not self.windows:
            return
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("状态：已停止")
        self.backend.terminate()
        for window in list(self.windows):
            if window.winfo_exists():
                window.destroy()
        self.windows = []
        logger.info("记牌器已停止")

    def destroy(self) -> None:
        if self.backend.is_running:
            self.backend.terminate()
        for window in list(self.windows):
            if window.winfo_exists():
                window.destroy()
        super().destroy()

    def delayed_destroy(self) -> None:
        self.after(1000, self.destroy)

    def confirm_stop_before_edit(self) -> bool:
        if not self.backend.is_running:
            return True
        messagebox.showinfo("请先停止记牌", "正在记牌时不能修改参数，请先关闭记牌器。")
        return False
