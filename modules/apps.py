"""
MÃ³dulo de apps - lanzar aplicaciones, abrir documentos y controlar procesos.
"""

import os
import subprocess
import psutil
from .base import ModuleBase
from utils.emoji import COMPUTADORA


class AppsModule(ModuleBase):
    """Control de aplicaciones y documentos."""

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["abrir", "open", "lanzar", "launch", "iniciar", "start"]):
            return self._abrir(command)
        elif any(p in cmd for p in ["cerrar", "close", "kill", "matar", "terminar", "quitar"]):
            return self._cerrar(command)
        elif any(p in cmd for p in ["programas", "apps", "aplicaciones", "ejecutando", "running", "tasklist"]):
            return self._listar_procesos()
        elif any(p in cmd for p in ["bloc de notas", "notepad", "calculadora", "calc", "paint",
                                     "explorador", "explorer", "cmd", "terminal", "powershell"]):
            # Atajos directos
            return self._abrir_directo(command)
        else:
            return self.help()

    def _abrir(self, command: str) -> str:
        query = self._extraer_query(command, ["abrir", "open", "lanzar", "launch", "iniciar", "start",
                                                "el", "la", "un", "una", "por favor"])
        if not query:
            return "  ⚠️ Â¿QuÃ© aplicaciÃ³n quieres abrir?"

        # Apps conocidas
        apps = {
            "chrome": "chrome",
            "google chrome": "chrome",
            "navegador": "chrome",
            "firefox": "firefox",
            "edge": "msedge",
            "explorador": "explorer",
            "explorador de archivos": "explorer",
            "archivos": "explorer",
            "carpetas": "explorer",
            "bloc de notas": "notepad",
            "notepad": "notepad",
            "calculadora": "calc",
            "paint": "mspaint",
            "cmd": "cmd",
            "simbolo del sistema": "cmd",
            "terminal": "cmd",
            "powershell": "powershell",
            "power shell": "powershell",
            "panel de control": "control",
            "configuracion": "ms-settings:",
            "configuraciÃ³n": "ms-settings:",
            "ajustes": "ms-settings:",
            "word": "WINWORD",
            "excel": "EXCEL",
            "powerpoint": "POWERPNT",
            "outlook": "OUTLOOK",
            "visual studio": "devenv",
            "vs code": "code",
            "vscode": "code",
            "visual studio code": "code",
            "spotify": "spotify",
            "discord": "discord",
            "slack": "slack",
            "telegram": "telegram",
            "whatsapp": "whatsapp",
            "zoom": "zoom",
            "skype": "skype",
            "notas": "onenote",
            "one note": "onenote",
        }

        for nombre, comando in apps.items():
            if nombre in query.lower():
                return self._lanzar_comando(comando, nombre)

        # Intentar buscar con Everything
        try:
            es_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "es.exe")
            if os.path.exists(es_path):
                result = subprocess.run(
                    [es_path, "-n", "5", "-s", f'{query} ext:exe;lnk'],
                    capture_output=True, text=True, timeout=5
                )
                resultados = [l.strip() for l in result.stdout.split("\n") if l.strip()]
                if resultados:
                    return self._lanzar_exe(resultados[0], query)
        except:
            pass

        # Fallback: buscar en Start Menu y en PATH
        res = self._buscar_en_start_menu(query)
        if res:
            return res
        res = self._buscar_en_path(query)
        if res:
            return res

        return f"  No sÃ© cÃ³mo abrir '{query}'. Prueba con una app conocida (chrome, word, etc)."

    def _abrir_directo(self, command: str) -> str:
        mapping = {
            "bloc de notas": ("notepad", "Bloc de notas"),
            "notepad": ("notepad", "Bloc de notas"),
            "calculadora": ("calc", "Calculadora"),
            "calc": ("calc", "Calculadora"),
            "paint": ("mspaint", "Paint"),
            "explorador": ("explorer", "Explorador"),
            "cmd": ("cmd", "SÃ­mbolo del sistema"),
            "terminal": ("cmd", "Terminal"),
            "powershell": ("powershell", "PowerShell"),
        }
        for key, (com, nom) in mapping.items():
            if key in command.lower():
                return self._lanzar_comando(com, nom)
        return self.help()

    def _lanzar_comando(self, comando: str, nombre: str) -> str:
        try:
            subprocess.Popen(f"start {comando}", shell=True)
            return f"  Abriendo {nombre}..."
        except FileNotFoundError:
            return f"  ⚠️ No encontrÃ© '{nombre}' en el sistema."
        except Exception as e:
            return f"  ⚠️ Error abriendo {nombre}: {e}"

    def _lanzar_exe(self, ruta: str, nombre: str) -> str:
        try:
            if ruta.endswith(".lnk"):
                subprocess.Popen(["start", "", ruta], shell=True)
            else:
                subprocess.Popen([ruta], shell=True)
            return f"  Abriendo {os.path.basename(ruta)}..."
        except Exception as e:
            return f"  ⚠️ Error: {e}"

    def _buscar_en_start_menu(self, app: str) -> str:
        """Busca una aplicaciÃ³n en el menÃº de inicio."""
        start_menu = os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs")
        common_start = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
        for base in [start_menu, common_start]:
            for root, dirs, files in os.walk(base):
                for f in files:
                    if f.endswith(".lnk") and app.lower() in f.lower():
                        try:
                            subprocess.Popen(["start", "", os.path.join(root, f)], shell=True)
                            return f"  Abriendo {f.replace('.lnk', '')}."
                        except Exception:
                            continue
                for d in dirs:
                    if app.lower() in d.lower():
                        for f2 in os.listdir(os.path.join(root, d)):
                            if f2.endswith(".lnk"):
                                try:
                                    subprocess.Popen(["start", "", os.path.join(root, d, f2)], shell=True)
                                    return f"  Abriendo {f2.replace('.lnk', '')}."
                                except Exception:
                                    continue
        return ""

    def _buscar_en_path(self, app: str) -> str:
        """Busca una aplicaciÃ³n en el PATH del sistema."""
        try:
            result = subprocess.run(["where", app], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                ruta = result.stdout.strip().split("\n")[0]
                os.startfile(ruta)
                return f"  Abriendo {app}."
        except Exception:
            pass
        return ""

    def _cerrar(self, command: str) -> str:
        query = self._extraer_query(command, ["cerrar", "close", "kill", "matar", "terminar",
                                               "quitar", "la", "el", "por favor"])
        if not query:
            return "  ⚠️ Â¿QuÃ© aplicaciÃ³n quieres cerrar?"

        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if query.lower() in proc.info['name'].lower():
                    proc.kill()
                    return f"  Cerrado: {proc.info['name']}"
            return f"  No encontrÃ© el proceso '{query}' ejecutÃ¡ndose."
        except Exception as e:
            return f"  ⚠️ Error: {e}"

    def _listar_procesos(self) -> str:
        try:
            procesos = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
                try:
                    if proc.info['memory_percent'] and proc.info['memory_percent'] > 0.1:
                        procesos.append((proc.info['name'], proc.info['pid'],
                                        proc.info['memory_percent']))
                except:
                    pass

            procesos.sort(key=lambda x: x[2], reverse=True)
            salida = f"  {COMPUTADORA}  APLICACIONES ABIERTAS\n"
            salida += "  ----------------------------------------\n"
            for i, (name, pid, mem) in enumerate(procesos[:15], 1):
                salida += f"  {i}. {name} (PID: {pid}) - {mem:.1f}%\n"
            return salida
        except Exception as e:
            return f"  ⚠️ Error listando procesos: {e}"

    def _extraer_query(self, command: str, ignorar: list) -> str:
        words = command.lower().split()
        for p in ignorar:
            words = [w for w in words if w != p]
        return " ".join(words).strip().strip('"').strip("'")

    def help(self) -> str:
        return (
            "APLICACIONES:\n"
            "  abrir <app>              - Abre una aplicaciÃ³n\n"
            "  cerrar <app>             - Cierra una aplicaciÃ³n\n"
            "  programas                - Lista aplicaciones abiertas\n\n"
            "Apps conocidas: chrome, firefox, word, excel, vscode,\n"
            "spotify, discord, telegram, calculadora, bloc de notas,\n"
            "cmd, powershell, explorador, paint, outlook, zoom\n\n"
            "Ej: abrir chrome\n"
            "    abrir spotify\n"
            "    cerrar chrome\n"
            "    programas"
        )

