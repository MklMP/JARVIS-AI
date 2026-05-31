import os
import re
import json
import subprocess
from datetime import timedelta
from .base import ModuleBase
from utils.emoji import CARPETA, ARCHIVO, PELICULA

try:
    from utils.emoji import PELICULA
except ImportError:
    PELICULA = "[Movie]"


VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".mpeg", ".mpg", ".m4v", ".divx"}
MIN_DURACION_SEG = 3600  # 1 hora
MAX_RESULTADOS = 50
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "catalogo_cache.json")

FFPROBE = None
for _p in [
    r"C:\ffmpeg-8.0.1-essentials_build\bin\ffprobe.exe",
    r"C:\ffmpeg\bin\ffprobe.exe",
    "ffprobe",
]:
    try:
        subprocess.run([_p, "-version"], capture_output=True, timeout=5)
        FFPROBE = _p
        break
    except Exception:
        continue

# Buscar reproductor multimedia con soporte de pantalla completa
VLC_PATH = None
MPC_PATH = None

for _p in [
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
]:
    if os.path.isfile(_p):
        VLC_PATH = _p
        break

for _p in [
    r"C:\Program Files (x86)\MPC-HC\mpc-hc.exe",
    r"C:\Program Files\MPC-HC\mpc-hc.exe",
    r"C:\Program Files (x86)\K-Lite Codec Pack\MPC-HC64\mpc-hc64.exe",
]:
    if os.path.isfile(_p):
        MPC_PATH = _p
        break


