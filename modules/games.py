"""
MÃ³dulo de juegos - detecta, aprende y lanza videojuegos.
"""

import os
import re
import json
import subprocess
import difflib
from .base import ModuleBase


class GamesModule(ModuleBase):
    """DetecciÃ³n y lanzamiento de videojuegos."""

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self.db_path = os.path.expanduser("~/.jarvis/games_db.json")
        self._games_db = {}
        self._pendiente_ruta = None
        self._cargar_db()
        # Escanear carpetas comunes al inicio si la DB estÃ¡ vacÃ­a
        if not self._games_db:
            self._escanear_inicio()

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ PÃšBLICO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def execute(self, command: str, **kwargs) -> str:
        # Responder a ruta pendiente (usuario dio una carpeta)
        if self._pendiente_ruta:
            return self._procesar_ruta_pendiente(command)

        cmd = command.lower()

        # Escaneo proactivo: "escanear D:\Games"
        if cmd.startswith("escanear "):
            carpeta = cmd[9:].strip()
            return self._escanear_carpeta(carpeta)

        # Extraer nombre del juego
        game = self._extraer_juego(cmd)
        if not game:
            return "  Â¿QuÃ© juego quieres abrir?"

        # Buscar en DB
        ruta = self._buscar_en_db(game)
        if ruta:
            return self._lanzar_juego(ruta, game)

        # No encontrado: escanear systema para encontrarlo
        encontrado = self._escanear_para_juego(game)
        if encontrado:
            return self._lanzar_juego(encontrado, game)

        # Pedir ruta al usuario
        self._pendiente_ruta = (game, None)
        return f"  No encontrÃ© '{game}'. Dime la carpeta donde estÃ¡ instalado (ej: C:\\Archivos de programa\\Dota 2)."

    def help(self) -> str:
        return (
            "JUEGOS:\n"
            "  abre <juego>              - Abre un videojuego\n"
            "  juega <juego>             - Abre un videojuego\n"
            "  lanzar <juego>            - Abre un videojuego\n\n"
            "Ej: abre el dota\n"
            "    juega al minecraft\n"
            "    abre el juego fortnite\n"
            "    lanzar cs go\n\n"
            "Si no conozco un juego, dime la carpeta donde estÃ¡ y lo aprendo."
        )

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ BASE DE DATOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _cargar_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            if os.path.exists(self.db_path):
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self._games_db = json.load(f)
            self._limpiar_entradas_malas()
        except Exception:
            self._games_db = {}

    def _limpiar_entradas_malas(self):
        """Elimina entradas de DB que apuntan a ejecutables no-juego."""
        skip_words = ["unins", "setup", "redist", "vconsole", "console", "crash",
                      "dedicated", "patchr", "launcher", "beacon", "steam",
                      "dotnet", "vc_redist", "dxsetup", "directx", "vcredist",
                      "devtools", "debug", "sdk", "samples", "vstools"]
        cambios = False
        for k, v in list(self._games_db.items()):
            name = os.path.basename(v).lower()
            if any(s in name for s in skip_words):
                del self._games_db[k]
                cambios = True
        if cambios:
            self._guardar_db()

    def _guardar_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self._games_db, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _aprender_juego(self, nombre: str, ruta_exe: str):
        self._games_db[nombre.lower().strip()] = ruta_exe
        # TambiÃ©n almacenar variantes del nombre para mejor matching
        for alias in [nombre.lower().strip().replace(" ", ""),
                       nombre.lower().strip().replace("-", " "),
                       nombre.lower().strip().replace("_", " ")]:
            if alias != nombre.lower().strip():
                self._games_db[alias] = ruta_exe
        self._guardar_db()

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ EXTRACCIÃ“N â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _extraer_juego(self, cmd: str) -> str:
        # Patrones: "abre el dota", "juega al dota", "lanzar cs go"
        m = re.search(r'\b(abrir|abre|lanzar|iniciar|jugar|juega|juegue|pon|poner)\s+(el\s+|la\s+|al\s+|un\s+|una\s+)?(juego\s+|partida\s+|partidita\s+)?(.+)', cmd)
        if m:
            nombre = m.group(m.lastindex).strip()
            # Quitar palabras sobrantes
            nombre = re.sub(r'\b(juego|juegos|partida|partidita|vamos|dale|yah|ya)\b', '', nombre).strip()
            return nombre if len(nombre) > 1 else ""
        return ""

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ BÃšSQUEDA EN DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _buscar_en_db(self, game: str) -> str:
        game_lower = game.lower().strip()
        # Coincidencia exacta
        if game_lower in self._games_db:
            return self._games_db[game_lower]
        # Coincidencia parcial: el nombre del juego contiene el query o viceversa
        for nombre, ruta in self._games_db.items():
            if game_lower in nombre or nombre in game_lower:
                return ruta
        # Fuzzy match
        nombres = list(self._games_db.keys())
        matches = difflib.get_close_matches(game_lower, nombres, n=1, cutoff=0.55)
        if matches:
            return self._games_db[matches[0]]
        return None

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ ESCANEO AUTOMÃTICO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _escanear_para_juego(self, game: str) -> str:
        """Busca un juego por nombre escaneando carpetas comunes."""
        carpetas = self._carpetas_comunes()
        mejor_match = None
        mejor_score = 0
        game_lower = game.lower()
        for carpeta in carpetas:
            if not os.path.isdir(carpeta):
                continue
            for root, dirs, files in os.walk(carpeta):
                depth = root.replace(carpeta, "").count(os.sep)
                if depth > 4:
                    continue
                for entry in dirs:
                    entry_lower = entry.lower()
                    ratio = difflib.SequenceMatcher(None, game_lower, entry_lower).ratio()
                    if game_lower in entry_lower or entry_lower in game_lower or ratio > 0.5:
                        entrada_path = os.path.join(root, entry)
                        exe = self._buscar_exe_principal(entrada_path)
                        if exe:
                            score = ratio
                            if game_lower in entry_lower:
                                score += 0.3
                            if score > mejor_score:
                                mejor_score = score
                                mejor_match = exe
        if mejor_match:
            self._aprender_juego(game, mejor_match)
            return mejor_match

        # Buscar en el menÃº de inicio
        for base in [os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
                      r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"]:
            if not os.path.isdir(base):
                continue
            for root, dirs, files in os.walk(base):
                for f in files:
                    if f.lower().endswith(".lnk") and game.lower() in f.lower().replace(".lnk", ""):
                        ruta_lnk = os.path.join(root, f)
                        exe = self._resolver_acceso_directo(ruta_lnk)
                        if exe and os.path.isfile(exe):
                            self._aprender_juego(game, exe)
                            return exe
        return None

    def _escanear_inicio(self):
        """Escanea carpetas comunes al inicio para precargar juegos."""
        carpetas = self._carpetas_comunes()
        encontrados = 0
        for carpeta in carpetas:
            if not os.path.isdir(carpeta):
                continue
            try:
                for root, dirs, files in os.walk(carpeta):
                    depth = root.replace(carpeta, "").count(os.sep)
                    if depth > 4:
                        continue
                    for entry in dirs:
                        entry_path = os.path.join(root, entry)
                        if any(skip in entry.lower() for skip in ["windows", "system", "backup",
                                                                    "microsoft", "temp", "tmp",
                                                                    "cache", "logs", "help"]):
                            continue
                        exe = self._buscar_exe_principal(entry_path)
                        if exe:
                            self._aprender_juego(entry.strip(), exe)
                            encontrados += 1
            except:
                continue
        if encontrados:
            self._guardar_db()

    def _escanear_carpeta(self, carpeta: str) -> str:
        """Escanea una carpeta en busca de juegos y los aprende."""
        if not os.path.isdir(carpeta):
            return f"  La carpeta '{carpeta}' no existe."
        encontrados = 0
        for entry in os.listdir(carpeta):
            entry_path = os.path.join(carpeta, entry)
            if not os.path.isdir(entry_path):
                continue
            exe = self._buscar_exe_principal(entry_path)
            if exe:
                nombre = entry.strip()
                self._aprender_juego(nombre, exe)
                encontrados += 1
        if encontrados:
            self._guardar_db()
            return f"  EncontrÃ© {encontrados} juego(s) en '{carpeta}' y los guardÃ©. Ya puedes pedirme que los abra."
        return f"  No encontrÃ© juegos en '{carpeta}'. Â¿Tienen subcarpetas con los juegos?"

    def _carpetas_comunes(self) -> list:
        """Devuelve carpetas donde suelen instalarse juegos."""
        carpetas = [
            "C:\\Program Files",
            "C:\\Program Files (x86)",
            os.path.expanduser("~\\Desktop"),
            os.path.expanduser("~\\Downloads"),
            os.path.expanduser("~\\Saved Games"),
        ]
        # Unidades de disco adicionales
        for letra in "DEFGHIJKLMNOPQRSTUVWXYZ":
            unidad = f"{letra}:\\"
            if os.path.exists(unidad):
                carpetas.append(unidad)
        # Steam
        steam_paths = [
            "C:\\Program Files (x86)\\Steam",
            os.path.expanduser("~\\AppData\\Local\\Steam"),
        ]
        for sp in steam_paths:
            if os.path.isdir(sp):
                carpetas.append(sp)
                # AÃ±adir steamapps\common para la ruta por defecto
                common = os.path.join(sp, "steamapps", "common")
                if os.path.isdir(common):
                    carpetas.append(common)
                # Leer libraryfolders.vdf para mÃ¡s carpetas
                vdf = os.path.join(sp, "steamapps", "libraryfolders.vdf")
                if os.path.isfile(vdf):
                    try:
                        with open(vdf, "r", encoding="utf-8") as f:
                            for linea in f:
                                m = re.search(r'"\s*"\s*"\s*(.:[^"]+)"', linea)
                                if m:
                                    lib = m.group(1).replace("\\\\", "\\")
                                    carpetas.append(os.path.join(lib, "steamapps", "common"))
                    except:
                        pass
        # Epic Games
        epic = os.path.expanduser("~\\AppData\\Local\\EpicGames")
        if os.path.isdir(epic):
            carpetas.append(epic)
        carpetas = [c for c in carpetas if os.path.isdir(c)]
        return carpetas

    def _buscar_exe_principal(self, folder: str) -> str:
        """Encuentra el .exe principal de un juego.
        Prioriza por nombre (coincidencia con carpeta), luego por tamaÃ±o.
        """
        folder_name = os.path.basename(folder).lower()
        skip_words = ["unins", "setup", "redist", "vconsole", "console", "crash",
                      "dedicated", "patchr", "launcher", "beacon", "steam",
                      "dotnet", "vc_redist", "dxsetup", "directx", "vcredist",
                      "devtools", "debug", "sdk", "samples", "vstools"]
        try:
            candidatos = []
            for root, dirs, files in os.walk(folder):
                depth = root.replace(folder, "").count(os.sep)
                if depth > 6:
                    continue
                for f in files:
                    name = f.lower()
                    if not name.endswith(".exe"):
                        continue
                    if any(s in name for s in skip_words):
                        continue
                    ruta = os.path.join(root, f)
                    try:
                        tam = os.path.getsize(ruta)
                    except:
                        continue
                    name_no_ext = name.replace(".exe", "")
                    match_peso = 0
                    if folder_name in name_no_ext or name_no_ext in folder_name:
                        match_peso = 2
                    elif any(p in name_no_ext for p in folder_name.split()):
                        match_peso = 1
                    candidatos.append((match_peso, tam, ruta))
            if not candidatos:
                return None
            candidatos.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return candidatos[0][2]
        except:
            return None

    def _resolver_acceso_directo(self, lnk_path: str) -> str:
        """Resuelve un acceso directo .lnk a su destino real."""
        try:
            import ctypes
            from ctypes import wintypes
            shell32 = ctypes.windll.shell32
            pidl = ctypes.c_void_p()
            if shell32.SHParseDisplayName(lnk_path, 0, ctypes.byref(pidl), 0, 0) == 0:
                buf = ctypes.create_unicode_buffer(260)
                shell32.SHGetPathFromIDListW(pidl, buf)
                return buf.value
        except:
            pass
        return lnk_path

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ LANZAMIENTO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _lanzar_juego(self, ruta: str, nombre: str) -> str:
        if not os.path.exists(ruta):
            for k, v in list(self._games_db.items()):
                if v == ruta:
                    del self._games_db[k]
            self._guardar_db()
            return f"  ⚠️ El juego '{nombre}' ya no estÃ¡ en {ruta}. Dime la nueva ruta."
        # Validar que el exe no sea basura conocida
        name_lower = os.path.basename(ruta).lower()
        skip_words = ["unins", "setup", "redist", "vconsole", "console", "crash",
                      "dedicated", "patchr", "launcher", "beacon", "steam",
                      "dotnet", "vc_redist", "dxsetup", "directx", "vcredist",
                      "devtools", "debug", "sdk", "samples", "vstools"]
        if any(s in name_lower for s in skip_words):
            for k, v in list(self._games_db.items()):
                if v == ruta:
                    del self._games_db[k]
            self._guardar_db()
            mejor = self._escanear_para_juego(nombre)
            if mejor:
                ruta = mejor
            else:
                return f"  ⚠️ '{os.path.basename(ruta)}' no es un juego vÃ¡lido. Buscando uno mejor..."
        try:
            nombre_mostrar = os.path.splitext(os.path.basename(ruta))[0]
            game_dir = os.path.dirname(ruta)
            subprocess.Popen([ruta], shell=True, cwd=game_dir)
            return f"  â–¶ Abriendo {nombre_mostrar}..."
        except Exception as e:
            return f"  ⚠️ Error al abrir {nombre}: {e}"

    def _procesar_ruta_pendiente(self, command: str) -> str:
        """Procesa la respuesta del usuario cuando preguntamos por la ruta de un juego."""
        juego, callback = self._pendiente_ruta
        ruta = command.strip().strip('"').strip("'")
        # Extraer ruta de unidad (X:\...) del texto natural
        m = re.search(r'([A-Za-z]:[\\/][^\s,;]+)', ruta)
        if m:
            ruta = m.group(1)
        if os.path.isdir(ruta):
            exe = self._buscar_exe_principal(ruta)
            if exe:
                self._aprender_juego(juego, exe)
                self._pendiente_ruta = None
                return f"  Aprendido: '{juego}' â†’ {exe}\n{self._lanzar_juego(exe, juego)}"
            # Si no encontrÃ³ exe, buscar en subdirectorios con nombres parecidos al juego
            for entry in os.listdir(ruta):
                sub = os.path.join(ruta, entry)
                if os.path.isdir(sub):
                    exe = self._buscar_exe_principal(sub)
                    if exe:
                        self._aprender_juego(juego, exe)
                        self._pendiente_ruta = None
                        return f"  Aprendido: '{juego}' â†’ {exe}\n{self._lanzar_juego(exe, juego)}"
            self._pendiente_ruta = None
            return f"  No encontrÃ© un .exe de juego en '{ruta}' ni en sus subcarpetas. Â¿Es esta la carpeta correcta?"
        # No es una carpeta vÃ¡lida, cancelar
        self._pendiente_ruta = None
        return "  OK, cancela la operaciÃ³n."

    def set_pendiente_ruta(self, juego: str):
        """Establece que estamos esperando una ruta de juego del usuario."""
        self._pendiente_ruta = (juego, None)

