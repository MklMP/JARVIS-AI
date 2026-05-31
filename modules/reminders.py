"""
MÃ³dulo de recordatorios con persistencia SQLite y alertas en tiempo real.
"""

import os
import json
import threading
import time
import sqlite3
import datetime
from .base import ModuleBase
from utils.emoji import RELON, CALENDARIO


class RemindersModule(ModuleBase):
    """Recordatorios persistentes con timer en segundo plano."""

    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reminders.db")

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self._alertas_pendientes = []
        self._init_db()
        self._timer_activo = False
        self._iniciar_timer()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                texto TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT,
                creado_en TEXT DEFAULT (datetime('now')),
                completado INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def _iniciar_timer(self):
        """Timer en segundo plano que revisa recordatorios cada 30 segundos."""
        def _loop():
            self._timer_activo = True
            while self._timer_activo:
                self._revisar_recordatorios()
                time.sleep(30)
        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def detener(self):
        self._timer_activo = False

    def _revisar_recordatorios(self):
        ahora = datetime.datetime.now()
        fecha_hoy = ahora.strftime("%Y-%m-%d")
        hora_actual = ahora.strftime("%H:%M")

        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.execute("""
            SELECT id, texto, fecha, hora FROM recordatorios
            WHERE completado = 0
        """)
        for row in cursor.fetchall():
            rid, texto, fecha, hora = row
            if fecha == fecha_hoy:
                if hora and hora <= hora_actual:
                    self._alertas_pendientes.append({
                        "id": rid,
                        "texto": texto,
                        "fecha": fecha,
                        "hora": hora
                    })
                    conn.execute("UPDATE recordatorios SET completado = 1 WHERE id = ?", (rid,))
                elif not hora:
                    self._alertas_pendientes.append({
                        "id": rid,
                        "texto": texto,
                        "fecha": fecha,
                        "hora": ""
                    })
                    conn.execute("UPDATE recordatorios SET completado = 1 WHERE id = ?", (rid,))
        conn.commit()
        conn.close()

    def obtener_alertas(self) -> list:
        alertas = self._alertas_pendientes.copy()
        self._alertas_pendientes.clear()
        return alertas

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["recordatorio", "recordar", "remind", "recuerdame",
                                   "acuerdame", "no olvides", "tarea"]):
            return self._crear_recordatorio(command)
        elif any(p in cmd for p in ["lista recordatorios", "mis recordatorios",
                                     "pendientes", "listar recordatorios"]):
            return self._listar_recordatorios()
        elif any(p in cmd for p in ["borrar recordatorio", "eliminar recordatorio",
                                     "completar", "delete reminder"]):
            return self._borrar_recordatorio(command)
        elif any(p in cmd for p in ["alarma", "alarm", "despertador", "wake"]):
            return self._crear_alarma(command)
        else:
            return self.help()

    def _crear_recordatorio(self, command: str) -> str:
        import re

        texto = ""
        fecha = datetime.date.today().strftime("%Y-%m-%d")
        hora = ""

        # Detectar "en X minutos/horas"
        match_min = re.search(r'en\s+(\d+)\s*(minuto|minutos|min|m)\b', command, re.IGNORECASE)
        match_hor = re.search(r'en\s+(\d+)\s*(hora|horas|hrs|h)\b', command, re.IGNORECASE)
        if match_min:
            mins = int(match_min.group(1))
            ahora = datetime.datetime.now()
            futuro = ahora + datetime.timedelta(minutes=mins)
            fecha = futuro.strftime("%Y-%m-%d")
            hora = futuro.strftime("%H:%M")
        elif match_hor:
            hrs = int(match_hor.group(1))
            ahora = datetime.datetime.now()
            futuro = ahora + datetime.timedelta(hours=hrs)
            fecha = futuro.strftime("%Y-%m-%d")
            hora = futuro.strftime("%H:%M")

        # Detectar "a las HH:MM"
        match_hora = re.search(r'a\s+las\s+(\d{1,2}):(\d{2})', command, re.IGNORECASE)
        if match_hora:
            hora = f"{int(match_hora.group(1)):02d}:{match_hora.group(2)}"

        # Detectar "maÃ±ana" o "pasado maÃ±ana"
        if "pasado maÃ±ana" in cmd or "pasado" in cmd:
            fecha = (datetime.date.today() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        elif "maÃ±ana" in cmd:
            fecha = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        # Extraer texto despuÃ©s de "recordar" o "recordatorio"
        match = re.search(r'(?:recordar|recordatorio|recuerdame|que|:)\s*(.+)', command, re.IGNORECASE)
        if match:
            texto = match.group(1).strip()
            # Limpiar palabras sobrantes
            for p in ["en", "minutos", "minuto", "min", "m", "horas", "hora", "hrs", "h"]:
                texto = re.sub(r'\s+\d+\s*' + p, '', texto, flags=re.IGNORECASE)
            texto = re.sub(r'a\s+las\s+\d{1,2}:\d{2}', '', texto, flags=re.IGNORECASE)
            texto = re.sub(r'maÃ±ana|pasado\s+maÃ±ana|pasado', '', texto, flags=re.IGNORECASE)
            texto = texto.strip().strip(',').strip()

        if not texto:
            return (
                "  ⚠️ No entendÃ­ el recordatorio.\n"
                "  Ej: recordar comprar leche maÃ±ana a las 10:00\n"
                "      recuerdame llamar a Juan en 30 minutos\n"
                "      recordatorio: reuniÃ³n a las 15:00"
            )

        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            "INSERT INTO recordatorios (texto, fecha, hora) VALUES (?, ?, ?)",
            (texto, fecha, hora)
        )
        conn.commit()
        conn.close()

        salida = f"  {CALENDARIO}  Recordatorio guardado:\n"
        salida += f"     \"{texto}\"\n"
        salida += f"     Fecha: {fecha}"
        if hora:
            salida += f" a las {hora}"
        return salida

    def _crear_alarma(self, command: str) -> str:
        import re
        match = re.search(r'(\d{1,2}):(\d{2})', command)
        if match:
            hora = f"{int(match.group(1)):02d}:{match.group(2)}"
            texto = "Alarma"
            match_txt = re.search(r'(?:alarma|despertador|para)\s*(.+)', command, re.IGNORECASE)
            if match_txt:
                texto = match_txt.group(1).strip()
            fecha = datetime.date.today().strftime("%Y-%m-%d")
            conn = sqlite3.connect(self.DB_PATH)
            conn.execute(
                "INSERT INTO recordatorios (texto, fecha, hora) VALUES (?, ?, ?)",
                (f"[t] {texto}", fecha, hora)
            )
            conn.commit()
            conn.close()
            return f"  {RELON}  Alarma configurada a las {hora}: {texto}"
        return "  ⚠️ Especifica la hora. Ej: alarma a las 07:00"

    def _listar_recordatorios(self) -> str:
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.execute("""
            SELECT id, texto, fecha, hora FROM recordatorios
            WHERE completado = 0
            ORDER BY fecha, hora
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"  {CALENDARIO}  No tienes recordatorios pendientes."

        salida = f"  {CALENDARIO}  RECORDATORIOS PENDIENTES\n"
        salida += "  ----------------------------------------\n"
        for rid, texto, fecha, hora in rows:
            hora_str = f" {hora}" if hora else ""
            salida += f"  [{rid}] {fecha}{hora_str} - {texto}\n"
        return salida

    def _borrar_recordatorio(self, command: str) -> str:
        import re
        match = re.search(r'(\d+)', command)
        if match:
            rid = int(match.group(1))
            conn = sqlite3.connect(self.DB_PATH)
            conn.execute("UPDATE recordatorios SET completado = 1 WHERE id = ?", (rid,))
            conn.commit()
            conn.close()
            return f"  Recordatorio #{rid} completado."
        return "  ⚠️ Especifica el nÃºmero del recordatorio. Ej: completar 3"

    def help(self) -> str:
        return (
            "RECORDATORIOS:\n"
            "  recordar <texto> [maÃ±ana] [a las HH:MM]\n"
            "  recordar <texto> en <N> minutos/horas\n"
            "  alarma a las HH:MM [texto]\n"
            "  lista recordatorios         - Muestra pendientes\n"
            "  completar <ID>              - Marca como hecho\n\n"
            "Ej: recordar comprar leche maÃ±ana a las 10:00\n"
            "    recuerdame llamar a Juan en 30 minutos\n"
            "    alarma a las 07:00 clase de yoga"
        )

