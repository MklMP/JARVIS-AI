import os
from datetime import datetime
from .base import ModuleBase
from utils.emoji import SI, CARPETA, ARCHIVO, LIBRO


class FilesModule(ModuleBase):
    """MÃ³dulo de archivos y documentos."""

    def __init__(self, config: dict, api_keys: dict):
        super().__init__(config, api_keys)
        self._core_ref = None  # Set by JarvisCore to enable asking for path

    def set_core(self, core):
        self._core_ref = core

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["crear", "create", "nuevo", "new", "archivo", "file"]):
            return self._crear_archivo(command, kwargs)
        elif any(p in cmd for p in ["listar", "list", "ls", "directorio", "dir", "folder"]):
            return self._listar_directorio(command)
        elif any(p in cmd for p in ["leer", "read", "ver", "abrir", "open"]):
            return self._leer_archivo(command)
        elif any(p in cmd for p in ["eliminar", "delete", "borrar", "rm"]):
            return "⚠️ FunciÃ³n de eliminaciÃ³n desactivada por seguridad."
        elif any(p in cmd for p in ["mkdir", "carpeta", "directorio"]):
            return self._crear_directorio(command)
        else:
            return self.help()

    def _crear_archivo(self, command: str, kwargs: dict) -> str:
        import re
        cmd = command.lower()
        nombre = kwargs.get("nombre", "")
        contenido = kwargs.get("contenido", "")
        ruta = kwargs.get("ruta", "")

        if not nombre:
            match = re.search(r'llamado\s+["\']?(.+?)["\']?(?:\s|$)', command, re.IGNORECASE)
            if not match:
                match = re.search(r'nombre\s+["\']?(.+?)["\']?(?:\s|$)', command, re.IGNORECASE)
            if not match:
                match = re.search(r'con\s+el\s+nombre\s+["\']?(.+?)["\']?(?:\s|$)', command, re.IGNORECASE)
            if match:
                nombre = match.group(1).strip()

        if not nombre:
            nombre = "Jarvis"

        if "." not in nombre:
            nombre += ".txt"

        # Si no se especificÃ³ ruta, preguntar
        if not ruta:
            # Buscar "en <carpeta>" en el comando
            match = re.search(r'en\s+["\']?(.+?)["\']?(?:\s|$)', command, re.IGNORECASE)
            if match:
                carpeta = match.group(1).strip()
                if os.path.isdir(carpeta):
                    ruta = carpeta
                else:
                    return f"  ⚠️ La carpeta '{carpeta}' no existe."
            else:
                # Preguntar por la ruta
                if self._core_ref and hasattr(self._core_ref, '_pendiente_archivo'):
                    self._core_ref._pendiente_archivo = {
                        "nombre": nombre,
                        "comando": command,
                    }
                    return f"  Â¿En quÃ© ruta quieres guardar '{nombre}'? (Ej: C:\\Users\\{os.environ.get('USERNAME', 'tu_usuario')}\\Desktop)"
                ruta = os.path.expanduser("~")

        if not os.path.isabs(nombre):
            ruta_completa = os.path.join(ruta, nombre)
        else:
            ruta_completa = nombre

        try:
            with open(ruta_completa, "w", encoding="utf-8") as f:
                f.write(contenido or f"Archivo creado por Jarvis - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
            tamaño = os.path.getsize(ruta_completa)
            return (
                f"  {SI}  Archivo creado: {ruta_completa}\n"
                f"  Tamaño: {tamaño} bytes"
            )
        except PermissionError:
            return f"  ⚠️ Permiso denegado para escribir en {ruta_completa}"
        except Exception as e:
            return f"  ⚠️ Error creando archivo: {e}"

    def _listar_directorio(self, command: str) -> str:
        import re
        cmd = command.lower()

        # Buscar ruta
        ruta = os.path.expanduser("~")
        match = re.search(r'en\s+["\']?(.+?)["\']?(?:\s|$)', command, re.IGNORECASE)
        if match:
            ruta = match.group(1).strip()

        if not os.path.isdir(ruta):
            return f"  ⚠️ La ruta '{ruta}' no existe o no es un directorio."

        try:
            items = os.listdir(ruta)
            if not items:
                return f"  {CARPETA}  El directorio '{ruta}' estÃ¡ vacÃ­o."

            carpetas = []
            archivos = []
            for item in sorted(items):
                item_path = os.path.join(ruta, item)
                if os.path.isdir(item_path):
                    carpetas.append(f"  {CARPETA}  {item}/")
                else:
                    tamaño = os.path.getsize(item_path)
                    if tamaño < 1024:
                        tamaño_str = f"{tamaño} B"
                    elif tamaño < 1024**2:
                        tamaño_str = f"{tamaño/1024:.1f} KB"
                    else:
                        tamaño_str = f"{tamaño/1024**2:.1f} MB"
                    archivos.append(f"  {ARCHIVO}  {item}  ({tamaño_str})")

            resultado = f"  {CARPETA}  CONTENIDO DE: {ruta}\n"
            resultado += "  ------------------------------------\n"
            resultado += "\n".join(carpetas + archivos)
            return resultado

        except PermissionError:
            return f"  ⚠️ Permiso denegado para leer {ruta}"
        except Exception as e:
            return f"  ⚠️ Error listando directorio: {e}"

    def _leer_archivo(self, command: str) -> str:
        import re
        cmd = command.lower()

        ruta = ""
        match = re.search(r'(?:el\s+)?(?:archivo\s+)?["\']?(.+?)["\']?(?:\s|$)', command, re.IGNORECASE)
        if match:
            ruta = match.group(1).strip()

        if not ruta:
            return "  ⚠️ Debes especificar quÃ© archivo quieres leer."

        if not os.path.isabs(ruta):
            ruta = os.path.join(os.path.expanduser("~"), ruta)

        if not os.path.isfile(ruta):
            return f"  ⚠️ El archivo '{ruta}' no existe."

        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
            return (
                f"  {LIBRO}  {ruta}\n"
                f"  ------------------------------------\n"
                f"{contenido[:2000]}"
            )
        except Exception as e:
            return f"  ⚠️ Error leyendo archivo: {e}"

    def _crear_directorio(self, command: str) -> str:
        import re
        cmd = command.lower()

        nombre = ""
        match = re.search(r'llamado\s+["\']?(.+?)["\']?(?:\s|$)', command, re.IGNORECASE)
        if not match:
            match = re.search(r'(?:crear|nuev[oa])\s+(?:carpeta|directorio)\s+["\']?(.+?)["\']?(?:\s|$)', command, re.IGNORECASE)
        if match:
            nombre = match.group(1).strip()

        if not nombre:
            return "  ⚠️ Debes especificar un nombre para la carpeta.\n  Uso: crear carpeta llamada <nombre>"

        if not os.path.isabs(nombre):
            ruta = os.path.join(os.path.expanduser("~"), nombre)
        else:
            ruta = nombre

        try:
            os.makedirs(ruta, exist_ok=True)
            return f"  {SI}  Carpeta creada: {ruta}"
        except PermissionError:
            return f"  ⚠️ Permiso denegado para crear {ruta}"
        except Exception as e:
            return f"  ⚠️ Error creando carpeta: {e}"

    def help(self) -> str:
        return (
            "Comandos de archivos:\n"
            "  crear archivo llamado <nombre>              - Crea un archivo de texto\n"
            "  crear archivo llamado <nombre> en <ruta>    - Crea archivo en ruta especÃ­fica\n"
            "  crear carpeta llamada <nombre>              - Crea una carpeta\n"
            "  listar [en <ruta>]                          - Lista contenido del directorio\n"
            "  leer <archivo>                              - Muestra contenido del archivo\n\n"
            "Ej:  crear archivo llamado hola.txt\n"
            "     crear archivo llamado notas.txt en C:\\Users\\TuUsuario\\Documents\n"
            "     crear carpeta llamada Proyectos\n"
            "     listar\n"
            "     listar en C:\\Users\\TuUsuario\\Documents"
        )

