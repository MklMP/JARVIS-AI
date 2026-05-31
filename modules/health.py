"""
MÃ“DULO DE SALUD Y SMARTWATCH
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
ConexiÃ³n Bluetooth real con smartwatch vÃ­a BLE.
AnÃ¡lisis inteligente: pulso, sueÃ±o, pasos, estrÃ©s.
Consejos contextuales: "Te noto alterado, pongo mÃºsica relajante"
"""

import os
import sqlite3
import datetime
import random
import threading
import time
import json
from .base import ModuleBase
from utils.emoji import COMPUTADORA, GRAFICO, ADVERTENCIA, BATERIA


class HealthModule(ModuleBase):
    """
    Salud + Smartwatch:
    - BLE: escanea y conecta smartwatch real
    - Lee estÃ¡ndar GATT: pulso, baterÃ­a, pasos
    - Almacena en SQLite para tendencias
    - AnÃ¡lisis contextual con consejos
    """

    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "health.db")

    # UUIDs estÃ¡ndar BLE
    HR_SVC = "0000180d-0000-1000-8000-00805f9b34fb"
    HR_MEAS = "00002a37-0000-1000-8000-00805f9b34fb"
    BAT_SVC = "0000180f-0000-1000-8000-00805f9b34fb"
    BAT_LVL = "00002a19-0000-1000-8000-00805f9b34fb"
    DEV_INFO = "0000180a-0000-1000-8000-00805f9b34fb"

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self._init_db()
        self._ble = None
        self._smartwatch_conectado = None
        self._monitoreando = False
        self._ultima_lectura = {}
        self._usar_mock = True  # Mock hasta que se conecte un reloj real
        self._cargar_ultimos_datos()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS health_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pulso INTEGER, pasos INTEGER,
                sueno_horas REAL, sueno_calidad INTEGER,
                estres INTEGER, spo2 INTEGER, calorias INTEGER,
                fuente TEXT DEFAULT 'mock',
                notas TEXT
            )
        """)
        try:
            conn.execute("ALTER TABLE health_log ADD COLUMN fuente TEXT DEFAULT 'mock'")
        except sqlite3.OperationalError:
            pass  # columna ya existe
        conn.commit()
        conn.close()

    def _cargar_ultimos_datos(self):
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.execute("""
            SELECT pulso, pasos, sueno_horas, sueno_calidad, estres, spo2,
                   calorias, fuente, timestamp
            FROM health_log ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        if row:
            self._ultima_lectura = {
                "pulso": row[0], "pasos": row[1], "sueno_horas": row[2],
                "sueno_calidad": row[3], "estres": row[4], "spo2": row[5],
                "calorias": row[6], "fuente": row[7], "timestamp": row[8]
            }
            self._usar_mock = row[7] == "mock"
        else:
            self._generar_mock()

    def _generar_mock(self):
        ahora = datetime.datetime.now()
        h = ahora.hour
        pulso_base = 62 if h < 6 else (68 if h < 10 else 72)
        estres_base = 20 if h < 6 else (30 if h < 10 else 45)
        self._ultima_lectura = {
            "pulso": pulso_base + random.randint(-5, 8),
            "pasos": random.randint(2000, 8000),
            "sueno_horas": round(random.uniform(5.5, 8.5), 1),
            "sueno_calidad": random.randint(50, 95),
            "estres": estres_base + random.randint(-10, 15),
            "spo2": random.randint(96, 99),
            "calorias": random.randint(1500, 2500),
            "fuente": "mock",
            "timestamp": ahora.isoformat(),
        }
        self._guardar(self._ultima_lectura)

    def _guardar(self, d):
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("""
            INSERT INTO health_log (timestamp, pulso, pasos, sueno_horas,
                sueno_calidad, estres, spo2, calorias, fuente)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (d.get("timestamp", datetime.datetime.now().isoformat()),
              d.get("pulso"), d.get("pasos"), d.get("sueno_horas"),
              d.get("sueno_calidad"), d.get("estres"), d.get("spo2"),
              d.get("calorias"), d.get("fuente", "mock")))
        conn.commit()
        conn.close()

    def _historial(self, dias=7):
        limite = (datetime.datetime.now() - datetime.timedelta(days=dias)).isoformat()
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute("""
            SELECT pulso, pasos, sueno_horas, sueno_calidad, estres, spo2, timestamp, fuente
            FROM health_log WHERE timestamp > ? ORDER BY timestamp
        """, (limite,)).fetchall()
        conn.close()
        return rows

    # ================================================================
    # BLE - SMARTWATCH
    # ================================================================

    def _init_ble(self):
        if self._ble is None:
            try:
                from bleak import BleakScanner, BleakClient
                self._ble = {"scanner": BleakScanner, "client": BleakClient}
            except ImportError:
                self._ble = False

    def escanear_relojes(self) -> list:
        """Escanea dispositivos BLE cercanos y filtra posibles smartwatches."""
        self._init_ble()
        if not self._ble:
            return []

        try:
            dispositivos = []

            def callback(d, ad):
                nombre = d.name or ""
                if any(kw in nombre.lower() for kw in ["watch", "band", "fit", "mi", "huawei",
                                                        "samsung", "apple", "garmin", "polar",
                                                        "suunto", "coros", "amazfit", "zepp",
                                                        "da fit", "idw", "y8", "h9", "pro",
                                                        "smart", "health", "pulse"]):
                    dispositivos.append((d.name or "Desconocido", d.address, ad.rssi))

            # Escanear 5 segundos
            import asyncio
            async def scan():
                scanner = self._ble["scanner"]()
                scanner.register_detection_callback(callback)
                await scanner.start()
                await asyncio.sleep(5)
                await scanner.stop()

            asyncio.run(scan())
            return dispositivos

        except Exception as e:
            return [f"[Error BLE: {e}]"]

    def conectar_reloj(self, address: str) -> str:
        """Conecta a un smartwatch por direcciÃ³n MAC BLE."""
        self._init_ble()
        if not self._ble:
            return "BLE no disponible. Instala 'bleak': pip install bleak"

        try:
            import asyncio

            async def connect():
                client = self._ble["client"](address)
                await client.connect()
                if not client.is_connected:
                    return "No se pudo conectar. Â¿El reloj estÃ¡ encendido y cerca?"

                # Leer pulso
                datos = {"fuente": address, "timestamp": datetime.datetime.now().isoformat()}

                try:
                    hr_data = await client.read_gatt_char(self.HR_MEAS)
                    if hr_data:
                        datos["pulso"] = hr_data[0] if len(hr_data) == 1 else hr_data[1]
                except:
                    pass

                try:
                    bat = await client.read_gatt_char(self.BAT_LVL)
                    if bat:
                        datos["bateria_reloj"] = bat[0]
                except:
                    pass

                # Suscribirse a notificaciones de pulso en tiempo real
                hr_values = []

                def hr_callback(sender, data):
                    if data:
                        hr_values.append(data[0] if len(data) == 1 else data[1])

                try:
                    await client.start_notify(self.HR_MEAS, hr_callback)
                    await asyncio.sleep(10)  # Leer por 10 segundos
                    await client.stop_notify(self.HR_MEAS)
                except:
                    pass

                if hr_values:
                    datos["pulso"] = sum(hr_values) // len(hr_values)

                await client.disconnect()

                if datos.get("pulso"):
                    self._ultima_lectura = datos
                    self._usar_mock = False
                    self._guardar(datos)
                    return f"Conectado. Pulso: {datos['pulso']} bpm" + \
                           (f" | BaterÃ­a reloj: {datos.get('bateria_reloj')}%" if datos.get("bateria_reloj") else "")
                return "Conectado pero no se recibieron datos de pulso."

            return asyncio.run(connect())

        except Exception as e:
            return f"Error conectando: {e}"

    # ================================================================
    # COMANDOS
    # ================================================================

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["escanear", "scan", "buscar reloj", "smartwatch", "bluetooth"]):
            return self._cmd_escanear()
        elif any(p in cmd for p in ["conectar", "connect", "vincular", "pair", "enlazar"]):
            return self._cmd_conectar(command)
        elif any(p in cmd for p in ["salud", "pulso", "heart", "panel"]):
            return self._panel()
        elif any(p in cmd for p in ["tendencia", "trend", "historial", "semana"]):
            return self._tendencias()
        elif any(p in cmd for p in ["consejo", "tip", "recomienda", "sugiere"]):
            return self._consejo()
        elif any(p in cmd for p in ["estres", "stress", "ansiedad", "alterado", "nervios"]):
            return self._analizar_estado()
        elif any(p in cmd for p in ["sueno", "sueÃ±o", "sleep", "dormir"]):
            return self._analizar_sueno()
        else:
            return self.help()

    def _cmd_escanear(self) -> str:
        self._init_ble()
        if not self._ble:
            return ("⚠️ Biblioteca BLE no disponible.\n"
                    "  InstÃ¡lala: pip install bleak\n"
                    "  Luego podrÃ¡s escanear smartwatches cercanos.")

        try:
            dispositivos = self.escanear_relojes()
            if not dispositivos:
                return ("  Escaneo completado. No se encontraron smartwatches.\n"
                        "  AsegÃºrate de que el reloj estÃ© encendido, cerca y en modo pairing.")

            salida = f"  [t] SMARTWATCHES DETECTADOS:\n  --------------------------\n"
            for i, (nombre, mac, rssi) in enumerate(dispositivos, 1):
                salida += f"  {i}. {nombre}\n     {mac} (seÃ±al: {rssi})\n"
            salida += "\n  Para conectar: conectar <nÃºmero>"
            return salida

        except Exception as e:
            return f"⚠️ Error escaneando: {e}"

    def _cmd_conectar(self, command: str) -> str:
        import re
        # Buscar MAC address o nÃºmero de la lista
        match_mac = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', command)
        match_num = re.search(r'(\d+)', command)

        if match_mac:
            return self.conectar_reloj(match_mac.group(0))
        elif match_num:
            idx = int(match_num.group(1)) - 1
            dispositivos = self.escanear_relojes()
            if 0 <= idx < len(dispositivos):
                return self.conectar_reloj(dispositivos[idx][1])
            return f"NÃºmero invÃ¡lido. Solo {len(dispositivos)} dispositivos encontrados."

        return ("  Â¿A quÃ© reloj conectarme?\n"
                "  Primero escanea: escanear\n"
                "  Luego: conectar <nÃºmero>")

    def _panel(self) -> str:
        d = self._ultima_lectura
        fuente = d.get("fuente", "mock")
        tag = " (MOCK - datos simulados)" if self._usar_mock else f" ({fuente[:12]}...)"
        if self._smartwatch_conectado:
            tag = f" ({self._smartwatch_conectado})"

        salida = f"  {COMPUTADORA}  PANEL DE SALUD{tag}\n"
        salida += "  ----------------------------------------\n"
        salida += f"  Pulso:       {d.get('pulso', '--')} bpm\n"
        salida += f"  SpO2:        {d.get('spo2', '--')}%\n"
        salida += f"  Pasos:       {d.get('pasos', 0):,}\n"
        salida += f"  Calorias:    {d.get('calorias', '--')}\n"
        salida += f"  Sueno:       {d.get('sueno_horas', '--')}h (calidad: {d.get('sueno_calidad', '--')}%)\n"
        salida += f"  Estres:      {d.get('estres', '--')}%\n"
        if d.get("bateria_reloj"):
            salida += f"  {BATERIA} Reloj:      {d['bateria_reloj']}%\n"
        salida += f"\n  {self._analisis_rapido()}\n"
        if self._usar_mock:
            salida += "\n  ⚠️ Datos simulados. Di 'escanear' para conectar tu smartwatch real."
        return salida

    def _analisis_rapido(self) -> str:
        d = self._ultima_lectura
        p = d.get("pulso", 70)
        e = d.get("estres", 30)
        s = d.get("sueno_horas", 7)
        sc = d.get("sueno_calidad", 70)
        pasos = d.get("pasos", 0)
        problemas = []
        if p > 85: problemas.append("pulso elevado")
        if e > 60: problemas.append("estres alto")
        if s < 6: problemas.append("pocas horas de sueno")
        if sc < 50: problemas.append("mala calidad de sueno")
        if pasos < 3000: problemas.append("poca actividad")
        if not problemas:
            return "✅ Todo en equilibrio."
        return f"⚠️ {' â€¢ '.join(problemas)}. Di 'consejo' para sugerencias."

    def _tendencias(self) -> str:
        h = self._historial(7)
        if len(h) < 2:
            return "No hay suficientes datos aun."

        def prom(v):
            return sum(v) / len(v) if v else 0

        def trend(v):
            if len(v) < 3: return "estable"
            m = len(v) // 2
            return "â†‘ al alza" if prom(v[m:]) - prom(v[:m]) > 5 else \
                   "â†“ a la baja" if prom(v[:m]) - prom(v[m:]) > 5 else "â†’ estable"

        pulsos = [r[0] for r in h if r[0]]
        pasos_l = [r[1] for r in h if r[1]]
        suenos = [r[2] for r in h if r[2]]
        estres_l = [r[4] for r in h if r[4] is not None]

        s = f"  {GRAFICO}  TENDENCIAS (7 dias)\n  --------------------------\n"
        s += f"  Pulso:  {prom(pulsos):.0f} bpm {trend(pulsos)}\n"
        s += f"  Pasos:  {prom(pasos_l):.0f} {trend(pasos_l)}\n"
        s += f"  Sueno:  {prom(suenos):.1f}h {trend(suenos)}\n"
        s += f"  Estres: {prom(estres_l):.0f}% {trend(estres_l)}\n"

        if prom(estres_l) > 60:
            s += "\n  [i] Estres alto ultimamente. Â¿Musica relajante?"
        if prom(suenos) < 6:
            s += "\n  [i] Duermes poco. Â¿Activo modo relax?"
        if prom(pasos_l) < 4000:
            s += "\n  [i] Sedentario. Â¿Te recuerdo moverte?"
        return s

    def _analizar_estado(self) -> str:
        d = self._ultima_lectura
        p = d.get("pulso", 70)
        e = d.get("estres", 30)
        if e > 65 or p > 90:
            return (f"  {ADVERTENCIA} Te noto alterado.\n"
                    f"  Pulso: {p} bpm | Estres: {e}%\n\n"
                    f"  [i] Recomiendo:\n"
                    f"     â€¢ Respirar profundo 10 veces\n"
                    f"     â€¢ Poner musica relajante (di: 'musica relajante')\n"
                    f"     â€¢ Tomar un te o agua tranquilo\n"
                    f"     â€¢ Dar un paseo de 5 min\n"
                    f"  Â¿Quieres que ponga musica?")
        elif e > 45:
            return f"  Estres moderado ({e}%). Podrias relajarte un poco."
        return f"  Tranquilo. Pulso: {p} bpm | Estres: {e}%"

    def _analizar_sueno(self) -> str:
        d = self._ultima_lectura
        h = d.get("sueno_horas", 7)
        c = d.get("sueno_calidad", 70)
        s = f"  ANALISIS DE SUENO\n  --------------------------\n  Duracion: {h}h\n  Calidad:  {c}%\n\n"
        if h < 5.5:
            s += "[R] Muy poco sueno. Afecta tu salud.\n   â€¢ Acuestate 30 min antes\n   â€¢ Evita pantallas 1h antes"
        elif h < 7:
            s += "[Y] Podrias dormir mas. Ideal 7-9h.\n"
            if c < 60:
                s += "   â€¢ Prueba musica para dormir."
        else:
            s += "[G] Buen descanso.\n"
            if c < 70:
                s += "   â€¢ La calidad podria mejorar."
        return s

    def _consejo(self) -> str:
        d = self._ultima_lectura
        p = d.get("pulso", 70)
        e = d.get("estres", 30)
        s = d.get("sueno_horas", 7)
        pasos = d.get("pasos", 0)
        ahora = datetime.datetime.now()
        h = ahora.hour

        consejos = []
        if 6 <= h < 9:
            consejos.append("Buenos dias! Desayunaste bien?")
        elif 12 <= h < 14:
            consejos.append("Hora de comer. Algo ligero si tienes tarde ocupada.")
        elif 18 <= h < 20:
            consejos.append("Buena hora para una caminata.")
        elif h >= 21 or h < 5:
            consejos.append("Preparate para dormir.")

        if e > 65:
            consejos.append("Estres alto. 5 min de meditacion?")
            consejos.append("Puedo poner musica relajante")
        if s < 6:
            consejos.append("Dormiste poco. Hoy con calma.")
        if pasos < 2000:
            consejos.append("No has caminado mucho. 15 min de paseo?")
        elif pasos > 8000:
            consejos.append("Buen trabajo con los pasos hoy!")
        if p > 85:
            consejos.append("Pulso elevado. Bebe agua, tal vez mucho cafe.")

        random.shuffle(consejos)
        salida = f"  {GRAFICO}  CONSEJO DEL MOMENTO\n  --------------------------\n"
        for c in consejos[:3]:
            salida += f"  â€¢ {c}\n"
        if self._usar_mock:
            salida += "\n⚠️ Datos simulados. Conecta tu smartwatch con 'escanear'"
        return salida

    def help(self) -> str:
        return (
            "SALUD Y SMARTWATCH:\n"
            "  salud              - Panel de salud\n"
            "  escanear           - Busca smartwatches BLE cerca\n"
            "  conectar <num/mac> - Conecta smartwatch\n"
            "  tendencias         - Evolucion semanal\n"
            "  consejo            - Sugerencia inteligente\n"
            "  estres             - Analisis emocional\n"
            "  sueno              - Analisis de descanso\n\n"
            "  Compatible con cualquier smartwatch BLE\n"
            "  (estandar GATT Heart Rate)\n\n"
            "  Ej: escanear\n"
            "      conectar 1\n"
            "      consejo"
        )

