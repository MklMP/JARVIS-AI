import json
import os
import re
import difflib
from datetime import datetime

MEMORIA_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "memoria.json")


class Memoria:
    """Sistema de memoria y aprendizaje automático para Jarvis.

    - Almacena hechos aprendidos (clave → valor)
    - Aprende de interacciones pasadas
    - Pesos neuronales simples para predecir qué módulo aplicar
    - Coincidencia difusa para recuperar información
    """

    def __init__(self):
        self._path = MEMORIA_PATH
        self._datos = self._cargar()

    def _cargar(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "hechos": {},
            "interacciones": [],
            "pesos": {},
            "aprendido": {},
            "correcciones": {},
        }

    def guardar(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._datos, f, indent=2, ensure_ascii=False)

    def aprender(self, tema: str, info: str):
        clave = tema.lower().strip()
        ahora = datetime.now().isoformat()
        if clave not in self._datos["hechos"]:
            self._datos["hechos"][clave] = {"valor": info, "veces": 0, "ultima": ""}
        self._datos["hechos"][clave]["valor"] = info
        self._datos["hechos"][clave]["veces"] += 1
        self._datos["hechos"][clave]["ultima"] = ahora
        self.guardar()

    def recordar(self, consulta: str) -> str:
        resultado = self._recordar_raw(consulta)
        if resultado:
            return resultado[1]
        return ""

    def recordar_formateado(self, consulta: str) -> str:
        resultado = self._recordar_raw(consulta)
        if resultado:
            clave, valor = resultado
            if clave.lower() in valor.lower():
                return valor.capitalize()
            if clave.lower() == consulta.lower().strip():
                return valor
            return f"{clave}: {valor}"
        return ""

    STOP_WORDS = {"el", "la", "los", "las", "de", "del", "en", "un", "una", "y", "e", "o", "a", "que",
                   "es", "son", "con", "por", "para", "su", "sus", "tu", "mi", "se", "no", "lo", "le",
                   "al", "como", "más", "mas", "pero", "sin", "esto", "esta", "este", "ese", "esa"}

    def _filtrar_stop_words(self, palabras: set) -> set:
        return {p for p in palabras if len(p) > 2 and p not in self.STOP_WORDS}

    def _recordar_raw(self, consulta: str):
        consulta_lower = consulta.lower().strip()
        if consulta_lower in self._datos["hechos"]:
            self._datos["hechos"][consulta_lower]["veces"] += 1
            self.guardar()
            return (consulta_lower, self._datos["hechos"][consulta_lower]["valor"])

        palabras = self._filtrar_stop_words(set(consulta_lower.split()))
        candidatos = []
        for clave, hecho in self._datos["hechos"].items():
            palabras_clave = self._filtrar_stop_words(set(clave.split()))
            if not palabras_clave or not palabras:
                continue
            comun = palabras & palabras_clave
            if len(comun) >= max(len(palabras), len(palabras_clave)) * 0.5:
                ratio = len(comun) / max(len(palabras | palabras_clave), 1)
                candidatos.append((ratio, clave, hecho["valor"]))
        if candidatos:
            candidatos.sort(reverse=True)
            if candidatos[0][0] >= 0.4:
                return (candidatos[0][1], candidatos[0][2])

        return None

    def registrar_interaccion(self, entrada: str, respuesta: str, modulo: str = ""):
        self._datos["interacciones"].append({
            "entrada": entrada,
            "respuesta": respuesta,
            "modulo": modulo,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self._datos["interacciones"]) > 1000:
            self._datos["interacciones"] = self._datos["interacciones"][-1000:]

        palabras = set(entrada.lower().split())
        for p in palabras:
            if len(p) < 3:
                continue
            if p not in self._datos["pesos"]:
                self._datos["pesos"][p] = {}
            if modulo:
                self._datos["pesos"][p][modulo] = self._datos["pesos"][p].get(modulo, 0) + 1

        self.guardar()

    def predecir_modulo(self, entrada: str) -> str:
        palabras = set(entrada.lower().split())
        scores = {}
        for p in palabras:
            if p in self._datos["pesos"]:
                for mod, peso in self._datos["pesos"][p].items():
                    scores[mod] = scores.get(mod, 0) + peso
        if scores:
            return max(scores, key=scores.get)
        return ""

    def olvidar(self, tema: str) -> bool:
        clave = tema.lower().strip()
        if clave in self._datos["hechos"]:
            del self._datos["hechos"][clave]
            self.guardar()
            return True
        return False

    def listar_hechos(self) -> list:
        return [f"{k}: {v['valor']}" for k, v in sorted(self._datos["hechos"].items(), key=lambda x: x[1].get("ultima", ""), reverse=True)]

    def estadisticas(self) -> dict:
        return {
            "hechos": len(self._datos["hechos"]),
            "interacciones": len(self._datos["interacciones"]),
            "pesos": sum(len(v) for v in self._datos["pesos"].values()),
        }
