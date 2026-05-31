"""Memoria persistente de directorios por categoría.

Guarda rutas que el usuario o JARVIS aprenden para música, juegos, libros, etc.
"""
import json
import os


class DirMemory:
    """Guarda y recupera directorios por categoría."""

    def __init__(self, ruta_db: str = None):
        if ruta_db is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ruta_db = os.path.join(base, "directorios.json")
        self.ruta_db = ruta_db
        self._datos = {}
        self._cargar()

    def _cargar(self):
        self._datos = {"music": [], "games": [], "books": [], "movies": [], "apps": []}
        if os.path.exists(self.ruta_db):
            try:
                with open(self.ruta_db, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k in self._datos:
                            if k in data and isinstance(data[k], list):
                                self._datos[k] = [d for d in data[k] if os.path.isdir(d)]
            except Exception:
                pass

    def _guardar(self):
        try:
            with open(self.ruta_db, "w", encoding="utf-8") as f:
                json.dump(self._datos, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def agregar(self, categoria: str, ruta: str) -> bool:
        """Agrega un directorio para una categoría si existe y no está repetido."""
        if not os.path.isdir(ruta):
            return False
        if categoria not in self._datos:
            self._datos[categoria] = []
        ruta_norm = os.path.realpath(ruta)
        if ruta_norm not in self._datos[categoria]:
            self._datos[categoria].append(ruta_norm)
            self._guardar()
            return True
        return False

    def obtener(self, categoria: str) -> list:
        """Devuelve todos los directorios guardados para una categoría."""
        return self._datos.get(categoria, [])

    def tiene(self, categoria: str) -> bool:
        return len(self.obtener(categoria)) > 0

    def quitar(self, categoria: str, ruta: str) -> bool:
        if categoria in self._datos:
            ruta_norm = os.path.realpath(ruta)
            if ruta_norm in self._datos[categoria]:
                self._datos[categoria].remove(ruta_norm)
                self._guardar()
                return True
        return False

    def todas(self) -> dict:
        return dict(self._datos)
