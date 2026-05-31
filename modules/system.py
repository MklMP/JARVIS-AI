import platform
import psutil
import os
import subprocess
import re
import time
from datetime import datetime
from .base import ModuleBase
from utils.emoji import RELON, CALENDARIO, COMPUTADORA, BATERIA, MEMORIA, DISCO


class TimeModule(ModuleBase):
    """MÃ³dulo de hora, fecha y sistema."""

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["hora", "tiempo", "time", "hour", "quÃ© hora"]):
            return self._hora_actual()
        elif any(p in cmd for p in ["fecha", "date", "dÃ­a", "dia", "quÃ© dÃ­a"]):
            return self._fecha_actual()
        elif any(p in cmd for p in ["alarma", "alarm", "temporizador", "timer"]):
            return self._alarma_timer(cmd)
        else:
            return self.help()

    def _hora_actual(self) -> str:
        ahora = datetime.now()
        return f"  {RELON}  Son las {ahora.strftime('%H:%M:%S')} con {ahora.second} segundos."

    def _fecha_actual(self) -> str:
        from utils.display import formatear_fecha
        ahora = datetime.now()
        fecha = formatear_fecha(ahora)
        hora = ahora.strftime("%H:%M:%S")
        return f"  {CALENDARIO}  Hoy es {fecha}\n  {RELON}  Son las {hora}"

    def _alarma_timer(self, cmd: str) -> str:
        return ("  [Reloj]  Funcionalidad de alarma/temporizador en desarrollo.\n"
                "     PrÃ³ximamente: alarmas, temporizadores y recordatorios.")

    def help(self) -> str:
        return (
            "Comandos:\n"
            "  hora         - Muestra la hora actual\n"
            "  fecha        - Muestra la fecha actual\n"
            "  alarma       - Configurar alarma (prÃ³ximamente)\n"
            "  temporizador - Temporizador (prÃ³ximamente)"
        )


