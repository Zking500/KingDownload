import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import threading
import yt_dlp
import os
import time
import pygame
import sys
import json
import shutil
import subprocess
import platform
import webbrowser
import urllib.request
import zipfile
from tkinter import simpledialog
import tempfile

try:
    import py7zr
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "py7zr"])
    import py7zr

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z"
FFMPEG_FOLDER = "ffmpeg_bin"

FONDO_COLOR = "#0b1113"
BOTON_COLOR = "#1f6feb"
TEXTO_COLOR = "#ffffff"
FUENTE = ("Arial", 11)
CONFIG_FILE = "config.txt"
HISTORIAL_FILE = "historial.json"
DEFAULT_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DEFAULT_FOLDER, exist_ok=True)

PREFERIDOS = [
    ("h264_nvenc", "NVIDIA GPU (rápido, compatible)"),
    ("h264_amf", "AMD GPU (rápido, compatible)"),
    ("h264_qsv", "Intel GPU (rápido, compatible)"),
    ("libx264", "CPU (universal, más lento)"),
]

# ===================== helpers ===================== #

def resource_path(relative_path: str) -> str:
    """Obtiene rutas absolutas compatibles con PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def ffmpeg_available() -> bool:
    """Comprueba si FFmpeg está disponible en el sistema o en ffmpeg_bin."""
    # Busca en PATH
    if shutil.which("ffmpeg"):
        return True
    # Busca en ffmpeg_bin local
    local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg_bin", "ffmpeg.exe")
    return os.path.isfile(local_ffmpeg)


def add_to_path(path: str) -> None:
    """Agrega una carpeta al PATH de la sesión actual."""
    if path and path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")

# ===================== descarga automática de FFmpeg ===================== #

class FFmpegInstaller:
    """Maneja la descarga e instalación automática de FFmpeg (solo Windows)."""

    WINDOWS_ZIP_URL = (
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    )

    def __init__(self, parent: tk.Tk):
        self.parent = parent
        self.install_dir = os.path.join(os.getcwd(), "ffmpeg_bin")
        os.makedirs(self.install_dir, exist_ok=True)

    def prompt_install(self) -> bool:
        """Pregunta al usuario y, en caso afirmativo, intenta instalar FFmpeg."""
        if platform.system() != "Windows":
            messagebox.showinfo(
                "Instalación no soportada",
                "La instalación automática solo está disponible en Windows. "
                "Por favor, instala FFmpeg manualmente desde: https://ffmpeg.org/download.html",
            )
            return False

        resp = messagebox.askyesno(
            "FFmpeg faltante",
            "No se encontró FFmpeg en tu sistema.\n\n"
            "¿Deseas que la aplicación lo descargue e instale automáticamente?",
        )
        if not resp:
            return False

        try:
            self._download_and_extract()
            add_to_path(self.install_dir)
            if ffmpeg_available():
                messagebox.showinfo(
                    "FFmpeg instalado",
                    "FFmpeg se instaló correctamente y está listo para usarse.",
                )
                return True
            else:
                raise RuntimeError("FFmpeg sigue sin detectarse tras la instalación.")
        except Exception as err:
            messagebox.showerror(
                "Error de instalación",
                f"Ocurrió un problema instalando FFmpeg automáticamente:\n{err}\n\n"
                "Procede a instalarlo manualmente si el problema persiste.",
            )
            return False

    def _download_and_extract(self) -> None:
        """Descarga el ZIP oficial de FFmpeg y extrae ffmpeg.exe."""
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
        os.close(tmp_fd)

        # Descarga
        with urllib.request.urlopen(self.WINDOWS_ZIP_URL) as resp, open(tmp_path, "wb") as out_f:
            total = int(resp.headers.get("Content-Length", 0))
            read = 0
            chunk = 8192
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                out_f.write(buf)
                read += len(buf)
                self._update_progress(read, total)

        # Extracción
        with zipfile.ZipFile(tmp_path) as z:
            members = [m for m in z.namelist() if m.endswith("ffmpeg.exe")]
            if not members:
                raise FileNotFoundError("ffmpeg.exe no encontrado en el ZIP.")
            for m in members:
                extracted_path = z.extract(m, self.install_dir)
                # mover ffmpeg.exe a la raíz de install_dir
                target_path = os.path.join(self.install_dir, "ffmpeg.exe")
                shutil.move(extracted_path, target_path)
                break  # solo necesitamos uno
        os.remove(tmp_path)

    def _update_progress(self, read: int, total: int) -> None:
        """Actualiza una barra de progreso simple en la ventana principal."""
        percent = read / total * 100 if total else 0
        self.parent.progress["value"] = percent
        self.parent.status_label.config(
            text=f"Descargando FFmpeg... {percent:0.1f}%")
        self.parent.update_idletasks()

# ===================== clase principal ===================== #

class YouTubeDownloader(tk.Tk):
    """Interfaz gráfica para descargar video (MP4) + audio (MP3) desde YouTube (incluye YouTube Music)."""

    def __init__(self) -> None:
        super().__init__()

        # ---- ventana ---- #
        self.title("Descargador YouTube (Video MP4 + Audio MP3) - zkingStudios")
        try:
            self.iconbitmap(resource_path("img/logo.ico"))
        except Exception:
            pass
        self.geometry("600x650")
        self.resizable(False, False)
        self.configure(bg=FONDO_COLOR)

        # ---- audio de interfaz ---- #
        pygame.mixer.init()
        self.sfx: dict[str, pygame.mixer.Sound] = {}

        # ---- variables de estado ---- #
        self.url_var = tk.StringVar()
        self.formats: list[tuple[str, str]] = []  # (descripcion, itag)
        self.selected_format = tk.StringVar()
        self.download_folder = DEFAULT_FOLDER
        self._start_time = None
        self.current_video_title: str = ""
        self.current_thumbnail: ImageTk.PhotoImage | None = None
        self.only_mp3 = tk.BooleanVar(value=False)
        self.encoder = None

        # ---- carga configuración previa ---- #
        self.load_config()
        # self.ask_encoder_if_needed()  # <-- QUITAR selección de encoder al inicio

        # ---- gestionar FFmpeg ---- #
        self.after(100, self.ensure_ffmpeg_and_encoder)

        # ---- interfaz ---- #
        self.create_menu()
        self.create_widgets()
        self.bind_shortcuts()

    def ensure_ffmpeg_and_encoder(self):
        # 1. Asegura FFmpeg antes de cualquier otra cosa
        self.ensure_ffmpeg()
        # 2. Carga encoder (o usa por defecto si no existe)
        self.load_encoder()

    def ensure_ffmpeg(self):
        exe_path = os.path.join(os.getcwd(), "ffmpeg_bin", "ffmpeg.exe")
        if not os.path.exists(exe_path):
            try:
                # Usa el ZIP oficial (no el 7z)
                tmp_zip = os.path.join(os.getcwd(), "ffmpeg_bin", "ffmpeg_tmp.zip")
                os.makedirs("ffmpeg_bin", exist_ok=True)
                url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
                with urllib.request.urlopen(url) as resp, open(tmp_zip, "wb") as out_f:
                    shutil.copyfileobj(resp, out_f)
                with zipfile.ZipFile(tmp_zip) as z:
                    exe_files = [f for f in z.namelist() if f.endswith("ffmpeg.exe")]
                    if not exe_files:
                        raise RuntimeError("ffmpeg.exe no encontrado en el ZIP")
                    for f in exe_files:
                        extracted_path = z.extract(f, "ffmpeg_bin")
                        dst = os.path.join("ffmpeg_bin", "ffmpeg.exe")
                        shutil.move(extracted_path, dst)
                        subdir = os.path.dirname(extracted_path)
                        if os.path.exists(subdir) and subdir != "ffmpeg_bin":
                            shutil.rmtree(subdir, ignore_errors=True)
                        break
                os.remove(tmp_zip)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo descargar FFmpeg:\n{e}")

    def load_encoder(self):
        if os.path.exists("config.txt"):
            with open("config.txt", "r", encoding="utf-8") as f:
                self.encoder = f.read().strip()
        else:
            self.encoder = "libx264"  # Usa por defecto, no pregunta

    def select_encoder_dialog(self):
        opciones = [
            ("h264_nvenc", "Tengo NVIDIA (rápido, recomendado para edición)"),
            ("h264_amf", "Tengo AMD (rápido, recomendado para edición)"),
            ("h264_qsv", "Tengo solo gráficos integrados Intel"),
            ("libx264", "Solo CPU (universal, más lento)"),
        ]
        msg = "¿Qué tipo de gráfica tienes?\n\n"
        for i, (cod, desc) in enumerate(opciones, 1):
            msg += f"{i}. {desc}\n"
        msg += "\nEscribe el número de la opción:"
        sel = simpledialog.askinteger("Configuración de encoder", msg, minvalue=1, maxvalue=len(opciones))
        if sel and 1 <= sel <= len(opciones):
            self.encoder = opciones[sel-1][0]
            with open("config.txt", "w", encoding="utf-8") as f:
                f.write(self.encoder)
            messagebox.showinfo("Encoder guardado", f"Encoder '{self.encoder}' guardado en config.txt")
        else:
            # Si cancela, usa libx264 por defecto
            self.encoder = "libx264"
            with open("config.txt", "w", encoding="utf-8") as f:
                f.write(self.encoder)
            messagebox.showwarning("Sin cambios", "No se cambió el encoder. Se usará CPU (libx264).")

    # ---------- comprobación e instalación de FFmpeg ---------- #

    def check_ffmpeg(self) -> None:
        """Verifica si FFmpeg existe, ofrece instalarlo o abrir enlace."""
        if ffmpeg_available():
            return

        installer = FFmpegInstaller(self)
        installed = installer.prompt_install()
        if not installed:
            abrir = messagebox.askyesno(
                "Instalar FFmpeg",
                "FFmpeg es necesario para las conversiones a MP4/MP3.\n\n"
                "¿Deseas abrir la página de descargas en tu navegador?",
            )
            if abrir:
                webbrowser.open("https://ffmpeg.org/download.html")

    # ---------- configuración ---------- #

    def load_config(self) -> None:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                path = f.read().strip()
                if os.path.isdir(path):
                    self.download_folder = path

    def save_config(self) -> None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(self.download_folder)

    # ---------- atajos ---------- #

    def bind_shortcuts(self) -> None:
        self.bind("<Control-v>", lambda _e: self.paste_url())
        self.bind("<Return>", lambda _e: self.list_formats_thread())
        self.bind("<Control-d>", lambda _e: self.download_thread())
        self.bind("<Control-h>", lambda _e: self.show_history())

    # ---------- menú ---------- #

    def create_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        archivo_menu = tk.Menu(menubar, tearoff=0)
        archivo_menu.add_command(label="Seleccionar carpeta...", command=self.select_folder)
        archivo_menu.add_command(label="Ver historial", command=self.show_history)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Salir", command=self.destroy)
        menubar.add_cascade(label="Archivo", menu=archivo_menu)

        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="Cambiar encoder de video...", command=self.select_encoder_dialog)
        menubar.add_cascade(label="Configuración", menu=config_menu)

        ayuda_menu = tk.Menu(menubar, tearoff=0)
        ayuda_menu.add_command(label="Acerca de formatos", command=self.show_help)
        ayuda_menu.add_command(
            label="Créditos", command=lambda: messagebox.showinfo("Créditos", "Desarrollado por zkingStudios"))
        menubar.add_cascade(label="Ayuda", menu=ayuda_menu)

    # ---------- widgets ---------- #

    def create_widgets(self) -> None:
        self.load_logo()

        tk.Label(self, text="URL del video o playlist:", bg=FONDO_COLOR, fg=TEXTO_COLOR, font=FUENTE).pack(pady=(10, 0))
        url_entry = tk.Entry(self, textvariable=self.url_var, width=70, font=FUENTE, bg=FONDO_COLOR,
                             fg=TEXTO_COLOR, insertbackground=TEXTO_COLOR)
        url_entry.pack(pady=5)

        self.btn_list = ttk.Button(self, text="Listar formatos (video)", command=self.list_formats_thread)
        self.btn_list.pack(pady=5)

        self.thumbnail_label = tk.Label(self, bg=FONDO_COLOR)
        self.thumbnail_label.pack(pady=5)

        tk.Label(self, text="Selecciona resolución (solo video):", bg=FONDO_COLOR, fg=TEXTO_COLOR,
                 font=FUENTE).pack(pady=(10, 0))
        self.combo_formats = ttk.Combobox(self, textvariable=self.selected_format, width=65, state="readonly")
        self.combo_formats.pack(pady=5)

        self.filename_preview = tk.Label(self, text="", bg=FONDO_COLOR, fg=TEXTO_COLOR, font=FUENTE)
        self.filename_preview.pack(pady=5)

        self.btn_download = ttk.Button(self, text="Descargar (MP4 + MP3)", command=self.download_thread)
        self.btn_download.pack(pady=10)

        self.progress = ttk.Progressbar(self, length=500, mode="determinate")
        self.progress.pack(pady=5)

        self.status_label = tk.Label(self, text="", bg=FONDO_COLOR, fg=TEXTO_COLOR, font=FUENTE)
        self.status_label.pack()

        self.only_mp3_check = ttk.Checkbutton(
            self, text="Solo MP3 (modo música)", variable=self.only_mp3
        )
        self.only_mp3_check.pack(pady=2)

    def load_logo(self) -> None:
        logo_path = resource_path("img/logo.png")
        try:
            img = Image.open(logo_path).resize((120, 120))
            photo = ImageTk.PhotoImage(img)
            self.logo_img = photo  # evitar que el GC la limpie
            tk.Label(self, image=photo, bg=FONDO_COLOR).pack(pady=5)
        except Exception:
            pass

    # ---------- utilidades de sonido ---------- #

    def play_sound(self, name: str) -> None:
        path = resource_path(os.path.join("sfx", f"{name}.mp3"))
        if os.path.exists(path):
            if name not in self.sfx:
                try:
                    self.sfx[name] = pygame.mixer.Sound(path)
                except Exception:
                    return
            self.sfx[name].play()

    # ---------- portapapeles ---------- #

    def paste_url(self) -> None:
        try:
            self.url_var.set(self.clipboard_get())
        except Exception:
            pass

    # ---------- carpeta destino ---------- #

    def select_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.download_folder = folder
            self.save_config()
            self.status_label.config(text=f"Carpeta seleccionada: {folder}")
            self.play_sound("click")

    # ---------- mensajes de ayuda ---------- #

    @staticmethod
    def show_help() -> None:
        msg = (
            "Descarga simplificada:\n\n"
            "1. Se mostrará SOLO la lista de formatos VIDEO‑ONLY disponibles.\n"
            "2. El video se descargará y convertirá automáticamente a MP4 (H.264)\n   compatible con la mayoría de editores (DaVinci Resolve, etc.).\n"
            "3. El audio se descarga aparte en la mejor calidad disponible y\n   se convierte a MP3 de 320 kbps.\n"
            "4. Recuerda tener instalado FFmpeg para las conversiones."
        )
        messagebox.showinfo("Ayuda de formatos", msg)

    # ---------- historial ---------- #

    def show_history(self) -> None:
        if os.path.exists(HISTORIAL_FILE):
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
        else:
            datos = []
        historial_text = "\n\n".join(f"{d['fecha']} - {d['titulo']} ({d['formato']})" for d in datos)
        messagebox.showinfo("Historial de Descargas", historial_text or "No hay descargas registradas aún.")

    # =============================================================
    #                LISTADO DE FORMATOS (SOLO VIDEO)
    # =============================================================

    def list_formats_thread(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Por favor ingresa una URL válida.")
            return
        self.status_label.config(text="Obteniendo formatos de video...")
        self.play_sound("click")
        threading.Thread(target=self.list_formats, args=(url,), daemon=True).start()

    def list_formats(self, url: str) -> None:
        try:
            ydl_opts = {"quiet": True, "skip_download": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            self.current_video_title = info.get("title", "video")
            thumbnail_url = info.get("thumbnail")
            self.formats = []

            # miniatura
            if thumbnail_url:
                from urllib.request import urlopen
                from io import BytesIO

                data = urlopen(thumbnail_url).read()
                img = Image.open(BytesIO(data)).resize((160, 90))
                photo = ImageTk.PhotoImage(img)
                self.current_thumbnail = photo
                self.thumbnail_label.config(image=photo)
                self.thumbnail_label.image = photo

            # Solo una WebM por resolución
            seen_resolutions = set()
            for f in info.get("formats", []):
                acodec, vcodec = f.get("acodec"), f.get("vcodec")
                ext = f.get("ext")
                resolution = f.get("resolution") or (
                    f.get("height") and f"{f.get('height')}p") or "?p"
                if acodec == "none" and vcodec != "none" and ext == "webm":
                    if resolution in seen_resolutions:
                        continue
                    seen_resolutions.add(resolution)
                    itag = f.get("format_id")
                    filesize = f.get("filesize") or f.get("filesize_approx") or 0
                    size_mb = round(filesize / (1024 * 1024), 2)
                    desc = f"{resolution} — {ext.upper()} — {size_mb}MB (itag:{itag})"
                    self.formats.append((desc, itag))

            self.combo_formats["values"] = [f[0] for f in self.formats]
            if self.formats:
                self.combo_formats.current(0)
                preview_name = f"{self.current_video_title}.mp4"
                self.filename_preview.config(text=f"Archivo de video final: {preview_name}")
                self.status_label.config(text=f"Se encontraron {len(self.formats)} resoluciones de video.")
            else:
                self.combo_formats.set("")
                self.filename_preview.config(text="")
                self.status_label.config(text="No se encontraron formatos de video‑only.")

        except Exception as err:
            messagebox.showerror("Error", f"No se pudo obtener formatos:\n{err}")
            self.play_sound("error")
            self.status_label.config(text="")

    # =============================================================
    #                       DESCARGA PRINCIPAL
    # =============================================================

    def download_thread(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Por favor ingresa una URL válida.")
            return
        if not self.selected_format.get():
            messagebox.showerror("Error", "Selecciona una resolución de video.")
            return
        if not ffmpeg_available():
            messagebox.showerror(
                "FFmpeg requerido",
                "FFmpeg es necesario para descargar/convertir. Instálalo antes de continuar.",
            )
            return
        self.play_sound("click")
        self.progress["value"] = 0
        self.status_label.config(text="Preparando descarga...")
        threading.Thread(target=self.download, args=(url,), daemon=True).start()

    def download(self, url: str) -> None:
        desc_sel = self.selected_format.get()
        itag = next((itag for desc, itag in self.formats if desc == desc_sel), None)
        if not itag and not self.only_mp3.get():
            messagebox.showerror("Error", "Formato de video inválido seleccionado.")
            self.play_sound("error")
            return

        safe_title = "".join(c for c in self.current_video_title if c.isalnum() or c in " -_")
        temp_dir = os.path.join(self.download_folder, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        outtmpl_audio = os.path.join(temp_dir, f"{safe_title}.%(ext)s")
        outtmpl_video = os.path.join(temp_dir, f"{safe_title}_video.%(ext)s")
        ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg_bin", "ffmpeg.exe")

        # Opciones para descargar el mejor audio
        ydl_opts_audio = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl_audio,
            "quiet": True,
            "progress_hooks": [self.progress_hook],
            "ffmpeg_location": ffmpeg_path
        }

        # Opciones para descargar solo video
        ydl_opts_video = {
            "format": itag,
            "outtmpl": outtmpl_video,
            "quiet": True,
            "progress_hooks": [self.progress_hook],
            "ffmpeg_location": ffmpeg_path
        }

        fases = []
        if self.only_mp3.get():
            fases = ["1/3 Descargando audio...", "2/3 Convirtiendo a MP3...", "3/3 Borrando temporales..."]
        else:
            fases = [
                "1/5 Descargando audio...",
                "2/5 Descargando video...",
                "3/5 Convirtiendo video a MP4...",
                "4/5 Convirtiendo audio a MP3...",
                "5/5 Borrando temporales..."
            ]

        self._start_time = time.time()
        try:
            # Fase 1: Descargar audio
            self.status_label.config(text=fases[0])
            with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                info_audio = ydl.extract_info(url, download=True)
                audio_file = ydl.prepare_filename(info_audio)

            # Fase 2: Solo MP3 o Video+Audio
            if self.only_mp3.get():
                self.status_label.config(text=fases[1])
                mp3_file = os.path.join(self.download_folder, f"{safe_title}.mp3")
                subprocess.run([
                    ffmpeg_path, "-y", "-i", audio_file, "-vn", "-ab", "320k", "-ar", "44100", "-f", "mp3", mp3_file
                ], check=True)
            else:
                # Fase 2: Descargar video
                self.status_label.config(text=fases[1])
                with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
                    info_video = ydl.extract_info(url, download=True)
                    video_file = ydl.prepare_filename(info_video)

                # Fase 3: Convertir video a MP4
                self.status_label.config(text=fases[2])
                mp4_file = os.path.join(self.download_folder, f"{safe_title}.mp4")
                cmd = [ffmpeg_path, "-y", "-i", video_file, "-c:v", self.encoder]
                if self.encoder in ("libx264", "h264_nvenc"):
                    cmd += ["-preset", "fast", "-crf", "22"]
                cmd += ["-an", mp4_file]

                subprocess.run(cmd, check=True)

                # Fase 4: Convertir audio a MP3
                self.status_label.config(text=fases[3])
                mp3_file = os.path.join(self.download_folder, f"{safe_title}.mp3")
                subprocess.run([
                    ffmpeg_path, "-y", "-i", audio_file, "-vn", "-ab", "320k", "-ar", "44100", "-f", "mp3", mp3_file
                ], check=True)

            # Fase final: Borrar temporales
            self.status_label.config(text=fases[-1])
            for f in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, f))
                except Exception:
                    pass
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass

            self.record_download(safe_title, desc_sel if not self.only_mp3.get() else "MP3")
            messagebox.showinfo("Éxito", "Descarga completada con éxito!")
            self.play_sound("success")
            self.status_label.config(text=f"Descarga completada en {time.time() - self._start_time:.1f} segundos.")
            self.progress["value"] = 100

        except Exception as err:
            messagebox.showerror("Error", f"Error durante la descarga:\n{err}")
            self.play_sound("error")
            self.status_label.config(text="Error en la descarga")
            self.progress["value"] = 0

    def progress_hook(self, d: dict) -> None:
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
            percent = (downloaded / total) * 100 if total else 0

            speed = d.get("speed") or 0  # <-- Cambia aquí: si es None, usa 0
            speed_mb = speed / (1024 * 1024) if speed else 0

            if self._start_time:
                elapsed = time.time() - self._start_time
                if speed > 0 and percent > 0:
                    remaining = (total - downloaded) / speed
                    time_str = f"{elapsed:.1f}s | {remaining:.1f}s restantes"
                else:
                    time_str = f"{elapsed:.1f}s"
            else:
                time_str = ""

            self.progress["value"] = percent
            self.status_label.config(
                text=f"Descargando... {percent:.1f}% | {speed_mb:.1f} MB/s | {time_str}"
            )
            self.update_idletasks()

    def record_download(self, title: str, formato: str) -> None:
        """Guarda la descarga en el historial."""
        entry = {
            "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "titulo": title,
            "formato": formato.split("—")[0].strip(),
        }
        
        historial = []
        if os.path.exists(HISTORIAL_FILE):
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                try:
                    historial = json.load(f)
                except json.JSONDecodeError:
                    historial = []
        
        historial.insert(0, entry)
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)

    def progress_hook(self, d: dict) -> None:
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
            percent = (downloaded / total) * 100 if total else 0
            
            speed = d.get("speed") or 0  # <-- Cambia aquí: si es None, usa 0
            speed_mb = speed / (1024 * 1024) if speed else 0
            
            if self._start_time:
                elapsed = time.time() - self._start_time
                if speed > 0 and percent > 0:
                    remaining = (total - downloaded) / speed
                    time_str = f"{elapsed:.1f}s | {remaining:.1f}s restantes"
                else:
                    time_str = f"{elapsed:.1f}s"
            else:
                time_str = ""
            
            self.progress["value"] = percent
            self.status_label.config(
                text=f"Descargando... {percent:.1f}% | {speed_mb:.1f} MB/s | {time_str}"
            )
            self.update_idletasks()

    def record_download(self, title: str, formato: str) -> None:
        """Guarda la descarga en el historial."""
        entry = {
            "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "titulo": title,
            "formato": formato.split("—")[0].strip(),
        }
        
        historial = []
        if os.path.exists(HISTORIAL_FILE):
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                try:
                    historial = json.load(f)
                except json.JSONDecodeError:
                    historial = []
        
        historial.insert(0, entry)
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)

    def ask_encoder_if_needed(self):
        # Siempre pregunta al usuario qué encoder usar
        self.select_encoder_dialog()

    def load_encoder(self):
        if os.path.exists("config.txt"):
            with open("config.txt", "r", encoding="utf-8") as f:
                self.encoder = f.read().strip()
        else:
            self.encoder = "libx264"

    def select_encoder_dialog(self):
        opciones = [
            ("h264_nvenc", "Tengo NVIDIA (rápido, recomendado para edición)"),
            ("h264_amf", "Tengo AMD (rápido, recomendado para edición)"),
            ("h264_qsv", "Tengo solo gráficos integrados Intel"),
            ("libx264", "Solo CPU (universal, más lento)"),
        ]
        msg = "¿Qué tipo de gráfica tienes?\n\n"
        for i, (cod, desc) in enumerate(opciones, 1):
            msg += f"{i}. {desc}\n"
        msg += "\nEscribe el número de la opción:"
        sel = simpledialog.askinteger("Configuración de encoder", msg, minvalue=1, maxvalue=len(opciones))
        if sel and 1 <= sel <= len(opciones):
            self.encoder = opciones[sel-1][0]
            with open("config.txt", "w", encoding="utf-8") as f:
                f.write(self.encoder)
            messagebox.showinfo("Encoder guardado", f"Encoder '{self.encoder}' guardado en config.txt")
        else:
            # Si cancela, usa libx264 por defecto
            self.encoder = "libx264"
            with open("config.txt", "w", encoding="utf-8") as f:
                f.write(self.encoder)
            messagebox.showwarning("Sin cambios", "No se cambió el encoder. Se usará CPU (libx264).")

    # En el menú de configuración, llama a select_encoder_dialog para cambiar el encoder
    def create_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        archivo_menu = tk.Menu(menubar, tearoff=0)
        archivo_menu.add_command(label="Seleccionar carpeta...", command=self.select_folder)
        archivo_menu.add_command(label="Ver historial", command=self.show_history)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Salir", command=self.destroy)
        menubar.add_cascade(label="Archivo", menu=archivo_menu)

        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="Cambiar encoder de video...", command=self.select_encoder_dialog)
        menubar.add_cascade(label="Configuración", menu=config_menu)

        ayuda_menu = tk.Menu(menubar, tearoff=0)
        ayuda_menu.add_command(label="Acerca de formatos", command=self.show_help)
        ayuda_menu.add_command(
            label="Créditos", command=lambda: messagebox.showinfo("Créditos", "Desarrollado por zkingStudios"))
        menubar.add_cascade(label="Ayuda", menu=ayuda_menu)

if __name__ == "__main__":
    app = YouTubeDownloader()
    app.mainloop()
