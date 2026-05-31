"""
MÃ³dulo de mÃºsica - bÃºsqueda, listado y reproducciÃ³n local.
Usa Everything para buscar y pygame (o WMP) para reproducir.
"""

import os
import subprocess
import threading
import random
import json
from .base import ModuleBase
from utils.emoji import ARCHIVO


class MusicModule(ModuleBase):
    """ReproducciÃ³n de mÃºsica local."""

    ES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "es.exe")
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "music_dirs.json")

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self._player = None
        self._colar_actual = None
        self._reproduciendo = False
        self._pausado = False
        self._playlist = []
        self._indice_actual = -1
        self._resultados_youtube = []
        self._directorios = []
        self._pendiente_ruta = False
        self._cargar_directorios()

    def _cargar_directorios(self):
        if os.path.exists(self.DB_PATH):
            try:
                with open(self.DB_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._directorios = [d for d in (data if isinstance(data, list) else []) if os.path.isdir(d)]
            except Exception:
                self._directorios = []

    def _guardar_directorios(self):
        try:
            with open(self.DB_PATH, "w", encoding="utf-8") as f:
                json.dump(self._directorios, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def agregar_directorio(self, ruta: str):
        ruta_norm = os.path.realpath(ruta)
        if os.path.isdir(ruta_norm) and ruta_norm not in self._directorios:
            self._directorios.append(ruta_norm)
            self._guardar_directorios()

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        # Respuesta a ruta pendiente: usuario dio carpeta de mÃºsica
        if self._pendiente_ruta:
            self._pendiente_ruta = False
            m = re.search(r'([A-Za-z]:[\\/](?:[^\s\\]+[\\/])*[^\s\\]*)', command)
            if m:
                ruta = m.group(1).strip().rstrip("\\")
                if os.path.isdir(ruta):
                    self.agregar_directorio(ruta)
                    query = getattr(self, '_ultimo_query', '')
                    if query:
                        return self.execute(f"musica {query}")
                    return self._reproducir_aleatorio()
            # No encontrÃ³ ruta, reintentar con query original
            query = getattr(self, '_ultimo_query', '')
            if query:
                return self.execute(f"musica {query}")
            return self._reproducir_aleatorio()

        # Seleccionar resultado de YouTube por nÃºmero: "reproduce 1", "abre 3"
        if self._resultados_youtube:
            m = re.search(r'\b(reproduce|reproducir|abre|abrir|pon|poner|toca|tocar)\s+(\d+)\b', cmd)
            if m:
                num = int(m.group(2))
                if 1 <= num <= len(self._resultados_youtube):
                    vid, titulo = self._resultados_youtube[num - 1]
                    import webbrowser
                    webbrowser.open(f"https://www.youtube.com/watch?v={vid}")
                    return f"  Abriendo '{titulo}' en YouTube..."
                return f"  NÃºmero invÃ¡lido. Hay {len(self._resultados_youtube)} resultados."

        # Palabras clave principales de musica
        keywords_musica = ["musica", "mÃºsica", "music", "canciÃ³n", "cancion",
                           "song", "reproduce", "play", "pon"]
        # Palabras clave de control
        keywords_control = ["siguiente", "next", "skip", "saltar",
                           "anterior", "prev", "back", "atras",
                           "pausa", "pause", "parar", "stop", "detener",
                           "reanudar", "resume", "continuar", "seguir",
                           "volumen", "volume", "subir", "bajar",
                           "lista", "playlist", "cola", "queue",
                           "aleatorio", "shuffle", "random", "azar",
                           "cerrar", "quitar", "terminar", "apagar",
                           "finalizar", "silencio", "basta", "callar"]

        if any(p in cmd for p in keywords_musica):
            return self._reproducir(command)
        elif any(p in cmd for p in keywords_control):
            if any(p in cmd for p in ["siguiente", "next", "skip", "saltar"]):
                return self._siguiente()
            elif any(p in cmd for p in ["anterior", "prev", "back", "atras"]):
                return self._anterior()
            elif any(p in cmd for p in ["pausa", "pause", "parar", "stop", "detener",
                                        "cerrar", "quitar", "terminar", "apagar",
                                        "finalizar", "silencio", "basta", "callar"]):
                return self._pausar()
            elif any(p in cmd for p in ["reanudar", "resume", "continuar", "seguir"]):
                return self._reanudar()
            elif any(p in cmd for p in ["volumen", "volume", "subir", "bajar"]):
                return self._ajustar_volumen(command)
            elif any(p in cmd for p in ["lista", "playlist", "cola", "queue"]):
                return self._mostrar_playlist()
            elif any(p in cmd for p in ["aleatorio", "shuffle", "random", "azar"]):
                return self._aleatorio()
        else:
            return self.help()

    def _buscar_canciones(self, query: str, max_results: int = 20) -> list:
        # 1. Intentar con es.exe
        if os.path.exists(self.ES_PATH):
            query_normalizada = query.strip().replace(" ", "*")
            query_es = f"*.mp3|*.wav|*.flac|*.aac|*.ogg|*.m4a|*.wma"
            args = [self.ES_PATH, "-n", str(max_results * 2), query_normalizada, query_es]
            try:
                result = subprocess.run(args, capture_output=True, text=True, timeout=10)
                lineas = [l.strip() for l in result.stdout.split("\n") if l.strip()]
            except Exception:
                lineas = []
            if not lineas and " " in query:
                try:
                    result = subprocess.run(
                        [self.ES_PATH, "-n", str(max_results * 2), query, query_es],
                        capture_output=True, text=True, timeout=10
                    )
                    lineas = [l.strip() for l in result.stdout.split("\n") if l.strip()]
                except Exception:
                    pass
            if lineas:
                excluir = {"presets", "samples", "sample", "librerÃ­as", "librerias",
                            "libreria", "librerÃ­a", "producciÃ³n", "produccion",
                            "proyectos", "projects", "backup", "backups",
                            "vstplugins", "vst3", "vst", "aax", "audio units",
                            "kontakt", "sound library", "sound libraries",
                            "recycle bin", "system32", "windows", "program files",
                            "program files (x86)", "c:\\$recycle.bin"}
                filtrados = []
                for r in lineas:
                    r_lower = r.lower()
                    partes = r_lower.split(os.sep)
                    if any(parte in excluir for parte in partes):
                        continue
                    filtrados.append(r)
                if filtrados:
                    return filtrados[:max_results]

        # 2. Fallback: buscar en directorios conocidos
        if self._directorios:
            query_lower = query.lower() if query else ""
            resultados = []
            ext_validas = (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma")
            for directorio in self._directorios:
                for root, dirs, files in os.walk(directorio):
                    # Saltar directorios de sistema
                    if any(p in root.lower() for p in ("presets", "samples", "librer", "produccion", "vst")):
                        continue
                    for f in files:
                        if f.lower().endswith(ext_validas):
                            if not query_lower or query_lower in f.lower():
                                ruta_completa = os.path.join(root, f)
                                resultados.append(ruta_completa)
                                if len(resultados) >= max_results:
                                    return resultados
            if resultados:
                return resultados

        return []

    def _reproducir(self, command: str) -> str:
        # Extraer consulta: buscar la keyword de mÃºsica MÃS relevante
        parts = command.lower().split()
        # Keywords ordenadas por prioridad (mÃ¡s especÃ­ficas primero)
        keywords = ["reproduce", "play", "pon", "busca", "buscar",
                     "musica", "mÃºsica", "music", "canciÃ³n", "cancion", "song"]
        # Encontrar la Ãºltima keyword de mÃºsica en el comando
        idx = None
        # Preferir "musica"/"mÃºsica" sobre "busca" si aparecen
        best_kw = None
        for i, p in enumerate(parts):
            if p in keywords:
                best_kw = p
                idx = i
        if idx is not None:
            # Tomar palabras despuÃ©s de la keyword (saltando artÃ­culos/preposiciones)
            query_parts = []
            for j in range(idx + 1, len(parts)):
                if parts[j] not in ("un", "una", "la", "el", "de", "del", "que",
                                    "y", "e", "o", "a", "en", "por", "para", "con",
                                    "las", "los", "sus", "mi", "tu", "al", "algo"):
                    query_parts.append(parts[j])
            query = " ".join(query_parts).strip()
        else:
            # Sin keyword de mÃºsica reconocida
            ignorar = keywords + ["un", "una", "la", "el", "de", "del", "que",
                                   "y", "e", "o", "a", "en", "por", "para", "con",
                                   "las", "los", "sus", "mi", "tu", "al", "algo", "por favor"]
            query = " ".join(p for p in parts if p not in ignorar).strip()

        if not query:
            # Si no hay consulta, reproducir aleatorio
            return self._reproducir_aleatorio()

        # 1. Intentar busqueda local
        canciones = self._buscar_canciones(query)
        if canciones:
            if len(canciones) >= 1:
                self._playlist = canciones
                self._indice_actual = 0
            return self._reproducir_archivo(canciones[0])

        # 2. Si hay directorios conocidos pero no encontramos nada, dar mensaje
        if self._directorios:
            return f"  No encontrÃ© '{query}' en tus carpetas de mÃºsica."

        # 3. Preguntar por carpeta (una sola vez)
        if not self._pendiente_ruta:
            self._pendiente_ruta = True
            self._ultimo_query = query
            return ("  No encontrÃ© mÃºsica. Â¿DÃ³nde tienes tus canciones? "
                    "Dime la carpeta (ej: D:\\MÃºsica)")

        # 4. Fallback: buscar en YouTube y listar resultados
        return self._buscar_youtube(query)

    def _buscar_youtube(self, query: str) -> str:
        """Busca en YouTube y devuelve una lista numerada."""
        import urllib.parse
        import re as _re
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        instancias = [
            f"https://inv.nadeko.net/search?q={urllib.parse.quote(query + ' musica')}",
            f"https://vid.puffyan.us/search?q={urllib.parse.quote(query + ' musica')}",
            f"https://yewtu.be/search?q={urllib.parse.quote(query + ' musica')}",
        ]
        r = None
        for url in instancias:
            try:
                import requests
                r = requests.get(url, headers=headers, timeout=8)
                if r.status_code == 200:
                    break
            except Exception:
                continue

        if r is not None and r.status_code == 200:
            try:
                resultados = []
                # Buscar patrones de video en el HTML
                for m in _re.finditer(r'href="(/watch\?v=[a-zA-Z0-9_-]+)"[^>]*>\s*<[^>]*>\s*<[^>]*>([^<]+)', r.text):
                    vid_url = m.group(1)
                    vid = vid_url.split("v=")[1].split("&")[0]
                    titulo = _re.sub(r'<[^>]+>', '', m.group(2)).strip()
                    if titulo and vid and titulo not in [x[1] for x in resultados]:
                        resultados.append((vid, titulo))
                        if len(resultados) >= 8:
                            break
                # Si el patron anterior no funciono, intentar busqueda mas simple
                if not resultados:
                    for m in _re.finditer(r'/watch\?v=([a-zA-Z0-9_-]{11})', r.text):
                        vid = m.group(1)
                        if vid not in [x[0] for x in resultados]:
                            resultados.append((vid, f"Video {len(resultados)+1}"))
                            if len(resultados) >= 8:
                                break
                if resultados:
                    resumen = f"  Resultados en YouTube para '{query}':\n"
                    for i, (vid, titulo) in enumerate(resultados, 1):
                        titulo_mostrar = titulo[:60] + "..." if len(titulo) > 60 else titulo
                        resumen += f"    {i}. {titulo_mostrar}\n"
                    resumen += "\n  Di 'reproduce <nÃºmero>' para abrir uno."
                    self._resultados_youtube = resultados
                    return resumen
            except Exception:
                pass

        # Fallback definitivo: abrir busqueda en YouTube en el navegador
        import webbrowser
        url_search = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query + ' musica')}"
        webbrowser.open(url_search)
        return f"  Abriendo bÃºsqueda de '{query}' en YouTube..."

    def _reproducir_archivo(self, ruta: str) -> str:
        # Verificar si existe; si no, intentar con glob (maneja ? en la ruta)
        if not os.path.exists(ruta):
            import glob as _glob
            coincidencias = _glob.glob(ruta)
            if not coincidencias:
                # Reemplazar ? por wildcard de un caracter y reintentar
                ruta_glob = ruta.replace("?", "?")
                if "?" in ruta:
                    coincidencias = _glob.glob(ruta_glob)
            if coincidencias:
                ruta = coincidencias[0]
            elif self._playlist and self._indice_actual < len(self._playlist) - 1:
                self._indice_actual += 1
                return self._reproducir_archivo(self._playlist[self._indice_actual])
            else:
                return f"  ⚠️ El archivo ya no existe: {ruta}"

        self._detener_actual()
        self._colar_actual = ruta
        nombre = os.path.splitext(os.path.basename(ruta))[0]

        # Windows: usar Windows Media Player o el reproductor asociado
        threading.Thread(target=self._lanzar_reproduccion, args=(ruta,), daemon=True).start()
        self._reproduciendo = True
        self._pausado = False

        return f"  â–¶ Reproduciendo: {nombre}"

    def _lanzar_reproduccion(self, ruta: str):
        """Lanza la reproducciÃ³n usando el reproductor por defecto de Windows."""
        try:
            os.startfile(ruta)
        except Exception as e:
            # Fallback: usar Windows Media Player
            try:
                subprocess.Popen(
                    ["C:\\Program Files\\Windows Media Player\\wmplayer.exe", ruta],
                    shell=True
                )
            except:
                pass

    def _detener_actual(self):
        if self._reproduciendo:
            try:
                subprocess.run(["taskkill", "/f", "/im", "wmplayer.exe"],
                              capture_output=True, timeout=3)
            except:
                pass
        self._reproduciendo = False
        self._pausado = False

    def _reproducir_aleatorio(self) -> str:
        # Buscar mÃºsica popular/aleatoria
        canciones = self._buscar_canciones("", max_results=50)
        if not canciones:
            return "  No encontrÃ© mÃºsica en tu computadora."

        self._playlist = canciones
        random.shuffle(self._playlist)
        self._indice_actual = 0
        return self._reproducir_archivo(self._playlist[0])

    def _siguiente(self) -> str:
        if not self._playlist or self._indice_actual >= len(self._playlist) - 1:
            return "  No hay mÃ¡s canciones en la cola."
        self._indice_actual += 1
        return self._reproducir_archivo(self._playlist[self._indice_actual])

    def _anterior(self) -> str:
        if not self._playlist or self._indice_actual <= 0:
            return "  No hay canciÃ³n anterior."
        self._indice_actual -= 1
        return self._reproducir_archivo(self._playlist[self._indice_actual])

    def _pausar(self) -> str:
        if self._pausado:
            return "  Ya estÃ¡ pausado."
        self._pausado = True
        # Enviar pausa al reproductor (funciona con WMP)
        try:
            subprocess.run(["taskkill", "/f", "/im", "wmplayer.exe"],
                          capture_output=True, timeout=3)
        except:
            pass
        return "  Reproduccion pausada."

    def _reanudar(self) -> str:
        if not self._pausado:
            if self._colar_actual:
                return self._reproducir_archivo(self._colar_actual)
            return "  No hay nada que reanudar."
        self._pausado = False
        return self._reproducir_archivo(self._colar_actual)

    def _ajustar_volumen(self, command: str) -> str:
        return ("  Control de volumen: usa los controles de tu teclado "
                "o el mezclador de volumen de Windows (Fn+F7/F8).")

    def _mostrar_playlist(self) -> str:
        if not self._playlist:
            return "  La lista de reproducciÃ³n estÃ¡ vacÃ­a."
        salida = f"  {ARCHIVO}  LISTA DE REPRODUCCIÃ“N ({len(self._playlist)} canciones)\n"
        salida += "  ----------------------------------------\n"
        inicio = max(0, self._indice_actual - 2)
        fin = min(len(self._playlist), inicio + 8)
        for i in range(inicio, fin):
            nombre = os.path.splitext(os.path.basename(self._playlist[i]))[0]
            marca = " â–¶" if i == self._indice_actual else ""
            salida += f"  {i+1}. {nombre}{marca}\n"
        if len(self._playlist) > fin:
            salida += f"  ... y {len(self._playlist) - fin} mÃ¡s\n"
        return salida

    def _aleatorio(self) -> str:
        if self._playlist:
            random.shuffle(self._playlist)
            self._indice_actual = 0
            return "  Modo aleatorio activado. Reproduciendo nueva cancion:\n" + self._reproducir_archivo(self._playlist[0])
        return "  No hay playlist para mezclar."

    def help(self) -> str:
        return (
            "MÃšSICA:\n"
            "  musica <artista/canciÃ³n>    - Busca y reproduce mÃºsica\n"
            "  siguiente / anterior        - Cambia de canciÃ³n\n"
            "  pausa / reanudar            - Control de reproducciÃ³n\n"
            "  lista                       - Muestra la cola actual\n"
            "  aleatorio                   - ReproducciÃ³n aleatoria\n"
            "  volumen                     - Control de volumen\n\n"
            "Ej: musica queen\n"
            "    musica rock en espaÃ±ol\n"
            "    siguiente\n"
            "    reproduce 2  (para elegir de la lista)"
        )

