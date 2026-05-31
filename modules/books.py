"""
MÃ³dulo de libros - detecta, lista y abre archivos PDF.
Soporta selecciÃ³n numerada y lectura con TTS.
"""

import os
import re
import json
import random
import difflib
from .base import ModuleBase

try:
    import fitz
    _HAS_PDF_EXTRACT = True
except ImportError:
    _HAS_PDF_EXTRACT = False


class BooksModule(ModuleBase):
    """DetecciÃ³n y apertura de libros PDF."""

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self.db_path = os.path.expanduser("~/.jarvis/books_db.json")
        self._books_db = {}
        self._cargar_db()
        self._pendiente_ruta = None
        self._pendiente_seleccion = None
        self._pendiente_accion = None

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ PÃšBLICO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower().strip()

        if self._pendiente_accion:
            return self._procesar_accion(cmd)

        if self._pendiente_seleccion:
            return self._procesar_seleccion(cmd)

        if self._pendiente_ruta:
            return self._procesar_ruta_pendiente(cmd)

        if cmd.startswith("listar") or cmd.startswith("lista"):
            return self._listar_libros()

        if cmd.startswith("escanear "):
            carpeta = cmd[9:].strip()
            return self._escanear_carpeta(carpeta)

        libro = self._extraer_libro(cmd)
        if libro:
            ruta = self._buscar_en_db(libro)
            if ruta:
                return self._hacer_accion(ruta, libro)
            encontrado = self._escanear_para_libro(libro)
            if encontrado:
                return self._hacer_accion(encontrado, libro)
            return f"  No encontrÃ© '{libro}'. Prueba con 'lista libros' para ver los disponibles."

        return self.help()

    def help(self) -> str:
        return (
            "LIBROS:\n"
            "  abre libro <nombre>       - Abre un libro PDF\n"
            "  lista libros              - Muestra los libros disponibles\n"
            "  que libros tengo          - Muestra los libros disponibles\n\n"
            "Ej: abre libro el principito\n"
            "    que libros tengo\n"
            "    lista libros"
        )

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ BASE DE DATOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _cargar_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            if os.path.exists(self.db_path):
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self._books_db = json.load(f)
        except Exception:
            self._books_db = {}

    def _guardar_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self._books_db, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _aprender_libro(self, nombre: str, ruta_pdf: str):
        self._books_db[nombre.lower().strip()] = ruta_pdf
        alias = nombre.lower().strip().replace("_", " ").replace("-", " ")
        if alias != nombre.lower().strip():
            self._books_db[alias] = ruta_pdf
        self._guardar_db()

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ EXTRACCIÃ“N â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _extraer_libro(self, cmd: str) -> str:
        m = re.search(r'\b(abrir|abre|lanzar|abreme|abrame|buscar|busca)\s+(el\s+|la\s+|un\s+|una\s+)?(libro|pdf|libro\s+llamado|libro\s+que\s+se\s+llama)\s+(.+)', cmd)
        if m:
            nombre = m.group(m.lastindex).strip()
            nombre = re.sub(r'\b(libro|pdf|por\s*favor|gracias)\b', '', nombre).strip()
            return nombre if len(nombre) > 1 else ""
        m = re.search(r'\b(abrir|abre|lanzar|abreme|abrame)\s+(el\s+|la\s+|un\s+|una\s+)?(.+)', cmd)
        if m:
            nombre = m.group(m.lastindex).strip()
            nombre = re.sub(r'\b(por\s*favor|gracias)\b', '', nombre).strip()
            if nombre and len(nombre) > 2:
                return nombre
        return ""

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ LISTAR + SELECCIONAR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _listar_libros(self) -> str:
        if not self._books_db:
            self._escanear_inicio()
        if not self._books_db:
            return "  No tengo libros en mi base de datos. Dime una carpeta donde tengas PDFs."
        ordenados = sorted(self._books_db.items(), key=lambda x: x[0])
        total = len(ordenados)
        mostrar = ordenados[:50]
        salida = f"  LIBROS DISPONIBLES ({total})\n"
        salida += "  â”€" * 15 + "\n"
        for i, (nombre, _) in enumerate(mostrar, 1):
            salida += f"  [{i}] {nombre.capitalize()}\n"
        if total > 50:
            salida += f"  ... y {total - 50} mÃ¡s\n"
        salida += f"\n  Di el nÃºmero del libro (1-{min(50, total)}), 'cualquiera' para uno al azar, o 'todos' para mostrarlos."
        self._pendiente_seleccion = ordenados
        return salida

    def _procesar_seleccion(self, cmd: str) -> str:
        libros = self._pendiente_seleccion
        self._pendiente_seleccion = None

        if re.search(r'\b(cancel|ninguno|no|nunca|para|salir)\b', cmd):
            return "  OK, cancelado."

        if re.search(r'\b(todos|todo|mostrar|ver\s+todos|resto|mas|m[Ã¡a]s|completos?|listar|lista)\b', cmd):
            salida = f"  TODOS LOS LIBROS ({len(libros)})\n"
            salida += "  â”€" * 15 + "\n"
            for i, (nombre, _) in enumerate(libros, 1):
                salida += f"  [{i}] {nombre.capitalize()}\n"
            salida += f"\n  Di el nÃºmero, 'cualquiera' o 'cancelar'."
            self._pendiente_seleccion = libros
            return salida

        if re.search(r'\b(cualquiera|aleatorio|random|cualquier|elige\s+t[Ãºu]|decide\s+t[Ãºu]|lo\s+que\s+quieras|como\s+quieras|el\s+que\s+quieras)\b', cmd):
            idx = random.randint(0, len(libros) - 1)
            nombre, ruta = libros[idx]
            return self._preguntar_accion(ruta, nombre)

        m = re.search(r'\b(\d+)\b', cmd)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(libros):
                nombre, ruta = libros[idx]
                return self._preguntar_accion(ruta, nombre)
            return f"  NÃºmero invÃ¡lido (1-{len(libros)}). Intenta de nuevo o di 'cancelar'."

        m = re.search(r'\b(abrir|abre|leer|lee|leerlo|abrirlo)\b', cmd)
        if m:
            return "  Â¿CuÃ¡l? Di un nÃºmero o 'cualquiera'."

        self._pendiente_seleccion = None
        return "  No entendÃ­. Di un nÃºmero (ej: '5'), 'cualquiera' o 'cancelar'."

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ ACCIÃ“N (ABRIR / LEER) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _preguntar_accion(self, ruta: str, nombre: str) -> str:
        self._pendiente_accion = (ruta, nombre)
        return f"  ✅ {nombre.capitalize()}\n  Â¿Que hago? Di 'abrir' para abrirlo o 'leer' para leerlo en voz alta."

    def _procesar_accion(self, cmd: str) -> str:
        ruta, nombre = self._pendiente_accion
        self._pendiente_accion = None

        if re.search(r'\b(abrir|abre|abrelo|abrirlo|abreme|open|mostrar|ver)\b', cmd):
            return self._abrir_libro(ruta, nombre)

        if re.search(r'\b(leer|lee|leerlo|leelo|lectura|leerme|read|voz|hablar|texto)\b', cmd):
            return self._leer_libro(ruta, nombre)

        if re.search(r'\b(cancel|no|ninguno|salir|parar)\b', cmd):
            return "  OK, cancelado."

        return f"  Â¿'abrir' o 'leer'? (di 'abrir' para abrir el PDF o 'leer' para leerlo en voz alta)"

    def _hacer_accion(self, ruta: str, nombre: str) -> str:
        return self._preguntar_accion(ruta, nombre)

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ ABRIR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _abrir_libro(self, ruta: str, nombre: str) -> str:
        if not os.path.exists(ruta):
            for k, v in list(self._books_db.items()):
                if v == ruta:
                    del self._books_db[k]
            self._guardar_db()
            return f"  ⚠️ El libro '{nombre}' ya no estÃ¡ en {ruta}. Dime la nueva ubicaciÃ³n."
        try:
            os.startfile(ruta)
            nombre_mostrar = os.path.splitext(os.path.basename(ruta))[0]
            return f"  Abriendo {nombre_mostrar}..."
        except Exception as e:
            return f"  ⚠️ Error al abrir {nombre}: {e}"

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ LEER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _leer_libro(self, ruta: str, nombre: str) -> str:
        if not os.path.exists(ruta):
            return f"  ⚠️ El libro '{nombre}' ya no estÃ¡."
        if not _HAS_PDF_EXTRACT:
            return f"  No puedo extraer el texto (falta PyMuPDF). InstalÃ¡lo con: pip install PyMuPDF\n  Por ahora, lo abro: {self._abrir_libro(ruta, nombre)}"
        try:
            doc = fitz.open(ruta)
            paginas = len(doc)
            if paginas == 0:
                doc.close()
                return f"  El PDF '{nombre}' estÃ¡ vacÃ­o."
            # Extraer las primeras pÃ¡ginas (mÃ¡x 30 para no saturar)
            max_pag = min(paginas, 30)
            texto = []
            for i in range(max_pag):
                p = doc.load_page(i)
                t = p.get_text().strip()
                if t:
                    texto.append(t)
            doc.close()
            if not texto:
                return f"  No pude extraer texto de '{nombre}' (PDF escaneado/imagen). Lo abro: {self._abrir_libro(ruta, nombre)}"
            contenido = "\n\n".join(texto)
            # Limitar a ~2000 chars para no sobrecargar
            if len(contenido) > 2000:
                contenido = contenido[:2000] + "...\n\n[El libro continÃºa. Di 'sigue' o 'continua' para mÃ¡s.]"
            return f"  Leyendo '{nombre}' ({paginas} pags, mostrando primeras {max_pag}):\n\n{contenido}"
        except Exception as e:
            return f"  ⚠️ Error al leer '{nombre}': {e}"

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ BÃšSQUEDA EN DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _buscar_en_db(self, libro: str) -> str:
        libro_lower = libro.lower().strip()
        if libro_lower in self._books_db:
            return self._books_db[libro_lower]
        for nombre, ruta in self._books_db.items():
            if libro_lower in nombre or nombre in libro_lower:
                return ruta
        nombres = list(self._books_db.keys())
        matches = difflib.get_close_matches(libro_lower, nombres, n=1, cutoff=0.5)
        if matches:
            return self._books_db[matches[0]]
        return None

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ ESCANEO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _escanear_para_libro(self, libro: str) -> str:
        carpetas = self._carpetas_comunes()
        for carpeta in carpetas:
            if not os.path.isdir(carpeta):
                continue
            for root, dirs, files in os.walk(carpeta):
                depth = root.replace(carpeta, "").count(os.sep)
                if depth > 4:
                    continue
                for f in files:
                    if not f.lower().endswith(".pdf"):
                        continue
                    nombre_base = os.path.splitext(f)[0].lower()
                    if libro.lower() in nombre_base or difflib.SequenceMatcher(None, libro.lower(), nombre_base).ratio() > 0.5:
                        ruta = os.path.join(root, f)
                        self._aprender_libro(nombre_base, ruta)
                        return ruta
        return None

    def _escanear_carpeta(self, carpeta: str) -> str:
        if not os.path.isdir(carpeta):
            return f"  La carpeta '{carpeta}' no existe."
        encontrados = 0
        for root, dirs, files in os.walk(carpeta):
            depth = root.replace(carpeta, "").count(os.sep)
            if depth > 4:
                continue
            for f in files:
                if not f.lower().endswith(".pdf"):
                    continue
                nombre = os.path.splitext(f)[0]
                ruta = os.path.join(root, f)
                self._aprender_libro(nombre, ruta)
                encontrados += 1
        if encontrados:
            self._guardar_db()
            return f"  EncontrÃ© {encontrados} libro(s) en '{carpeta}' y los guardÃ©. Di 'lista libros' para verlos."
        return f"  No encontrÃ© PDFs en '{carpeta}'."

    def _escanear_inicio(self):
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
                    for f in files:
                        if not f.lower().endswith(".pdf"):
                            continue
                        nombre = os.path.splitext(f)[0]
                        ruta = os.path.join(root, f)
                        self._aprender_libro(nombre, ruta)
                        encontrados += 1
            except:
                continue
        if encontrados:
            self._guardar_db()

    def _carpetas_comunes(self) -> list:
        carpetas = [
            os.path.expanduser("~\\Desktop"),
            os.path.expanduser("~\\Downloads"),
            os.path.expanduser("~\\Documents"),
            os.path.expanduser("~\\OneDrive"),
            os.path.expanduser("~\\Dropbox"),
        ]
        for letra in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            unidad = f"{letra}:\\"
            if os.path.exists(unidad):
                for sub in ["Books", "Libros", "PDF", "pdfs", "eBooks", "lectura", "Documents", "Descargas"]:
                    p = os.path.join(unidad, sub)
                    if os.path.isdir(p):
                        carpetas.append(p)
        return list(dict.fromkeys(carpetas))

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ RUTA PENDIENTE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def set_pendiente_ruta(self, libro: str):
        self._pendiente_ruta = libro

    def _procesar_ruta_pendiente(self, cmd: str) -> str:
        libro = self._pendiente_ruta
        self._pendiente_ruta = None
        m = re.search(r'([A-Za-z]:[\\/](?:[^\s,;)]+))', cmd)
        if m:
            carpeta = m.group(1)
            if os.path.isdir(carpeta):
                return self._escanear_carpeta(carpeta)
            if os.path.isfile(carpeta):
                self._aprender_libro(libro, carpeta)
                return self._abrir_libro(carpeta, libro)
            return f"  La ruta '{carpeta}' no existe."
        encontrado = self._escanear_para_libro(libro)
        if encontrado:
            return self._abrir_libro(encontrado, libro)
        return f"  No encontrÃ© '{libro}'. Â¿Puedes decirme la carpeta donde estÃ¡? (ej: \"estÃ¡ en D:\\Libros\")"

