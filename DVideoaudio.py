import json
import queue
import re
import shutil
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import yt_dlp


APP_NAME = "YT Downloader - MP3 / MP4"
CONFIG_FILE = Path("yt_downloader_config.json")

QUALITY_OPTIONS = [
    "Mejor disponible",
    "2160p (3840×2160)",
    "1440p (2560×1440)",
    "1080p (1920×1080)",
    "720p (1280×720)",
    "480p (854×480)",
    "360p (640×360)",
]


def ocultar_consola_windows():
    try:
        import ctypes
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            ctypes.windll.user32.ShowWindow(whnd, 0)
    except Exception:
        pass


def nombre_seguro(nombre: str) -> str:
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip()
    return nombre[:180] if len(nombre) > 180 else nombre


def url_valida_basica(url: str) -> bool:
    return bool(re.match(r"^https?://", url.strip(), re.IGNORECASE))


def formatear_bytes(n: Optional[float]) -> str:
    if n is None:
        return "?"
    unidades = ["B", "KB", "MB", "GB", "TB"]
    valor = float(n)
    for unidad in unidades:
        if valor < 1024 or unidad == unidades[-1]:
            return f"{valor:.1f} {unidad}"
        valor /= 1024
    return f"{n} B"


def formatear_velocidad(n: Optional[float]) -> str:
    if not n:
        return "?"
    return f"{formatear_bytes(n)}/s"


