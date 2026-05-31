"""Memoria vectorial para JARVIS — recuperación semántica sin API externa.

Usa TF-IDF + coseno como embedding para búsqueda por similitud.
No requiere GPU ni descarga de modelos.
"""
import os
import json
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class MemoriaVectorial:
    """Almacena experiencias como vectores TF-IDF y recupera las más similares."""

    def __init__(self, ruta_db: str = None):
        if ruta_db is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ruta_db = os.path.join(base, "memoria_vectorial.json")
        self.ruta_db = ruta_db
        self.entradas = []
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=2000,
            sublinear_tf=True,
            stop_words=None,
        )
        self._vectores = None
        self._dirty = False
        self._cargar()

    def _cargar(self):
        if os.path.exists(self.ruta_db):
            try:
                with open(self.ruta_db, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entradas = data if isinstance(data, list) else []
                print(f"[MemoriaVec] Cargadas {len(self.entradas)} entradas")
            except Exception as e:
                print(f"[MemoriaVec] Error cargando: {e}")
                self.entradas = []

    def _guardar(self):
        try:
            with open(self.ruta_db, "w", encoding="utf-8") as f:
                json.dump(self.entradas, f, ensure_ascii=False, indent=2)
            self._dirty = False
        except Exception as e:
            print(f"[MemoriaVec] Error guardando: {e}")

    def _reconstruir_vectores(self):
        if not self.entradas:
            self._vectores = None
            return
        textos = [e.get("texto", "") for e in self.entradas]
        try:
            self._vectores = self.vectorizer.fit_transform(textos)
        except Exception:
            self._vectores = None

    def recordar(self, query: str, top_k: int = 3, umbral: float = 0.3) -> list:
        """Recupera las entradas más similares a la consulta."""
        if not self.entradas or not query.strip():
            return []

        self._reconstruir_vectores()
        if self._vectores is None:
            return []

        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self._vectores)[0]

        indices = np.argsort(sims)[::-1][:top_k]
        resultados = []
        for idx in indices:
            if sims[idx] >= umbral:
                resultados.append({
                    "texto": self.entradas[idx].get("texto", ""),
                    "respuesta": self.entradas[idx].get("respuesta", ""),
                    "intent": self.entradas[idx].get("intent", ""),
                    "similitud": float(round(sims[idx], 4)),
                    "fecha": self.entradas[idx].get("fecha", ""),
                })
        return resultados

    def aprender(self, texto: str, respuesta: str, intent: str = ""):
        """Guarda una interacción en la memoria vectorial."""
        from datetime import datetime
        entrada = {
            "texto": texto,
            "respuesta": respuesta,
            "intent": intent,
            "fecha": datetime.now().isoformat(),
        }
        # Evitar duplicados exactos
        for e in self.entradas:
            if e["texto"] == texto and e["respuesta"] == respuesta:
                return
        self.entradas.append(entrada)
        self._dirty = True
        # Guardar cada N entradas
        if len(self.entradas) % 5 == 0:
            self._guardar()

    def limpiar(self):
        self.entradas = []
        self._vectores = None
        self._guardar()

    @property
    def total(self) -> int:
        return len(self.entradas)