class CatalogoModule(ModuleBase):
    """Escanea el disco en busca de películas (videos >1h) y permite seleccionar una."""

    def __init__(self, config: dict, api_keys: dict):
        super().__init__(config, api_keys)
        self._catalogo = []
        self._cache_valido = False
        self._cargar_cache()

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        # "catalogo" -> mostrar catálogo
        if any(p in cmd for p in ["catalogo", "catálogo", "películas", "peliculas", "mis pelis", "filmoteca", "videoteca", "lista pelis"]):
            if "actualizar" in cmd or "refrescar" in cmd or "recargar" in cmd or "reindexar" in cmd or "reescanear" in cmd:
                return self._escanear()
            if self._catalogo:
                return self._mostrar_catalogo()
            return self._escanear()

        # "elige 3", "seleccionar 5", "reproduce 2" -> reproducir
        m = re.search(r'\b(\d+)\b', cmd)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(self._catalogo):
                return self._reproducir(idx)
            return f"  Número inválido. Elige entre 1 y {len(self._catalogo)}."

        return self.help()

    def _escanear(self) -> str:
        """Escanea directorios comunes en busca de videos >1h."""
        import time
        inicio = time.time()

        self._catalogo = []
        directorios = self._obtener_directorios()

        partes = []
        for base_dir in directorios:
            if not os.path.isdir(base_dir):
                continue
            partes.append(f"  {CARPETA}  {base_dir}")
            for root, dirs, files in os.walk(base_dir):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in VIDEO_EXT:
                        continue
                    ruta = os.path.join(root, f)
                    duracion = self._obtener_duracion(ruta)
                    if duracion and duracion >= MIN_DURACION_SEG:
                        self._catalogo.append({
                            "ruta": ruta,
                            "nombre": os.path.splitext(f)[0],
                            "duracion": duracion,
                            "ext": ext,
                            "tamano": os.path.getsize(ruta),
                        })

        self._catalogo.sort(key=lambda x: x["duracion"], reverse=True)
        self._guardar_cache()

        elapsed = time.time() - inicio
        if not self._catalogo:
            return (
                f"  No encontré películas (>1h) en los directorios escaneados.\n"
                f"  Puedes agregar carpetas en config.json en 'modules.catalogo.directorios'."
            )
        return (
            f"  Escaneo completado en {elapsed:.1f}s.\n"
            f"  {PELICULA}  Encontré {len(self._catalogo)} película(s).\n"
            f"  Di el número para reproducir, o revisa el catálogo con 'catalogo'."
        )

    def _mostrar_catalogo(self) -> str:
        if not self._catalogo:
            return "  No hay catálogo cargado. Di 'actualizar catalogo' para escanear."

        lineas = [f"  {PELICULA}  CATÁLOGO DE PELÍCULAS ({len(self._catalogo)})\n"]
        for i, peli in enumerate(self._catalogo[:MAX_RESULTADOS], 1):
            duracion = str(timedelta(seconds=int(peli["duracion"])))
            tamano = self._formatear_tamano(peli["tamano"])
            nombre = peli["nombre"][:60]
            lineas.append(f"  {i:2d}. {ARCHIVO} {nombre}")
            dirname = os.path.basename(os.path.dirname(peli["ruta"]))
            lineas.append(f"      {duracion} · {tamano} · {dirname}")

        if len(self._catalogo) > MAX_RESULTADOS:
            lineas.append(f"\n  ... y {len(self._catalogo) - MAX_RESULTADOS} más.")
            lineas.append(f"  (Di 'actualizar catalogo' para reescanear)")

        lineas.append(f"\n  Di el número de la película para reproducirla.")
        return "\n".join(lineas)

    def _reproducir(self, idx: int) -> str:
        peli = self._catalogo[idx]
        ruta = peli["ruta"]
        if not os.path.exists(ruta):
            return f"  El archivo ya no existe:\n  {ruta}"

        reproductor = None
        args = []

        if VLC_PATH:
            reproductor = VLC_PATH
            args = ["--fullscreen", "--play-and-exit", "--no-video-title"]
        elif MPC_PATH:
            reproductor = MPC_PATH
            args = ["/fullscreen", "/play"]

        if reproductor:
            try:
                subprocess.Popen([reproductor] + args + [ruta])
                return (
                    f"  {PELICULA}  Reproduciendo (pantalla completa): {peli['nombre']}\n"
                    f"  {peli['ruta']}"
                )
            except Exception:
                pass

        # Fallback: reproductor por defecto de Windows
        try:
            os.startfile(ruta)
            return (
                f"  {PELICULA}  Reproduciendo: {peli['nombre']}\n"
                f"  {peli['ruta']}"
            )
        except Exception:
            try:
                subprocess.Popen(["start", "", ruta], shell=True)
                return (
                    f"  {PELICULA}  Reproduciendo: {peli['nombre']}\n"
                    f"  {peli['ruta']}"
                )
            except Exception as e2:
                return f"  No pude abrir el archivo: {e2}"

    def _obtener_directorios(self) -> list:
        mod_config = self.config.get("modules", {}).get("catalogo", {})
        config_dirs = mod_config.get("directorios", [])

        # Siempre incluir defaults + lo configurado
        user = os.environ.get("USERPROFILE", "C:\\Users\\MKL")
        defaults = [
            os.path.join(user, "Videos"),
            os.path.join(user, "Desktop"),
            os.path.join(user, "Downloads"),
            os.path.join(user, "Documents"),
            os.path.join(user, "Movies"),
            os.path.join(user, "OneDrive", "Videos"),
            os.path.join(user, "OneDrive", "Desktop"),
            os.path.join(user, "OneDrive", "Downloads"),
            os.path.join(user, "OneDrive", "Documents"),
        ]
        dirs = config_dirs + defaults

        # Filtrar solo los que existen (sin duplicados)
        vistos = set()
        unicos = []
        for d in dirs:
            normalizado = os.path.realpath(d).lower()
            if normalizado not in vistos and os.path.isdir(d):
                vistos.add(normalizado)
                unicos.append(d)
        return unicos

    def _obtener_duracion(self, ruta: str) -> int:
        """Retorna duración en segundos usando ffprobe. 0 si no se puede determinar."""
        if not FFPROBE:
            return 0
        try:
            result = subprocess.run(
                [FFPROBE, "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-show_format", ruta],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return 0
            info = json.loads(result.stdout)
            # Intentar obtener duración del formato
            fmt = info.get("format", {})
            dur = fmt.get("duration")
            if dur:
                return float(dur)
            # Fallback: obtener duración del primer stream de video
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    dur = stream.get("duration")
                    if dur:
                        return float(dur)
                    # Si no hay duración en stream, calcular desde tags
                    tag_dur = stream.get("tags", {}).get("DURATION")
                    if tag_dur:
                        return self._parse_duration_tag(tag_dur)
            return 0
        except Exception:
            return 0

    def _parse_duration_tag(self, tag: str) -> float:
        """Parsea duración en formato HH:MM:SS.mmm"""
        try:
            parts = tag.split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            pass
        return 0

    def _formatear_tamano(self, bytes_: int) -> str:
        if bytes_ < 1024**3:
            return f"{bytes_ / 1024**2:.1f} MB"
        return f"{bytes_ / 1024**3:.2f} GB"

    def _cargar_cache(self):
        if not os.path.exists(CACHE_FILE):
            return
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._catalogo = data.get("peliculas", [])
            self._cache_valido = True
        except Exception:
            self._catalogo = []
            self._cache_valido = False

    def _guardar_cache(self):
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"peliculas": self._catalogo, "total": len(self._catalogo)}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def help(self) -> str:
        return (
            "CATÁLOGO DE PELÍCULAS:\n"
            "  catalogo                  - Muestra el catálogo de películas\n"
            "  actualizar catalogo       - Reescanea el disco en busca de películas\n"
            "  <número>                  - Reproduce la película del número indicado\n"
            "\n"
            "Ej: catalogo\n"
            "    reproduce 3\n"
            "    actualizar catalogo"
        )
