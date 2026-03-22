# image_tools.py — Keep Color + Strip Fill
# Объединённый инструмент с тёмным UI, вкладками, работает на малых экранах.

import os, sys, math, warnings
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import numpy as np

Image.MAX_IMAGE_PIXELS = None
warnings.simplefilter("ignore", Image.DecompressionBombWarning)

APP_TITLE = "Image Tools"

# ── palette ──────────────────────────────────────────────────────────────────
BG     = "#0d0f18"   # основной фон — глубокий синеватый
PANEL  = "#13161f"   # панели
PANEL2 = "#0f1117"   # фон канваса
BTN    = "#1e2233"   # кнопки
BTN_H  = "#252d45"   # кнопки hover
ACCENT = "#4d7cff"   # акцент — синий
ACC2   = "#3dd68c"   # зелёный акцент
FG     = "#c8cfe8"   # основной текст
FG2    = "#4a5578"   # приглушённый текст
TROUGH = "#1e2233"   # трек слайдера
BORDER = "#1e2640"   # границы
SEL    = "#1a2a50"   # выделение

# ── morphology ────────────────────────────────────────────────────────────────
def _ii(a):
    p = np.zeros((a.shape[0]+1, a.shape[1]+1), np.int32)
    p[1:, 1:] = a.cumsum(0).cumsum(1)
    return p

def _erode(m, k):
    if k <= 1: return m.copy()
    r = k // 2
    p = np.pad(m.astype(np.uint8), r)
    ii = _ii(p); H, W = m.shape; out = np.empty((H, W), bool)
    for y in range(H):
        row = ii[y+k, k:W+k] - ii[y+k, :W] - ii[y, k:W+k] + ii[y, :W]
        out[y] = row == k*k
    return out

def _dilate(m, k):
    if k <= 1: return m.copy()
    r = k // 2
    p = np.pad(m.astype(np.uint8), r)
    ii = _ii(p); H, W = m.shape; out = np.empty((H, W), bool)
    for y in range(H):
        row = ii[y+k, k:W+k] - ii[y+k, :W] - ii[y, k:W+k] + ii[y, :W]
        out[y] = row > 0
    return out

def opening(m, min_w):
    if min_w <= 0: return m
    k = 2*int(min_w)+1
    return _dilate(_erode(m, k), k)

# ── pixel math ────────────────────────────────────────────────────────────────
def make_mask(arr_rgb, rgb, tol):
    d = arr_rgb.astype(np.int16) - np.array(rgb, np.int16)
    return (d*d).sum(2) <= tol*tol

def fill_left(arr, mask, extra=0):
    out = arr.copy()
    for y in range(mask.shape[0]):
        xs = np.where(mask[y])[0]
        if len(xs): out[y, :min(int(xs[0])+extra+1, mask.shape[1])] = 255
    return out

def fill_right(arr, mask, extra=0):
    out = arr.copy()
    for y in range(mask.shape[0]):
        xs = np.where(mask[y])[0]
        if len(xs): out[y, max(int(xs[-1])-extra, 0):] = 255
    return out

def rgb_hex(rgb): return "#{:02X}{:02X}{:02X}".format(*rgb)

