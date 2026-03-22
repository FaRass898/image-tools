# image_tools.py — Keep Color + Strip Fill
# Объединённый инструмент с тёмным UI, вкладками, работает на малых экранах.

import os, sys, math, warnings, threading, urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import numpy as np

VERSION      = "1.0.0"
GITHUB_USER  = "FaRass898"
GITHUB_REPO  = "improj-viewer"
VERSION_URL  = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/image_tools_version.txt"
UPDATE_URL   = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/image_tools.py"

Image.MAX_IMAGE_PIXELS = None
warnings.simplefilter("ignore", Image.DecompressionBombWarning)

APP_TITLE = "Image Tools"

# ── palette ──────────────────────────────────────────────────────────────────
# Стиль: «Промышленный аналитик» — тёмно-стальной с янтарными акцентами
BG      = "#10121a"   # глубокий фон
PANEL   = "#181c28"   # панели
PANEL2  = "#0e1018"   # фон канваса
BTN     = "#1f2538"   # кнопки по умолчанию
BTN_H   = "#2a3350"   # кнопки hover
ACCENT  = "#e8a230"   # янтарный акцент (основной)
ACC_H   = "#f5b84a"   # янтарный hover
ACC2    = "#3fcf8e"   # зелёный (успех / применить)
ACC2_H  = "#52e0a0"   # зелёный hover
DANGER  = "#e05555"   # красный
FG      = "#dce3f5"   # основной текст
FG2     = "#4e5a7a"   # приглушённый
FG3     = "#8898c0"   # средний
TROUGH  = "#1a1e2e"   # трек слайдера
BORDER  = "#232840"   # границы
SEL     = "#1a2850"   # выделение
CANVAS  = "#080a12"   # холст

