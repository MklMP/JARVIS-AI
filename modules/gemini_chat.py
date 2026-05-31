import requests
import json


class GeminiChat:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "gemini-2.0-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1/models"

    def preguntar(self, pregunta: str, max_tokens: int = 300) -> dict:
        if not self.api_key:
            return {"exito": False, "resultado": ""}

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": pregunta}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
            }
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        texto = parts[0].get("text", "").strip()
                        if texto:
                            return {"exito": True, "resultado": texto, "fuente": "Gemini"}
            error_msg = r.text[:200]
            return {"exito": False, "resultado": "", "error": f"HTTP {r.status_code}: {error_msg}"}
        except Exception as e:
            return {"exito": False, "resultado": "", "error": str(e)}

    def preguntar_con_extras(self, pregunta: str, contexto: str = "") -> dict:
        """Versión mejorada con contexto adicional."""
        if contexto:
            prompt = f"Responde en español de forma clara y concisa.\n\nContexto: {contexto}\n\nPregunta: {pregunta}"
        else:
            prompt = f"Responde en español de forma clara y concisa.\n\nPregunta: {pregunta}"
        return self.preguntar(prompt)
