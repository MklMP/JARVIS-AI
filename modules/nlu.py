"""Clasificador de intención local (MLP + TF-IDF) para JARVIS."""
import os
import re
import json
import joblib
import numpy as np


class IntentClassifier:
    """Clasificador de intención ligero que corre 100% local."""

    def __init__(self, models_dir: str = None):
        if models_dir is None:
            models_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.models_dir = models_dir
        self.clf = None
        self.vectorizer = None
        self.le = None
        self.labels = []
        self._cargado = False
        self._cargar_modelos()

    def _cargar_modelos(self):
        try:
            clf_path = os.path.join(self.models_dir, "intent_model.joblib")
            vec_path = os.path.join(self.models_dir, "vectorizer.joblib")
            le_path = os.path.join(self.models_dir, "intent_encoder.joblib")
            labels_path = os.path.join(self.models_dir, "intent_labels.json")

            if not all(os.path.exists(p) for p in [clf_path, vec_path, le_path]):
                print("[NLU] Modelos no encontrados. Ejecuta training/train_intent.py")
                return

            self.clf = joblib.load(clf_path)
            self.vectorizer = joblib.load(vec_path)
            self.le = joblib.load(le_path)
            self.labels = self.le.classes_.tolist() if hasattr(self.le, "classes_") else []
            self._cargado = True
            print(f"[NLU] Cargado: {len(self.labels)} intenciones")
        except Exception as e:
            print(f"[NLU] Error cargando modelos: {e}")

    @property
    def disponible(self) -> bool:
        return self._cargado

    def clasificar(self, texto: str) -> tuple:
        """(intent, confidence) o (None, 0.0) si no disponible o baja confianza."""
        if not self._cargado:
            return None, 0.0

        texto_limpio = texto.lower().strip()
        if not texto_limpio:
            return None, 0.0

        try:
            X = self.vectorizer.transform([texto_limpio])
            pred_enc = self.clf.predict(X)[0]
            probs = self.clf.predict_proba(X)[0]
            confidence = float(max(probs))
            intent = self.le.inverse_transform([pred_enc])[0]
            return intent, confidence
        except Exception as e:
            print(f"[NLU] Error en clasificación: {e}")
            return None, 0.0

    def clasificar_con_umbral(self, texto: str, umbral: float = 0.85) -> tuple:
        """(intent, confidence) si supera el umbral, sino (None, confidence)."""
        intent, confidence = self.clasificar(texto)
        if intent and confidence >= umbral:
            return intent, confidence
        return None, confidence


# Mapeo de intenciones locales que NO requieren el agente/LLM
INTENT_ACCION_LOCAL = {
    "greeting": "saludo",
    "goodbye": "despedida",
    "thanks": "agradecimiento",
    "affirmation": "afirmacion",
    "affirmative_answer": "afirmacion_respuesta",
    "denial": "negacion",
    "compliment": "cumplido",
    "insult": "insulto",
    "sad": "animo_bajo",
    "who_are_you": "presentacion",
    "creator": "creador",
    "capabilities": "ayuda",
    "how_are_you": "como_estas",
    "jokes": "chiste",
    "curious_fact": "dato_curioso",
    "memory_show": "memoria_mostrar",
    "memory_learn": "memoria_aprender",
    "memory_forget": "memoria_olvidar",
    "user_name": "nombre_usuario",
    "continue": "continuar",
    "time": "hora",
    "weather": "clima",
    "news": "noticias",
    "stocks": "bolsa",
    "music": "musica",
    "apps": "aplicaciones",
    "games": "juegos",
    "books": "libros",
    "catalogo": "catalogo",
    "movie_info": "info_pelicula",
    "maps": "mapas",
    "system_info": "sistema",
    "disks": "discos",
    "fragmentation": "fragmentacion",
    "backups": "backups",
    "usb": "usb",
    "health": "salud",
    "reminders": "recordatorios",
    "email": "correo",
    "whatsapp": "whatsapp",
    "mathematics": "matematicas",
    "web_search": "busqueda_web",
    "wikipedia_search": "busqueda_wikipedia",
    "how_to": "como_hacer",
    "ip_info": "ip",
    "wifi_info": "wifi_info",
    "toggles": "interruptores",
    "restore_point": "punto_restauracion",
    "uninstall": "desinstalar",
    "encode_decode": "codificar",
    "shutdown": "apagar",
    "open_url": "abrir_url",
    "virustotal": "virustotal",
    "article": "articulo",
    "correction": "correccion",
    "followup": "seguimiento",
    "amplify": "ampliar",
    "argue": "argumentar",
}

# Intenciones que pueden manejarse SIN el agente (respuesta local o módulo local)
INTENT_SIN_AGENTE = {
    "greeting", "goodbye", "thanks", "affirmation", "denial",
    "compliment", "insult", "sad", "who_are_you", "creator",
    "capabilities", "how_are_you", "jokes", "curious_fact",
    "memory_show", "memory_learn", "memory_forget",
    "user_name", "continue", "affirmative_answer",
}
