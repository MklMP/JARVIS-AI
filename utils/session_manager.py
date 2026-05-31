import json
import os
import uuid
from datetime import datetime

SESSIONS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions.json")


def sanitize_string(s):
    if isinstance(s, str):
        return s.encode('utf-8', 'replace').decode('utf-8')
    return s


def sanitize_dict(d):
    if isinstance(d, dict):
        return {k: sanitize_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [sanitize_dict(i) for i in d]
    elif isinstance(d, str):
        return sanitize_string(d)
    return d


def limpiar_archivo_corrupto(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8', errors='surrogateescape') as f:
            contenido = f.read()
        contenido_limpio = contenido.encode('utf-8', 'replace').decode('utf-8')
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido_limpio)
        return json.loads(contenido_limpio) if contenido_limpio.strip() else {}
    except Exception as e:
        print(f"Historial corrupto, reiniciando: {e}")
        try:
            with open(ruta, 'w') as f:
                json.dump({}, f)
        except Exception:
            pass
        return {}


class SessionManager:
    def __init__(self):
        self._path = SESSIONS_PATH
        self._datos = self._cargar()
        self._activa = self._datos.get("activa", "")

    def _cargar(self) -> dict:
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                return sanitize_dict(raw) if raw else {"sessions": {}, "activa": ""}
            except Exception:
                return limpiar_archivo_corrupto(self._path)
        return {"sessions": {}, "activa": ""}

    def guardar(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._datos["activa"] = self._activa
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._datos, f, indent=2, ensure_ascii=False)

    def listar(self) -> list:
        sessions = self._datos.get("sessions", {})
        result = []
        for sid, s in sessions.items():
            result.append({
                "id": sid,
                "name": s.get("name", "Sin nombre"),
                "created": s.get("created", ""),
                "updated": s.get("updated", ""),
                "count": len(s.get("history", [])),
                "active": sid == self._activa,
            })
        result.sort(key=lambda x: x["updated"], reverse=True)
        return result

    def crear(self, name: str = None) -> dict:
        sid = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        self._datos.setdefault("sessions", {})[sid] = {
            "name": name or f"Sesión {len(self._datos['sessions']) + 1}",
            "history": [],
            "ultima_respuesta": "",
            "ultima_respuesta_tema": "",
            "created": now,
            "updated": now,
        }
        self._activa = sid
        self.guardar()
        return {"id": sid, "name": self._datos["sessions"][sid]["name"]}

    def switch(self, session_id: str) -> dict:
        sessions = self._datos.get("sessions", {})
        if session_id not in sessions:
            return {"ok": False, "error": "Sesión no encontrada"}
        self._activa = session_id
        now = datetime.now().isoformat()
        sessions[session_id]["updated"] = now
        self.guardar()
        s = sessions[session_id]
        return sanitize_dict({
            "ok": True,
            "history": s.get("history", []),
            "ultima_respuesta": s.get("ultima_respuesta", ""),
            "ultima_respuesta_tema": s.get("ultima_respuesta_tema", ""),
        })

    def rename(self, session_id: str, new_name: str) -> bool:
        sessions = self._datos.get("sessions", {})
        if session_id not in sessions:
            return False
        sessions[session_id]["name"] = new_name.strip() or sessions[session_id]["name"]
        self.guardar()
        return True

    def eliminar(self, session_id: str) -> bool:
        sessions = self._datos.get("sessions", {})
        if session_id not in sessions:
            return False
        del sessions[session_id]
        if self._activa == session_id:
            restantes = list(sessions.keys())
            self._activa = restantes[0] if restantes else ""
        self.guardar()
        return True

    def activa(self) -> str:
        return self._activa

    def obtener_activa(self) -> dict:
        sessions = self._datos.get("sessions", {})
        s = sessions.get(self._activa)
        if not s:
            return {}
        return sanitize_dict(s)

    def guardar_historial(self, comando: str, respuesta: str):
        sessions = self._datos.setdefault("sessions", {})
        s = sessions.get(self._activa)
        if not s:
            return
        # Limitar a 5000 chars para mantener el JSON manejable
        comando = sanitize_string(comando)
        respuesta = sanitize_string(respuesta)
        resp_guardada = respuesta[:5000] if respuesta else ""
        s.setdefault("history", []).append({"cmd": comando, "resp": resp_guardada, "ts": datetime.now().isoformat()})
        # Podar historial si excede 200 entradas (las más viejas)
        if len(s["history"]) > 200:
            s["history"] = s["history"][-200:]
        s["updated"] = datetime.now().isoformat()
        self.guardar()

    def guardar_estado(self, ultima_respuesta: str, ultima_respuesta_tema: str):
        sessions = self._datos.setdefault("sessions", {})
        s = sessions.get(self._activa)
        if not s:
            return
        s["ultima_respuesta"] = sanitize_string(ultima_respuesta)
        s["ultima_respuesta_tema"] = sanitize_string(ultima_respuesta_tema)
        self.guardar()
