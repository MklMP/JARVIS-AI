import os
import re
import json
import hashlib
import time
from .base import ModuleBase


class VirusTotalModule(ModuleBase):
    """
    Análisis de archivos con VirusTotal.
    Escanea archivos locales y devuelve reporte de detección.
    """

    API_URL = "https://www.virustotal.com/api/v3"

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self.api_key = api_keys.get("virustotal", "")
        self._last_result = None

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()
        if not self.api_key:
            return "  No hay API key de VirusTotal configurada."

        if kwargs.get("file_path"):
            return self._escanear_archivo(kwargs["file_path"])

        if cmd.startswith("virustotal "):
            path = cmd[11:].strip().strip('"').strip("'")
            return self._escanear_archivo(path)

        m_hash = re.search(r'\b([a-fA-F0-9]{32,64})\b', cmd)
        if m_hash:
            return self._consultar_hash(m_hash.group(1))

        return self.help()

    def _escanear_archivo(self, path: str) -> str:
        if not os.path.isfile(path):
            return f"  Archivo no encontrado: {path}"

        import requests
        headers = {"x-apikey": self.api_key}
        tamano = os.path.getsize(path)
        nombre = os.path.basename(path)

        file_hash = self._calcular_hashes(path)
        if not file_hash:
            return "  Error calculando hash del archivo."

        reporte = self._consultar_hash(file_hash["sha256"])
        if reporte and "No detectado" not in reporte:
            return reporte

        try:
            with open(path, "rb") as f:
                files = {"file": (nombre, f)}
                resp = requests.post(
                    f"{self.API_URL}/files",
                    headers=headers,
                    files=files,
                    timeout=120
                )
            if resp.status_code == 200:
                data = resp.json()
                analysis_id = data.get("data", {}).get("id", "")
                if analysis_id:
                    time.sleep(15)
                    return self._obtener_analisis(analysis_id)
            body = resp.text[:300] if resp.text else ""
            return f"  Error al subir archivo: HTTP {resp.status_code}\n  {body}"
        except Exception as e:
            return f"  Error: {e}"

    def _calcular_hashes(self, path: str) -> dict:
        sha256 = hashlib.sha256()
        sha1 = hashlib.sha1()
        md5 = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
                sha1.update(chunk)
                md5.update(chunk)
        return {"sha256": sha256.hexdigest(), "sha1": sha1.hexdigest(), "md5": md5.hexdigest()}

    def _consultar_hash(self, file_hash: str) -> str:
        import requests
        headers = {"x-apikey": self.api_key}
        try:
            resp = requests.get(
                f"{self.API_URL}/files/{file_hash}",
                headers=headers,
                timeout=30
            )
            if resp.status_code == 200:
                return self._formatear_reporte(resp.json())
            body = resp.text[:300] if resp.text else ""
            return f"  VirusTotal: HTTP {resp.status_code}\n  {body}"
        except Exception as e:
            return f"  Error consultando VirusTotal: {e}"

    def _obtener_analisis(self, analysis_id: str) -> str:
        import requests
        headers = {"x-apikey": self.api_key}
        try:
            resp = requests.get(
                f"{self.API_URL}/analyses/{analysis_id}",
                headers=headers,
                timeout=30
            )
            if resp.status_code == 200:
                return self._formatear_reporte(resp.json())
            body = resp.text[:300] if resp.text else ""
            return f"  Error obteniendo análisis: HTTP {resp.status_code}\n  {body}"
        except Exception as e:
            return f"  Error: {e}"

    def _formatear_reporte(self, data: dict) -> str:
        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("stats", attrs.get("last_analysis_stats", {}))
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        undetected = stats.get("undetected", 0)
        harmless = stats.get("harmless", 0)
        total = malicious + suspicious + undetected + harmless
        nombre = attrs.get("meaningful_name", attrs.get("sha256", "")[:16])

        if malicious > 0:
            riesgo = "PELIGROSO" if malicious >= 5 else "SOSPECHOSO"
        else:
            riesgo = "LIMPIO"

        resultado = (
            f"  VirusTotal — {nombre}\n"
            f"  ───────────────────────────\n"
            f"  Estado: {riesgo}\n"
            f"  Maliciosos: {malicious}/{total}\n"
            f"  Sospechosos: {suspicious}\n"
            f"  No detectados: {undetected}\n"
            f"  Inocuos: {harmless}"
        )
        if malicious > 0:
            results = attrs.get("last_analysis_results", {})
            detectados = []
            for engine, res in results.items():
                if res.get("category") == "malicious":
                    detectados.append(f"    {engine}: {res.get('result', 'malware')}")
            if detectados:
                resultado += "\n  Detectado por:\n" + "\n".join(detectados[:10])
        self._last_result = resultado
        return resultado

    def help(self) -> str:
        return (
            "  VIRUSTOTAL\n"
            "  ─────────────────────\n"
            "  virustotal <ruta>   — Escanea un archivo\n"
            "  También compatible con envio desde interfaz web\n"
        )