class SystemModule(ModuleBase):
    """MÃ³dulo de informaciÃ³n del sistema y control de dispositivos."""

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        # ---- RESTORE POINT ----
        if re.search(r'\b(punto\s*de\s*restauraci[oÃ³]n|restore\s*point|crear\s*punto|respald[oa]\s*sistema|backup\s*sistema|proteger\s*sistema|salvaguard[ia])\b', cmd):
            return self._crear_restore_point()

        # ---- WIFI: perfiles / contraseÃ±a ----
        if re.search(r'\b(perfiles?\s*wifi|wifi\s*perfiles?|redes\s*wifi|wifi\s*guardados?|lista\s*wifi)\b', cmd):
            return self._listar_profiles_wifi()
        if re.search(r'\b(contraseÃ±[ao]|clave|password|pass|key)\b.*\b(wifi|wi-fi)\b', cmd):
            return self._wifi_password(command)

        if any(p in cmd for p in ["sistema", "system", "info", "pc", "computadora", "computador"]):
            return self._info_sistema()
        elif any(p in cmd for p in ["baterÃ­a", "bateria", "battery"]):
            return self._bateria()
        elif any(p in cmd for p in ["cpu", "procesador", "processor"]):
            return self._cpu_info()
        elif any(p in cmd for p in ["memoria", "ram", "memory"]):
            return self._memoria_info()
        elif any(p in cmd for p in ["disco", "disk", "almacenamiento", "storage"]):
            return self._disco_info()

        # ---- TOGGLES ----
        if re.search(r'\b(apaga|desactivar|desactiva|apagar|detener|deten|off|parar)\b.*\b(apache|xampp)\b', cmd):
            return self._toggle_apache(False)
        if re.search(r'\b(activar|activa|enciende|prender|prende|encender|on|iniciar|inicia|arrancar)\b.*\b(apache|xampp)\b', cmd):
            return self._toggle_apache(True)
        if re.search(r'\b(apaga|desactivar|desactiva|apagar|off|parar|desconectar)\b.*\b(bluetooth|bt)\b', cmd):
            return self._toggle_bluetooth(False)
        if re.search(r'\b(activar|activa|enciende|prender|prende|encender|on|conectar)\b.*\b(bluetooth|bt)\b', cmd):
            return self._toggle_bluetooth(True)
        if re.search(r'\b(apaga|desactivar|desactiva|apagar|off|parar|desconectar)\b.*\b(wifi|wi-fi|wireless|inalambrica|red)\b', cmd):
            return self._toggle_wifi(False)
        if re.search(r'\b(activar|activa|enciende|prender|prende|encender|on|conectar)\b.*\b(wifi|wi-fi|wireless|inalambrica|red)\b', cmd):
            return self._toggle_wifi(True)
        if re.search(r'\b(apaga|desactivar|desactiva|apagar|off|quitar)\b.*\b(luz\s*nocturna|luces\s*nocturnas|night\s*light|modo\s*nocturno)\b', cmd):
            return self._toggle_night_light(False)
        if re.search(r'\b(activar|activa|enciende|prender|prende|encender|on|poner)\b.*\b(luz\s*nocturna|luces\s*nocturnas|night\s*light|modo\s*nocturno)\b', cmd):
            return self._toggle_night_light(True)

        # ---- UNINSTALL ----
        m = re.search(r'\b(desinstalar|borrar|eliminar|quitar|remover)\s+(la\s+|el\s+|a\s+)?(.+)', cmd)
        if m:
            app = m.group(3).strip()
            if app and app not in ("desinstalar", "borrar", "eliminar", "quitar", "remover"):
                return self._uninstall_app(app)

        return self.help()

    def _toggle_apache(self, activar: bool) -> str:
        accion = "Iniciando" if activar else "Deteniendo"
        try:
            # Buscar servicio de Apache (Xampp usa Apache2.4 o Apache2.2)
            result = subprocess.run(
                ["sc", "query", "Apache2.4"],
                capture_output=True, text=True, timeout=10
            )
            servicio = "Apache2.4"
            if result.returncode != 0:
                result = subprocess.run(
                    ["sc", "query", "Apache2.2"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    servicio = "Apache2.2"
                else:
                    return "  ⚠️ No encontrÃ© el servicio de Apache (Xampp). Â¿EstÃ¡ instalado?"
            cmd = ["net", "start", servicio] if activar else ["net", "stop", servicio]
            subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            time.sleep(1)
            check = subprocess.run(["sc", "query", servicio], capture_output=True, text=True, timeout=5)
            if "RUNNING" in check.stdout:
                return f"  Apache {servicio} activado correctamente."
            else:
                return f"  Apache {servicio} detenido correctamente."
        except subprocess.TimeoutExpired:
            return f"  ⚠️ Tiempo de espera agotado al {accion.lower()} Apache."
        except Exception as e:
            return f"  ⚠️ Error al {accion.lower()} Apache: {e}"

    def _toggle_bluetooth(self, activar: bool) -> str:
        try:
            accion_txt = "activar" if activar else "desactivar"
            if activar:
                ps_cmd = (
                    "$devs=Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue;"
                    "if(-not $devs){echo 'no_device';exit};"
                    "$changed=0;"
                    "foreach($dev in $devs){"
                    "if($dev.Status -ne 'OK'){"
                    "try{Enable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false -ErrorAction Stop | Out-Null;$changed++}"
                    "catch{echo 'perm_error';exit}"
                    "}};"
                    "echo 'ok'"
                )
            else:
                ps_cmd = (
                    "$devs=Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue;"
                    "if(-not $devs){echo 'no_device';exit};"
                    "$changed=0;"
                    "foreach($dev in $devs){"
                    "if($dev.Status -eq 'OK'){"
                    "try{Disable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false -ErrorAction Stop | Out-Null;$changed++}"
                    "catch{echo 'perm_error';exit}"
                    "}};"
                    "echo 'ok'"
                )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=30
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            if "no_device" in stdout:
                return "  ⚠️ No se encontrÃ³ dispositivo Bluetooth en este equipo."
            if "perm_error" in stdout or "perm_error" in stderr:
                return f"  ⚠️ No tengo permisos para {accion_txt} Bluetooth. Ejecuta Jarvis como administrador."
            if result.returncode == 0 and "ok" in stdout:
                return f"  Bluetooth {'activado' if activar else 'desactivado'}."
            return f"  ⚠️ No se pudo {accion_txt} Bluetooth. {stdout[:100]}"
        except subprocess.TimeoutExpired:
            return f"  ⚠️ Tiempo de espera agotado al {accion_txt} Bluetooth."
        except Exception as e:
            return f"  ⚠️ Error Bluetooth: {e}"

    def _toggle_wifi(self, activar: bool) -> str:
        try:
            accion_txt = "activar" if activar else "desactivar"
            if activar:
                ps_cmd = (
                    "$a=Get-NetAdapter -Name '*Wi-Fi*','*Wireless*','*WLAN*' -ErrorAction SilentlyContinue;"
                    "if(-not $a){echo 'no_adapter';exit};"
                    "$changed=0;"
                    "foreach($n in $a){"
                    "if($n.Status -eq 'Disabled'){"
                    "try{Enable-NetAdapter -Name $n.Name -Confirm:$false -ErrorAction Stop | Out-Null;if($?){$changed++}}"
                    "catch{echo 'perm_error';exit}"
                    "}};"
                    "echo 'ok'"
                )
            else:
                ps_cmd = (
                    "$a=Get-NetAdapter -Name '*Wi-Fi*','*Wireless*','*WLAN*' -ErrorAction SilentlyContinue;"
                    "if(-not $a){echo 'no_adapter';exit};"
                    "$changed=0;"
                    "foreach($n in $a){"
                    "if($n.Status -eq 'Up'){"
                    "try{Disable-NetAdapter -Name $n.Name -Confirm:$false -ErrorAction Stop | Out-Null;if($?){$changed++}}"
                    "catch{echo 'perm_error';exit}"
                    "}};"
                    "echo 'ok'"
                )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=30
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            if "no_adapter" in stdout:
                return "  ⚠️ No se encontrÃ³ adaptador WiFi en este equipo."
            if "perm_error" in stdout or "perm_error" in stderr:
                return f"  ⚠️ No tengo permisos para {accion_txt} WiFi. Ejecuta Jarvis como administrador."
            if result.returncode == 0 and "ok" in stdout:
                return f"  WiFi {'activado' if activar else 'desactivado'}."
            return f"  ⚠️ No se pudo {accion_txt} WiFi. {stdout[:100]}"
        except subprocess.TimeoutExpired:
            return f"  ⚠️ Tiempo de espera agotado al {'activar' if activar else 'desactivar'} WiFi."
        except Exception as e:
            return f"  ⚠️ Error WiFi: {e}"

    def _crear_restore_point(self) -> str:
        """Crea un punto de restauraciÃ³n de Windows."""
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            if not is_admin:
                return "  [!) Necesito permisos de administrador para crear un punto de restauraciÃ³n. Ejecuta Jarvis como administrador."
            from datetime import datetime
            fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
            ps_cmd = (
                "try{"
                "Checkpoint-Computer -Description \"Jarvis Backup $([datetime]::Now.ToString('yyyy-MM-dd HH:mm'))\" -RestorePointType MODIFY_SETTINGS -ErrorAction Stop;"
                "echo 'ok'"
                "}catch{echo $_.Exception.Message}"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=60
            )
            stdout = result.stdout.strip()
            if "ok" in stdout:
                return f"  Punto de restauraciÃ³n creado correctamente ({fecha})."
            if "denied" in stdout.lower() or "access" in stdout.lower() or "permisos" in stdout.lower():
                return "  ⚠️ No tengo permisos para crear un punto de restauraciÃ³n. Ejecuta Jarvis como administrador."
            if "system restore" in stdout.lower() or "enable" in stdout.lower() or "deshabilit" in stdout.lower():
                return "  ⚠️ La protecciÃ³n del sistema estÃ¡ deshabilitada. ActÃ­vala desde 'Crear punto de restauraciÃ³n' en Windows."
            return f"  ⚠️ No se pudo crear el punto de restauraciÃ³n: {stdout[:200]}"
        except subprocess.TimeoutExpired:
            return "  [!) Tiempo de espera agotado. La creaciÃ³n puede tardar hasta 1 minuto en sistemas lentos."
        except Exception as e:
            return f"  ⚠️ Error al crear punto de restauraciÃ³n: {e}"

    def _toggle_night_light(self, activar: bool) -> str:
        try:
            # Night light via Windows Registry
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.bluelightreductionsettings.bluelightreductionstate\windows.data.bluelightreductionsettings.bluelightreductionstate"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
                value, regtype = winreg.QueryValueEx(key, "Data")
                # The Data blob has the state byte at position 20 (0=off, 1=on)
                data = bytearray(value)
                if len(data) > 20:
                    data[20] = 1 if activar else 0
                    winreg.SetValueEx(key, "Data", 0, regtype, bytes(data))
                winreg.CloseKey(key)
                time.sleep(1)
                return f"  Luz nocturna {'activada' if activar else 'desactivada'}."
            except FileNotFoundError:
                return "  ⚠️ No se pudo cambiar la luz nocturna por este mÃ©todo. Usa ConfiguraciÃ³n > Pantalla."
        except Exception as e:
            return f"  ⚠️ Error al cambiar luz nocturna: {e}"

    def _uninstall_app(self, app: str) -> str:
        try:
            # Buscar en el registro de desinstalaciÃ³n
            import winreg
            paths = [
                r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ]
            found = []
            for base_path in paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path)
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            try:
                                name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                uninst, _ = winreg.QueryValueEx(subkey, "UninstallString")
                                if name and app.lower() in name.lower():
                                    found.append((name, uninst))
                            except FileNotFoundError:
                                pass
                            winreg.CloseKey(subkey)
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except Exception:
                    continue

            if not found:
                return f"  No encontrÃ© '{app}' instalado. Â¿Tal vez es una app de Microsoft Store? Prueba: winget uninstall {app}"

            if len(found) == 1:
                name, uninst = found[0]
                return self._ejecutar_desinstalacion(name, uninst)
            else:
                res = f"  EncontrÃ© varias apps con '{app}':\n"
                for i, (name, uninst) in enumerate(found[:5], 1):
                    res += f"  {i}. {name}\n"
                res += "  Especifica el nÃºmero exacto."
                return res
        except Exception as e:
            return f"  ⚠️ Error al buscar '{app}': {e}"

    def _ejecutar_desinstalacion(self, name: str, uninst: str) -> str:
        try:
            if uninst.startswith("MsiExec.exe") or "msiexec" in uninst.lower():
                subprocess.Popen(uninst + " /quiet", shell=True)
            elif uninst.endswith(".exe"):
                subprocess.Popen(f'"{uninst}" /S /silent /quiet', shell=True)
            else:
                subprocess.Popen(f'"{uninst}"', shell=True)
            return f"  Iniciando desinstalaciÃ³n de '{name}' en segundo plano."
        except Exception as e:
            return f"  ⚠️ Error al desinstalar '{name}': {e}"

    def _abrir_app_instalada(self, app: str) -> str:
        """Intenta abrir cualquier app instalada por nombre."""
        # Buscar en Start Menu
        start_menu = os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs")
        common_start = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
        for base in [start_menu, common_start]:
            for root, dirs, files in os.walk(base):
                for f in files:
                    if f.endswith(".lnk") and app.lower() in f.lower():
                        ruta = os.path.join(root, f)
                        try:
                            os.startfile(ruta)
                            return f"  Abriendo {f.replace('.lnk', '')}."
                        except Exception:
                            continue
                for d in dirs:
                    if app.lower() in d.lower():
                        for f2 in os.listdir(os.path.join(root, d)):
                            if f2.endswith(".lnk"):
                                ruta = os.path.join(root, d, f2)
                                try:
                                    os.startfile(ruta)
                                    return f"  Abriendo {f2.replace('.lnk', '')}."
                                except Exception:
                                    continue
        # Buscar en PATH
        try:
            result = subprocess.run(["where", app], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                ruta = result.stdout.strip().split("\n")[0]
                os.startfile(ruta)
                return f"  Abriendo {app}."
        except Exception:
            pass
        return f"  No encontrÃ© '{app}' instalado."

    def _info_sistema(self) -> str:
        uname = platform.uname()
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        dias, seg = uptime.days, uptime.seconds
        horas = seg // 3600
        minutos = (seg % 3600) // 60
        cpu_pct = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        lines = [
            f"  {COMPUTADORA}  INFORMACION DEL SISTEMA",
            f"  ---------------------------",
            f"  Sistema:   {uname.system} {uname.release}",
            f"  VersiÃ³n:   {uname.version}",
            f"  Hostname:  {uname.node}",
        ]
        # Usuarios activos
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-LocalUser | Where-Object {$_.Enabled -eq $true} | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                users = [u.strip() for u in r.stdout.strip().split('\n') if u.strip()]
                if users:
                    lines.append(f"  Usuarios:  {', '.join(users)}")
        except Exception:
            pass
        lines.extend([
            f"  Procesador: {uname.processor or 'Desconocido'}",
            f"  NÃºcleos:   {psutil.cpu_count(logical=True)} lÃ³gicos / {psutil.cpu_count(logical=False)} fÃ­sicos",
            f"  CPU:       {cpu_pct}% de uso",
            f"  RAM:       {mem.percent}% usado ({mem.used // 1024**3} GB / {mem.total // 1024**3} GB)",
        ])
        # Discos
        for part in psutil.disk_partitions():
            if "cdrom" in part.opts or part.fstype == "":
                continue
            try:
                uso = psutil.disk_usage(part.mountpoint)
                lines.append(f"  Disco {part.device}: {uso.used // 1024**3} GB / {uso.total // 1024**3} GB ({uso.percent}%)")
            except PermissionError:
                continue
        lines.append(f"  Encendido: {boot_time.strftime('%d/%m/%Y %H:%M')}  ({dias}d {horas}h {minutos}m)")
        # Red
        lines.append(f"  -- RED --")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'}).IPAddress"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                ips = [ip.strip() for ip in r.stdout.strip().split('\n') if ip.strip()]
                if ips:
                    lines.append(f"  IP privada: {', '.join(ips)}")
        except Exception:
            pass
        try:
            import requests
            r = requests.get("https://api.ipify.org?format=text", timeout=5)
            if r.status_code == 200:
                lines.append(f"  IP pÃºblica: {r.text.strip()}")
        except Exception:
            pass
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object Name,MacAddress,LinkSpeed | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip() not in ('', '[]'):
                import json
                adapters = json.loads(r.stdout)
                if not isinstance(adapters, list):
                    adapters = [adapters]
                for a in adapters[:3]:
                    lines.append(f"  {a.get('Name','')}: MAC {a.get('MacAddress','')} | {a.get('LinkSpeed','')}")
        except Exception:
            pass
        return "\n".join(lines)

    def _listar_profiles_wifi(self) -> str:
        try:
            r = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                return "  ⚠️ No se pudo obtener la lista de perfiles WiFi."
            perfiles = []
            for line in r.stdout.split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    val = parts[1].strip()
                    if val and val not in (' ', ''):
                        perfiles.append(val)
            if not perfiles:
                return "  No hay perfiles WiFi guardados."
            res = f"  Perfiles WiFi guardados ({len(perfiles)}):\n"
            for i, p in enumerate(perfiles, 1):
                res += f"    {i}. {p}\n"
            res += "\n  Di 'contraseÃ±a del wifi <nombre>' para ver la clave."
            return res
        except Exception as e:
            return f"  ⚠️ Error al listar perfiles WiFi: {e}"

    def _wifi_password(self, cmd: str) -> str:
        # Extraer nombre del perfil
        nombre = None
        numero = None
        m = re.search(r'(?:contraseÃ±[ao]|clave|password|pass|key)\s*(?:del\s+)?(?:wifi\s+)?(?:de\s+)?[Â´\"\u201C]?([^\"\u201D\s]+(?:\s+[^\"\u201D\s]+)*)', cmd)
        if m:
            nombre = m.group(1).strip().strip('"\'')
            # Check if it's a stop word
            if nombre.lower() in ("contraseÃ±a", "contraseÃ±o", "clave", "password", "pass", "key", "wifi", "wi-fi", "del", "de", "la", "el", "las", "los"):
                nombre = None
            elif nombre.isdigit():
                numero = int(nombre)
                nombre = None
        if not nombre and not numero:
            return f"  Â¿QuÃ© perfil WiFi? Di el nombre. Ej: 'contraseÃ±a del wifi MiFibra'\n\n{self._listar_profiles_wifi()}"
        # If number, map to profile name
        if numero:
            try:
                r = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=10)
                perfiles = []
                for line in r.stdout.split('\n'):
                    if ':' in line:
                        val = line.split(':', 1)[1].strip()
                        if val and val not in (' ', ''):
                            perfiles.append(val)
                if 1 <= numero <= len(perfiles):
                    nombre = perfiles[numero - 1]
                else:
                    return f"  NÃºmero invÃ¡lido. Hay {len(perfiles)} perfiles. Usa 'perfiles wifi' para verlos."
            except Exception as e:
                return f"  ⚠️ Error: {e}"
        try:
            r = subprocess.run(["netsh", "wlan", "show", "profile", f"name={nombre}", "key=clear"],
                              capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                # Try fuzzy matching
                r2 = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=10)
                fuzzy = []
                for line in r2.stdout.split('\n'):
                    if ':' in line:
                        val = line.split(':', 1)[1].strip()
                        if val and nombre.lower() in val.lower():
                            fuzzy.append(val)
                if fuzzy:
                    nombre = fuzzy[0]
                    r = subprocess.run(["netsh", "wlan", "show", "profile", f"name={nombre}", "key=clear"],
                                      capture_output=True, text=True, timeout=15)
                else:
                    return f"  No encontrÃ© el perfil WiFi '{nombre}'. Usa 'perfiles wifi' para ver la lista."
            password = None
            for line in r.stdout.split('\n'):
                if 'Contenido de la clave' in line or 'Key Content' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        password = parts[1].strip()
                    break
            if password:
                return f"  ContraseÃ±a de '{nombre}': {password}"
            return f"  El perfil '{nombre}' no tiene contraseÃ±a o es una red abierta."
        except Exception as e:
            return f"  ⚠️ Error al obtener contraseÃ±a: {e}"

    def _bateria(self) -> str:
        if not hasattr(psutil, "sensors_battery"):
            return "  ⚠️ No se pudo leer informaciÃ³n de la baterÃ­a."
        try:
            bat = psutil.sensors_battery()
            if bat is None:
                return "  ⚠️ No se detectÃ³ baterÃ­a (PC de escritorio?)."
            pct = bat.percent
            estado = "cargando" if bat.power_plugged else "desconectado"
            tiempo_rest = ""
            if bat.secsleft > 0 and not bat.power_plugged:
                hrs = bat.secsleft // 3600
                mins = (bat.secsleft % 3600) // 60
                tiempo_rest = f" ({hrs}h {mins}m restantes)"
            return f"  {BATERIA}  BaterÃ­a: {pct}% ({estado}){tiempo_rest}"
        except Exception:
            return "  ⚠️ No se pudo leer informaciÃ³n de la baterÃ­a."

    def _cpu_info(self) -> str:
        return f"  {COMPUTADORA}  CPU: {platform.processor() or 'Desconocido'} | Uso: {psutil.cpu_percent(interval=0.5)}%"

    def _memoria_info(self) -> str:
        mem = psutil.virtual_memory()
        return (
            f"  {MEMORIA}  MEMORIA RAM\n"
            f"  Total: {mem.total // 1024**3} GB\n"
            f"  Usado: {mem.used // 1024**3} GB ({mem.percent}%)\n"
            f"  Libre: {mem.available // 1024**3} GB"
        )

    def _disco_info(self) -> str:
        resultado = f"  {DISCO}  ALMACENAMIENTO\n"
        for part in psutil.disk_partitions():
            if "cdrom" in part.opts or part.fstype == "":
                continue
            try:
                uso = psutil.disk_usage(part.mountpoint)
                resultado += (
                    f"  {part.device} ({part.mountpoint})\n"
                    f"    Total: {uso.total // 1024**3} GB\n"
                    f"    Usado: {uso.used // 1024**3} GB ({uso.percent}%)\n"
                    f"    Libre: {uso.free // 1024**3} GB\n"
                )
            except PermissionError:
                continue
        return resultado

    def help(self) -> str:
        return (
            "Comandos:\n"
            "  sistema           - InformaciÃ³n completa del sistema\n"
            "  cpu               - Estado del procesador\n"
            "  memoria           - Uso de RAM\n"
            "  disco             - Almacenamiento\n"
            "  baterÃ­a           - Estado de la baterÃ­a\n"
            "  activar/apagar apache   - Controla Xampp Apache\n"
            "  activar/apagar bluetooth - Activa/desactiva Bluetooth\n"
            "  activar/apagar wifi     - Activa/desactiva WiFi\n"
            "  activar/apagar luz nocturna - Controla luz nocturna\n"
            "  desinstalar <app>       - Desinstala una aplicaciÃ³n\n"
            "  abrir <app>             - Abre cualquier app instalada"
        )

