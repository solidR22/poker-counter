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
from misc.custom_types import ConfigDict
from models.config import GUI, THRESHOLDS, reload_config
from models.runtime_status import RuntimeStatus

from .counter_display_window import CounterDisplayWindow
from .region_editor import SettingsPanel


class MasterWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.backend = BackendThread()
        self.runtime_status = RuntimeStatus()
        self.counter_window: CounterDisplayWindow | None = None
        self.status_var = tk.StringVar(value="等待启动")
        self.preview_title_var = tk.StringVar(value="等待调试预览")
        self.preview_zoom_var = tk.StringVar(value="100%")
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._preview_zoom = 1.0

        self._setup_window()
        self._build_layout()
        self.refresh_layout_from_config()
        self._schedule_status_refresh()
        logger.success("主界面已创建")

    def _setup_window(self) -> None:
        self.title("斗地主记牌器")
        self.configure(bg="#edf2f7")
        self.minsize(1040, 760)

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
        root.columnconfigure(0, weight=5)
        root.columnconfigure(1, weight=4)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="斗地主记牌器", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="主界面只保留控制、状态和调试预览。牌数统计会单独显示在一个可移动的小窗口里，尽量不占用打牌区域。",
            style="Sub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.control_tab = ttk.Frame(self.notebook, padding=16, style="App.TFrame")
        self.settings_tab = ttk.Frame(self.notebook, padding=8, style="App.TFrame")
        self.notebook.add(self.control_tab, text="运行")
        self.notebook.add(self.settings_tab, text="设置")
        self._build_control_tab()
        self._build_settings_tab()

    def _build_control_tab(self) -> None:
        self.control_tab.columnconfigure(0, weight=1)
        self.control_tab.columnconfigure(1, weight=1)
        self.control_tab.rowconfigure(1, weight=1)

        hero = ttk.Frame(self.control_tab, style="Card.TFrame", padding=18)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        hero.columnconfigure(0, weight=1)
        ttk.Label(hero, text="运行控制", background="#ffffff", font=("Microsoft YaHei UI", 14, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            hero,
            text="开始记牌后会自动打开独立记牌窗口。你可以把那个窗口拖到牌桌边缘，主界面则留给状态观察和调试。",
            background="#ffffff",
            foreground="#52606d",
            font=("Microsoft YaHei UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(6, 14))

        actions = ttk.Frame(hero, style="Card.TFrame")
        actions.grid(row=2, column=0, sticky="w")
        self.start_button = ttk.Button(actions, text="开始记牌", style="Primary.TButton", command=self._switch_on)
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button = ttk.Button(actions, text="停止记牌", command=self._switch_off, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="打开记牌窗", command=self._open_counter_window).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="调试本地图片", command=self._debug_local_image).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(actions, text="打开设置", command=self.show_settings).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(actions, text="退出", command=self.destroy).grid(row=0, column=5)

        status_card = ttk.LabelFrame(
            self.control_tab,
            text="运行状态",
            style="Section.TLabelframe",
            padding=16,
        )
        status_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        status_card.columnconfigure(0, weight=1)
        status_card.rowconfigure(2, weight=1)
        ttk.Label(status_card, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            status_card,
            text="这里显示识别阶段、地主判断、最近出牌和历史记录。即使把记牌窗口移到旁边，也能在这里跟踪程序状态。",
            background="#ffffff",
            foreground="#52606d",
            font=("Microsoft YaHei UI", 10),
            wraplength=420,
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

        preview_card = ttk.LabelFrame(
            self.control_tab,
            text="调试预览",
            style="Section.TLabelframe",
            padding=16,
        )
        preview_card.grid(row=1, column=1, sticky="nsew")
        preview_card.columnconfigure(0, weight=1)
        preview_card.rowconfigure(2, weight=1)

        preview_header = ttk.Frame(preview_card)
        preview_header.grid(row=0, column=0, sticky="ew")
        preview_header.columnconfigure(0, weight=1)
        ttk.Label(preview_header, textvariable=self.preview_title_var, background="#ffffff").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(preview_header, text="-", width=3, command=lambda: self._change_preview_zoom(0.8)).grid(
            row=0, column=1, padx=(8, 4)
        )
        ttk.Button(preview_header, text="+", width=3, command=lambda: self._change_preview_zoom(1.25)).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(preview_header, text="重置", command=self._reset_preview_zoom).grid(row=0, column=3, padx=(4, 8))
        ttk.Label(preview_header, textvariable=self.preview_zoom_var, background="#ffffff").grid(
            row=0, column=4, sticky="e"
        )

        ttk.Label(
            preview_card,
            text="用于查看识别框、模板匹配结果和本地图片调试输出。",
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

    def _open_counter_window(self) -> None:
        if self.counter_window and self.counter_window.winfo_exists():
            self.counter_window.deiconify()
            self.counter_window.lift()
            self.counter_window.focus_force()
            return
        self.counter_window = CounterDisplayWindow(self)

    def _close_counter_window(self) -> None:
        if self.counter_window and self.counter_window.winfo_exists():
            self.counter_window.destroy()
        self.counter_window = None

    def refresh_layout_from_config(self) -> None:
        reload_config()
        self._setup_window_position(GUI.get("SWITCH", {}))
        if self.counter_window and self.counter_window.winfo_exists():
            self.counter_window.refresh_position()

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

    def _format_cards(self, cards: dict[str, int]) -> str:
        if not cards:
            return "无"
        return " ".join(f"{name}x{count}" for name, count in cards.items())

    def _refresh_runtime_status(self) -> None:
        snapshot = self.runtime_status.snapshot()
        self.status_var.set(f"当前状态：{snapshot['phase']}")
        region_state_names = {"WAIT": "等待", "ACTIVE": "激活", "PASS": "过牌"}

        text_lines = [
            f"阶段：{snapshot['phase']}",
            f"对局状态：{'已开始' if snapshot['game_started'] else '未开始'}",
            f"地主：{snapshot['landlord']}",
            f"当前出牌方：{snapshot['current_player']}",
            f"消息：{snapshot['message']}",
            "",
            "地主置信度：",
        ]
        confidences = snapshot["landlord_confidences"]
        text_lines.extend([f"  {name}: {value}" for name, value in confidences.items()] or ["  无"])
        text_lines.append("")
        text_lines.append("区域状态：")
        region_states = snapshot["region_states"]
        text_lines.extend([f"  {name}: {region_state_names.get(value, value)}" for name, value in region_states.items()] or ["  无"])
        text_lines.append("")
        text_lines.append(f"手牌识别：{self._format_cards(snapshot['my_cards'])}")
        text_lines.append(f"最近出牌：{self._format_cards(snapshot['last_cards'])}")
        text_lines.append("")
        text_lines.append("最近识别历史：")
        history = snapshot.get("recognized_history", [])
        if history:
            for index, record in enumerate(reversed(history[-10:]), start=1):
                text_lines.append(f"  {index}. {record['player']} -> {self._format_cards(record['cards'])}")
        else:
            text_lines.append("  无")

        self.debug_text.configure(state="normal")
        self.debug_text.delete("1.0", tk.END)
        self.debug_text.insert("1.0", "\n".join(text_lines))
        self.debug_text.configure(state="disabled")

        self.preview_title_var.set(f"调试预览：{snapshot['preview_title']}")
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
            self.preview_label.config(image="", text="暂无调试预览", font=("Microsoft YaHei UI", 10))

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
            phase="本地图片调试",
            preview_title=title,
            preview_png=buffer.getvalue(),
            last_cards=cards_result,
            message="已完成本地图片调试",
        )

    def _debug_local_image(self) -> None:
        file_path = filedialog.askopenfilename(
            title="选择一张用于调试的截图",
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp"), ("所有文件", "*.*")],
        )
        if not file_path:
            return

        image_path = Path(file_path)
        image = Image.open(image_path).convert("L")
        array = np.array(image)
        cards, matches = identify_cards_with_matches(array, THRESHOLDS["card"])
        cards_result = {card.value: count for card, count in cards.items()}
        self._render_debug_preview(f"本地图片调试 - {image_path.name}", image, matches, cards_result)
        messagebox.showinfo("调试完成", f"识别结果：{cards_result or '无'}")

    def _switch_on(self) -> None:
        if self.backend.is_running:
            return
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("当前状态：运行中")
        self._open_counter_window()
        self.backend.start()
        logger.info("记牌器已启动")

    def _switch_off(self) -> None:
        if not self.backend.is_running:
            return
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("当前状态：已停止")
        self.backend.terminate()
        self._close_counter_window()
        logger.info("记牌器已停止")

    def destroy(self) -> None:
        if self.backend.is_running:
            self.backend.terminate()
        self._close_counter_window()
        super().destroy()

    def delayed_destroy(self) -> None:
        self.after(1000, self.destroy)

    def confirm_stop_before_edit(self) -> bool:
        if not self.backend.is_running:
            return True
        messagebox.showinfo("请先停止记牌", "运行中不能直接修改配置，请先停止记牌后再编辑。")
        return False
