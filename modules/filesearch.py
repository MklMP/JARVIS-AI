"""
MÃ³dulo de bÃºsqueda de archivos con Everything.
Usa es.exe para bÃºsqueda instantÃ¡nea en todo el disco.
"""

import subprocess
import os
import re
from .base import ModuleBase
from utils.emoji import CARPETA, ARCHIVO


class FileSearchModule(ModuleBase):
    """BÃºsqueda ultra-rÃ¡pida de archivos con Everything."""

    ES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "es.exe")

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["buscar", "search", "find", "encuentra", "donde esta",
                                   "dÃ³nde estÃ¡", "archivo", "encuentrame"]):
            return self._buscar(command)
        elif any(p in cmd for p in ["tipo", "type", "extension", "ext"]):
            return self._buscar_por_tipo(command)
        else:
            return self.help()

    def _buscar(self, command: str) -> str:
        query = self._extraer_query(command)
        if not query:
            return "  ⚠️ Â¿QuÃ© archivo quieres buscar? Ej: buscar presupuesto.xlsx"

        resultados = self._ejecutar_es(query, max_results=15)
        if not resultados:
            return f"  No encontrÃ© archivos para '{query}'."

        return self._formatear_resultados(resultados, query)

    def _buscar_por_tipo(self, command: str) -> str:
        tipos = {
            "musica": "ext:mp3;wav;flac;aac;ogg;wma",
            "music": "ext:mp3;wav;flac;aac;ogg;wma",
            "video": "ext:mp4;mkv;avi;mov;wmv;flv",
            "imagen": "ext:jpg;jpeg;png;gif;bmp;tiff;webp",
            "image": "ext:jpg;jpeg;png;gif;bmp;tiff;webp",
            "documento": "ext:doc;docx;xls;xlsx;ppt;pptx;pdf;txt",
            "document": "ext:doc;docx;xls;xlsx;ppt;pptx;pdf;txt",
            "pdf": "ext:pdf",
            "excel": "ext:xls;xlsx;csv",
            "word": "ext:doc;docx",
            "codigo": "ext:py;js;ts;java;c;cpp;cs;go;rs;rb;php;html;css",
            "code": "ext:py;js;ts;java;c;cpp;cs;go;rs;rb;php;html;css",
            "zip": "ext:zip;rar;7z;tar;gz",
        }

        tipo = "document"
        for key, val in tipos.items():
            if key in command.lower():
                tipo = val
                break

        # Buscar tambiÃ©n query especÃ­fica
        query = self._extraer_query(command, ignorar=["tipo", "type", "extension", "ext", "de", "archivos", "musica", "video", "imagen", "documento"])
        query_es = f"{query} {tipo}" if query else tipo

        resultados = self._ejecutar_es(query_es.strip(), max_results=15)
        if not resultados:
            return f"  No encontrÃ© archivos de ese tipo."

        return self._formatear_resultados(resultados, f"tipo: {tipo}")

    def _extraer_query(self, command: str, ignorar: list = None) -> str:
        if ignorar is None:
            ignorar = ["buscar", "search", "find", "encuentra", "donde esta",
                       "dÃ³nde estÃ¡", "encuentrame", "archivo", "archivos",
                       "de", "el", "la", "los", "las", "un", "una",
                       "me", "por favor"]
        cmd = command.lower()
        for palabra in ignorar:
            cmd = cmd.replace(palabra, "")
        return cmd.strip().strip('"').strip("'")

    def _ejecutar_es(self, query: str, max_results: int = 15) -> list:
        if not os.path.exists(self.ES_PATH):
            return [f"⚠️ es.exe no encontrado en {self.ES_PATH}"]

        try:
            result = subprocess.run(
                [self.ES_PATH, "-n", str(max_results), "-s", query],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0 and result.returncode != 1:
                return []
            lineas = [l.strip() for l in result.stdout.split("\n") if l.strip()]
            return lineas
        except subprocess.TimeoutExpired:
            return []
        except Exception as e:
            return [f"⚠️ Error: {e}"]

    def _formatear_resultados(self, resultados: list, query: str) -> str:
        if not resultados or (len(resultados) == 1 and resultados[0].startswith("[!")):
            return "\n".join(resultados)

        salida = f"  {CARPETA}  RESULTADOS DE: {query}\n"
        salida += f"  ----------------------------------------\n"
        for i, ruta in enumerate(resultados, 1):
            nombre = os.path.basename(ruta)
            dirname = os.path.dirname(ruta)
            salida += f"  {i}. {ARCHIVO} {nombre}\n"
            salida += f"     {dirname}\n"
        salida += f"\n  {len(resultados)} archivo(s) encontrado(s)"
        return salida

    def help(self) -> str:
        return (
            "BÃšSQUEDA DE ARCHIVOS (Everything):\n"
            "  buscar <nombre>             - Busca archivos al instante\n"
            "  buscar tipo musica          - Archivos de mÃºsica\n"
            "  buscar tipo video           - Archivos de video\n"
            "  buscar tipo documento       - Documentos\n"
            "  buscar tipo imagen          - ImÃ¡genes\n"
            "  buscar tipo codigo          - CÃ³digo fuente\n"
            "  buscar presupuesto tipo excel - Busca excels de presupuesto\n\n"
            "Ej: buscar informe.pdf\n"
            "    buscar tipo musica\n"
            "    buscar factura tipo pdf"
        )