# ── app ───────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x700")
        self.minsize(820, 560)
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
        self.var_sf_pre = tk.BooleanVar(value=True)
        self.var_dir    = tk.StringVar(value="left")
        self.var_extra  = tk.IntVar(value=0)
        self.ix_sel = self.iy_sel = None

        self._styles()
        self._build_topbar()
        self._build_tabs()
        self._build_canvas()
        self._build_status()

        self.bind("<e>",      lambda e: self.toggle_eye())
        self.bind("<Escape>", lambda e: self._eye_off())
        self.bind("<r>",      lambda e: self.reset_result())
        self.bind("<f>",      lambda e: self.zoom_fit())

    # ── widget helpers ────────────────────────────────────────────────────────
    def _styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook",
                    background=BG, borderwidth=0, tabmargins=[0,0,0,0])
        s.configure("TNotebook.Tab",
                    background=BTN, foreground=FG2,
                    padding=[18, 7], font=("Segoe UI", 9, "bold"))
        s.map("TNotebook.Tab",
              background=[("selected", PANEL), ("active", BTN_H)],
              foreground=[("selected", ACCENT), ("active", FG)])
        s.configure("TFrame", background=PANEL)
        s.configure("Horizontal.TProgressbar",
                    background=ACCENT, troughcolor=TROUGH, borderwidth=0)

    def _btn(self, p, text, cmd, accent=False, green=False, w=None):
        if accent:   bg, fg, hov = ACCENT, "#ffffff", "#6b94ff"
        elif green:  bg, fg, hov = "#1a3a28", ACC2, "#243524"
        else:        bg, fg, hov = BTN,    FG,       BTN_H
        b = tk.Button(p, text=text, command=cmd,
                      bg=bg, fg=fg,
                      activebackground=hov, activeforeground=fg,
                      relief="flat", padx=10, pady=5,
                      font=("Segoe UI", 9), cursor="hand2", bd=0)
        if w: b.config(width=w)
        b.bind("<Enter>", lambda e, b=b, hv=hov: b.config(bg=hv))
        b.bind("<Leave>", lambda e, b=b, ob=bg:  b.config(bg=ob))
        return b

    def _lbl(self, p, text, fg=None, **kw):
        return tk.Label(p, text=text, bg=PANEL, fg=fg or FG,
                        font=("Segoe UI", 9), **kw)

    def _scl(self, p, var, lo, hi, length=100, cmd=None):
        return tk.Scale(p, from_=lo, to=hi, variable=var,
                        orient="horizontal", length=length, showvalue=0,
                        bg=PANEL, fg=FG, troughcolor=TROUGH,
                        highlightthickness=0,
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
        tk.Frame(p, width=1, bg=BORDER).pack(side="left", fill="y", padx=5, pady=4)

    def _val_lbl(self, p, var, w=3):
        return tk.Label(p, textvariable=var, width=w,
                        bg=PANEL, fg=FG2, font=("Segoe UI", 8))

    # ── top bar ───────────────────────────────────────────────────────────────
    def _build_topbar(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="x", side="top")

        # Логотип / заголовок
        hdr = tk.Frame(outer, bg="#0a0c14", height=38)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="✦  Image Tools",
                 bg="#0a0c14", fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=14, pady=8)
        tk.Label(hdr, text="Keep Color  ·  Strip Fill",
                 bg="#0a0c14", fg=FG2,
                 font=("Segoe UI", 8)).pack(side="left", pady=8)
        tk.Frame(outer, height=1, bg=BORDER).pack(fill="x")

        row = tk.Frame(outer, bg=PANEL)
        row.pack(fill="x", padx=8, pady=6)

        # File
        self._btn(row, "📂  Открыть",  self.open_image).pack(side="left", padx=2)
        self._btn(row, "💾  Сохранить",  self.save_image).pack(side="left", padx=2)
        self._btn(row, "↩  Сброс", self.reset_result).pack(side="left", padx=2)
        self._sep(row)

        # Eyedropper
        self.btn_eye = self._btn(row, "🔬  Пипетка  [E]", self.toggle_eye)
        self.btn_eye.pack(side="left", padx=2)

        # Color swatch — красивее
        sw_wrap = tk.Frame(row, bg=PANEL); sw_wrap.pack(side="left", padx=6)
        self.swatch = tk.Frame(sw_wrap, width=80, height=28,
                               bg=BTN, relief="flat", bd=0)
        self.swatch.pack()
        self.swatch.pack_propagate(False)
        self.swatch_lbl = tk.Label(self.swatch, text="—",
                                   bg=BTN, fg=FG2, font=("Segoe UI", 8))
        self.swatch_lbl.pack(fill="both", expand=True)
        self._sep(row)

        # Tolerance
        self._lbl(row, "Допуск:").pack(side="left")
        self._scl(row, self.var_tol, 0, 128, 100,
                  cmd=lambda v: self._tol_changed()).pack(side="left", padx=4)
        self._val_lbl(row, self.var_tol).pack(side="left")
        self._sep(row)

        # Zoom
        self._lbl(row, "Масштаб:").pack(side="left")
        self._scl(row, self.var_zoom, 5, 800, 110,
                  cmd=self._zoom_scale).pack(side="left", padx=4)
        self.zoom_lbl = tk.Label(row, text="100%", width=5,
                                 bg=PANEL, fg=ACCENT, font=("Segoe UI", 9, "bold"))
        self.zoom_lbl.pack(side="left")
        self._btn(row, "⊡ Вписать", self.zoom_fit).pack(side="left", padx=2)
        self._btn(row, "1:1",   lambda: self._set_zoom(100)).pack(side="left", padx=2)

        # hint справа
        tk.Label(row, text="ПКМ/СКМ — панорама  ·  Scroll — зум  ·  R — сброс  ·  F — вписать",
                 bg=PANEL, fg=FG2, font=("Segoe UI", 8)).pack(side="right", padx=12)

        tk.Frame(outer, height=1, bg=BORDER).pack(fill="x")

    # ── tabs ──────────────────────────────────────────────────────────────────
    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="x", side="top")

        fkc = ttk.Frame(self.nb)
        self.nb.add(fkc, text="  🎨  Оставить цвет  ")
        self._tab_kc(fkc)

        fsf = ttk.Frame(self.nb)
        self.nb.add(fsf, text="  ⬛  Заливка от края  ")
        self._tab_sf(fsf)

        tk.Frame(self, height=1, bg=BORDER).pack(fill="x")

    def _tab_kc(self, f):
        row = tk.Frame(f, bg=PANEL, pady=6)
        row.pack(fill="x", padx=10)

        self._lbl(row, "Тонкие:").pack(side="left", padx=(0, 4))
        for txt, val in [("не трогать","none"),("убрать ≤N","remove"),("оставить ≤N","keep")]:
            self._rad(row, txt, self.var_thin, val,
                      cmd=lambda: self._kc_redraw()).pack(side="left", padx=2)

        self._lbl(row, "  N:").pack(side="left")
        self._scl(row, self.var_minw, 0, 20, 70,
                  cmd=lambda v: self._kc_redraw()).pack(side="left")
        self._val_lbl(row, self.var_minw, 2).pack(side="left")
        self._sep(row)

        self._chk(row, "✂ Crop on save", self.var_crop).pack(side="left", padx=3)
        self._chk(row, "👁 Preview", self.var_kc_pre,
                  cmd=self.redraw).pack(side="left", padx=3)
        self._sep(row)

        self.btn_kc = self._btn(row, "▶  Применить",
                                self.kc_apply, green=True)
        self.btn_kc.pack(side="left", padx=4)
        self.btn_kc.config(state="disabled")

        self._lbl(row, "  Tile:").pack(side="left")
        tk.Spinbox(row, from_=256, to=8192, increment=256, width=5,
                   textvariable=self.var_tile,
                   bg=BTN, fg=FG, buttonbackground=BTN_H,
                   font=("Segoe UI", 8)).pack(side="left")

    def _tab_sf(self, f):
        row = tk.Frame(f, bg=PANEL, pady=6)
        row.pack(fill="x", padx=10)

        self._lbl(row, "Направление:").pack(side="left", padx=(0, 4))
        self._rad(row, "← Влево",  self.var_dir, "left",
                  cmd=lambda: self._sf_redraw()).pack(side="left", padx=2)
        self._rad(row, "Вправо →", self.var_dir, "right",
                  cmd=lambda: self._sf_redraw()).pack(side="left", padx=2)
        self._sep(row)

        self._lbl(row, "Extra:").pack(side="left")
        self._scl(row, self.var_extra, 0, 60, 70,
                  cmd=lambda v: self._sf_redraw()).pack(side="left")
        self._val_lbl(row, self.var_extra, 2).pack(side="left")
        self._sep(row)

        self._chk(row, "👁 Preview", self.var_sf_pre,
                  cmd=self.redraw).pack(side="left", padx=3)
        self._sep(row)

        self._btn(row, "▶ Строка", self.sf_strip).pack(side="left", padx=2)
        self._btn(row, "▶▶ Всё изображение", self.sf_full, green=True).pack(side="left", padx=2)
        self._btn(row, "✕ Сбросить",   self.sf_reset).pack(side="left", padx=2)

        self.sf_info = tk.Label(row, text="  кликни на изображение чтобы задать строку",
                                bg=PANEL, fg=FG2, font=("Segoe UI", 8))
        self.sf_info.pack(side="left", padx=6)

    # ── canvas + status ───────────────────────────────────────────────────────
    def _build_canvas(self):
        self.canvas = tk.Canvas(self, bg="#080a12", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        cv = self.canvas
        cv.bind("<Button-1>",    self.on_click)
        cv.bind("<MouseWheel>",  self.on_wheel)
        cv.bind("<Button-4>",    lambda e: self._scroll(60))
        cv.bind("<Button-5>",    lambda e: self._scroll(-60))
        cv.bind("<ButtonPress-2>",  self._pan0)
        cv.bind("<B2-Motion>",      self._pan1)
        cv.bind("<ButtonPress-3>",  self._pan0)
        cv.bind("<B3-Motion>",      self._pan1)
        cv.bind("<Configure>",   lambda e: self.redraw())

    def _build_status(self):
        sbar = tk.Frame(self, bg="#0a0c14", height=26)
        sbar.pack(fill="x", side="bottom"); sbar.pack_propagate(False)
        tk.Frame(sbar, height=1, bg=BORDER).pack(fill="x", side="top")
        self.status = tk.Label(sbar, text="  Откройте изображение…",
                               anchor="w", bg="#0a0c14", fg=FG2,
                               font=("Segoe UI", 8), padx=8)
        self.status.pack(fill="both", expand=True)

    def set_st(self, t): self.status.config(text=t)

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
        self.btn_eye.config(bg="#1a3a28" if self.eye_on else BTN,
                           fg=ACC2 if self.eye_on else FG)
        self.set_st("👁 Кликни по цвету на изображении" if self.eye_on else "Пипетка ВЫКЛ")

    def _eye_off(self):
        if self.eye_on: self.toggle_eye()

    def _swatch(self, rgb):
        if rgb is None:
            self.swatch.config(bg=BTN)
            self.swatch_lbl.config(text="  нет цвета", bg=BTN, fg=FG2)
        else:
            h = rgb_hex(rgb); lum = .299*rgb[0]+.587*rgb[1]+.114*rgb[2]
            self.swatch.config(bg=h)
            self.swatch_lbl.config(text=h, bg=h, fg="#000" if lum > 140 else "#fff")

    # ── interactions ──────────────────────────────────────────────────────────
    def on_click(self, ev):
        if self.orig_img is None: return
        if not self.eye_on:
            self._pan_center(ev.x, ev.y); return
        ix, iy = self._c2i_cl(ev.x, ev.y)
        if ix is None: return
        pix = self.orig_img.getpixel((ix, iy))
        self.sel_rgb = (pix[0], pix[1], pix[2])
        self.ix_sel, self.iy_sel = ix, iy
        self._swatch(self.sel_rgb)
        self.btn_kc.config(state="normal")
        self.sf_info.config(text=f"  anchor: строка {iy}, столбец {ix}")
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
    def _sf_redraw(self):
        if self.var_sf_pre.get(): self.redraw()

    def _sf_run(self, arr, mask):
        extra = self.var_extra.get()
        return (fill_left(arr, mask, extra) if self.var_dir.get() == "left"
                else fill_right(arr, mask, extra))

    def sf_strip(self):
        if self.orig_img is None or not self.sel_rgb:
            messagebox.showwarning("Strip Fill", "Откройте изображение и выберите цвет."); return
        arr  = np.array((self.result_img or self.orig_img).convert("RGB"))
        mask = make_mask(arr, self.sel_rgb, self.var_tol.get())
        yc   = self.iy_sel if self.iy_sel is not None else arr.shape[0]//2
        y0, y1 = max(0, yc-40), min(arr.shape[0], yc+40)
        arr[y0:y1] = self._sf_run(arr[y0:y1], mask[y0:y1])
        self.result_img = Image.fromarray(arr, "RGB").convert("RGBA")
        self.redraw(); self.set_st(f"Strip Fill: строки {y0}…{y1} ✓")

    def sf_full(self):
        if self.orig_img is None or not self.sel_rgb:
            messagebox.showwarning("Strip Fill", "Откройте изображение и выберите цвет."); return
        arr  = np.array((self.result_img or self.orig_img).convert("RGB"))
        mask = make_mask(arr, self.sel_rgb, self.var_tol.get())
        self.result_img = Image.fromarray(self._sf_run(arr, mask), "RGB").convert("RGBA")
        self.redraw(); self.set_st("Strip Fill применён на всё изображение ✓")

    def sf_reset(self):
        self.ix_sel = self.iy_sel = None
        self.sf_info.config(text="  кликни на изображение чтобы задать строку")
        self.set_st("Выбор сброшен"); self.redraw()

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
            arr  = np.array(tile.convert("RGB"))
            mask = make_mask(arr, self.sel_rgb, tol)
            return Image.fromarray(self._sf_run(arr, mask), "RGB").resize((ow, oh), rs)

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
