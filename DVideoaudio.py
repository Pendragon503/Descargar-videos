import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import yt_dlp


def ocultar_consola_windows():
    try:
        import ctypes
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            ctypes.windll.user32.ShowWindow(whnd, 0)
    except Exception:
        pass


def nombre_seguro(nombre: str) -> str:
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', nombre)
    nombre = re.sub(r'\s+', ' ', nombre).strip()
    return nombre[:180] if len(nombre) > 180 else nombre


def obtener_titulo(url_video: str) -> str:
    opciones_info = {'quiet': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(opciones_info) as ydl:
        info = ydl.extract_info(url_video, download=False)
        titulo = info.get('title', 'descarga')
    return nombre_seguro(titulo)


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("YT Downloader - MP3 / MP4")
        self.state("zoomed")
        self.minsize(1000, 600)

        self.url_var = tk.StringVar()
        self.carpeta_var = tk.StringVar()
        self.modo_var = tk.StringVar(value="mp3")

        # Calidad MP4 (por defecto 1080p ~ 1920x1080)
        self.calidad_var = tk.StringVar(value="1080p (1920×1080)")

        self.en_proceso = False

        self._style()
        self._build_ui()

        # Mostrar/ocultar selector de calidad según modo
        self.modo_var.trace_add("write", lambda *_: self._toggle_calidad_ui())
        self._toggle_calidad_ui()

    def _style(self):
        self.configure(bg="#0f172a")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.C_BG = "#0f172a"
        self.C_PANEL = "#111c35"
        self.C_TEXT = "#e5e7eb"
        self.C_MUTED = "#9ca3af"
        self.C_ACCENT = "#22c55e"
        self.C_ACCENT2 = "#3b82f6"
        self.C_WARN = "#f59e0b"
        self.C_BORDER = "#1f2a44"

        style.configure("Root.TFrame", background=self.C_BG)
        style.configure("Panel.TFrame", background=self.C_PANEL)

        style.configure("Title.TLabel", background=self.C_BG, foreground=self.C_TEXT,
                        font=("Segoe UI", 18, "bold"))
        style.configure("Sub.TLabel", background=self.C_BG, foreground=self.C_MUTED,
                        font=("Segoe UI", 10))

        style.configure("Label.TLabel", background=self.C_PANEL, foreground=self.C_TEXT,
                        font=("Segoe UI", 10))

        style.configure("Footer.TLabel", background=self.C_BG, foreground=self.C_MUTED,
                        font=("Segoe UI", 9))

        style.configure("TRadiobutton", background=self.C_PANEL, foreground=self.C_TEXT,
                        font=("Segoe UI", 10))

        style.configure("TEntry", fieldbackground="#0b1224", foreground=self.C_TEXT,
                        bordercolor=self.C_BORDER, lightcolor=self.C_BORDER, darkcolor=self.C_BORDER,
                        padding=10)

        style.configure("TCombobox", padding=8)

        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=10)

        style.configure("Accent.TButton", background=self.C_ACCENT, foreground="#052e16")
        style.map("Accent.TButton",
                  background=[("active", "#16a34a"), ("disabled", "#14532d")],
                  foreground=[("disabled", "#94a3b8")])

        style.configure("Secondary.TButton", background=self.C_ACCENT2, foreground="#0b1224")
        style.map("Secondary.TButton",
                  background=[("active", "#2563eb"), ("disabled", "#1e3a8a")],
                  foreground=[("disabled", "#94a3b8")])

        style.configure("Danger.TButton", background=self.C_WARN, foreground="#0b1224")
        style.map("Danger.TButton",
                  background=[("active", "#d97706"), ("disabled", "#78350f")],
                  foreground=[("disabled", "#94a3b8")])

    def _build_ui(self):
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Root.TFrame")
        header.pack(fill="x", padx=18, pady=(16, 10))

        ttk.Label(header, text="Descargador YouTube", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="MP3 (audio) o MP4 (video). Logs en vivo. Sin drama.", style="Sub.TLabel").pack(anchor="w", pady=(2, 0))

        main = ttk.Frame(root, style="Root.TFrame")
        main.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        left.configure(width=440)
        left.grid_propagate(False)

        right = ttk.Frame(main, style="Panel.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # --- Controles (izquierda) ---
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

        self.btn_carpeta = ttk.Button(folder_row, text="Elegir…", style="Secondary.TButton", command=self.elegir_carpeta)
        self.btn_carpeta.grid(row=0, column=1, padx=(10, 0))

        # Formato
        opt_frame = ttk.LabelFrame(left, text="Formato", padding=12)
        opt_frame.pack(fill="x", padx=14, pady=(16, 0))
        opt_frame.configure(style="Panel.TFrame")

        self.rb_mp3 = ttk.Radiobutton(opt_frame, text="MP3 (solo audio)", variable=self.modo_var, value="mp3")
        self.rb_mp4 = ttk.Radiobutton(opt_frame, text="MP4 (video)", variable=self.modo_var, value="mp4")
        self.rb_mp3.grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.rb_mp4.grid(row=0, column=1, sticky="w")

        # Calidad (solo MP4)
        self.calidad_box = ttk.LabelFrame(left, text="Calidad de video (MP4)", padding=12)
        self.calidad_box.configure(style="Panel.TFrame")

        ttk.Label(self.calidad_box, text="Elige la calidad máxima:", style="Label.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.combo_calidad = ttk.Combobox(
            self.calidad_box,
            textvariable=self.calidad_var,
            state="readonly",
            values=[
                "Mejor disponible",
                "2160p (3840×2160)",
                "1440p (2560×1440)",
                "1080p (1920×1080)",
                "720p (1280×720)",
                "480p (854×480)",
                "360p (640×360)",
            ]
        )
        self.combo_calidad.grid(row=1, column=0, sticky="we")
        self.calidad_box.columnconfigure(0, weight=1)

        # Estado + botón
        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(left, textvariable=self.status_var, style="Label.TLabel").pack(anchor="w", padx=14, pady=(18, 8))

        self.btn_descargar = ttk.Button(left, text="Descargar", style="Accent.TButton", command=self.on_descargar)
        self.btn_descargar.pack(fill="x", padx=14)

        # --- Logs (derecha) ---
        ttk.Label(right, text="Logs", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))
        self.log = tk.Text(
            right,
            bg="#070d1b",
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            relief="flat",
            padx=10,
            pady=10,
            wrap="word"
        )
        self.log.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))

        # Footer
        footer = ttk.Frame(root, style="Root.TFrame")
        footer.pack(fill="x", padx=18, pady=(0, 14))
        ttk.Label(
            footer,
            text="Desarrollador William Martínez  |  GitHub: Pendragon503",
            style="Footer.TLabel"
        ).pack(anchor="w")

    def _toggle_calidad_ui(self):
        # Mostrar la caja solo si el modo es mp4
        if self.modo_var.get() == "mp4":
            self.calidad_box.pack(fill="x", padx=14, pady=(12, 0))
        else:
            self.calidad_box.pack_forget()

    # -------------------- Helpers --------------------
    def elegir_carpeta(self):
        carpeta = filedialog.askdirectory(title="Selecciona la carpeta destino")
        if carpeta:
            self.carpeta_var.set(carpeta)

    def log_print(self, msg: str):
        def _append():
            self.log.insert("end", msg + "\n")
            self.log.see("end")
        self.after(0, _append)

    def set_processing(self, processing: bool):
        def _apply():
            self.en_proceso = processing
            if processing:
                self.status_var.set("Procesando…")
                self.btn_descargar.config(text="Procesando…", style="Danger.TButton", state="disabled")
                self.btn_carpeta.config(state="disabled")
                self.rb_mp3.config(state="disabled")
                self.rb_mp4.config(state="disabled")
                self.url_entry.config(state="disabled")
                self.folder_entry.config(state="disabled")
                if self.modo_var.get() == "mp4":
                    self.combo_calidad.config(state="disabled")
            else:
                self.status_var.set("Listo.")
                self.btn_descargar.config(text="Descargar", style="Accent.TButton", state="normal")
                self.btn_carpeta.config(state="normal")
                self.rb_mp3.config(state="normal")
                self.rb_mp4.config(state="normal")
                self.url_entry.config(state="normal")
                self.folder_entry.config(state="normal")
                if self.modo_var.get() == "mp4":
                    self.combo_calidad.config(state="readonly")

        self.after(0, _apply)

    def _max_height_from_choice(self) -> int | None:
        choice = self.calidad_var.get().strip()
        if choice == "Mejor disponible":
            return None
        # Extrae el número antes de "p"
        m = re.search(r"(\d{3,4})p", choice)
        if not m:
            return 1080
        return int(m.group(1))

    # -------------------- Descarga --------------------
    def on_descargar(self):
        if self.en_proceso:
            return

        url = self.url_var.get().strip()
        carpeta = self.carpeta_var.get().strip()
        modo = self.modo_var.get().strip()

        if not url:
            messagebox.showerror("Falta URL", "Pega una URL.")
            return
        if not carpeta or not os.path.isdir(carpeta):
            messagebox.showerror("Carpeta inválida", "Elige una carpeta válida.")
            return

        archivo_errores = os.path.join(carpeta, "errores.txt")
        max_h = self._max_height_from_choice() if modo == "mp4" else None

        self.log_print("------------------------------------------------------------")
        if modo == "mp4":
            self.log_print(f"▶ Iniciando (MP4) | Calidad: {self.calidad_var.get()}")
        else:
            self.log_print("▶ Iniciando (MP3)")
        self.set_processing(True)

        t = threading.Thread(
            target=self._descargar_worker,
            args=(url, carpeta, modo, archivo_errores, max_h),
            daemon=True
        )
        t.start()

    def _descargar_worker(self, url_video: str, carpeta_destino: str, modo: str, archivo_errores: str, max_h: int | None):
        try:
            titulo = obtener_titulo(url_video)
            titulo = nombre_seguro(titulo)

            if modo == "mp3":
                nombre_final = f"{titulo}.mp3"
                ruta_final = os.path.join(carpeta_destino, nombre_final)

                if os.path.exists(ruta_final) and os.path.getsize(ruta_final) > 1024 * 1024:
                    self.log_print(f"⏭️ Ya existe (se omite): {nombre_final}")
                    return

                outtmpl = os.path.join(carpeta_destino, f"{titulo}.%(ext)s").replace("\\", "/")

                opciones = {
                    'format': 'bestaudio/best',
                    'outtmpl': outtmpl,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'noplaylist': True,
                    'ignoreerrors': True,
                    'quiet': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                                      'Chrome/120.0.0.0 Safari/537.36'
                    },
                    'extractor_args': {
                        'youtube': {'player_client': ['android', 'web']}
                    }
                }

                self.log_print(f"🎵 Descargando MP3: {url_video}")
                with yt_dlp.YoutubeDL(opciones) as ydl:
                    ydl.download([url_video])

                if os.path.exists(ruta_final) and os.path.getsize(ruta_final) > 1024 * 100:
                    self.log_print(f"✅ Listo: {nombre_final}")
                else:
                    raise RuntimeError("No se generó el MP3 final o quedó muy pequeño. (¿FFmpeg?)")

            else:
                nombre_final = f"{titulo}.mp4"
                ruta_final = os.path.join(carpeta_destino, nombre_final)

                if os.path.exists(ruta_final) and os.path.getsize(ruta_final) > 5 * 1024 * 1024:
                    self.log_print(f"⏭️ Ya existe (se omite): {nombre_final}")
                    return

                outtmpl = os.path.join(carpeta_destino, f"{titulo}.%(ext)s").replace("\\", "/")

                # Si max_h es None -> mejor disponible.
                if max_h is None:
                    format_str = "bv*+ba/best"
                else:
                    # “Hasta” esa calidad. Si no existe, baja a una menor.
                    format_str = f"bestvideo[height<={max_h}]+bestaudio/best[height<={max_h}]"

                opciones = {
                    'format': format_str,
                    'outtmpl': outtmpl,
                    'merge_output_format': 'mp4',
                    'noplaylist': True,
                    'ignoreerrors': True,
                    'quiet': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                                      'Chrome/120.0.0.0 Safari/537.36'
                    },
                    'extractor_args': {
                        'youtube': {'player_client': ['android', 'web']}
                    }
                }

                self.log_print(f"🎬 Descargando MP4: {url_video}")
                self.log_print(f"⚙️ Formato yt-dlp: {format_str}")
                with yt_dlp.YoutubeDL(opciones) as ydl:
                    ydl.download([url_video])

                if os.path.exists(ruta_final) and os.path.getsize(ruta_final) > 1024 * 500:
                    self.log_print(f"✅ Listo: {nombre_final}")
                else:
                    candidatos = [
                        f for f in os.listdir(carpeta_destino)
                        if f.startswith(titulo) and f.lower().endswith(".mp4")
                    ]
                    if candidatos:
                        self.log_print(f"✅ Listo (detectado): {candidatos[-1]}")
                    else:
                        raise RuntimeError("No se generó el MP4 final o quedó muy pequeño.")

        except Exception as e:
            self.log_print(f"❌ Error: {e}")
            try:
                with open(archivo_errores, "a", encoding="utf-8") as f:
                    f.write(url_video + "\n")
            except Exception:
                pass
        finally:
            self.set_processing(False)


if __name__ == "__main__":
    ocultar_consola_windows()
    App().mainloop()