def formatear_eta(segundos: Optional[int]) -> str:
    if segundos is None:
        return "?"
    segundos = max(0, int(segundos))
    m, s = divmod(segundos, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def extraer_max_height(choice: str) -> Optional[int]:
    choice = choice.strip()
    if choice == "Mejor disponible":
        return None
    m = re.search(r"(\d{3,4})p", choice)
    return int(m.group(1)) if m else 1080


def ffmpeg_disponible() -> bool:
    return shutil.which("ffmpeg") is not None


@dataclass
class DownloadRequest:
    url: str
    carpeta_destino: Path
    modo: str
    calidad_label: str
    abrir_carpeta_al_final: bool = False


class DownloadCancelled(Exception):
    pass


class YTDLPLogger:
    def __init__(self, emit_log):
        self.emit_log = emit_log

    def debug(self, msg):
        if msg and "[debug]" not in msg.lower():
            self.emit_log(msg)

    def warning(self, msg):
        if msg:
            self.emit_log(f"⚠ {msg}")

    def error(self, msg):
        if msg:
            self.emit_log(f"✖ {msg}")


class DownloaderService:
    def __init__(self, event_queue: queue.Queue):
        self.event_queue = event_queue
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def _emit(self, kind: str, **payload):
        self.event_queue.put({"kind": kind, **payload})

    def _log(self, msg: str):
        self._emit("log", message=msg)

    def _progress_hook(self, d):
        if self.cancel_event.is_set():
            raise DownloadCancelled("Descarga cancelada por el usuario.")

        status = d.get("status")

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed")
            eta = d.get("eta")

            percent = 0.0
            if total and total > 0:
                percent = downloaded * 100 / total

            filename = d.get("filename", "")
            self._emit(
                "progress",
                percent=percent,
                downloaded=downloaded,
                total=total,
                speed=speed,
                eta=eta,
                filename=filename,
                phase="downloading",
            )

        elif status == "finished":
            filename = d.get("filename", "")
            self._emit(
                "progress",
                percent=100.0,
                downloaded=None,
                total=None,
                speed=None,
                eta=0,
                filename=filename,
                phase="postprocessing",
            )
            self._log("📦 Descarga terminada. Procesando archivo...")

    def _common_opts(self):
        return {
            "noplaylist": True,
            "quiet": True,
            "no_warnings": False,
            "logger": YTDLPLogger(self._log),
            "progress_hooks": [self._progress_hook],
            "retries": 10,
            "fragment_retries": 10,
            "socket_timeout": 20,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            },
            "extractor_args": {
                "youtube": {"player_client": ["android", "web"]}
            },
        }

    def _obtener_info(self, url: str):
        opts = self._common_opts() | {
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _resolver_nombre_final(self, info: dict, modo: str) -> str:
        title = nombre_seguro(info.get("title", "descarga"))
        video_id = nombre_seguro(info.get("id", "sin_id"))
        sufijo = "AUDIO" if modo == "mp3" else "VIDEO"
        ext = "mp3" if modo == "mp3" else "mp4"
        return f"{title} [{video_id}] [{sufijo}].{ext}"

    def _build_mp3_options(self, outtmpl: str) -> dict:
        opts = self._common_opts()
        opts.update({
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
        return opts

    def _build_mp4_options(self, outtmpl: str, max_h: Optional[int]) -> dict:
        opts = self._common_opts()
        if max_h is None:
            format_str = "bestvideo*+bestaudio/best"
        else:
            format_str = f"bestvideo*[height<={max_h}]+bestaudio/best[height<={max_h}]"

        opts.update({
            "format": format_str,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
        })
        return opts

    def download(self, req: DownloadRequest):
        archivo_errores = req.carpeta_destino / "errores.txt"
        req.carpeta_destino.mkdir(parents=True, exist_ok=True)

        try:
            self.cancel_event.clear()
            self._emit("state", processing=True)
            self._emit("progress", percent=0.0, phase="starting")

            self._log("-" * 68)
            self._log(f"🔎 Analizando URL: {req.url}")

            if req.modo in {"mp3", "mp4"} and not ffmpeg_disponible():
                raise RuntimeError("FFmpeg no está instalado o no está en el PATH del sistema.")

            info = self._obtener_info(req.url)

            if not info:
                raise RuntimeError("No se pudo obtener información del video.")

            if "entries" in info and info.get("entries"):
                raise RuntimeError("La URL parece ser una playlist. Este programa descarga un solo video.")

            titulo = nombre_seguro(info.get("title", "descarga"))
            video_id = nombre_seguro(info.get("id", "sin_id"))
            sufijo_base = "AUDIO" if req.modo == "mp3" else "VIDEO"

            nombre_final = self._resolver_nombre_final(info, req.modo)
            ruta_final = req.carpeta_destino / nombre_final

            if ruta_final.exists() and ruta_final.stat().st_size > 100 * 1024:
                self._log(f"⏭ Ya existe, se omite: {ruta_final.name}")
                self._emit("done", ok=True, message=f"Archivo existente: {ruta_final.name}", final_path=str(ruta_final))
                return

            plantilla = str(req.carpeta_destino / f"{titulo} [{video_id}] [{sufijo_base}].%(ext)s")

            if req.modo == "mp3":
                self._log("🎵 Modo MP3")
                opciones = self._build_mp3_options(plantilla)
            else:
                max_h = extraer_max_height(req.calidad_label)
                self._log(f"🎬 Modo MP4 | Calidad máxima: {req.calidad_label}")
                opciones = self._build_mp4_options(plantilla, max_h)
                self._log(f"⚙ Formato yt-dlp: {opciones['format']}")

            self._log(f"📝 Título: {titulo}")
            self._log(f"🆔 ID: {video_id}")
            self._log(f"📁 Salida esperada: {ruta_final.name}")

            with yt_dlp.YoutubeDL(opciones) as ydl:
                ret = ydl.download([req.url])

            if self.cancel_event.is_set():
                raise DownloadCancelled("Descarga cancelada por el usuario.")

            if ret not in (0, None):
                raise RuntimeError(f"yt-dlp devolvió código no esperado: {ret}")

            if ruta_final.exists() and ruta_final.stat().st_size > 100 * 1024:
                self._log(f"✅ Listo: {ruta_final.name}")
                self._emit("done", ok=True, message=f"Descarga completada: {ruta_final.name}", final_path=str(ruta_final))
                return

            candidatos = sorted(req.carpeta_destino.glob(f"{titulo} [{video_id}] [{sufijo_base}]*"))
            candidatos_validos = [p for p in candidatos if p.is_file()]

            if candidatos_validos:
                detectado = candidatos_validos[-1]
                self._log(f"✅ Archivo detectado: {detectado.name}")
                self._emit("done", ok=True, message=f"Descarga completada: {detectado.name}", final_path=str(detectado))
                return

            raise RuntimeError("La descarga terminó, pero no se encontró el archivo final esperado.")

        except DownloadCancelled as e:
            self._log(f"🛑 {e}")
            self._emit("done", ok=False, cancelled=True, message=str(e), final_path=None)

        except Exception as e:
            self._log(f"❌ Error: {e}")
            try:
                with archivo_errores.open("a", encoding="utf-8") as f:
                    f.write(req.url + "\n")
            except Exception:
                pass
            self._emit("done", ok=False, cancelled=False, message=str(e), final_path=None)

        finally:
            self._emit("state", processing=False)


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.state("zoomed")
        self.minsize(1000, 650)
        self.configure(bg="#0f172a")

        self.event_queue = queue.Queue()
        self.downloader = DownloaderService(self.event_queue)
        self.worker_thread = None
        self.en_proceso = False
        self.ultimo_archivo = None

        self.url_var = tk.StringVar()
        self.carpeta_var = tk.StringVar()
        self.modo_var = tk.StringVar(value="mp3")
        self.calidad_var = tk.StringVar(value="1080p (1920×1080)")
        self.status_var = tk.StringVar(value="Listo para iniciar.")
        self.progress_text_var = tk.StringVar(value="En espera de ingreso.")
        self.abrir_carpeta_var = tk.BooleanVar(value=False)

        self.C_BG = "#0f172a"
        self.C_PANEL = "#111c35"
        self.C_TEXT = "#e5e7eb"
        self.C_MUTED = "#9ca3af"
        self.C_ACCENT = "#22c55e"
        self.C_ACCENT2 = "#3b82f6"
        self.C_WARN = "#f59e0b"
        self.C_BORDER = "#1f2a44"
        self.C_INPUT = "#0b1224"
        self.C_LOG = "#070d1b"

        self._load_config()
        self._style()
        self._build_ui()

        self.modo_var.trace_add("write", lambda *_: self._toggle_calidad_ui())
        self._toggle_calidad_ui()

        self.after(120, self._process_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Root.TFrame", background=self.C_BG)
        style.configure("Panel.TFrame", background=self.C_PANEL)

        style.configure(
            "Title.TLabel",
            background=self.C_BG,
            foreground=self.C_TEXT,
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Sub.TLabel",
            background=self.C_BG,
            foreground=self.C_MUTED,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Label.TLabel",
            background=self.C_PANEL,
            foreground=self.C_TEXT,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Footer.TLabel",
            background=self.C_BG,
            foreground=self.C_MUTED,
            font=("Segoe UI", 9),
        )

        style.configure(
            "TRadiobutton",
            background=self.C_PANEL,
            foreground=self.C_TEXT,
            font=("Segoe UI", 10),
        )

        style.map(
            "TRadiobutton",
            background=[("active", self.C_PANEL)],
            foreground=[("active", self.C_TEXT)],
        )

        style.configure(
            "TCheckbutton",
            background=self.C_PANEL,
            foreground=self.C_TEXT,
            font=("Segoe UI", 10),
        )

        style.map(
            "TCheckbutton",
            background=[("active", self.C_PANEL)],
            foreground=[("active", self.C_TEXT)],
        )

        style.configure(
            "TEntry",
            fieldbackground=self.C_INPUT,
            foreground=self.C_TEXT,
            bordercolor=self.C_BORDER,
            lightcolor=self.C_BORDER,
            darkcolor=self.C_BORDER,
            insertcolor=self.C_TEXT,
            padding=10,
        )

        style.configure("TCombobox", padding=8)

        style.configure(
            "TButton",
            font=("Segoe UI", 10, "bold"),
            padding=10,
        )

        style.configure("Accent.TButton", background=self.C_ACCENT, foreground="#052e16")
        style.map(
            "Accent.TButton",
            background=[("active", "#16a34a"), ("disabled", "#14532d")],
            foreground=[("disabled", "#94a3b8")],
        )

        style.configure("Secondary.TButton", background=self.C_ACCENT2, foreground="#0b1224")
        style.map(
            "Secondary.TButton",
            background=[("active", "#2563eb"), ("disabled", "#1e3a8a")],
            foreground=[("disabled", "#94a3b8")],
        )

        style.configure("Danger.TButton", background=self.C_WARN, foreground="#0b1224")
        style.map(
            "Danger.TButton",
            background=[("active", "#d97706"), ("disabled", "#78350f")],
            foreground=[("disabled", "#94a3b8")],
        )

        style.configure(
            "Custom.Horizontal.TProgressbar",
            troughcolor=self.C_INPUT,
            bordercolor=self.C_BORDER,
            background=self.C_ACCENT2,
            lightcolor=self.C_ACCENT2,
            darkcolor=self.C_ACCENT2,
        )

        style.configure(
            "Panel.TLabelframe",
            background=self.C_PANEL,
            foreground=self.C_TEXT,
            bordercolor=self.C_BORDER,
            relief="solid",
        )
        style.configure(
            "Panel.TLabelframe.Label",
            background=self.C_PANEL,
            foreground=self.C_TEXT,
            font=("Segoe UI", 10, "bold"),
        )

    def _build_ui(self):
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Root.TFrame")
        header.pack(fill="x", padx=18, pady=(16, 10))

        ttk.Label(header, text="Descargador YouTube", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Descarga en formato MP3 o MP4",
            style="Sub.TLabel"
        ).pack(anchor="w", pady=(2, 0))

        main = ttk.Frame(root, style="Root.TFrame")
        main.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        left.configure(width=450)
        left.grid_propagate(False)

        right = ttk.Frame(main, style="Panel.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        ttk.Label(left, text="URL del video", style="Label.TLabel").pack(anchor="w", padx=14, pady=(14, 6))
        self.url_entry = ttk.Entry(left, textvariable=self.url_var)
        self.url_entry.pack(fill="x", padx=14)
        self.url_entry.focus_set()

        ttk.Label(left, text="Carpeta destino", style="Label.TLabel").pack(anchor="w", padx=14, pady=(14, 6))
        folder_row = ttk.Frame(left, style="Panel.TFrame")
        folder_row.pack(fill="x", padx=14)
        folder_row.columnconfigure(0, weight=1)

        self.folder_entry = ttk.Entry(folder_row, textvariable=self.carpeta_var)
        self.folder_entry.grid(row=0, column=0, sticky="we")

        self.btn_carpeta = ttk.Button(
            folder_row,
            text="Elegir…",
            style="Secondary.TButton",
            command=self.elegir_carpeta,
        )
        self.btn_carpeta.grid(row=0, column=1, padx=(10, 0))

        opt_frame = ttk.LabelFrame(left, text="Formato", padding=12, style="Panel.TLabelframe")
        opt_frame.pack(fill="x", padx=14, pady=(16, 0))

        self.rb_mp3 = ttk.Radiobutton(opt_frame, text="MP3 (solo audio)", variable=self.modo_var, value="mp3")
        self.rb_mp4 = ttk.Radiobutton(opt_frame, text="MP4 (video)", variable=self.modo_var, value="mp4")
        self.rb_mp3.grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.rb_mp4.grid(row=0, column=1, sticky="w")

        self.calidad_box = ttk.LabelFrame(left, text="Calidad de video (MP4)", padding=12, style="Panel.TLabelframe")
        ttk.Label(self.calidad_box, text="Elige la calidad máxima:", style="Label.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.combo_calidad = ttk.Combobox(
            self.calidad_box,
            textvariable=self.calidad_var,
            state="readonly",
            values=QUALITY_OPTIONS,
        )
        self.combo_calidad.grid(row=1, column=0, sticky="we")
        self.calidad_box.columnconfigure(0, weight=1)

        extras_frame = ttk.LabelFrame(left, text="Opciones", padding=12, style="Panel.TLabelframe")
        extras_frame.pack(fill="x", padx=14, pady=(12, 0))
        self.chk_abrir_carpeta = ttk.Checkbutton(
            extras_frame,
            text="Abrir carpeta al terminar",
            variable=self.abrir_carpeta_var
        )
        self.chk_abrir_carpeta.grid(row=0, column=0, sticky="w")

        ttk.Label(left, textvariable=self.status_var, style="Label.TLabel").pack(anchor="w", padx=14, pady=(18, 6))

        actions = ttk.Frame(left, style="Panel.TFrame")
        actions.pack(fill="x", padx=14)

        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        self.btn_descargar = ttk.Button(actions, text="Descargar", style="Accent.TButton", command=self.on_descargar)
        self.btn_descargar.grid(row=0, column=0, sticky="we", padx=(0, 6))

        self.btn_cancelar = ttk.Button(actions, text="Cancelar", style="Danger.TButton", command=self.on_cancelar, state="disabled")
        self.btn_cancelar.grid(row=0, column=1, sticky="we", padx=(6, 0))

        self.btn_abrir_destino = ttk.Button(
            left,
            text="Abrir carpeta destino",
            style="Secondary.TButton",
            command=self.abrir_carpeta_destino
        )
        self.btn_abrir_destino.pack(fill="x", padx=14, pady=(10, 0))

        ttk.Label(right, text="Progreso", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        self.progress = ttk.Progressbar(
            right,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            style="Custom.Horizontal.TProgressbar",
        )
        self.progress.grid(row=1, column=0, sticky="ew", padx=14)

        self.progress_label = ttk.Label(right, textvariable=self.progress_text_var, style="Label.TLabel")
        self.progress_label.grid(row=2, column=0, sticky="w", padx=14, pady=(8, 10))

        ttk.Label(right, text="Logs", style="Label.TLabel").grid(row=3, column=0, sticky="nw", padx=14, pady=(4, 6))

        log_wrap = ttk.Frame(right, style="Panel.TFrame")
        log_wrap.grid(row=3, column=0, sticky="nsew", padx=14, pady=(28, 14))
        log_wrap.columnconfigure(0, weight=1)
        log_wrap.rowconfigure(0, weight=1)

        self.log = tk.Text(
            log_wrap,
            bg=self.C_LOG,
            fg=self.C_TEXT,
            insertbackground=self.C_TEXT,
            relief="flat",
            padx=10,
            pady=10,
            wrap="word",
            undo=False,
        )
        self.log.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_wrap, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(root, style="Root.TFrame")
        footer.pack(fill="x", padx=18, pady=(0, 14))
        ttk.Label(
            footer,
            text="Desarrollador William Martínez  |  GitHub: Pendragon503",
            style="Footer.TLabel",
        ).pack(anchor="w")

    def _toggle_calidad_ui(self):
        if self.modo_var.get() == "mp4":
            self.calidad_box.pack(fill="x", padx=14, pady=(12, 0))
        else:
            self.calidad_box.pack_forget()



    def _load_config(self):
        try:
            if CONFIG_FILE.exists():
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                carpeta = data.get("last_folder", "")
                abrir = data.get("open_folder_when_done", False)
                if carpeta:
                    self.carpeta_var.set(carpeta)
                self.abrir_carpeta_var.set(bool(abrir))
        except Exception:
            pass

    def _save_config(self):
        try:
            data = {
                "last_folder": self.carpeta_var.get().strip(),
                "open_folder_when_done": self.abrir_carpeta_var.get(),
            }
            CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def elegir_carpeta(self):
        carpeta = filedialog.askdirectory(title="Selecciona la carpeta destino")
        if carpeta:
            self.carpeta_var.set(carpeta)
            self._save_config()

    def abrir_carpeta_destino(self):
        carpeta = self.carpeta_var.get().strip()
        if not carpeta:
            messagebox.showwarning("Carpeta no definida", "Selecciona una carpeta destino.")
            return

        ruta = Path(carpeta)
        if not ruta.exists():
            messagebox.showwarning("Carpeta no válida", "La carpeta destino no existe o no es accesible.")
            return

        try:
            import os
            os.startfile(str(ruta))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")

    def log_print(self, msg: str):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def limpiar_progreso(self):
        self.progress["value"] = 0
        self.progress_text_var.set("Sin actividad.")

    def set_processing(self, processing: bool):
        self.en_proceso = processing

        if processing:
            self.status_var.set("Descargando...")
            self.btn_descargar.config(state="disabled", text="Descargando...", style="Danger.TButton")
            self.btn_cancelar.config(state="normal")
            self.btn_carpeta.config(state="disabled")
            self.rb_mp3.config(state="disabled")
            self.rb_mp4.config(state="disabled")
            self.url_entry.config(state="disabled")
            self.folder_entry.config(state="disabled")
            self.chk_abrir_carpeta.config(state="disabled")
            self.btn_abrir_destino.config(state="disabled")
            if self.modo_var.get() == "mp4":
                self.combo_calidad.config(state="disabled")
        else:
            self.status_var.set("Listo para iniciar.")
            self.btn_descargar.config(state="normal", text="Descargar", style="Accent.TButton")
            self.btn_cancelar.config(state="disabled")
            self.btn_carpeta.config(state="normal")
            self.rb_mp3.config(state="normal")
            self.rb_mp4.config(state="normal")
            self.url_entry.config(state="normal")
            self.folder_entry.config(state="normal")
            self.chk_abrir_carpeta.config(state="normal")
            self.btn_abrir_destino.config(state="normal")
            if self.modo_var.get() == "mp4":
                self.combo_calidad.config(state="readonly")

    def on_descargar(self):
        if self.en_proceso:
            return

        url = self.url_var.get().strip()
        carpeta = self.carpeta_var.get().strip()
        modo = self.modo_var.get().strip()

        if not url:
            messagebox.showerror("URL requerida", "Ingresa la URL del video.")
            return

        if not url_valida_basica(url):
            messagebox.showerror("URL inválida", "La URL debe comenzar con http:// o https://")
            return

        if not carpeta:
            messagebox.showerror("Carpeta requerida", "Selecciona una carpeta destino.")
            return

        carpeta_path = Path(carpeta)
        if not carpeta_path.exists() or not carpeta_path.is_dir():
            messagebox.showerror("Carpeta inválida", "Elige una carpeta válida.")
            return

        self._save_config()
        self.ultimo_archivo = None
        self.progress["value"] = 0
        self.progress_text_var.set("Preparando la descarga...")

        self.log_print("-" * 68)
        if modo == "mp4":
            self.log_print(f"▶ Iniciando descarga MP4 | Calidad: {self.calidad_var.get()}")
        else:
            self.log_print("▶ Iniciando descarga MP3")

        req = DownloadRequest(
            url=url,
            carpeta_destino=carpeta_path,
            modo=modo,
            calidad_label=self.calidad_var.get(),
            abrir_carpeta_al_final=self.abrir_carpeta_var.get(),
        )

        self.worker_thread = threading.Thread(
            target=self.downloader.download,
            args=(req,),
            daemon=True,
        )
        self.worker_thread.start()

    def on_cancelar(self):
        if not self.en_proceso:
            return
        self.downloader.cancel()
        self.status_var.set("Cancelando…")
        self.progress_text_var.set("Cancelación en proceso...")

    def _process_events(self):
        try:
            while True:
                event = self.event_queue.get_nowait()
                kind = event.get("kind")

                if kind == "log":
                    self.log_print(event["message"])

                elif kind == "state":
                    self.set_processing(event["processing"])

                elif kind == "progress":
                    self._update_progress(event)

                elif kind == "done":
                    self._handle_done(event)

        except queue.Empty:
            pass
        finally:
            self.after(120, self._process_events)

    def _update_progress(self, event: dict):
        phase = event.get("phase")

        if phase == "starting":
            self.progress["value"] = 0
            self.progress_text_var.set("Inicializando descarga...")
            return

        if phase == "postprocessing":
            self.progress["value"] = 100
            self.progress_text_var.set("Procesando archivo final...")
            return

        percent = event.get("percent", 0.0) or 0.0
        downloaded = event.get("downloaded")
        total = event.get("total")
        speed = event.get("speed")
        eta = event.get("eta")

        self.progress["value"] = max(0, min(100, percent))

        texto = (
            f"{percent:.1f}%  |  "
            f"{formatear_bytes(downloaded)} / {formatear_bytes(total)}  |  "
            f"{formatear_velocidad(speed)}  |  "
            f"ETA {formatear_eta(eta)}"
        )
        self.progress_text_var.set(texto)

    def _handle_done(self, event: dict):
        ok = event.get("ok", False)
        cancelled = event.get("cancelled", False)
        message = event.get("message", "")
        final_path = event.get("final_path")

        if final_path:
            self.ultimo_archivo = final_path

        if ok:
            self.status_var.set("Descarga completada.")
            self.progress["value"] = 100
            self.progress_text_var.set("Archivo descargado exitosamente.")
            self.log_print(f"🏁 {message}")

            if self.abrir_carpeta_var.get():
                carpeta = self.carpeta_var.get().strip()
                if carpeta:
                    try:
                        import os
                        os.startfile(carpeta)
                    except Exception:
                        pass

            messagebox.showinfo("Éxito", message)

        elif cancelled:
            self.status_var.set("Operación cancelada.")
            self.progress_text_var.set("Descarga cancelada por el usuario.")
            self.log_print("🧹 Descarga cancelada.")
            messagebox.showwarning("Cancelado", message)

        else:
            self.status_var.set("Error en la descarga.")
            self.progress_text_var.set("La descarga no se completó.")
            self.log_print("☠ Error en la descarga. Consulta el registro de detalles.")
            messagebox.showerror("Error", message)

    def _on_close(self):
        self._save_config()
        self.destroy()


if __name__ == "__main__":
    ocultar_consola_windows()
    App().mainloop()