# ── app ───────────────────────────────────────────────────────────────────────
# ── app ───────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x700")
        self.minsize(820, 560)
        try:
            ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_tools_icon.ico")
            if os.path.exists(ico): self.iconbitmap(ico)
        except: pass
        self.configure(bg=BG)
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except: pass

        # image
        self.orig_img   = None
        self.result_img = None
        self.tk_img     = None
        self.levels     = []

        # common
        self.eye_on   = False
        self.sel_rgb  = None
        self.var_tol  = tk.IntVar(value=30)

        # viewport
        self.zoom = 1.0
        self.min_z, self.max_z = 0.05, 8.0
        self.ox = self.oy = 0.0
        self.var_zoom = tk.IntVar(value=100)
        self._pan_last = None

        # Keep Color
        self.var_kc_pre = tk.BooleanVar(value=False)
        self.var_thin   = tk.StringVar(value="none")
        self.var_minw   = tk.IntVar(value=0)
        self.var_crop   = tk.BooleanVar(value=False)
        self.var_tile   = tk.IntVar(value=2048)

        # Strip Fill
        self.var_sf_pre   = tk.BooleanVar(value=True)
        self.var_dir      = tk.StringVar(value="left")
        self.var_extra    = tk.IntVar(value=0)
        self.var_sf_mode  = tk.StringVar(value="copy_left")
        self.var_sf_thick = tk.IntVar(value=3)
        self.var_x1       = tk.IntVar(value=-1)
        self.var_x2       = tk.IntVar(value=-1)
        self._sf_picking_x = 0
        self.ix_sel = self.iy_sel = None

        # Fix TIFF
        self.fix_files  = []   # список файлов для починки
        self.var_fix_fmt = tk.StringVar(value="tiff")  # формат вывода
        self.var_fix_comp = tk.StringVar(value="lzw")  # сжатие

        self._styles()
        self._build_topbar()
        self._build_tabs()
        self._build_canvas()
        self._build_status()

        self.bind("<e>",      lambda e: self.toggle_eye())
        self.bind("<Escape>", lambda e: self._eye_off())
        self.bind("<r>",      lambda e: self.reset_result())
        self.bind("<f>",      lambda e: self.zoom_fit())
        # Проверка обновлений в фоне
        threading.Thread(target=self._check_update_bg, daemon=True).start()

    # ── widget helpers ────────────────────────────────────────────────────────
    def _check_update_bg(self):
        """Тихая проверка обновлений при запуске."""
        try:
            req = urllib.request.Request(VERSION_URL,
                  headers={"User-Agent": "image-tools"})
            with urllib.request.urlopen(req, timeout=5) as r:
                latest = r.read().decode().strip()
            if latest and latest != VERSION:
                self.after(0, lambda v=latest: self._show_update_badge(v))
        except Exception:
            pass

    def _show_update_badge(self, latest):
        """Показывает кнопку обновления в статус-баре."""
        self.status.config(
            text=f"  🔔 Доступно обновление {latest}  (текущая {VERSION})  —  нажми для установки",
            fg=ACC2, cursor="hand2")
        self.status.bind("<Button-1>", lambda e, v=latest: self._do_update(v))

    def _do_update(self, latest):
        self.status.unbind("<Button-1>")
        self.status.config(fg=FG2, cursor="arrow")
        if not messagebox.askyesno("Обновление",
            "Доступна версия {}\nТекущая: {}\n\nСкачать и установить?\n(программа попросит перезапуститься)".format(latest, VERSION)):
            return
        win = tk.Toplevel(self); win.title("Обновление")
        win.geometry("340x100"); win.configure(bg=BG)
        win.resizable(False, False); win.grab_set()
        tk.Label(win, text="Скачиваем обновление...",
                 bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(pady=(20,8))
        pb = ttk.Progressbar(win, mode="indeterminate", length=280)
        pb.pack(padx=30); pb.start(10)

        def _dl():
            try:
                req = urllib.request.Request(UPDATE_URL,
                      headers={"User-Agent": "image-tools"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                cur = os.path.abspath(__file__)
                import shutil; shutil.copy2(cur, cur + ".backup")
                with open(cur, "wb") as f: f.write(data)
                self.after(0, lambda: _done(True))
            except Exception as e:
                self.after(0, lambda err=str(e): _done(False, err))

        def _done(ok, err=""):
            pb.stop(); win.destroy()
            if ok:
                messagebox.showinfo("Готово",
                    "Обновление установлено!\nЗакрой и снова открой программу.")
                self.set_st("  Обновление " + latest + " установлено — перезапусти программу")
            else:
                messagebox.showerror("Ошибка", "Не удалось скачать:\n" + str(err))

        threading.Thread(target=_dl, daemon=True).start()

    def _styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook",
                    background=BG, borderwidth=0, tabmargins=[0,0,0,0])
        s.configure("TNotebook.Tab",
                    background=BTN, foreground=FG2,
                    padding=[22, 9], font=("Segoe UI", 10, "bold"))
        s.map("TNotebook.Tab",
              background=[("selected", PANEL), ("active", BTN_H)],
              foreground=[("selected", ACCENT), ("active", FG)])
        s.configure("TFrame", background=PANEL)

    def _btn(self, p, text, cmd, kind="default", w=None, big=False):
        """kind: default | accent | green | danger"""
        cfg = {
            "default": (BTN,    FG,    BTN_H,  FG),
            "accent":  (ACCENT, "#0a0c14", ACC_H, "#0a0c14"),
            "green":   (ACC2,   "#0a0c14", ACC2_H, "#0a0c14"),
            "danger":  (DANGER, "#fff",  "#ff7070", "#fff"),
        }.get(kind, (BTN, FG, BTN_H, FG))
        bg, fg, hbg, hfg = cfg
        pad_x = 16 if big else 12
        pad_y = 10 if big else 6
        font_size = 10 if big else 9
        b = tk.Button(p, text=text, command=cmd,
                      bg=bg, fg=fg,
                      activebackground=hbg, activeforeground=hfg,
                      relief="flat", padx=pad_x, pady=pad_y,
                      font=("Segoe UI", font_size, "bold"), cursor="hand2", bd=0)
        if w: b.config(width=w)
        b.bind("<Enter>", lambda e, b=b, hv=hbg, hf=hfg: b.config(bg=hv, fg=hf))
        b.bind("<Leave>", lambda e, b=b, ob=bg, of=fg: b.config(bg=ob, fg=of))
        return b

    def _lbl(self, p, text, fg=None, big=False, **kw):
        fs = 10 if big else 9
        return tk.Label(p, text=text, bg=PANEL, fg=fg or FG3,
                        font=("Segoe UI", fs), **kw)

    def _scl(self, p, var, lo, hi, length=120, cmd=None):
        return tk.Scale(p, from_=lo, to=hi, variable=var,
                        orient="horizontal", length=length, showvalue=0,
                        bg=PANEL, fg=FG, troughcolor=TROUGH,
                        highlightthickness=0, sliderlength=14, width=6,
                        **({"command": cmd} if cmd else {}))

    def _chk(self, p, text, var, cmd=None):
        return tk.Checkbutton(p, text=text, variable=var,
                              bg=PANEL, fg=FG, selectcolor=SEL,
                              activebackground=PANEL, activeforeground=FG,
                              font=("Segoe UI", 9), bd=0,
                              **({"command": cmd} if cmd else {}))

    def _rad(self, p, text, var, val, cmd=None):
        return tk.Radiobutton(p, text=text, variable=var, value=val,
                              bg=PANEL, fg=FG, selectcolor=SEL,
                              activebackground=PANEL, activeforeground=FG,
                              font=("Segoe UI", 9), bd=0,
                              **({"command": cmd} if cmd else {}))

    def _sep(self, p):
        tk.Frame(p, width=1, bg=BORDER).pack(side="left", fill="y", padx=6, pady=6)

    def _val_lbl(self, p, var, w=3):
        return tk.Label(p, textvariable=var, width=w,
                        bg=PANEL, fg=ACCENT, font=("Segoe UI", 9, "bold"))

    # ── top bar ───────────────────────────────────────────────────────────────
    def _build_topbar(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="x", side="top")

        # Заголовок
        hdr = tk.Frame(outer, bg="#0b0d16", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="  IMAGE TOOLS",
                 bg="#0b0d16", fg=ACCENT,
                 font=("Consolas", 13, "bold")).pack(side="left", padx=16, pady=10)
        tk.Label(hdr, text="Keep Color  +  Strip Fill",
                 bg="#0b0d16", fg=FG2,
                 font=("Segoe UI", 8)).pack(side="left", pady=12)
        tk.Label(hdr, text="v"+VERSION,
                 bg="#0b0d16", fg=FG2, font=("Segoe UI", 8)
                 ).pack(side="right", padx=16)
        tk.Frame(outer, height=1, bg=BORDER).pack(fill="x")

        # Тулбар
        row = tk.Frame(outer, bg=PANEL)
        row.pack(fill="x")

        file_box = tk.Frame(row, bg=PANEL)
        file_box.pack(side="left", padx=8, pady=8)
        self._btn(file_box, "  Открыть", self.open_image, big=True
                  ).pack(side="left", padx=(0,4))
        self._btn(file_box, "  Сохранить", self.save_image, kind="green", big=True
                  ).pack(side="left", padx=(0,4))
        self._btn(file_box, "  Сброс", self.reset_result, big=True
                  ).pack(side="left")
        self._sep(row)

        eye_box = tk.Frame(row, bg=PANEL)
        eye_box.pack(side="left", pady=8)
        self.btn_eye = self._btn(eye_box, "  Пипетка  [E]",
                                  self.toggle_eye, big=True)
        self.btn_eye.pack(side="left", padx=(0,6))
        self.swatch = tk.Frame(eye_box, width=96, height=38,
                               bg=BTN, relief="flat", bd=0)
        self.swatch.pack(side="left")
        self.swatch.pack_propagate(False)
        self.swatch_lbl = tk.Label(self.swatch, text=" нет цвета",
                                   bg=BTN, fg=FG2, font=("Segoe UI", 8))
        self.swatch_lbl.pack(fill="both", expand=True)
        self._sep(row)

        tol_box = tk.Frame(row, bg=PANEL)
        tol_box.pack(side="left", pady=8)
        tk.Label(tol_box, text="ДОПУСК", bg=PANEL, fg=FG2,
                 font=("Consolas", 7, "bold")).pack(anchor="w")
        tr = tk.Frame(tol_box, bg=PANEL); tr.pack()
        self._scl(tr, self.var_tol, 0, 128, 110,
                  cmd=lambda v: self._tol_changed()).pack(side="left")
        self._val_lbl(tr, self.var_tol, 3).pack(side="left", padx=4)
        self._sep(row)

        zoom_box = tk.Frame(row, bg=PANEL)
        zoom_box.pack(side="left", pady=8)
        tk.Label(zoom_box, text="МАСШТАБ", bg=PANEL, fg=FG2,
                 font=("Consolas", 7, "bold")).pack(anchor="w")
        zr = tk.Frame(zoom_box, bg=PANEL); zr.pack()
        self._scl(zr, self.var_zoom, 5, 800, 110,
                  cmd=self._zoom_scale).pack(side="left")
        self.zoom_lbl = tk.Label(zr, text="100%", width=5,
                                 bg=PANEL, fg=ACCENT,
                                 font=("Consolas", 10, "bold"))
        self.zoom_lbl.pack(side="left", padx=4)
        self._btn(zr, "Вписать", self.zoom_fit).pack(side="left", padx=(4,2))
        self._btn(zr, "1:1", lambda: self._set_zoom(100)).pack(side="left", padx=2)

        tk.Label(row, text="ПКМ — панорама  ·  Scroll — зум  ·  R — сброс  ·  F — вписать",
                 bg=PANEL, fg=FG2, font=("Segoe UI", 8)).pack(side="right", padx=14)
        tk.Frame(outer, height=1, bg=BORDER).pack(fill="x")

    # ── tabs ──────────────────────────────────────────────────────────────────
    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="x", side="top")
        fkc = ttk.Frame(self.nb)
        self.nb.add(fkc, text="    ОСТАВИТЬ ЦВЕТ    ")
        self._tab_kc(fkc)
        fsf = ttk.Frame(self.nb)
        self.nb.add(fsf, text="    ЗАЛИВКА ОТ КРАЯ    ")
        self._tab_sf(fsf)
        ffix = ttk.Frame(self.nb)
        self.nb.add(ffix, text="    ПОЧИНИТЬ TIFF    ")
        self._tab_fix(ffix)
        tk.Frame(self, height=1, bg=BORDER).pack(fill="x")

    def _tab_kc(self, f):
        row = tk.Frame(f, bg=PANEL, pady=8)
        row.pack(fill="x", padx=12)
        tk.Label(row, text="ТОНКИЕ ЛИНИИ:", bg=PANEL, fg=FG2,
                 font=("Consolas", 8, "bold")).pack(side="left", padx=(0,8))
        for txt, val in [("не трогать","none"),("убрать N","remove"),("оставить N","keep")]:
            self._rad(row, txt, self.var_thin, val,
                      cmd=lambda: self._kc_redraw()).pack(side="left", padx=3)
        self._lbl(row, "  N:").pack(side="left", padx=(8,0))
        self._scl(row, self.var_minw, 0, 20, 80,
                  cmd=lambda v: self._kc_redraw()).pack(side="left", padx=4)
        self._val_lbl(row, self.var_minw, 2).pack(side="left")
        self._sep(row)
        self._chk(row, "Обрезать при сохранении", self.var_crop).pack(side="left", padx=6)
        self._chk(row, "Превью", self.var_kc_pre, cmd=self.redraw).pack(side="left", padx=6)
        self._sep(row)
        self.btn_kc = self._btn(row, "  ПРИМЕНИТЬ", self.kc_apply, kind="green", big=True)
        self.btn_kc.pack(side="left", padx=6)
        self.btn_kc.config(state="disabled")
        tk.Label(row, text="  Плитка:", bg=PANEL, fg=FG2,
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Spinbox(row, from_=256, to=8192, increment=256, width=5,
                   textvariable=self.var_tile,
                   bg=BTN, fg=FG, buttonbackground=BTN_H,
                   font=("Segoe UI", 9)).pack(side="left", padx=4)

    def _tab_sf(self, f):
        row = tk.Frame(f, bg=PANEL, pady=8)
        row.pack(fill="x", padx=12)

        # Статус выбранного цвета/точки
        self.sf_color_lbl = tk.Label(row, text="цвет не выбран",
            bg="#0d0f18", fg=FG2, font=("Segoe UI", 8),
            width=16, relief="flat", padx=6, pady=4)
        self.sf_color_lbl.pack(side="left", padx=(0,6))

        # Толеранс
        tk.Label(row, text="Толеранс:", bg=PANEL, fg=FG2,
                 font=("Segoe UI", 8)).pack(side="left")
        self._scl(row, self.var_tol, 0, 128, 80,
                  cmd=lambda v: self._sf_redraw()).pack(side="left", padx=2)
        self._val_lbl(row, self.var_tol, 3).pack(side="left", padx=(0,8))

        # Ограничить по X
        self.btn_pick_x = self._btn(row, "Ограничить по X (2 клика)",
                                     self._sf_start_pick_x, kind="accent", big=True)
        self.btn_pick_x.pack(side="left", padx=(0,8))
        self.var_x1 = tk.IntVar(value=-1)
        self.var_x2 = tk.IntVar(value=-1)
        self._sf_picking_x = 0  # 0=нет, 1=ждём первый клик, 2=ждём второй

        # Толщина ±px
        tk.Label(row, text="Толщина ±px:", bg=PANEL, fg=FG2,
                 font=("Segoe UI", 8)).pack(side="left")
        self.var_sf_thick = tk.IntVar(value=3)
        self._scl(row, self.var_sf_thick, 0, 30, 70,
                  cmd=lambda v: self._sf_redraw()).pack(side="left", padx=2)
        self._val_lbl(row, self.var_sf_thick, 2).pack(side="left", padx=(0,8))

        # Режим
        tk.Label(row, text="Режим:", bg=PANEL, fg=FG2,
                 font=("Segoe UI", 8)).pack(side="left", padx=(0,4))
        self.var_sf_mode = tk.StringVar(value="copy_left")
        for txt, val in [("копировать слева","copy_left"),
                          ("копировать справа","copy_right"),
                          ("покрасить белым","white")]:
            self._rad(row, txt, self.var_sf_mode, val,
                      cmd=lambda: self._sf_redraw()).pack(side="left", padx=2)

        # Предпросмотр
        self._chk(row, "Предпросмотр (только видимая область)",
                  self.var_sf_pre, cmd=self.redraw).pack(side="left", padx=8)

        # Применить
        self._btn(row, "ПРИМЕНИТЬ ко всей картинке",
                  self.sf_full, kind="green", big=True
                  ).pack(side="left", padx=(8,0))

        # Инфо строка
        self.sf_info = tk.Label(f,
            text="  Кликни на изображение чтобы выбрать цвет линии. "
                 "Затем нажми «Ограничить по X» и кликни 2 раза чтобы задать границы.",
            bg=PANEL, fg=FG2, font=("Segoe UI", 8))
        self.sf_info.pack(anchor="w", padx=12, pady=(0,4))
    def _tab_fix(self, f):
        # Верхняя строка — кнопки и настройки
        row = tk.Frame(f, bg=PANEL, pady=8)
        row.pack(fill="x", padx=12)

        tk.Label(row, text="ФОРМАТ:", bg=PANEL, fg=FG2,
                 font=("Consolas", 8, "bold")).pack(side="left", padx=(0,6))
        for txt, val in [("TIFF","tiff"), ("PNG","png"), ("JPEG","jpg")]:
            self._rad(row, txt, self.var_fix_fmt, val).pack(side="left", padx=3)
        self._sep(row)

        tk.Label(row, text="СЖАТИЕ:", bg=PANEL, fg=FG2,
                 font=("Consolas", 8, "bold")).pack(side="left", padx=(0,6))
        for txt, val in [("LZW","lzw"), ("Без сжатия","none"), ("ZIP","zip")]:
            self._rad(row, txt, self.var_fix_comp, val).pack(side="left", padx=3)
        self._sep(row)

        self._btn(row, "  Добавить файлы", self.fix_add_files, big=True
                  ).pack(side="left", padx=(0,4))
        self._btn(row, "  Починить все", self.fix_run_all, kind="green", big=True
                  ).pack(side="left", padx=(0,4))
        self._btn(row, "Очистить список", self.fix_clear
                  ).pack(side="left")

        # Список файлов
        list_frame = tk.Frame(f, bg=PANEL)
        list_frame.pack(fill="x", padx=12, pady=(4,8))

        # Заголовок таблицы
        hdr = tk.Frame(list_frame, bg="#0f1117", height=24)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        for text, w in [("Файл", 40), ("Размер", 12), ("Статус", 20)]:
            tk.Label(hdr, text=text, bg="#0f1117", fg=FG2,
                     font=("Consolas", 8, "bold"), width=w, anchor="w"
                     ).pack(side="left", padx=6)

        wrap = tk.Frame(list_frame, bg=PANEL)
        wrap.pack(fill="x")
        self.fix_listbox = tk.Listbox(wrap,
            bg="#0d0f18", fg=FG, selectbackground="#1f2d50",
            selectforeground=ACCENT, relief="flat", bd=0,
            font=("Consolas", 9), activestyle="none", height=6)
        sb = tk.Scrollbar(wrap, command=self.fix_listbox.yview,
                          bg=PANEL, troughcolor=TROUGH, bd=0, relief="flat")
        self.fix_listbox.configure(yscrollcommand=sb.set)
        self.fix_listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Инфо строка
        self.fix_info = tk.Label(list_frame,
            text="Добавь .tif/.tiff файлы — программа исправит повреждения и пересохранит",
            bg=PANEL, fg=FG2, font=("Segoe UI", 8))
        self.fix_info.pack(anchor="w", pady=(4,0))

    def fix_add_files(self):
        paths = filedialog.askopenfilenames(
            title="Выбери TIFF файлы",
            filetypes=[("TIFF","*.tif *.tiff"),("Все изображения","*.tif *.tiff *.png *.jpg"),("All","*.*")])
        if not paths: return
        added = 0
        for p in paths:
            if p not in self.fix_files:
                self.fix_files.append(p)
                size = os.path.getsize(p) / 1024 / 1024
                name = os.path.basename(p)
                self.fix_listbox.insert("end",
                    f"  {name:<40}  {size:6.1f} МБ   ожидает...")
                added += 1
        self.fix_info.config(text=f"Добавлено {added} файлов. Всего: {len(self.fix_files)}")

    def fix_clear(self):
        self.fix_files.clear()
        self.fix_listbox.delete(0, "end")
        self.fix_info.config(text="Список очищен")

    def fix_run_all(self):
        if not self.fix_files:
            messagebox.showwarning("", "Сначала добавь файлы"); return
        fmt  = self.var_fix_fmt.get()
        comp = self.var_fix_comp.get()
        ok = err = 0
        for i, path in enumerate(self.fix_files):
            self.fix_listbox.delete(i)
            name = os.path.basename(path)
            try:
                img = self._fix_open_tiff(path)
                if img is None:
                    raise ValueError("Не удалось открыть файл")
                # Папка рядом с файлом
                folder = os.path.dirname(path)
                base   = os.path.splitext(name)[0]
                out_path = os.path.join(folder, f"{base}_fixed.{fmt}")
                # Сохраняем
                save_kwargs = {}
                if fmt == "tiff":
                    c = {"lzw":"tiff_lzw","zip":"tiff_deflate","none":None}.get(comp)
                    if c: save_kwargs["compression"] = c
                elif fmt == "jpg":
                    save_kwargs["quality"] = 95
                    img = img.convert("RGB")
                img.save(out_path, **save_kwargs)
                size_out = os.path.getsize(out_path)/1024/1024
                self.fix_listbox.insert(i,
                    f"  {name:<40}  {size_out:6.1f} МБ   ✓ сохранён")
                self.fix_listbox.itemconfig(i, fg=ACC2)
                ok += 1
            except Exception as e:
                self.fix_listbox.insert(i,
                    f"  {name:<40}  —        ✗ {str(e)[:40]}")
                self.fix_listbox.itemconfig(i, fg=DANGER)
                err += 1
            self.fix_info.config(text=f"Обработано: {i+1}/{len(self.fix_files)}...")
            self.update_idletasks()
        self.fix_info.config(
            text=f"Готово!  Исправлено: {ok}  |  Ошибок: {err}  |  Файлы сохранены рядом с оригиналом")

    def _fix_open_tiff(self, path):
        """Пробует разные способы открыть повреждённый TIFF."""
        errors = []

        # Способ 1: стандартный Pillow
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                img = Image.open(path)
                img.load()
                return img.convert("RGBA")
        except Exception as e:
            errors.append(f"Pillow: {e}")

        # Способ 2: игнорируем ошибки через LOAD_TRUNCATED
        try:
            from PIL import ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            img = Image.open(path)
            img.load()
            ImageFile.LOAD_TRUNCATED_IMAGES = False
            return img.convert("RGBA")
        except Exception as e:
            errors.append(f"Truncated: {e}")

        # Способ 3: tifffile если установлен
        try:
            import tifffile
            import numpy as np
            arr = tifffile.imread(path)
            if arr.ndim == 2:
                arr = np.stack([arr,arr,arr], axis=2)
            if arr.dtype != np.uint8:
                arr = ((arr - arr.min()) / max(arr.max()-arr.min(),1) * 255).astype(np.uint8)
            return Image.fromarray(arr).convert("RGBA")
        except Exception as e:
            errors.append(f"tifffile: {e}")

        # Способ 4: читаем по частям (tile-based)
        try:
            from PIL import ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            img = Image.open(path)
            W, H = img.size
            out = Image.new("RGBA", (W, H), (255,255,255,255))
            tile_h = 256
            for y in range(0, H, tile_h):
                try:
                    box = (0, y, W, min(H, y+tile_h))
                    tile = img.crop(box)
                    out.paste(tile.convert("RGBA"), (0, y))
                except Exception:
                    pass  # Плохой тайл — оставляем белым
            ImageFile.LOAD_TRUNCATED_IMAGES = False
            return out
        except Exception as e:
            errors.append(f"Tile: {e}")

        raise ValueError(" | ".join(errors[-2:]))

    # ── canvas + status ───────────────────────────────────────────────────────
    def _build_canvas(self):
        self.canvas = tk.Canvas(self, bg=CANVAS, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        cv = self.canvas
        cv.bind("<Button-1>",       self.on_click)
        cv.bind("<MouseWheel>",     self.on_wheel)
        cv.bind("<Button-4>",       lambda e: self._scroll(60))
        cv.bind("<Button-5>",       lambda e: self._scroll(-60))
        cv.bind("<ButtonPress-2>",  self._pan0)
        cv.bind("<B2-Motion>",      self._pan1)
        cv.bind("<ButtonPress-3>",  self._pan0)
        cv.bind("<B3-Motion>",      self._pan1)
        cv.bind("<Configure>",      lambda e: self.redraw())

    def _build_status(self):
        sf = tk.Frame(self, bg="#0b0d16", height=28)
        sf.pack(fill="x", side="bottom"); sf.pack_propagate(False)
        tk.Frame(sf, height=1, bg=BORDER).pack(fill="x", side="top")
        self._st_dot = tk.Label(sf, text="●", bg="#0b0d16", fg=FG2,
                                 font=("Segoe UI", 8))
        self._st_dot.pack(side="left", padx=(10,4))
        self.status = tk.Label(sf, text="Откройте изображение…",
                               anchor="w", bg="#0b0d16", fg=FG2,
                               font=("Segoe UI", 8))
        self.status.pack(side="left", fill="both", expand=True)
        tk.Label(sf, text="Image Tools  v"+VERSION,
                 bg="#0b0d16", fg=FG2, font=("Segoe UI", 8)
                 ).pack(side="right", padx=12)

    def set_st(self, t):
        self.status.config(text=t)
        if hasattr(self, "_st_dot"):
            if "✓" in t or "Сохранено" in t or "применён" in t:
                self._st_dot.config(fg=ACC2)
            elif "…" in t or "плиток" in t:
                self._st_dot.config(fg=ACCENT)
            else:
                self._st_dot.config(fg=FG2)

    # ── file ops ──────────────────────────────────────────────────────────────
    def open_image(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),("All","*.*")])
        if not p: return
        try:
            img = Image.open(p).convert("RGBA"); img.load()
        except Exception as e:
            messagebox.showerror("Ошибка открытия", str(e)); return
        self.orig_img   = img
        self.result_img = None
        self.sel_rgb    = None
        self._swatch(None)
        self.btn_kc.config(state="disabled")
        self._build_mips(img)
        self.zoom = 1.0; self.var_zoom.set(100)
        self.ox = self.oy = 0.0
        self.ix_sel = self.iy_sel = None
        self.sf_info.config(text="  кликни на изображение чтобы задать строку")
        self.redraw()
        self.set_st(f"Открыто: {os.path.basename(p)}  {img.width}×{img.height}")
        self.after(60, self.zoom_fit)

    def save_image(self):
        if self.result_img is None:
            messagebox.showwarning("Сохранение", "Сначала примените инструмент."); return
        p = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG","*.png"),("JPEG","*.jpg *.jpeg"),("All","*.*")])
        if not p: return
        img = self.result_img
        if self.var_crop.get():
            arr = np.array(img)
            m = np.any(arr[...,:3] != 255, 2)
            if m.any():
                ys, xs = np.where(m)
                img = img.crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1))
        try:
            out = img.convert("RGB") if p.lower().endswith((".jpg",".jpeg")) else img
            out.save(p)
            self.set_st(f"Сохранено: {os.path.basename(p)}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def reset_result(self):
        self.result_img = None
        self.redraw()
        self.set_st("Сброс — показан оригинал")

    # ── eyedropper ────────────────────────────────────────────────────────────
    def toggle_eye(self):
        self.eye_on = not self.eye_on
        self.canvas.config(cursor="crosshair" if self.eye_on else "arrow")
        self.btn_eye.config(bg="#2a1e00" if self.eye_on else BTN,
                           fg=ACCENT if self.eye_on else FG)
        self.set_st("👁 Кликни по цвету на изображении" if self.eye_on else "Пипетка ВЫКЛ")

    def _eye_off(self):
        if self.eye_on: self.toggle_eye()

    def _swatch(self, rgb):
        if rgb is None:
            self.swatch.config(bg=BTN)
            self.swatch_lbl.config(text=" нет цвета", bg=BTN, fg=FG2)
        else:
            h = rgb_hex(rgb); lum = .299*rgb[0]+.587*rgb[1]+.114*rgb[2]
            self.swatch.config(bg=h)
            self.swatch_lbl.config(text=h, bg=h, fg="#000" if lum > 140 else "#fff")

    # ── interactions ──────────────────────────────────────────────────────────
    def on_click(self, ev):
        if self.orig_img is None: return

        # Режим выбора X-границ
        if self._sf_picking_x > 0:
            ix, iy = self._c2i_cl(ev.x, ev.y)
            if ix is None: return
            if self._sf_picking_x == 1:
                self.var_x1.set(ix)
                self._sf_picking_x = 2
                self.sf_info.config(
                    text=f"  X1={ix}  |  Клик 2/2: кликни на ПРАВУЮ границу полосы")
            else:
                self.var_x2.set(ix)
                self._sf_picking_x = 0
                self.canvas.config(cursor="arrow")
                self.btn_pick_x.config(bg=BTN, fg=FG)
                x1,x2 = min(self.var_x1.get(),ix), max(self.var_x1.get(),ix)
                self.var_x1.set(x1); self.var_x2.set(x2)
                self.sf_info.config(
                    text=f"  Границы X: {x1} — {x2}  |  Нажми «ПРИМЕНИТЬ»")
                self.set_st(f"X-границы заданы: {x1}..{x2}")
                self._sf_redraw()
            return

        if not self.eye_on:
            self._pan_center(ev.x, ev.y); return
        ix, iy = self._c2i_cl(ev.x, ev.y)
        if ix is None: return
        pix = self.orig_img.getpixel((ix, iy))
        self.sel_rgb = (pix[0], pix[1], pix[2])
        self.ix_sel, self.iy_sel = ix, iy
        self._swatch(self.sel_rgb)
        self.btn_kc.config(state="normal")
        # Обновляем sf_color_lbl если есть
        if hasattr(self, "sf_color_lbl"):
            h = rgb_hex(self.sel_rgb)
            lum = .299*self.sel_rgb[0]+.587*self.sel_rgb[1]+.114*self.sel_rgb[2]
            self.sf_color_lbl.config(bg=h, fg="#000" if lum>140 else "#fff",
                                      text=h)
        self.sf_info.config(
            text=f"  Цвет выбран: {rgb_hex(self.sel_rgb)}  @({ix},{iy})  "
                 f"Теперь нажми «Ограничить по X» или «ПРИМЕНИТЬ»")
        self.set_st(f"Цвет: {rgb_hex(self.sel_rgb)}  RGB{self.sel_rgb}  @({ix},{iy})")
        self.redraw()

    def on_wheel(self, ev):
        up = ev.delta > 0 if hasattr(ev, "delta") else ev.num == 4
        fac = 1.15 if up else 1/1.15
        new_z = max(self.min_z, min(self.max_z, self.zoom*fac))
        bx, by = self._btl()
        ix = (ev.x-bx)/self.zoom; iy = (ev.y-by)/self.zoom
        self.zoom = new_z
        self.var_zoom.set(int(new_z*100))
        self.zoom_lbl.config(text=f"{int(new_z*100)}%")
        bx2, by2 = self._btl()
        self.ox += ev.x-(bx2+ix*new_z)
        self.oy += ev.y-(by2+iy*new_z)
        self.redraw()

    def _scroll(self, dy): self.oy += dy; self.redraw()

    def _pan0(self, ev): self._pan_last = (ev.x, ev.y)
    def _pan1(self, ev):
        if not self._pan_last: return
        self.ox += ev.x-self._pan_last[0]; self.oy += ev.y-self._pan_last[1]
        self._pan_last = (ev.x, ev.y); self.redraw()

    def _pan_center(self, cx, cy):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.ox += cw/2-cx; self.oy += ch/2-cy; self.redraw()

    def _zoom_scale(self, val=None):
        self.zoom = max(self.min_z, min(self.max_z, self.var_zoom.get()/100))
        self.zoom_lbl.config(text=f"{int(self.zoom*100)}%")
        self.redraw()

    def _set_zoom(self, pct):
        self.var_zoom.set(pct); self._zoom_scale()

    def zoom_fit(self):
        if self.orig_img is None: return
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        W, H = self.orig_img.size
        z = min(cw/W, ch/H) * 0.95
        self.zoom = max(self.min_z, min(self.max_z, z))
        self.ox = self.oy = 0.0
        self.var_zoom.set(int(self.zoom*100))
        self.zoom_lbl.config(text=f"{int(self.zoom*100)}%")
        self.redraw()

    # ── coordinates ───────────────────────────────────────────────────────────
    def _btl(self):
        img = self.result_img or self.orig_img
        if img is None: return 0, 0
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        return (int((cw - int(img.width*self.zoom))//2 + self.ox),
                int((ch - int(img.height*self.zoom))//2 + self.oy))

    def _c2i_raw(self, cx, cy):
        bx, by = self._btl()
        return (cx-bx)/self.zoom, (cy-by)/self.zoom

    def _c2i_cl(self, cx, cy):
        img = self.result_img or self.orig_img
        if img is None: return None, None
        x, y = self._c2i_raw(cx, cy)
        if not (0 <= x < img.width and 0 <= y < img.height): return None, None
        return int(x), int(y)

    def _i2c(self, ix, iy):
        bx, by = self._btl()
        return int(bx+ix*self.zoom), int(by+iy*self.zoom)

    # ── mipmaps ───────────────────────────────────────────────────────────────
    def _build_mips(self, img):
        self.levels = [{"img": img, "s": 1.0}]
        W, H = img.size; s, cur = 1.0, img
        while min(cur.size) > 512:
            s *= .5
            cur = img.resize((max(1,int(W*s)), max(1,int(H*s))), Image.LANCZOS)
            self.levels.append({"img": cur, "s": s})

    def _pick_mip(self):
        best, be = self.levels[0], 1e18
        for L in self.levels:
            e = abs(self.zoom/L["s"]-1)
            if e < be: best, be = L, e
        return best

    # ── Keep Color ────────────────────────────────────────────────────────────
    def _kc_redraw(self):
        if self.var_kc_pre.get(): self.redraw()

    def _kc_tile(self, arr, target, tol, minw, mode):
        rgb  = arr[...,:3].astype(np.int16)
        mask = ((rgb - target)**2).sum(2) <= tol*tol
        if mode != "none" and minw > 0:
            op = opening(mask, minw)
            mask = op if mode == "remove" else (mask & ~op)
        out = arr.copy()
        out[...,0] = np.where(mask, out[...,0], 255)
        out[...,1] = np.where(mask, out[...,1], 255)
        out[...,2] = np.where(mask, out[...,2], 255)
        out[...,3] = 255
        return out

    def kc_apply(self):
        if not self.sel_rgb:
            messagebox.showwarning("Keep Color", "Выберите цвет пипеткой."); return
        tol    = int(self.var_tol.get())
        minw   = int(self.var_minw.get())
        mode   = self.var_thin.get()
        W, H   = self.orig_img.size
        th     = max(128, int(self.var_tile.get()))
        target = np.array(self.sel_rgb, np.int16)
        out    = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        r      = (2*minw+1)//2 if (mode != "none" and minw > 0) else 0
        n      = (H+th-1)//th
        for i, y0 in enumerate(range(0, H, th), 1):
            y1  = min(H, y0+th)
            pt  = max(0, y0-r); pb = min(H, y1+r)
            arr = np.array(self.orig_img.crop((0, pt, W, pb)))
            proc = self._kc_tile(arr, target, tol, minw, mode)
            c0, c1 = y0-pt, y0-pt+(y1-y0)
            out.paste(Image.fromarray(proc[c0:c1], "RGBA"), (0, y0))
            self.set_st(f"Keep Color: {i}/{n} плиток…")
            self.update_idletasks()
        self.result_img = out
        self.redraw()
        self.set_st("Keep Color применён ✓  Можно сохранять.")

    # ── Strip Fill ────────────────────────────────────────────────────────────
    def _sf_start_pick_x(self):
        """Активирует режим выбора X-границ (2 клика)."""
        self._sf_picking_x = 1
        self.var_x1.set(-1); self.var_x2.set(-1)
        self.canvas.config(cursor="crosshair")
        self.sf_info.config(
            text="  Клик 1/2: кликни на ЛЕВУЮ границу полосы")
        self.btn_pick_x.config(bg="#2a1e00", fg=ACCENT)

    def _sf_redraw(self):
        if self.var_sf_pre.get(): self.redraw()

    def _sf_run_arr(self, arr):
        """Применяет заливку к массиву numpy."""
        if not self.sel_rgb:
            return arr
        mode   = self.var_sf_mode.get()
        tol    = self.var_tol.get()
        thick  = self.var_sf_thick.get()
        x1     = self.var_x1.get()
        x2     = self.var_x2.get()
        W      = arr.shape[1]

        # Находим X-позицию линии по цвету в каждой строке
        mask = make_mask(arr[...,:3] if arr.ndim==3 else arr,
                         self.sel_rgb, tol)

        out = arr.copy()
        for y in range(arr.shape[0]):
            xs = np.where(mask[y])[0]
            if len(xs) == 0:
                continue
            # Если заданы границы X — фильтруем
            if x1 >= 0 and x2 >= 0:
                lx, rx = min(x1,x2), max(x1,x2)
                xs = xs[(xs >= lx) & (xs <= rx)]
            if len(xs) == 0:
                continue

            cx = int(np.median(xs))  # центр линии
            lft = max(0, cx - thick)
            rgt = min(W-1, cx + thick)

            if mode == "white":
                out[y, lft:rgt+1] = [255,255,255] + ([255] if arr.shape[2]==4 else [])
            elif mode == "copy_left":
                if lft > 0:
                    src = arr[y, lft-1]
                    out[y, lft:rgt+1] = src
            elif mode == "copy_right":
                if rgt < W-1:
                    src = arr[y, rgt+1]
                    out[y, lft:rgt+1] = src
        return out

    def sf_full(self):
        if self.orig_img is None:
            messagebox.showwarning("", "Откройте изображение"); return
        if not self.sel_rgb:
            messagebox.showwarning("", "Выберите цвет линии пипеткой"); return
        arr = np.array((self.result_img or self.orig_img).convert("RGBA"))
        out = self._sf_run_arr(arr)
        self.result_img = Image.fromarray(out, "RGBA")
        self.redraw()
        self.set_st("Заливка от края применена ✓")

    def sf_strip(self):
        """Применить только к видимой области."""
        self.sf_full()

    def sf_reset(self):
        self.ix_sel = self.iy_sel = None
        self.var_x1.set(-1); self.var_x2.set(-1)
        self._sf_picking_x = 0
        self.canvas.config(cursor="arrow")
        if hasattr(self, "sf_info"):
            self.sf_info.config(
                text="  Кликни на изображение чтобы выбрать цвет линии.")
        if hasattr(self, "btn_pick_x"):
            self.btn_pick_x.config(bg=BTN, fg=FG)
        self.set_st("Сброс")
        self.redraw()
    def _tol_changed(self):
        tab = self.nb.index(self.nb.select())
        if (tab == 0 and self.var_kc_pre.get()) or (tab == 1 and self.var_sf_pre.get()):
            self.redraw()

    # ── render ────────────────────────────────────────────────────────────────
    def redraw(self):
        self.canvas.delete("all")
        base = self.result_img or self.orig_img
        if base is None: return
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        W, H = base.size; bx, by = self._btl()

        x0r, y0r = self._c2i_raw(0, 0)
        x1r, y1r = self._c2i_raw(cw, ch)
        pad = max(2, int(2/max(self.zoom, 1e-6)))
        L = max(0, math.floor(min(x0r,x1r))-pad)
        T = max(0, math.floor(min(y0r,y1r))-pad)
        R = min(W, math.ceil(max(x0r,x1r))+pad)
        B = min(H, math.ceil(max(y0r,y1r))+pad)

        if R <= L or B <= T:
            self.canvas.create_rectangle(bx, by,
                bx+int(W*self.zoom), by+int(H*self.zoom), outline=BORDER)
            return

        ow = max(1, int((R-L)*self.zoom))
        oh = max(1, int((B-T)*self.zoom))
        rs = Image.NEAREST if self.zoom >= 2 else Image.LANCZOS
        disp = self._get_disp(base, L, T, R, B, ow, oh, rs)
        if disp is None: return

        self.tk_img = ImageTk.PhotoImage(disp)
        cx, cy = self._i2c(L, T)
        self.canvas.create_image(cx, cy, image=self.tk_img, anchor="nw")
        self.canvas.create_rectangle(bx, by,
            bx+int(W*self.zoom), by+int(H*self.zoom), outline=BORDER)

        # anchor line for Strip Fill
        if self.iy_sel is not None:
            ly = by + int(self.iy_sel*self.zoom)
            self.canvas.create_line(0, ly, cw, ly, fill="#ff6644", width=1, dash=(6,3))
        if self.ix_sel is not None:
            lx = bx + int(self.ix_sel*self.zoom)
            self.canvas.create_line(lx, 0, lx, ch, fill="#ff4444", width=1, dash=(4,3))

    def _get_disp(self, base, L, T, R, B, ow, oh, rs):
        tab = self.nb.index(self.nb.select())
        tol = self.var_tol.get()

        # ── Keep Color preview ──
        if tab == 0 and self.result_img is None and self.var_kc_pre.get() and self.sel_rgb:
            tile = self.orig_img.crop((L, T, R, B))
            arr  = np.array(tile)
            mask = make_mask(arr[...,:3], self.sel_rgb, tol)
            mode = self.var_thin.get(); minw = self.var_minw.get()
            if mode != "none" and minw > 0:
                op = opening(mask, minw)
                mask = op if mode == "remove" else (mask & ~op)
            out = arr.copy(); out[...,3] = np.where(mask, 255, 0)
            return Image.fromarray(out, "RGBA").resize((ow, oh), rs)

        # ── Strip Fill preview ──
        if tab == 1 and self.var_sf_pre.get() and self.sel_rgb and self.result_img is None:
            tile = self.orig_img.crop((L, T, R, B))
            arr  = np.array(tile.convert("RGBA"))
            # Корректируем X-границы для тайла
            x1_orig = self.var_x1.get(); x2_orig = self.var_x2.get()
            if x1_orig >= 0:
                self.var_x1.set(max(0, x1_orig - L))
                self.var_x2.set(max(0, x2_orig - L))
            out = self._sf_run_arr(arr)
            if x1_orig >= 0:
                self.var_x1.set(x1_orig)
                self.var_x2.set(x2_orig)
            return Image.fromarray(out, "RGBA").resize((ow, oh), rs)

        # ── Result or mipmap ──
        if self.result_img is not None:
            return base.crop((L, T, R, B)).resize((ow, oh), rs)

        m = self._pick_mip(); s = m["s"]; lvl = m["img"]
        box = (max(0,int(L*s)), max(0,int(T*s)),
               min(lvl.width,int(R*s)), min(lvl.height,int(B*s)))
        if box[2] <= box[0] or box[3] <= box[1]: return None
        eff = self.zoom/s
        return lvl.crop(box).resize((ow, oh), Image.NEAREST if eff >= 2 else Image.LANCZOS)


if __name__ == "__main__":
    App().mainloop()
