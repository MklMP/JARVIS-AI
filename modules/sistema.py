import os
import subprocess
import json
import shutil
import sys
import re


class SistemaModule:
    def __init__(self, config=None, api_keys=None):
        self._modulos_registrados = {}

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()
        if re.search(r'\banaliz[ae]r?\s*(los\s*)?discos|analiz[ae]r?\s*(el\s*)?disco|estado\s*de\s*l[o]s\s*discos|ver\s*(los\s*)?discos|c[oÃ³]mo\s*est[Ã¡a]n\s*l[o]s\s*discos|espacio\s*(en\s*)?(disco|el\s*disco)\b', cmd):
            return self.analizar_discos()
        if re.search(r'\bdesfragmentac[iÃ³]n|fragmentac[iÃ³]n\b', cmd):
            m = re.search(r'([a-zA-Z]:)', cmd)
            return self.analizar_fragmentacion(m.group(1).rstrip(":\\") if m else "C")
        if re.search(r'\bcopia\s*de\s*seguridad|copias\s*de\s*seguridad|backup|backups\b', cmd):
            return self.verificar_backups()
        if re.search(r'\busb|unidad\s*(externa|extra[Ã­i]ble|usb)|pendrive|flash\b', cmd):
            return self.listar_usb()
        if re.search(r'\bcopia|copiar|transferir|pasar\b', cmd):
            m = re.search(r'\b(copia|copiar|transferir|pasar)\s+(.+?)\s+(a|hacia|para|en|dentro\s*de)\s+(.+)', cmd)
            if m:
                origen = os.path.expandvars(os.path.expanduser(m.group(2).strip().strip('"').strip("'")))
                destino = os.path.expandvars(os.path.expanduser(m.group(4).strip().strip('"').strip("'")))
                if re.match(r'^[a-zA-Z]:$', destino):
                    destino = destino + "\\"
                return self.copiar_archivo(origen, destino)
            return "  Indica quÃ© archivo copiar y a dÃ³nde. Ej: copia C:\\doc.txt a E:\\."
        return "  Comando de sistema no reconocido. Prueba: analizar discos, fragmentacion, backups, usb, espacio en disco, copiar X a Y."

    def analizar_discos(self) -> str:
        partes = []
        drives = self._listar_discos()
        if not drives:
            return "No se encontraron discos."
        bajos = []
        for d in drives:
            partes.append(f"-> {d['letra']} ({d['tipo']})")
            partes.append(f"  Espacio: {d['usado_gb']:.1f} GB usados de {d['total_gb']:.1f} GB ({d['libre_gb']:.1f} GB libres)")
            partes.append(f"  Ocupado: {d['porciento']:.0f}%  |  Salud: {d['salud']}")
            if d['fs']:
                partes.append(f"  Sistema: {d['fs']}")
            if d['tipo'] == "Fixed" and d['porciento'] > 85:
                bajos.append(d['letra'])
            if d['tipo'] == "Removable" and d['libre_gb'] == 0:
                bajos.append(f"{d['letra']} (USB vacÃ­o/sin conectar)")
        res = "\n".join(partes)
        if bajos:
            res += f"\n\n⚠️ Discos con poco espacio: {', '.join(bajos)}"
        return res

    def _listar_discos(self) -> list:
        try:
            r = subprocess.run(
                ["powershell", "-c", "Get-Volume | Select-Object DriveLetter, FileSystem, DriveType, HealthStatus, SizeRemaining, Size | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            resultado = []
            fisicos = {}
            try:
                r2 = subprocess.run(
                    ["powershell", "-c", "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, Size, HealthStatus | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=10
                )
                fisicos_list = json.loads(r2.stdout) if r2.stdout.strip() else []
                if isinstance(fisicos_list, dict):
                    fisicos_list = [fisicos_list]
                for f in fisicos_list:
                    fisicos[f.get("FriendlyName", "?")] = f
            except Exception:
                pass
            for v in data:
                letra = v.get("DriveLetter", "")
                if not letra:
                    continue
                total_b = v.get("Size", 0) or 0
                libre_b = v.get("SizeRemaining", 0) or 0
                usado_b = total_b - libre_b
                total_gb = total_b / (1024**3)
                libre_gb = libre_b / (1024**3)
                usado_gb = usado_b / (1024**3)
                porciento = (usado_b / total_b * 100) if total_b > 0 else 0
                resultado.append({
                    "letra": f"{letra}:\\",
                    "fs": v.get("FileSystem", "") or "",
                    "tipo": v.get("DriveType", "?"),
                    "salud": v.get("HealthStatus", "?"),
                    "total_gb": total_gb,
                    "libre_gb": libre_gb,
                    "usado_gb": usado_gb,
                    "porciento": porciento,
                })
            return resultado
        except Exception as e:
            return [{"letra": "Error", "tipo": "", "total_gb": 0, "libre_gb": 0, "usado_gb": 0, "porciento": 0, "fs": "", "salud": str(e)}]

    def _drive_letra(self) -> str:
        """Devuelve la letra de la primera unidad extraÃ­ble (USB) o 'C:'"""
        drives = self._listar_discos()
        for d in drives:
            if d['tipo'] == "Removable" and d['libre_gb'] > 0:
                return d['letra'][0]
        return "C"

    def listar_usb(self) -> str:
        usbs = [d for d in self._listar_discos() if d['tipo'] == "Removable"]
        if not usbs:
            return "No se detectaron unidades USB conectadas."
        partes = ["Unidades USB detectadas:"]
        for u in usbs:
            partes.append(f"-> {u['letra']}  Libre: {u['libre_gb']:.1f} GB  Total: {u['total_gb']:.1f} GB")
        return "\n".join(partes)

    def copiar_archivo(self, origen: str, destino: str) -> str:
        if not os.path.exists(origen):
            return f"Error: No se encuentra el archivo '{origen}'"
        try:
            os.makedirs(os.path.dirname(destino), exist_ok=True) if os.path.dirname(destino) else None
            if os.path.isdir(destino):
                nombre = os.path.basename(origen)
                destino = os.path.join(destino, nombre)
            shutil.copy2(origen, destino)
            tam = os.path.getsize(destino)
            if tam < 1024:
                tam_str = f"{tam} bytes"
            elif tam < 1024**2:
                tam_str = f"{tam/1024:.1f} KB"
            else:
                tam_str = f"{tam/(1024**2):.1f} MB"
            return f"Copiado: {os.path.basename(origen)} â†’ {destino} ({tam_str})"
        except Exception as e:
            return f"Error copiando: {e}"

    def analizar_fragmentacion(self, drive: str = "") -> str:
        if not drive:
            drive = "C"
        drive = drive.rstrip(":\\").upper()
        try:
            r = subprocess.run(
                ["powershell", "-c", f"Optimize-Volume -DriveLetter {drive} -Analyze | Select-Object DriveLetter, DefragAnalysis | ConvertTo-Json"],
                capture_output=True, text=True, timeout=30
            )
            out = r.stdout.strip()
            if not out:
                r2 = subprocess.run(
                    ["powershell", "-c", f"Optimize-Volume -DriveLetter {drive} -Analyze | Format-List"],
                    capture_output=True, text=True, timeout=30
                )
                salida = r2.stdout.strip()
                if not salida:
                    return f"AnÃ¡lisis de fragmentaciÃ³n para {drive}:\\ requiere permisos administrativos o la unidad es SSD."
                return f"FragmentaciÃ³n {drive}:\\:\n{salida[:500]}"
            try:
                data = json.loads(out)
                if isinstance(data, dict):
                    return f"FragmentaciÃ³n {drive}:\\: AnÃ¡lisis completado."
                return f"FragmentaciÃ³n {drive}:\\: {out[:300]}"
            except json.JSONDecodeError:
                return f"FragmentaciÃ³n {drive}:\\:\n{out[:500]}"
        except Exception as e:
            return f"Error analizando fragmentaciÃ³n: {e}"

    def verificar_backups(self) -> str:
        try:
            r = subprocess.run(
                ["powershell", "-c", "Get-WBBackupSet | Select-Object BackupTime, Successfully | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            out = r.stdout.strip()
            if not out or "Get-WBBackupSet" in out:
                return "Windows Backup: No se encontraron copias de seguridad. Â¿Tienes instalado Windows Server Backup?"
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            if not data:
                return "No se encontraron copias de seguridad de Windows."
            partes = ["Copias de seguridad de Windows:"]
            for b in data:
                ok = "✅" if b.get("Successfully") else "❌"
                partes.append(f"  {b.get('BackupTime', '?')}  {ok}")
            return "\n".join(partes)
        except Exception as e:
            return f"Error verificando backups: {e}"

    def resumen_completo(self) -> str:
        discos = self.analizar_discos()
        usb = self.listar_usb()
        frag = self.analizar_fragmentacion("C")
        backups = self.verificar_backups()
        return f"{discos}\n\n{usb}\n\nFragmentaciÃ³n:\n{frag}\n\nBackups:\n{backups}"

