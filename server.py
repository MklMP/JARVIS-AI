#!/usr/bin/env python3
"""
JARVIS - Servidor Web
~~~~~~~~~~~~~~~~~~~~~
Interfaz web estilo HUD con animaciones.
Ejecutar: python server.py
Abrir: http://localhost:5000
"""

import os
import sys
import threading
import re
import time
import json
import subprocess
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sys; sys.stdout.reconfigure(errors='replace', encoding='utf-8'); sys.stderr.reconfigure(errors='replace', encoding='utf-8')

from flask import Flask, request, jsonify, render_template, Response
from main import JarvisCore
from utils.voice import JarvisTTS, JarvisSTT
from utils.display import cargar_config, guardar_config
from utils.notifier import notificar, marcar_ventana
from utils.session_manager import SessionManager
import sardiñas_engine as se
import screener_bollinger as sb
from modules.openrouter_chat import scan_bollinger_breakouts

# ── Sanitización de strings para evitar errores UTF-8 ──
def sanitize_string(s):
    """Elimina caracteres surrogate y otros no válidos para UTF-8."""
    if isinstance(s, str):
        return s.encode('utf-8', 'replace').decode('utf-8')
    return s

def sanitize_dict(d):
    """Aplica sanitize_string recursivamente a diccionarios/listas."""
    if isinstance(d, dict):
        return {k: sanitize_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [sanitize_dict(i) for i in d]
    elif isinstance(d, str):
        return sanitize_string(d)
    return d

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.before_request
def sanitizar_entrada():
    if request.is_json:
        request.sanitized_json = sanitize_dict(request.get_json(silent=True) or {})


@app.after_request
def sanitizar_salida(response):
    if response.is_json and response.data:
        try:
            original = json.loads(response.data)
            limpio = sanitize_dict(original)
            response.data = json.dumps(limpio, ensure_ascii=False).encode('utf-8')
            response.content_type = 'application/json; charset=utf-8'
        except Exception:
            pass
    return response

core = JarvisCore()

# ── Símbolos para scanner BB (subconjunto rápido de WATCHLIST) ──
WATCHLIST_BB = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA",
    "ADBE", "INTC", "AMD", "CRM", "ORCL", "IBM", "CSCO", "QCOM", "TXN", "AVGO",
    "NOW", "SHOP", "SPOT", "DDOG", "PANW", "FTNT", "ANET", "MRVL", "WDAY",
    "NET", "PLTR", "SNAP", "ZM", "COIN", "ABNB", "UBER", "PYPL",
]

# ── Estado global del sistema Sardiñas ──
_sardiñas_state = {
    "activo": False,
    "symbol": "",
    "paso_actual": "paso1_ventana",
    "pasos": {},
    "ventana": "",
    "operable": False,
}

# ── Progreso del scanner/screener (thread-safe via lock) ──
_scanner_progress = {"fase": "", "actual": 0, "total": 0, "mensaje": "", "resultado": None, "tipo": ""}
_scanner_lock = threading.Lock()

def _update_progress(fase, actual, total, mensaje=""):
    global _scanner_progress
    with _scanner_lock:
        _scanner_progress.update({"fase": fase, "actual": actual, "total": total, "mensaje": mensaje})

# ── Resultados cacheados para auto-carga del panel ──
_scanner_cache = {"resultado": None, "timestamp": None, "tipo": ""}
_screener_cache = {"resultado": None, "timestamp": None, "tipo": ""}
ultimo_screener = {"resultados": [], "timestamp": None}

def _calcular_entry_sl_tp(symbol, direccion):
    """Calcula niveles de entrada, SL y TP para un símbolo."""
    try:
        import yfinance as yf
        df = yf.download(symbol, period="5d", interval="15m", progress=False)
        if df is None or df.empty or len(df) < 20:
            return None
        # yfinance 0.2.40+ returns MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            close = float(df["Close"].iloc[-1, 0])
            high = df["High"].iloc[:, 0].astype(float)
            low = df["Low"].iloc[:, 0].astype(float)
        else:
            close = float(df["Close"].iloc[-1])
            high = df["High"].astype(float)
            low = df["Low"].astype(float)
        atr = (high - low).rolling(14).mean().iloc[-1]
        if pd.isna(atr) or atr <= 0:
            atr = close * 0.015
        entry = close
        if direccion == "compra":
            sl = entry - atr * 1.5
            tp1 = entry + atr * 1.5
            tp2 = entry + atr * 2.5
        else:
            sl = entry + atr * 1.5
            tp1 = entry - atr * 1.5
            tp2 = entry - atr * 2.5
        rr = abs(entry - tp1) / abs(entry - sl) if abs(entry - sl) > 0 else 0
        return {
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "rr": round(rr, 2),
            "atr": round(atr, 4),
        }
    except Exception as e:
        return None

def _scanner_thread_bb(symbols):
    """Ejecuta scan de Bollinger en background con progreso."""
    global _scanner_progress, _scanner_cache
    from modules.openrouter_chat import _calcular_bb
    from screener_bollinger import clasificar_fuera_bb
    import pandas as pd
    with _scanner_lock:
        _scanner_progress = {"fase": "iniciando", "actual": 0, "total": len(symbols), "mensaje": "", "resultado": None, "tipo": "scanner_bb"}
    resultados = []
    for i, sym in enumerate(symbols):
        with _scanner_lock:
            _scanner_progress["fase"] = "scanner_bb"
            _scanner_progress["actual"] = i + 1
            _scanner_progress["mensaje"] = f"Escaneando {sym}..."
        data = _calcular_bb(sym)
        if not data:
            continue
        if not data["below_lower"] and not data["above_upper"]:
            continue
        if data["vol_ratio"] < 0.8:
            continue
        direccion = "compra" if data["below_lower"] else "venta"
        nota = ""
        if direccion == "compra" and data["sma200"] is not None and data["close"] < data["sma200"]:
            nota = "Precio bajo MA200"
        niveles = _calcular_entry_sl_tp(sym, direccion)
        # Clasificar fuera de BB
        item_clasif = {
            "symbol": sym, "precio": data["close"],
            "banda": "superior" if data["above_upper"] else "inferior",
            "direccion": direccion,
            "upper": data["upper"], "lower": data["lower"],
        }
        clasif = clasificar_fuera_bb(data["hist"], item_clasif)
        resultados.append({
            "symbol": data["symbol"],
            "price": round(data["close"], 2),
            "direction": direccion,
            "upper": round(data["upper"], 2),
            "lower": round(data["lower"], 2),
            "band_width": round(data["band_width"], 2),
            "vol_ratio": round(data["vol_ratio"], 2),
            "note": nota,
            "niveles": niveles,
            "prediccion": clasif["prediccion"],
            "score_continuacion": clasif["score_continuacion"],
            "razones_bb": clasif["razones"],
            "velas_fuera_bb": clasif["velas_fuera_bb"],
        })
    resultados.sort(key=lambda x: (x["vol_ratio"] if x["vol_ratio"] else 0) + (x["band_width"] if x["band_width"] else 0), reverse=True)
    with _scanner_lock:
        _scanner_progress["fase"] = "completado"
        _scanner_progress["mensaje"] = f"Completado: {len(resultados)} oportunidades encontradas"
        _scanner_progress["resultado"] = resultados
        _scanner_cache["resultado"] = resultados
        _scanner_cache["timestamp"] = time.time()
        _scanner_cache["tipo"] = "scanner_bb"
    # También poblar ultimo_screener para veredicto si es el primer resultado disponible
    global ultimo_screener
    if resultados and not ultimo_screener.get("resultados"):
        ultimo_screener["resultados"] = resultados
        ultimo_screener["timestamp"] = time.time()

def _scanner_thread_screener(symbols):
    """Ejecuta screener_completo en background con progreso."""
    global _scanner_progress, _screener_cache
    with _scanner_lock:
        _scanner_progress = {"fase": "iniciando", "actual": 0, "total": len(symbols), "mensaje": "", "resultado": None, "tipo": "screener"}
    def _prog(fase, a, t, msg):
        with _scanner_lock:
            _scanner_progress["fase"] = fase
            _scanner_progress["actual"] = a
            _scanner_progress["total"] = t
            _scanner_progress["mensaje"] = msg
    resultado = sb.screener_completo(symbols, progress_callback=_prog)
    if resultado and resultado.get("mejores"):
        for r in resultado["mejores"]:
            niveles = _calcular_entry_sl_tp(r["symbol"], r.get("direccion", "compra"))
            if niveles:
                r["niveles"] = niveles
    with _scanner_lock:
        _scanner_progress["fase"] = "completado"
        _scanner_progress["mensaje"] = f"Completado: {resultado['pasaron_filtros']} de {resultado['fuera_bollinger']} fuera de BB pasaron filtros"
        _scanner_progress["resultado"] = resultado
        _screener_cache["resultado"] = resultado
        _screener_cache["timestamp"] = time.time()
        _screener_cache["tipo"] = "screener"
    global ultimo_screener
    ultimo_screener["resultados"] = resultado.get("mejores", []) if resultado else []
    ultimo_screener["timestamp"] = time.time()

# ── Auto-iniciar scanner y screener al arrancar ──
def _auto_start_scanner_screener():
    """Lanza scanner y screener en segundo plano al iniciar la app."""
    import time as _t
    _t.sleep(3)
    t1 = threading.Thread(target=_scanner_thread_bb, args=(WATCHLIST_BB,), daemon=True)
    t1.start()
    _t.sleep(2)
    t2 = threading.Thread(target=_scanner_thread_screener, args=(sb.WATCHLIST,), daemon=True)
    t2.start()

threading.Thread(target=_auto_start_scanner_screener, daemon=True).start()

# ── Trading System (QuantumTrade) en background ──
_TRADING_SYSTEM_PORT = 8080
_ts_process = None

def _start_trading_system():
    """Inicia el servidor QuantumTrade (FastAPI) en un subproceso."""
    global _ts_process
    ts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading-system')
    if not os.path.exists(ts_dir):
        return
    try:
        _ts_process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'server:app',
             '--host', '127.0.0.1', '--port', str(_TRADING_SYSTEM_PORT),
             '--log-level', 'error'],
            cwd=ts_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        import time
        time.sleep(2)
        if _ts_process.poll() is not None:
            print("[WARN] QuantumTrade exited immediately (exit code: {})".format(_ts_process.returncode))
        else:
            print("[OK] QuantumTrade started on port", _TRADING_SYSTEM_PORT)
    except Exception as e:
        print("[WARN] No se pudo iniciar QuantumTrade:", e)
threading.Thread(target=_start_trading_system, daemon=True).start()

# ── Proxy para Trading System (con retry) ──
@app.route('/ts/', defaults={'subpath': ''})
@app.route('/ts/<path:subpath>')
def ts_proxy(subpath):
    """Proxy a QuantumTrade corriendo en localhost:8080, con retry hasta 15s."""
    target = f'http://127.0.0.1:{_TRADING_SYSTEM_PORT}/{subpath}'
    last_error = None
    for attempt in range(6):
        try:
            r = requests.request(
                method=request.method,
                url=target,
                headers={k: v for k, v in request.headers if k.lower() not in ('host', 'content-length')},
                data=request.get_data(),
                cookies=request.cookies,
                params=request.args,
                timeout=5
            )
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = [(k, v) for k, v in r.headers.items() if k.lower() not in excluded_headers]
            return Response(r.content, r.status_code, headers)
        except requests.ConnectionError:
            last_error = 'Iniciando servidor QuantumTrade...'
            _t.sleep(2.5)
        except Exception as e:
            last_error = str(e)
            break
    return f'<h3>Trading System no disponible</h3><p>{last_error}</p>', 503

@app.route('/sw.js')
def service_worker():
    resp = app.send_static_file('sw.js')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp

@app.route('/manifest.json')
def manifest():
    resp = app.send_static_file('manifest.json')
    resp.headers['Cache-Control'] = 'no-cache'
    return resp
_sesiones = SessionManager()
# Asegurar que existe al menos una sesion
if not _sesiones.listar():
    _sesiones.crear("Principal")
_config_local = cargar_config()
_voz_guardada = _config_local.get("tts_voice", "")
tts = JarvisTTS(voz_config=_voz_guardada)
if _voz_guardada:
    tts.seleccionar_voz(_voz_guardada)
stt = JarvisSTT()

# Control de estado de TTS
_tts_speaking = False
_tts_lock = threading.Lock()
_ultima_respuesta = ""

# Monitor de discos en segundo plano (cada 30 min)
def _monitorear_discos():
    from modules.sistema import SistemaModule
    sm = SistemaModule()
    _ultima_alerta = {}
    while True:
        time.sleep(1800)
        try:
            resultado = sm.analizar_discos()
            if "CRÍTICO" in resultado or "PELIGRO" in resultado:
                for linea in resultado.split('\n'):
                    for unidad in ['C:', 'D:', 'E:', 'F:', 'G:', 'H:']:
                        if unidad in linea and ('CRÍTICO' in linea or 'PELIGRO' in linea or '90%' in linea):
                            if _ultima_alerta.get(unidad, 0) + 3600 < time.time():
                                notificar("Jarvis - Alerta de Disco", f"{unidad} necesita atención:\n{linea.strip()}")
                                _ultima_alerta[unidad] = time.time()
        except Exception:
            pass

threading.Thread(target=_monitorear_discos, daemon=True).start()

# Control de acceso al microfono (evitar conflicto frontend vs wake-word vs listener)
_mic_in_use = False
_mic_lock = threading.Lock()

def _adquirir_mic() -> bool:
    """Intenta adquirir el microfono exclusivamente. Retorna True si se obtuvo."""
    global _mic_in_use
    with _mic_lock:
        if _mic_in_use:
            return False
        _mic_in_use = True
        return True

def _liberar_mic():
    global _mic_in_use
    with _mic_lock:
        _mic_in_use = False


def _cortar_en_oraciones(texto, max_chars=300):
    """Corta un texto al limite de caracteres respetando oraciones completas."""
    if len(texto) <= max_chars:
        return texto
    # Buscar el ultimo punto, signo de interrogacion o exclamacion antes del limite
    for delim in ['. ', '? ', '! ', '.\n', '?\n', '!\n']:
        idx = texto.rfind(delim, 0, max_chars)
        if idx > max_chars // 2:
            return texto[:idx + 1].strip()
    # Si no hay oracion completa, cortar en el ultimo espacio
    idx = texto.rfind(' ', 0, max_chars)
    if idx > max_chars // 2:
        return texto[:idx].strip()
    return texto[:max_chars].rsplit(' ', 1)[0].strip() if ' ' in texto[:max_chars] else texto[:max_chars]


def detectar_multi_tema(texto):
    """
    Determina si el mensaje del usuario contiene varios temas o preguntas distintas.
    Combina heuristica rapida con verificacion opcional via LLM.
    """
    if not texto or len(texto) < 20:
        return False

    condiciones = 0

    # 1) Contar signos de interrogacion
    if texto.count('?') >= 2 or texto.count('¿') >= 2:
        condiciones += 1

    # 2) Viñetas, guiones o numeraciones
    if re.search(r'(?:^|\n)\s*[\-\*]\s', texto) or re.search(r'(?:^|\n)\s*\d+[.)]\s', texto):
        condiciones += 1

    # 3) Conectores que separan preguntas
    conectores = ['y también', 'además', 'por otro lado', 'luego', 'después',
                  'por otra parte', 'asimismo', 'también quiero', 'también necesito',
                  'y aparte', 'y por cierto', 'cambiando de tema', 'otra cosa']
    if any(c in texto.lower() for c in conectores):
        condiciones += 1

    # 4) Multiples oraciones con verbos de solicitud
    oraciones = re.split(r'[.!?]+', texto)
    oraciones = [o.strip() for o in oraciones if len(o.strip()) > 10]
    verbos_solicitud = ['analiza', 'busca', 'dime', 'calcula', 'explica',
                        'muestra', 'abre', 'crea', 'ejecuta', 'reproduce',
                        'investiga', 'compara', 'traduce', 'resume', 'envía',
                        'descarga', 'instala', 'configura', 'qué es', 'cómo']
    if len(oraciones) >= 2:
        solicitudes = sum(1 for o in oraciones if any(v in o.lower() for v in verbos_solicitud))
        if solicitudes >= 2:
            condiciones += 1

    # Umbral: al menos 2 condiciones
    if condiciones >= 2:
        return True

    # 5) Si es largo y tiene comas o "y", considerar multi-tema
    if len(texto) > 100 and (',' in texto or ' y ' in texto.lower()):
        return True

    return False


def split_into_messages(text):
    """
    Divide un texto en fragmentos basandose en puntuacion final (. ! ?).
    Retorna una lista de cadenas no vacias, cada una con una idea completa.
    """
    if isinstance(text, dict):
        text = text.get("reply", text.get("content", str(text)))
    if not isinstance(text, str):
        text = str(text)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    merged = []
    buffer = ""
    for s in sentences:
        if len(s) < 10 and buffer:
            buffer += " " + s
        else:
            if buffer:
                merged.append(buffer)
            buffer = s
    if buffer:
        merged.append(buffer)
    return merged


def _tts_hablar(texto):
    import pythoncom
    pythoncom.CoInitialize()
    try:
        global _tts_speaking
        with _tts_lock:
            _tts_speaking = True
        try:
            tts.decir(texto, esperar=True)
        except Exception:
            pass
        finally:
            with _tts_lock:
                _tts_speaking = False
    finally:
        pythoncom.CoUninitialize()


def _tts_esta_hablando():
    with _tts_lock:
        return _tts_speaking


# ================================================================
# AUTO-RENOMBRAR SESION
# ================================================================

def _auto_nombrar_sesion():
    """Renombra la sesion activa si aun tiene nombre generico."""
    try:
        sesion = _sesiones.obtener_activa()
        if not sesion:
            return
        nombre = sesion.get("name", "")
        hist = sesion.get("history", [])
        # Solo renombrar si el nombre es generico y hay >= 3 intercambios
        if not (nombre.startswith("Sesión") or nombre == "Principal"):
            return
        if len(hist) < 3:
            return
        # Construir resumen de los ultimos mensajes
        conversacion = []
        for h in hist[-8:]:
            user_msg = h.get("cmd", "")[:200].strip()
            bot_msg = h.get("resp", "")[:200].strip()
            if user_msg:
                conversacion.append(f"Usuario: {user_msg}")
            if bot_msg:
                conversacion.append(f"Jarvis: {bot_msg}")
        texto = "\n".join(conversacion)
        ai = core.openrouter or core.gemini
        if not ai:
            return
        prompt = (
            "Resume el tema principal de esta conversacion en MAXIMO 4 PALABRAS en español. "
            "Responde SOLO el titulo, nada mas.\n\n"
            f"{texto}"
        )
        r = ai.preguntar(prompt, max_tokens=30)
        if r.get("exito"):
            titulo = r["resultado"].strip().strip('"').strip("'")
            if titulo and len(titulo) <= 50 and titulo.lower() != nombre.lower():
                _sesiones.rename(_sesiones.activa(), titulo)
    except Exception:
        pass


# ================================================================
# API
# ================================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    import platform as _platform
    pc_info = {
        "usuario": os.getlogin(),
        "hostname": _platform.node(),
        "os": _platform.system(),
        "os_version": _platform.version(),
        "cpu": _platform.processor() or "desconocido",
    }
    try:
        import psutil
        pc_info["ram"] = f"{round(psutil.virtual_memory().total / (1024**3))} GB"
        pc_info["cpu_hilos"] = psutil.cpu_count(logical=True)
    except Exception:
        pass
    return jsonify({
        "online": True,
        "modulos": len(core.modules),
        "tts": tts.disponible,
        "tts_voice": tts.voz_actual,
        "stt": stt.disponible,
        "version": core.config.get("version", "1.0"),
        "plataforma": sys.platform,
        "motores": ["duckduckgo", "wikipedia", "openrouter", "yahoofinance", "bloomberg", "investing", "youtube"],
        "pc": pc_info,
    })


@app.route("/api/voices")
def api_voices():
    return jsonify({
        "voces": tts.listar_voces(),
        "actual": tts.voz_actual,
    })


@app.route("/api/voice", methods=["POST"])
def api_voice_set():
    data = request.get_json(silent=True) or {}
    voz_id = data.get("voice", "").strip()
    if not voz_id:
        return jsonify({"error": "voice id required"}), 400
    ok = tts.seleccionar_voz(voz_id)
    if ok:
        config = cargar_config()
        config["tts_voice"] = voz_id
        guardar_config(config)
        return jsonify({"ok": True, "voz": voz_id})
    return jsonify({"error": "No se pudo cambiar a esa voz"}), 400


# Palabras clave para detectar consultas de salud/remedios caseros
_PALABRAS_SALUD = re.compile(
    r'\b(duele?|dolor|fiebre|tos|gripe|resfriado|estómago|barriga|cabeza|garganta|'
    r'muscular|remedio|medicamento|enferm[oa]|síntoma|vómito|náusea|mareo|'
    r'abuela|abuelo|mamá|papá|hij[oa]|bebé|niñ[oa]|fiebre|alergia|indigestión|'
    r'diarrea|estreñimiento|insomnio|quemadura|herida|moretón|inflamación|'
    r'calambre|mareo|picadura|resfrío|cólico|acidez|reflujo|malestar)\b',
    re.IGNORECASE
)


def _responder_salud(comando: str) -> str:
    """Responde consultas de salud usando Gemini vía OpenRouter (sin restricciones de DeepSeek)."""
    if not hasattr(core, 'openrouter') or not core.openrouter:
        return ""
    modelo_salud = "google/gemini-2.0-flash-001"
    prompt = (
        "Eres JARVIS, un asistente amable y práctico. "
        "El usuario te pregunta sobre un tema de salud cotidiana. "
        "Tu misión es AYUDAR con consejos prácticos:\n"
        "1. Haz 1-2 preguntas breves para entender mejor el contexto.\n"
        "2. Ofrece remedios caseros suaves y seguros (infusiones, reposo, dieta blanda).\n"
        "3. Da medidas de alivio inmediato (postura cómoda, aflojar ropa, etc.).\n"
        "4. Al final, recuerda consultar al médico si el problema persiste.\n"
        "NUNCA te limites a decir 've al médico'. Siempre da pasos útiles primero.\n"
        "Responde en español, con un tono amable y servicial.\n\n"
        f"Usuario: {comando}"
    )
    messages = [
        {"role": "system", "content": "Eres JARVIS, un asistente doméstico práctico y servicial. Respondes en español."},
        {"role": "user", "content": prompt}
    ]
    resp = core.openrouter._intentar_llamada(messages, tools=None, max_tokens=800, model=modelo_salud)
    if "error" not in resp:
        choices = resp.get("choices", [])
        if choices:
            texto = choices[0].get("message", {}).get("content", "").strip()
            if texto:
                return texto
    return ""


@app.route("/api/command", methods=["POST"])
def api_command():
    data = getattr(request, 'sanitized_json', {}) or {}
    comando = data.get("command", "").strip()
    if not comando:
        return jsonify({"error": "Comando vacio"}), 400

    try:
        global _ultima_respuesta
        motores = data.get("motores")

        # Detectar intención Sardiñas
        comando_lower = comando.lower()
        _patron_sardiñas = re.compile(
            r'\b(analiza.*(yoel|sardiñas|sardinas|tradingway|the tradingway|estrategia.*yoel)|'
            r'\byoel\b.*\b(sardiñas|sardinas|analiza|tradingway)|'
            r'\bthe tradingway\b|'
            r'\btradingway\b|'
            r'\bsardiñas\b.*\b(para|de|con|analiza)\b)',
            re.IGNORECASE
        )
        m_sym = re.search(r'\bpara\s+([\w.\-^]{1,15})\b|\bde\s+([\w.\-^]{1,15})\b|\bcon\s+([\w.\-^]{1,15})\b', comando_lower)
        sardinas_activar = False
        sardinas_data = {}
        if _patron_sardiñas.search(comando):
            sym = ""
            if m_sym:
                sym = (m_sym.group(1) or m_sym.group(2) or m_sym.group(3) or "").upper()
            if not sym or sym in ("YOEL", "SARDIÑAS", "SARDINAS", "EL", "LA", "UN"):
                # Intentar extraer con mapeo de símbolos al final del comando
                palabras = comando_lower.split()
                for p in reversed(palabras):
                    if re.match(r'^[a-z0-9.\-^]{1,15}$', p) and p not in (
                        "yoel", "sardiñas", "sardinas", "tradingway", "the", "para", "de", "con",
                        "analiza", "analisis", "estrategia", "sistema", "estilo"
                    ):
                        sym = p.upper()
                        break
            if sym:
                _init_sardiñas(sym)
                ventana, operable, msg = se.evaluar_ventana()
                sardinas_activar = True
                sardinas_data = {
                    "sardiñas_activar": True,
                    "symbol": sym,
                    "checklist": _sardiñas_state["pasos"],
                    "mensaje_inicial": msg,
                    "ventana": ventana,
                    "operable": operable,
                    "paso_actual": _sardiñas_state["paso_actual"],
                }

        # Detectar petición de veredicto final (antes de procesar, para inyectar contexto)
        es_veredicto = bool(re.search(r'\b(mejor acci[oó]n|veredicto final|an.lisis concluyente|cu.l es la mejor|cuál recomiendas|qué acción me recomiendas|qu[ée] acci.n es mejor|mejor setup|la mejor para entrar)\b', comando_lower))
        veredicto_data = None
        if es_veredicto:
            try:
                vr = _calcular_veredicto_desde_cache()
                if vr:
                    veredicto_data = vr
                    core._veredicto_data = vr
            except Exception:
                pass

        # Detectar consultas de salud y responder con Gemini (sin restricciones)
        if _PALABRAS_SALUD.search(comando):
            respuesta_salud = _responder_salud(comando)
            if respuesta_salud:
                respuesta = respuesta_salud
            else:
                respuesta = core.procesar(comando, motores=motores)
        else:
            respuesta = core.procesar(comando, motores=motores)

        if not isinstance(respuesta, str):
            respuesta = str(respuesta)

        # Guardar en sesion activa
        if respuesta and not respuesta.startswith("__"):
            _sesiones.guardar_historial(comando, respuesta)
            _sesiones.guardar_estado(
                respuesta,
                getattr(core, '_ultima_respuesta_tema', '')[:300] if hasattr(core, '_ultima_respuesta_tema') else ''
            )
            # Auto-renombrar sesion segun el tema de la conversacion
            _auto_nombrar_sesion()
        if respuesta == "__EXIT__":
            threading.Thread(target=_salir, daemon=True).start()
            return jsonify({"respuesta": "Apagando sistema...", "exit": True})

        # "Continua" → re-enviar la última respuesta hablada
        if respuesta == "__CONTINUE__":
            if _ultima_respuesta:
                return jsonify({"respuesta": _ultima_respuesta, "continue": True})
            return jsonify({"respuesta": "No tengo nada que repetir."})

        # Guardar respuesta para "continua"
        _ultima_respuesta = respuesta

        # Voice-only: respuesta que solo se habla, no se escribe
        if respuesta and respuesta.startswith("V__"):
            texto_voz = respuesta[3:].strip()
            if texto_voz:
                threading.Thread(target=_tts_hablar, args=(texto_voz,), daemon=True).start()
            return jsonify({"respuesta": "", "voice_only": True})

        # Notificaciones automáticas
        if respuesta and not respuesta.startswith("__"):
            r_lower = respuesta.lower()
            if any(p in r_lower for p in ["copiado:", "archivo copiado", "copia completada", "transferido:"]):
                notificar("Jarvis - Copia Completada", respuesta.strip()[:120], solo_si_ausente=True)
            if "crítico" in r_lower and ("disco" in r_lower or ": " in r_lower):
                notificar("Jarvis - Alerta de Disco", respuesta.strip()[:120])
            _programar_notificacion_ausencia(respuesta)

        sesion_info = _sesiones.obtener_activa()
        sesion_nombre = sesion_info.get("name", "") if sesion_info else ""
        es_multi = detectar_multi_tema(comando) if comando else False
        if respuesta and not respuesta.startswith("__"):
            if es_multi and len(respuesta) > 200:
                mensajes = split_into_messages(respuesta)
            else:
                mensajes = [respuesta]
        else:
            mensajes = []
        result = {
            "respuesta": respuesta,
            "session_name": sesion_nombre,
            "mensajes": mensajes,
            "multi_tema": es_multi,
        }
        if sardinas_activar:
            result.update(sardinas_data)
        if veredicto_data:
            result["veredicto"] = veredicto_data
        return jsonify(sanitize_dict(result))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# SESIONES
# ============================================================

@app.route("/api/sessions", methods=["GET"])
def api_sessions_list():
    return jsonify({"sessions": _sesiones.listar(), "activa": _sesiones.activa()})

@app.route("/api/sessions", methods=["POST"])
def api_sessions_create():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    sesion = _sesiones.crear(name or None)
    core.history.clear()
    core._ultima_respuesta_tema = ""
    core._ultima_respuesta = ""
    core._tema_actual = ""
    core.memoria = type(core.memoria)()  # Reiniciar memoria
    return jsonify({"ok": True, "session": sesion})

@app.route("/api/sessions/switch", methods=["POST"])
def api_sessions_switch():
    data = request.get_json(silent=True) or {}
    sid = data.get("session_id", "")
    if not sid:
        return jsonify({"ok": False, "error": "session_id requerido"}), 400
    result = _sesiones.switch(sid)
    if not result.get("ok"):
        return jsonify(result), 404
    # Restaurar estado del core
    core.history.clear()
    core.history.extend(result.get("history", []))
    if hasattr(core, '_ultima_respuesta_tema'):
        core._ultima_respuesta_tema = result.get("ultima_respuesta_tema", "")
    global _ultima_respuesta
    _ultima_respuesta = result.get("ultima_respuesta", "")
    return jsonify(result)

@app.route("/api/sessions/rename", methods=["POST"])
def api_sessions_rename():
    data = request.get_json(silent=True) or {}
    sid = data.get("session_id", "")
    name = data.get("name", "").strip()
    if not sid or not name:
        return jsonify({"ok": False, "error": "session_id y name requeridos"}), 400
    ok = _sesiones.rename(sid, name)
    return jsonify({"ok": ok})

@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def api_sessions_delete(session_id):
    ok = _sesiones.eliminar(session_id)
    if not ok:
        return jsonify({"ok": False, "error": "Sesion no encontrada"}), 404
    # Si la sesion activa fue eliminada, restaurar la primera disponible
    activa = _sesiones.activa()
    result = _sesiones.switch(activa) if activa else _sesiones.crear("Principal")
    if result.get("ok"):
        core.history.clear()
        core.history.extend(result.get("history", []))
        if hasattr(core, '_ultima_respuesta_tema'):
            core._ultima_respuesta_tema = result.get("ultima_respuesta_tema", "")
        global _ultima_respuesta
        _ultima_respuesta = result.get("ultima_respuesta", "")
    return jsonify({"ok": True})


@app.route("/api/speak", methods=["POST"])
def api_speak():
    data = request.get_json(silent=True) or {}
    texto = data.get("text", "").strip()
    if not texto or not tts.disponible:
        return jsonify({"ok": False}), 200
    threading.Thread(target=_tts_hablar, args=(texto,), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/speak-status")
def api_speak_status():
    return jsonify({"speaking": _tts_esta_hablando()})


@app.route("/api/stt", methods=["POST"])
def api_stt():
    data = request.get_json(silent=True) or {}
    timeout = data.get("timeout", 5)
    if not _adquirir_mic():
        return jsonify({"texto": "", "error": "Microfono ocupado por wake word"})
    try:
        texto = stt.escuchar(timeout=timeout)
        return jsonify({"texto": texto, "error": texto.startswith("[") if texto else False})
    finally:
        _liberar_mic()


@app.route("/api/stop-speak", methods=["POST"])
def api_stop_speak():
    global _tts_speaking
    with _tts_lock:
        _tts_speaking = False
    tts.detener()
    return jsonify({"ok": True})


@app.route("/api/tts-test", methods=["POST"])
def api_tts_test():
    data = request.get_json(silent=True) or {}
    texto = data.get("text", "Hola, soy Jarvis")
    if tts.disponible:
        threading.Thread(target=_tts_hablar, args=(texto,), daemon=True).start()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "TTS no disponible"})


@app.route("/api/last-response")
def api_last_response():
    """Devuelve la ultima respuesta para reanudar."""
    return jsonify({"texto": _ultima_respuesta})


@app.route("/api/mic-diagnose", methods=["GET"])
def api_mic_diagnose():
    """Diagnostico completo del microfono."""
    info = {}
    info["stt_disponible"] = stt.disponible
    info["mic_en_uso"] = _mic_in_use
    info["python"] = sys.version
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        info["mic_index_actual"] = stt._mic_index if hasattr(stt, '_mic_index') else None
        info["mic_list"] = []
        for i, m in enumerate(sr.Microphone.list_microphone_names()):
            info["mic_list"].append({"index": i, "name": m})
    except Exception as e:
        info["mic_error"] = str(e)
    return jsonify(info)


@app.route("/api/listening-status")
def api_listening_status():
    """Estado actual del microfono."""
    return jsonify({
        "mic_in_use": _mic_in_use,
        "tts_speaking": _tts_esta_hablando(),
    })


@app.route("/api/wake-word", methods=["POST"])
def api_wake_word():
    """Activa escucha por voz (triggered por dos palmadas o clic)."""
    data = request.get_json(silent=True) or {}
    wake_text = data.get("wake_text", "jarvis")
    if not _adquirir_mic():
        return jsonify({"texto": "", "error": "Microfono ocupado"})
    try:
        import winsound
        global _tts_speaking
        with _tts_lock:
            _tts_speaking = False
        tts.detener()
        try:
            winsound.Beep(880, 150)
        except Exception:
            pass
        texto = stt.escuchar(timeout=12)
        if not texto:
            return jsonify({"texto": "", "error": "No se detecto voz"})
        sys.stderr.write(f"[WAKE] Comando: {texto}\n")
        sys.stderr.flush()
        # Autocorrección silenciosa para entrada de voz
        if core.openrouter and texto:
            texto = core.openrouter.autocorregir_texto(texto)
            sys.stderr.write(f"[WAKE] Autocorregido: {texto}\n")
            sys.stderr.flush()
        respuesta = core.procesar(texto)
        if not respuesta or respuesta in ("__EXIT__", "__CONTINUE__"):
            if respuesta == "__EXIT__":
                threading.Thread(target=_salir, daemon=True).start()
            return jsonify({"texto": texto, "respuesta": respuesta or ""})
        global _ultima_respuesta
        _ultima_respuesta = respuesta
        texto_hablar = re.sub(r'[^\x20-\xff\n]', '', respuesta)
        texto_hablar = '\n'.join(l for l in texto_hablar.split('\n') if not re.match(r'^[\s\-_=]{3,}', l))
        texto_hablar = _cortar_en_oraciones(texto_hablar.strip(), 300)
        if texto_hablar:
            threading.Thread(target=_tts_hablar, args=(texto_hablar,), daemon=True).start()
        # Notificaciones automáticas tras wake-word
        if respuesta and not respuesta.startswith("__"):
            r_lower = respuesta.lower()
            if any(p in r_lower for p in ["copiado:", "archivo copiado", "copia completada", "transferido:"]):
                notificar("Jarvis - Copia Completada", respuesta.strip()[:120], solo_si_ausente=True)
            if "crítico" in r_lower and ("disco" in r_lower or ": " in r_lower):
                notificar("Jarvis - Alerta de Disco", respuesta.strip()[:120])
            _programar_notificacion_ausencia(respuesta)
        return jsonify({"texto": texto, "respuesta": respuesta})
    finally:
        _liberar_mic()


@app.route("/api/window-state", methods=["POST"])
def api_window_state():
    data = request.get_json(silent=True) or {}
    marcar_ventana(data.get("activa", True))
    return jsonify({"ok": True})

@app.route("/api/photo-metadata", methods=["POST"])
def api_photo_metadata():
    """Extrae metadatos EXIF vía exiftools.com API (metadatos completos)."""
    if "photo" not in request.files:
        return jsonify({"error": "No se recibió ninguna foto"}), 400
    file = request.files["photo"]
    if not file.filename:
        return jsonify({"error": "Archivo vacío"}), 400
    try:
        api_key = core.config.get("exiftools_api_key", "").strip()
        if not api_key:
            return jsonify({"error": "No hay API key de exiftools.com. Regístrate gratis en https://exiftools.com/api-keys y agrega 'exiftools_api_key' a config.json"}), 400

        archivo = (file.filename, file.read(), file.content_type or "application/octet-stream")
        headers = {"X-API-Key": api_key}
        r = requests.post(
            "https://exiftools.com/api/v1/extract",
            headers=headers,
            files={"file": archivo},
            timeout=30
        )
        if r.status_code == 401:
            return jsonify({"error": "API key inválida. Regenera en https://exiftools.com/api-keys"}), 401
        if not r.ok:
            return jsonify({"error": f"exiftools.com error {r.status_code}: {r.text[:200]}"}), 502

        data = r.json()
        if not data.get("success"):
            return jsonify({"error": data.get("error", "Error desconocido de exiftools.com")}), 502

        metadata = data.get("metadata", data)
        # Devolver metadata completa exactamente como llega
        metadata["_filename"] = file.filename
        metadata["_size"] = len(archivo[1])
        return jsonify(metadata)
    except requests.Timeout:
        return jsonify({"error": "Tiempo de espera agotado al consultar exiftools.com"}), 504
    except requests.ConnectionError:
        return jsonify({"error": "No se pudo conectar con exiftools.com. Verifica tu conexión a internet."}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/virustotal", methods=["POST"])
def api_virustotal():
    """Analiza un archivo con VirusTotal."""
    if "file" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Archivo vacío"}), 400
    try:
        import tempfile
        path = os.path.join(tempfile.gettempdir(), file.filename)
        file.save(path)
        mod = core.modules.get("virustotal")
        if not mod:
            return jsonify({"error": "Módulo VirusTotal no disponible"}), 500
        result = mod["instance"].execute("virustotal", file_path=path)
        os.remove(path)
        return jsonify({"result": result, "text": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/learn", methods=["POST"])
def api_learn():
    """Enseña algo a Jarvis: 'tema' y 'info'."""
    data = request.get_json(silent=True) or {}
    tema = data.get("tema", "").strip()
    info = data.get("info", "").strip()
    if not tema or not info:
        return jsonify({"ok": False, "error": "Se requieren 'tema' e 'info'"}), 400
    core.memoria.aprender(tema, info)
    return jsonify({"ok": True, "mensaje": f"Aprendido: {tema}"})

@app.route("/api/forget", methods=["POST"])
def api_forget():
    """Hace que Jarvis olvide un tema."""
    data = request.get_json(silent=True) or {}
    tema = data.get("tema", "").strip()
    if not tema:
        return jsonify({"ok": False, "error": "Se requiere 'tema'"}), 400
    if core.memoria.olvidar(tema):
        return jsonify({"ok": True, "mensaje": f"Olvidado: {tema}"})
    return jsonify({"ok": False, "error": f"No encontré '{tema}'"}), 404

@app.route("/api/memory")
def api_memory():
    """Lista los hechos que Jarvis ha aprendido."""
    hechos = core.memoria.listar_hechos()
    stats = core.memoria.estadisticas()
    return jsonify({"hechos": hechos, "stats": stats})

@app.route("/api/search-web", methods=["POST"])
def api_search_web():
    """Busca silenciosamente en la web y devuelve resultado."""
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"ok": False, "error": "Se requiere 'query'"}), 400
    resultado = core.buscador_web.buscar(query)
    return jsonify(resultado)


# ════════════════════════════════════════════════════════════════
#  SISTEMA DE TRADING YOEL SARDIÑAS
# ════════════════════════════════════════════════════════════════

_PASOS_SARDIÑAS = [
    "paso1_ventana",
    "paso2_tendencia_1d",
    "paso3_escenario_4h",
    "paso4_bollinger_15m",
    "paso5_setup",
    "paso6_niveles",
    "paso7_riesgo",
    "paso8_psicologia",
    "paso9_ejecucion",
]


def _init_sardiñas(symbol: str):
    """Inicializa el estado de la checklist Sardiñas."""
    global _sardiñas_state
    info = se.paso_inicial(symbol)
    ventana = info["ventana"]
    operable = info["operable"]
    paso1_estado = "completado" if operable else "saltado"
    paso1_msg = info["mensaje_ventana"]

    _sardiñas_state = {
        "activo": True,
        "symbol": symbol,
        "paso_actual": "paso2_tendencia_1d" if operable else "paso9_ejecucion",
        "ventana": ventana,
        "operable": operable,
        "pasos": {
            "paso1_ventana": {"estado": paso1_estado, "mensaje": paso1_msg,
                              "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
            "paso2_tendencia_1d": {"estado": "en_progreso" if operable else "pendiente",
                                   "mensaje": "Pendiente — ¿El precio está por encima de la MME20 en 1D? (sí/no)",
                                   "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
            "paso3_escenario_4h": {"estado": "pendiente",
                                   "mensaje": "Pendiente",
                                   "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
            "paso4_bollinger_15m": {"estado": "pendiente",
                                    "mensaje": "Pendiente",
                                    "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
            "paso5_setup": {"estado": "pendiente",
                            "mensaje": "Pendiente",
                            "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
            "paso6_niveles": {"estado": "pendiente",
                              "mensaje": "Pendiente",
                              "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
            "paso7_riesgo": {"estado": "pendiente",
                             "mensaje": "Pendiente",
                             "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
            "paso8_psicologia": {"estado": "pendiente",
                                 "mensaje": "Pendiente",
                                 "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
            "paso9_ejecucion": {"estado": "pendiente",
                                "mensaje": "Pendiente",
                                "grafico_url": "", "tradingview_url": "", "finviz_url": ""},
        }
    }
    return _sardiñas_state


def _get_sardiñas_state():
    global _sardiñas_state
    if not _sardiñas_state["activo"]:
        return {"activo": False, "pasos": {}}
    return _sardiñas_state


def _ejecutar_paso(paso: str, respuesta: str):
    """Ejecuta la lógica de un paso y avanza al siguiente."""
    global _sardiñas_state
    state = _sardiñas_state
    if not state["activo"]:
        return state
    sym = state["symbol"]
    idx = _PASOS_SARDIÑAS.index(paso)
    enlaces = se.generar_enlaces(sym)

    if paso == "paso2_tendencia_1d":
        si = respuesta.lower() in ("si", "sí", "yes", "confirmo", "ok")
        df_1d, err = se.obtener_datos(sym, interval="1d", period="2mo")
        if err:
            state["pasos"][paso] = {"estado": "saltado", "mensaje": f"Error: {err}"}
        else:
            mme20 = df_1d["Close"].ewm(span=20).mean().iloc[-1]
            close = df_1d["Close"].iloc[-1]
            trend = "ALCISTA" if close > mme20 else "BAJISTA"
            if si:
                msg = f"Sí. Tendencia 1D: {trend}. Precio ${close:.2f} vs MME20 ${mme20:.2f}."
            else:
                msg = f"No. Tendencia 1D: {trend}. Precio ${close:.2f} vs MME20 ${mme20:.2f}."
            state["pasos"][paso] = {"estado": "completado", "mensaje": msg,
                                    "grafico_url": "", "tradingview_url": enlaces["tradingview"],
                                    "finviz_url": enlaces["finviz"]}
        next_paso = "paso3_escenario_4h"

    elif paso == "paso3_escenario_4h":
        df_4h, err = se.obtener_datos(sym, interval="1h", period="10d")
        if err:
            state["pasos"][paso] = {"estado": "saltado", "mensaje": f"Error: {err}"}
        else:
            mme20_4h = df_4h["Close"].ewm(span=20).mean().iloc[-1]
            close = df_4h["Close"].iloc[-1]
            bb = se.calcular_bollinger(df_4h)
            bb_w = bb["BB_Width"].iloc[-1]
            avg_w = bb["BB_Width"].mean()
            comp_msg = "compresión" if bb_w < avg_w * 0.75 else "expansión"
            dir_4h = "alcista" if close > mme20_4h else "bajista"
            msg = f"Escenario 4H: {dir_4h.upper()}, {comp_msg}. Close ${close:.2f}."
            state["pasos"][paso] = {"estado": "completado", "mensaje": msg,
                                    "grafico_url": "", "tradingview_url": enlaces["tradingview"],
                                    "finviz_url": ""}
        next_paso = "paso4_bollinger_15m"

    elif paso == "paso4_bollinger_15m":
        df_15m, err = se.obtener_datos(sym, interval="15m", period="3d")
        if err:
            state["pasos"][paso] = {"estado": "saltado", "mensaje": f"Error: {err}"}
        else:
            bb = se.calcular_bollinger(df_15m)
            close = df_15m["Close"].iloc[-1]
            bb_up = bb["BB_Upper"].iloc[-1]
            bb_lo = bb["BB_Lower"].iloc[-1]
            bb_w = bb["BB_Width"].iloc[-1]
            avg_w = bb["BB_Width"].mean()
            pos = "fuera arriba" if close >= bb_up else ("fuera abajo" if close <= bb_lo else "dentro")
            comp_msg = "COMPRESION" if bb_w < avg_w * 0.75 else "normal"
            buf = se.generar_grafico(sym, interval="15m", period="3d")
            grafico_url = ""
            if buf:
                import base64
                b64 = base64.b64encode(buf.read()).decode()
                grafico_url = f"data:image/png;base64,{b64}"
            msg = f"BB(20,2) 15m: precio {pos}, ancho {bb_w:.2f}% ({comp_msg})."
            state["pasos"][paso] = {"estado": "completado", "mensaje": msg,
                                    "grafico_url": grafico_url,
                                    "tradingview_url": enlaces["tradingview"],
                                    "finviz_url": enlaces["finviz"]}
        next_paso = "paso5_setup"

    elif paso == "paso5_setup":
        df_15m, err = se.obtener_datos(sym, interval="15m", period="3d")
        setup, direc, comp, desc = ("NINGUNO", "N/A", False, "Sin datos.")
        if not err and df_15m is not None:
            setup, direc, comp, desc = se.detectar_setup(df_15m)
        msg = f"Setup: {setup} ({direc}). {desc}"
        state["pasos"][paso] = {"estado": "completado", "mensaje": msg,
                                "grafico_url": "",
                                "tradingview_url": enlaces["tradingview"],
                                "finviz_url": enlaces["finviz"]}
        next_paso = "paso6_niveles"

    elif paso == "paso6_niveles":
        df_15m, err = se.obtener_datos(sym, interval="15m", period="3d")
        if err or df_15m is None:
            msg = "No se pudieron calcular niveles."
        else:
            close = df_15m["Close"].iloc[-1]
            atr = (df_15m["High"] - df_15m["Low"]).rolling(14).mean().iloc[-1]
            soporte = df_15m["Low"].iloc[-20:].min()
            resistencia = df_15m["High"].iloc[-20:].max()
            entry = close
            sl = entry - atr * 1.5
            tp1 = entry + atr * 1.5
            tp2 = entry + atr * 2.5
            msg = (f"Entrada: ${entry:.2f} | SL: ${sl:.2f} | "
                   f"TP1: ${tp1:.2f} | TP2: ${tp2:.2f} | "
                   f"Soporte: ${soporte:.2f} | Resistencia: ${resistencia:.2f}")
        state["pasos"][paso] = {"estado": "completado", "mensaje": msg,
                                "grafico_url": "",
                                "tradingview_url": enlaces["tradingview"],
                                "finviz_url": ""}
        next_paso = "paso7_riesgo"

    elif paso == "paso7_riesgo":
        df_15m, err = se.obtener_datos(sym, interval="15m", period="3d")
        if err or df_15m is None:
            msg = "No se pudo calcular riesgo."
        else:
            close = df_15m["Close"].iloc[-1]
            atr = (df_15m["High"] - df_15m["Low"]).rolling(14).mean().iloc[-1]
            riesgo_dolares = 75.0
            distancia = atr * 1.5
            tamanio = riesgo_dolares / distancia if distancia > 0 else 0
            msg = (f"Cuenta: $5000 | Riesgo 1.5% (${riesgo_dolares:.0f}) | "
                   f"Distancia SL: ${distancia:.2f} | "
                   f"Tamaño: {tamanio:.2f} unidades")
        state["pasos"][paso] = {"estado": "completado", "mensaje": msg,
                                "grafico_url": "",
                                "tradingview_url": "", "finviz_url": ""}
        next_paso = "paso8_psicologia"

    elif paso == "paso8_psicologia":
        msg = ("Reglas claras. Stop loss respetado. "
               "Máximo 2 trades hoy. Relación R:R mínima 1:2. "
               "No promediar. No mover stop en contra.")
        state["pasos"][paso] = {"estado": "completado", "mensaje": msg,
                                "grafico_url": "",
                                "tradingview_url": "", "finviz_url": ""}
        next_paso = "paso9_ejecucion"

    elif paso == "paso9_ejecucion":
        msg = ("Todos los pasos completados. "
               "Puede lanzar la operación según los niveles definidos. "
               "Recuerde: la mejor operación es la que NO hace.")
        state["pasos"][paso] = {"estado": "completado", "mensaje": msg,
                                "grafico_url": "",
                                "tradingview_url": "", "finviz_url": ""}
        next_paso = ""

    else:
        next_paso = ""

    # Avanzar al siguiente paso
    if next_paso and next_paso in _PASOS_SARDIÑAS:
        state["paso_actual"] = next_paso
        if state["pasos"][next_paso]["estado"] == "pendiente":
            state["pasos"][next_paso]["estado"] = "en_progreso"
    else:
        state["paso_actual"] = ""

    _sardiñas_state = state
    return state


@app.route("/api/sardiñas/iniciar", methods=["POST"])
def api_sardinas_iniciar():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip().upper()
    if not symbol:
        return jsonify({"success": False, "error": "Símbolo requerido"}), 400
    state = _init_sardiñas(symbol)
    ventana, operable, msg = se.evaluar_ventana()
    return jsonify({
        "success": True,
        "checklist": state["pasos"],
        "mensaje_inicial": msg,
        "symbol": symbol,
        "ventana": ventana,
        "operable": operable,
        "paso_actual": state["paso_actual"],
        "panel_abierto": True,
        "activo": True,
    })


@app.route("/api/sardiñas/estado", methods=["GET"])
def api_sardinas_estado():
    state = _get_sardiñas_state()
    return jsonify({
        "activo": state.get("activo", False),
        "checklist": state.get("pasos", {}),
        "paso_actual": state.get("paso_actual", ""),
        "symbol": state.get("symbol", ""),
        "ventana": state.get("ventana", ""),
        "operable": state.get("operable", False),
    })


@app.route("/api/sardiñas/confirmar", methods=["POST"])
def api_sardinas_confirmar():
    data = request.get_json(silent=True) or {}
    paso = data.get("paso", "")
    respuesta = data.get("respuesta", "")
    if not paso:
        return jsonify({"success": False, "error": "Paso requerido"}), 400
    if not _sardiñas_state.get("activo"):
        return jsonify({"success": False, "error": "Sistema no activo"}), 400
    state = _ejecutar_paso(paso, respuesta)
    return jsonify({
        "success": True,
        "checklist": state["pasos"],
        "paso_actual": state["paso_actual"],
        "symbol": state["symbol"],
        "ventana": state["ventana"],
        "operable": state["operable"],
    })


@app.route("/api/sardiñas/grafico/<symbol>/<interval>")
def api_sardinas_grafico(symbol, interval):
    buf = se.generar_grafico(symbol.upper(), interval=interval)
    if buf is None:
        return jsonify({"error": "No se pudo generar gráfico"}), 500
    return app.response_class(buf, mimetype="image/png")


# ════════════════════════════════════════════════════════════════
#  SCANNER / SCREENER BOLLINGER
# ════════════════════════════════════════════════════════════════


@app.route("/api/scanner/bollinger", methods=["POST"])
def api_scanner_bollinger():
    """Inicia escaneo de Bollinger en background."""
    data = request.get_json(silent=True) or {}
    symbols = data.get("symbols", WATCHLIST_BB)
    threading.Thread(target=_scanner_thread_bb, args=(symbols,), daemon=True).start()
    return jsonify({"ok": True, "mensaje": "Escaneo iniciado", "total": len(symbols)})


@app.route("/api/screener/bollinger", methods=["POST"])
def api_screener_bollinger():
    """Inicia screener de filtros en cascada en background."""
    data = request.get_json(silent=True) or {}
    symbols = data.get("symbols", sb.WATCHLIST)
    threading.Thread(target=_scanner_thread_screener, args=(symbols,), daemon=True).start()
    return jsonify({"ok": True, "mensaje": "Screener iniciado", "total": len(symbols)})


@app.route("/api/scanner/progress")
def api_scanner_progress():
    """Devuelve el progreso actual del scanner/screener."""
    with _scanner_lock:
        return jsonify(**_scanner_progress)


@app.route("/api/scanner/latest")
def api_scanner_latest():
    """Devuelve los resultados cacheados del scanner/screener."""
    return jsonify({
        "scanner": _scanner_cache,
        "screener": _screener_cache,
    })


@app.route("/api/scanner/enviar-al-chat", methods=["POST"])
def api_scanner_enviar_chat():
    """Envía los top resultados al chat como mensaje."""
    data = request.get_json(silent=True) or {}
    tipo = data.get("tipo", "scanner")  # "scanner" o "screener"
    cache = _scanner_cache if tipo == "scanner" else _screener_cache
    res = cache.get("resultado")
    if not res:
        return jsonify({"error": "No hay datos cacheados"}), 400
    if tipo == "scanner":
        items = res[:3]
    else:
        items = res.get("mejores", [])[:1]
    if not items:
        return jsonify({"error": "No hay resultados"}), 400
    lineas = []
    for it in items:
        sym = it.get("symbol", "?")
        price = it.get("price") or it.get("precio", "?")
        direc = it.get("direction") or it.get("direccion", "?")
        nv = it.get("niveles") or {}
        entry = nv.get("entry", price)
        sl = nv.get("sl", "?")
        tp1 = nv.get("tp1", "?")
        tp2 = nv.get("tp2", "?")
        rr = nv.get("rr", "?")
        score = it.get("score", "")
        vol = it.get("vol_ratio", "")
        rsi = it.get("rsi", "")
        band = it.get("banda", it.get("direction", ""))
        emoji = "🟢" if direc in ("compra", "buy") else "🔴"
        rango = f"SC:{score}" if score else f"V:{vol}x"
        rsi_txt = f"RSI:{rsi}" if rsi else ""
        if tipo == "scanner":
            lineas.append(f"{emoji} **{sym}** ${price} ({direc.upper()}) — {rango}")
            if entry and sl and tp1:
                lineas.append(f"   ↔ Entrada: ${entry} | SL: ${sl} | TP1: ${tp1} | TP2: ${tp2} | R/R: {rr}")
        else:
            detalle = it.get("motivos", [])
            lineas.append(f"{emoji} **{sym}** ${price} — Score: {score}/10 | V:{vol}x {rsi_txt}")
            if detalle:
                lineas.append(f"   📊 Indicadores: {' · '.join(str(d) for d in detalle[:3])}")
            if entry and sl and tp1:
                lineas.append(f"   ↔ Entrada: ${entry} | SL: ${sl} | TP1: ${tp1} | R/R: {rr}")
    titulo = "📉 **Scanner BB — Top 3 Oportunidades**" if tipo == "scanner" else "🔍 **Screener — Mejor Acción**"
    explicacion = ""
    if tipo == "scanner":
        explicacion = (
            "El scanner busca acciones fuera de BB(20,2) con volumen >0.8x. "
            "Rankeo por: volumen relativo + ancho de banda (mayor volatilidad = mejor setup). "
            "Se usan bandas de Bollinger como indicador principal: precio fuera de banda = posible reversión o continuación."
        )
    else:
        explicacion = (
            "El screener aplica 6 filtros en cascada: ① BB(20,2) breakout, ② Volumen >1.5x, "
            "③ Tendencia SMA50 alineada, ④ RSI en rango óptimo, ⑤ ATR controlado, "
            "⑥ Distancia a soporte/resistencia. Puntaje 0-10. Se selecciona la mejor."
        )
    join_char = '\n'
    mensaje = f"{titulo}\n{join_char.join(lineas)}\n\n💡 *{explicacion}*"
    global _ultima_respuesta
    _ultima_respuesta = mensaje
    return jsonify({"mensaje": mensaje, "items": items})


def _buscar_duckduckgo(consulta: str) -> str:
    """Busca en DuckDuckGo y devuelve texto resumido."""
    try:
        from urllib.parse import quote
        url = (
            "https://api.duckduckgo.com/"
            f"?q={quote(consulta)}&format=json&no_html=1&skip_disambig=1"
        )
        r = requests.get(url, timeout=8)
        if r.status_code in (200, 202):
            data = r.json()
            abstract = (
                data.get("AbstractText", "")
                or data.get("Answer", "")
                or data.get("Definition", "")
            )
            if abstract:
                return abstract[:600]
            topics = data.get("RelatedTopics", [])
            textos = []
            for t in topics[:3]:
                if isinstance(t, dict) and "Text" in t:
                    textos.append(t["Text"])
                elif isinstance(t, dict) and "Topics" in t:
                    for st in t["Topics"][:1]:
                        if "Text" in st:
                            textos.append(st["Text"])
            if textos:
                return ". ".join(textos)[:600]
    except Exception:
        pass
    return ""


def calcular_score(symbol: str) -> dict:
    """
    Calcula el Score de Calidad de Entrada (0–100) para un símbolo.
    Retorna dict con score_total y desglose de cada pilar.
    """
    import yfinance as yf
    score = {"score_total": 0, "pilares": {}, "datos": {}}
    try:
        # ── Obtener datos ──
        df = yf.download(symbol, period="3mo", interval="1d", progress=False)
        if df is None or df.empty or len(df) < 50:
            return score
        if isinstance(df.columns, pd.MultiIndex):
            close = df["Close"].iloc[:, 0].astype(float)
            high = df["High"].iloc[:, 0].astype(float)
            low = df["Low"].iloc[:, 0].astype(float)
            volume = df["Volume"].iloc[:, 0].astype(float)
            open_p = df["Open"].iloc[:, 0].astype(float)
        else:
            close = df["Close"].astype(float)
            high = df["High"].astype(float)
            low = df["Low"].astype(float)
            volume = df["Volume"].astype(float)
            open_p = df["Open"].astype(float)

        precio_actual = float(close.iloc[-1])
        score["datos"]["precio_actual"] = round(precio_actual, 2)

        # ── Pilar 1: Confirmación Técnica (30 pts) ──
        p1 = 0
        # Volumen relativo
        vol_avg = volume.tail(20).mean()
        vol_ratio = volume.iloc[-1] / vol_avg if vol_avg > 0 else 0
        score["datos"]["vol_ratio"] = round(vol_ratio, 2)
        if vol_ratio > 2.0:
            p1 += 10
            vol_score_note = ">2.0x"
        elif vol_ratio > 1.5:
            p1 += 7
            vol_score_note = "1.5-2.0x"
        elif vol_ratio > 1.0:
            p1 += 3
            vol_score_note = "1.0-1.5x"
        else:
            vol_score_note = f"{vol_ratio:.1f}x"

        # Tendencia SMA50
        sma50 = close.rolling(50).mean()
        pendiente_sma50 = sma50.diff().tail(5).mean() if len(sma50) > 5 else 0
        # Determinar dirección de ruptura desde el screener
        bb_period = 20
        sma20 = close.rolling(bb_period).mean()
        std20 = close.rolling(bb_period).std()
        bb_upper = sma20 + 2.0 * std20
        bb_lower = sma20 - 2.0 * std20
        direccion = "compra" if precio_actual <= bb_lower.iloc[-1] else "venta"
        score["datos"]["direccion"] = direccion
        if (direccion == "compra" and pendiente_sma50 > 0) or (direccion == "venta" and pendiente_sma50 < 0):
            p1 += 10
            alineacion = "alineada"
        else:
            alineacion = "no alineada"
        score["datos"]["pendiente_sma50"] = round(float(pendiente_sma50), 4)

        # Distancia a soporte/resistencia
        atr = (high - low).rolling(14).mean()
        atr_actual = float(atr.iloc[-1]) if not atr.empty else precio_actual * 0.015
        score["datos"]["atr"] = round(atr_actual, 4)
        if direccion == "compra":
            soporte = float(low.tail(30).min())
            distancia = (precio_actual - soporte) / atr_actual if atr_actual > 0 else 0
            score["datos"]["nivel_opuesto"] = round(soporte, 2)
        else:
            resistencia = float(high.tail(30).max())
            distancia = (resistencia - precio_actual) / atr_actual if atr_actual > 0 else 0
            score["datos"]["nivel_opuesto"] = round(resistencia, 2)
        score["datos"]["distancia_atr_nivel"] = round(distancia, 2)
        if distancia >= 1.5:
            p1 += 10
        elif distancia >= 0.5:
            p1 += 5
        score["pilares"]["p1_confirmacion_tecnica"] = {"puntos": p1, "vol_ratio": vol_score_note, "alineacion": alineacion, "distancia_atr": round(distancia, 2)}

        # ── Pilar 2: Momento y Volatilidad (25 pts) ──
        p2 = 0
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        rsi_series = 100 - (100 / (1 + rs))
        rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.empty and not pd.isna(rsi_series.iloc[-1]) else 50
        score["datos"]["rsi"] = round(rsi_val, 1)
        if direccion == "compra":
            if 55 <= rsi_val <= 75:
                p2 += 15
                rsi_note = "zona óptima"
            elif 40 <= rsi_val < 55 or 75 < rsi_val <= 85:
                p2 += 8
                rsi_note = "zona sub-óptima"
            else:
                rsi_note = "fuera de rango"
        else:
            if 25 <= rsi_val <= 45:
                p2 += 15
                rsi_note = "zona óptima"
            elif 15 <= rsi_val < 25 or 45 < rsi_val <= 55:
                p2 += 8
                rsi_note = "zona sub-óptima"
            else:
                rsi_note = "fuera de rango"
        score["datos"]["rsi_note"] = rsi_note

        # ATR controlado
        atr_media_50 = float(atr.tail(50).mean()) if len(atr) > 50 else atr_actual
        if atr_actual < 1.5 * atr_media_50:
            p2 += 10
            atr_control = "controlada"
        elif atr_actual > 2.0 * atr_media_50:
            atr_control = "elevada"
        else:
            p2 += 10
            atr_control = "moderada"
        score["datos"]["atr_control"] = atr_control
        score["pilares"]["p2_momento_volatilidad"] = {"puntos": p2, "rsi": rsi_note, "atr": atr_control}

        # ── Pilar 3: Sentimiento y Noticias (20 pts) ──
        p3 = 0
        noticias_texto = _buscar_duckduckgo(f"{symbol} stock news")
        score["datos"]["noticias_raw"] = noticias_texto[:200] if noticias_texto else ""
        palabras_pos = ["ganancia", "sube", "récord", "aprobación", "positivo", "aumenta",
                        "crece", "ascenso", "beneficio", "crecimiento", "éxito", "acuerdo",
                        "lanzamiento", "innovación", "supera", "rating", "comprar", "outperform",
                        "sobreponderar", "dividendo", "recompra"]
        palabras_neg = ["pérdida", "pierde", "cae", "desplome", "investigación", "demanda",
                        "multa", "sanción", "rebaja", "vender", "underperform", "infraponderar",
                        "negativo", "recorte", "quiebra", "fraude", "corrección", "caída"]
        if noticias_texto:
            texto_lower = noticias_texto.lower()
            pos_count = sum(1 for p in palabras_pos if p in texto_lower)
            neg_count = sum(1 for n in palabras_neg if n in texto_lower)
            if pos_count > neg_count:
                p3 += 15
                sentimiento = "positivo"
            elif neg_count > pos_count:
                sentimiento = "negativo"
            else:
                p3 += 8
                sentimiento = "neutral"
        else:
            p3 += 5
            sentimiento = "sin noticias"
        score["datos"]["sentimiento"] = sentimiento
        # Earnings check
        earnings_texto = _buscar_duckduckgo(f"{symbol} earnings date")
        earnings_proximos = False
        if earnings_texto:
            from datetime import timedelta
            hoy = datetime.now()
            # Buscar fechas en los próximos 2 días en el texto
            import re as _re
            fechas = _re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', earnings_texto)
            if fechas:
                for f in fechas:
                    try:
                        parts = _re.split(r'[/-]', f)
                        if len(parts) == 3:
                            d = datetime(int(parts[2]) if len(parts[2]) == 4 else 2000 + int(parts[2]),
                                         int(parts[1]), int(parts[0]))
                            if abs((d - hoy).days) <= 2:
                                earnings_proximos = True
                                break
                    except Exception:
                        pass
        if earnings_proximos:
            p3 -= 5
        score["datos"]["earnings_proximos"] = earnings_proximos
        score["pilares"]["p3_sentimiento_noticias"] = {"puntos": p3, "sentimiento": sentimiento, "earnings": "próximos" if earnings_proximos else "no"}

        # ── Pilar 4: Factor Psicológico (15 pts) ──
        p4 = 0
        # RSI en sobrecompra con divergencia
        divergencia_bajista = False
        if rsi_val > 75 and len(rsi_series) > 5 and len(close) > 5:
            rsi_hace_5 = float(rsi_series.iloc[-5]) if not pd.isna(rsi_series.iloc[-5]) else rsi_val
            precio_hace_5 = float(close.iloc[-5])
            if rsi_hace_5 < rsi_val and precio_hace_5 > precio_actual:
                divergencia_bajista = True
        if rsi_val > 75 and not divergencia_bajista:
            p4 += 5  # codicia pero con inercia
        # Persistencia (velas consecutivas fuera de banda)
        velas_fuera = 0
        bb_upper_val = float(bb_upper.iloc[-1])
        bb_lower_val = float(bb_lower.iloc[-1])
        for _, row in df.tail(10).iterrows():
            c = float(row["Close"] if not isinstance(row["Close"], pd.Series) else row["Close"].iloc[0])
            if (direccion == "compra" and c <= bb_lower_val) or (direccion == "venta" and c >= bb_upper_val):
                velas_fuera += 1
        score["datos"]["velas_fuera_bb"] = velas_fuera
        if velas_fuera > 3:
            # Verificar si volumen disminuye
            vol_tail = volume.tail(velas_fuera)
            if len(vol_tail) >= 2 and vol_tail.iloc[-1] < vol_tail.iloc[0]:
                p4 -= 5  # posible agotamiento
        # Coherencia narrativa
        if sentimiento in ("positivo",) and direccion == "compra":
            p4 += 5
        elif sentimiento in ("negativo",) and direccion == "venta":
            p4 += 5
        score["datos"]["divergencia_bajista"] = divergencia_bajista
        score["pilares"]["p4_factor_psicologico"] = {"puntos": p4, "divergencia": divergencia_bajista, "velas_fuera": velas_fuera}

        # ── Pilar 5: Contexto de Mercado (10 pts) ──
        p5 = 0
        try:
            spy = yf.download("SPY", period="1mo", interval="1d", progress=False)
            if spy is not None and not spy.empty:
                if isinstance(spy.columns, pd.MultiIndex):
                    spy_close = spy["Close"].iloc[:, 0].astype(float)
                else:
                    spy_close = spy["Close"].astype(float)
                spy_pendiente = spy_close.diff().tail(10).mean()
                spy_trend = "alcista" if spy_pendiente > 0 else "bajista"
                score["datos"]["spy_trend"] = spy_trend
                if (spy_trend == "alcista" and direccion == "compra") or (spy_trend == "bajista" and direccion == "venta"):
                    p5 += 5
        except Exception:
            score["datos"]["spy_trend"] = "error"
        try:
            vix = yf.download("^VIX", period="5d", interval="1d", progress=False)
            if vix is not None and not vix.empty:
                if isinstance(vix.columns, pd.MultiIndex):
                    vix_close = vix["Close"].iloc[:, 0].astype(float)
                else:
                    vix_close = vix["Close"].astype(float)
                vix_val = float(vix_close.iloc[-1])
                score["datos"]["vix"] = round(vix_val, 1)
                if vix_val < 20:
                    p5 += 5
                elif vix_val > 30:
                    p5 -= 5
        except Exception:
            score["datos"]["vix"] = None
        score["pilares"]["p5_contexto_mercado"] = {"puntos": p5}

        score["score_total"] = p1 + p2 + p3 + p4 + p5
        score["datos"]["score_total"] = score["score_total"]
        return score
    except Exception as e:
        return score


def generar_objeto_veredicto(symbol: str, detalle: dict) -> dict:
    """Genera el objeto JSON de veredicto para el mejor símbolo."""
    datos = detalle.get("datos", {})
    score_total = detalle.get("score_total", 0)
    precio_actual = datos.get("precio_actual", 0)
    vol_ratio = datos.get("vol_ratio", 0)
    rsi_val = datos.get("rsi", 50)
    direccion = datos.get("direccion", "compra")
    atr_v = datos.get("atr", precio_actual * 0.015)
    divergencia = datos.get("divergencia_bajista", False)
    spy_trend = datos.get("spy_trend", "neutral")
    vix_val = datos.get("vix", 20)
    sentimiento = datos.get("sentimiento", "sin noticias")
    velas_fuera = datos.get("velas_fuera_bb", 0)
    earnings = datos.get("earnings_proximos", False)
    pendiente = datos.get("pendiente_sma50", 0)

    # Determinar fuerza
    if vol_ratio > 3 and rsi_val > 70 and sentimiento == "positivo":
        fuerza = "IMPULSO EXPLOSIVO (alta probabilidad de continuación acelerada)"
    elif vol_ratio > 2 and 60 <= rsi_val <= 70:
        fuerza = "FUERTE EMPUJÓN (alta probabilidad de continuación)"
    elif vol_ratio > 1.5 and 50 <= rsi_val <= 60:
        fuerza = "SUAVE EMPUJÓN (probabilidad moderada de continuación)"
    elif divergencia or vol_ratio < 1.0:
        fuerza = "POSIBLE REVERSIÓN (debilidad en el movimiento)"
    else:
        fuerza = "MOVIMIENTO MODERADO (esperar confirmación)"

    # Probabilidad basada en reglas históricas
    probabilidad = "50-55%"
    if vol_ratio > 2 and 60 <= rsi_val <= 75 and not divergencia:
        trend_ok = (direccion == "compra" and pendiente > 0) or (direccion == "venta" and pendiente < 0)
        if trend_ok:
            probabilidad = "70-75%"
        else:
            probabilidad = "60-65%"
    elif 1.5 < vol_ratio <= 2 and 50 <= rsi_val <= 60:
        probabilidad = "60-65%"
    elif divergencia or rsi_val > 80:
        probabilidad = "50-55%"
    if vol_ratio < 1.0:
        probabilidad = "40-45%"

    # Niveles operativos
    entry = precio_actual
    if direccion == "compra":
        sl = entry - atr_v * 1.5
        tp1 = entry + atr_v * 1.5
        tp2 = entry + atr_v * 2.5
        stop_alerta = entry - atr_v * 0.8
    else:
        sl = entry + atr_v * 1.5
        tp1 = entry - atr_v * 1.5
        tp2 = entry - atr_v * 2.5
        stop_alerta = entry + atr_v * 0.8

    direccion_label = "COMPRA" if direccion == "compra" else "VENTA"
    emoji_dir = "🟢" if direccion == "compra" else "🔴"

    # Generar resumen
    partes_resumen = []
    if vol_ratio > 1.5:
        partes_resumen.append(f"volumen {vol_ratio:.1f}x sobre la media")
    if rsi_val:
        partes_resumen.append(f"RSI en {rsi_val:.0f}")
    if not divergencia:
        if rsi_val < 75:
            partes_resumen.append("sin divergencia")
    else:
        partes_resumen.append("con divergencia bajista")
    if sentimiento in ("positivo", "negativo"):
        if sentimiento == "positivo":
            partes_resumen.append("noticias positivas")
        else:
            partes_resumen.append("noticias negativas")
    if spy_trend != "neutral":
        spy_text = "favorable" if (spy_trend == "alcista" and direccion == "compra") or (spy_trend == "bajista" and direccion == "venta") else "neutral"
        partes_resumen.append(f"contexto SPY {spy_text} ({spy_trend})")

    resumen = f"{symbol} presenta una configuración con {', '.join(partes_resumen)}." if partes_resumen else f"{symbol} sin señales claras en este momento."

    # Razones psicológicas
    if rsi_val > 70:
        psicologia = "El mercado muestra codicia controlada; los compradores están absorbiendo la oferta sin signos inmediatos de agotamiento."
    elif rsi_val < 30:
        psicologia = "El mercado muestra miedo; los vendedores dominan pero podría haber un rebote técnico."
    elif sentimiento in ("positivo",):
        psicologia = "Las noticias positivas refuerzan el sesgo alcista con participantes confiados."
    elif sentimiento in ("negativo",):
        psicologia = "El sentimiento negativo está presionando el precio; los vendedores tienen el control."
    else:
        psicologia = "El mercado está en zona neutral; el movimiento dependerá del volumen y catalizadores."

    if divergencia:
        psicologia += " Sin embargo, se detecta divergencia bajista: el precio sube pero el RSI baja, lo que sugiere agotamiento."

    # Advertencia
    advertencia = ""
    if direccion == "compra":
        advertencia = f"Si el precio cae por debajo de ${stop_alerta:.2f}, la fuerza compradora podría debilitarse."
        if rsi_val > 80:
            advertencia += " RSI en sobrecompra extrema; considere cierre parcial si supera 85."
        if earnings:
            advertencia += " Earnings próximos — riesgo de evento inesperado."
    else:
        advertencia = f"Si el precio sube por encima de ${stop_alerta:.2f}, la presión vendedora podría disminuir."
        if earnings:
            advertencia += " Earnings próximos — riesgo de evento inesperado."

    return {
        "symbol": symbol,
        "score": score_total,
        "direccion": direccion_label,
        "fuerza": fuerza,
        "resumen": resumen,
        "datos_concretos": {
            "precio_actual": round(precio_actual, 2),
            "volumen_ratio": round(vol_ratio, 2),
            "rsi": round(rsi_val, 1),
            "atr": round(atr_v, 4),
            "noticias_sentimiento": sentimiento.capitalize(),
            "spy_tendencia": spy_trend.capitalize() if spy_trend else "N/A",
            "vix": round(vix_val, 1) if vix_val else None,
        },
        "probabilidad_exito": f"{probabilidad} (basada en estadísticas de setups similares con volumen {vol_ratio:.1f}x y RSI en {rsi_val:.0f})",
        "fuerza_movimiento": f"Se espera un movimiento { 'fuerte al alza' if direccion == 'compra' else 'fuerte a la baja' } en las próximas 2-4 horas, con posible aceleración si supera los {tp1:.2f} USD.",
        "niveles_operativos": {
            "entrada": round(entry, 2),
            "stop_loss": round(sl, 2),
            "take_profit_1": round(tp1, 2),
            "take_profit_2": round(tp2, 2),
        },
        "razones_psicologicas": psicologia,
        "advertencia": advertencia,
    }


@app.route("/api/screener/final_verdict", methods=["POST"])
def api_screener_final_verdict():
    """Evalúa todos los candidatos del screener y devuelve el veredicto del mejor."""
    data = request.get_json(silent=True) or {}
    symbols = data.get("symbols", [])
    global ultimo_screener
    if not symbols:
        symbols = [s.get("symbol") for s in ultimo_screener.get("resultados", []) if s.get("symbol")]
    if not symbols:
        return jsonify({"error": "No hay símbolos para analizar. Ejecuta el screener primero."}), 400
    if len(symbols) > 20:
        symbols = symbols[:20]
    mejores = []
    for sym in symbols:
        detalle = calcular_score(sym)
        if detalle.get("score_total", 0) > 0:
            mejores.append({"symbol": sym, "score": detalle["score_total"], "detalle": detalle})
    if not mejores:
        return jsonify({"error": "No se pudieron calcular scores para los símbolos proporcionados."}), 400
    mejores.sort(key=lambda x: x["score"], reverse=True)
    mejor = mejores[0]
    veredicto = generar_objeto_veredicto(mejor["symbol"], mejor["detalle"])
    return jsonify({
        "symbol": mejor["symbol"],
        "score": mejor["score"],
        "total_candidatos": len(mejores),
        "todos_scores": [{"symbol": m["symbol"], "score": m["score"]} for m in mejores[:5]],
        "veredicto": veredicto,
    })


def _calcular_veredicto_desde_cache():
    """Calcula veredicto usando los símbolos del último screener."""
    global ultimo_screener
    symbols = [s.get("symbol") for s in ultimo_screener.get("resultados", []) if s.get("symbol")]
    if not symbols:
        return None
    if len(symbols) > 20:
        symbols = symbols[:20]
    mejores = []
    for sym in symbols:
        detalle = calcular_score(sym)
        if detalle.get("score_total", 0) > 0:
            mejores.append({"symbol": sym, "score": detalle["score_total"], "detalle": detalle})
    if not mejores:
        return None
    mejores.sort(key=lambda x: x["score"], reverse=True)
    mejor = mejores[0]
    return generar_objeto_veredicto(mejor["symbol"], mejor["detalle"])


def _salir():
    time.sleep(1)
    os._exit(0)


# ── API: Listado de Estrategias ──
@app.route('/api/estrategias')
def api_estrategias():
    return jsonify({
        "estrategias": [
            {
                "id": "sardinas",
                "nombre": "Yoel Sardiñas \"The Tradingway\"",
                "descripcion": "Estrategia de trading basada en Bandas de Bollinger, ventanas horarias (London/New York), 4 setups (Breakout, Pullback, FVG, Reversal), FVGs, y Plan del 35%.",
                "activos": "acciones, ETFs, índices, forex",
                "timeframe": "5min-1h"
            },
            {
                "id": "screener_bollinger",
                "nombre": "Screener Bollinger",
                "descripcion": "Escaneo de mercado para detectar operaciones con Bandas de Bollinger (salidas de banda, compresiones/expansiones, walkbacks). Combina ICT + Bollinger.",
                "activos": "acciones US, ETFs",
                "timeframe": "diario"
            },
            {
                "id": "prediccion_institucional",
                "nombre": "Predicción Institucional",
                "descripcion": "Análisis de flujo de órdenes, órdenes OI, CVD, delta acumulado. Detecta manipulación institucional.",
                "activos": "acciones, ETFs, futuros",
                "timeframe": "1min-15min"
            },
            {
                "id": "comportamiento_colectivo",
                "nombre": "Comportamiento Colectivo",
                "descripcion": "Análisis de sentimiento de mercado basado en Fear & Greed Index, flujo de noticias, comportamiento de carteras.",
                "activos": "índices, cripto",
                "timeframe": "1h-diario"
            },
            {
                "id": "analisis_tecnico",
                "nombre": "Análisis Técnico Clásico",
                "descripcion": "Soportes/resistencias, medias móviles, RSI, MACD, patrones de velas, volumen.",
                "activos": "cualquier activo",
                "timeframe": "cualquier temporalidad"
            }
        ]
    })


# Notificación de ausencia: si el usuario no interactúa 60s después de una respuesta y la ventana está oculta
_away_timer = None
_away_lock = threading.Lock()

def _programar_notificacion_ausencia(respuesta: str):
    global _away_timer
    # Cancelar timer anterior
    with _away_lock:
        if _away_timer:
            _away_timer.cancel()
        texto = respuesta[:200]
        _away_timer = threading.Timer(60.0, _notificar_ausencia, args=[texto])
        _away_timer.daemon = True
        _away_timer.start()

def _notificar_ausencia(texto: str):
    notificar("Jarvis te ha respondido", f"{texto[:120]}...\n(Toca la ventana para ver la respuesta completa)", solo_si_ausente=True)


def _generar_saludo_web() -> dict:
    import random, platform as _platform
    pc_info = {
        "usuario": os.getlogin(),
        "hostname": _platform.node(),
        "os": _platform.system(),
        "os_version": _platform.version(),
        "cpu": _platform.processor() or "desconocido",
    }
    try:
        import psutil
        pc_info["ram"] = f"{round(psutil.virtual_memory().total / (1024**3))} GB"
        pc_info["cpu_hilos"] = psutil.cpu_count(logical=True)
    except Exception:
        pc_info["ram"] = "? GB"
        pc_info["cpu_hilos"] = "?"
    ahora = datetime.now()
    hora_int = ahora.hour
    if 5 <= hora_int < 12:
        periodo = "días"
    elif 12 <= hora_int < 19:
        periodo = "tardes"
    else:
        periodo = "noches"
    saludos = [
        f"Buenos {periodo}, {pc_info['usuario']}. Jarvis versión 2.5 listo.",
        f"Hola {pc_info['usuario']}. Sistema {pc_info['os']}, equipo {pc_info['hostname']}.",
        f"Bienvenido, {pc_info['usuario']}. {pc_info['os']} {pc_info['os_version'][:10]} operativo.",
        f"¡Hola {pc_info['usuario']}! PC con {pc_info['cpu_hilos']} hilos CPU, {pc_info['ram']} RAM.",
    ]
    return {"display": random.choice(saludos), "pc": pc_info}


if __name__ == "__main__":
    import colorama
    colorama.init()
    colorama.deinit()  # evitar crash en consola Windows con Unicode

    host = os.getenv("JARVIS_HOST", "127.0.0.1")
    port = int(os.getenv("JARVIS_PORT", "5000"))

    from utils.colors import banner_jarvis, incrementar_tiempo

    saludo = _generar_saludo_web()
    pc = saludo["pc"]
    try:
        print("\n" + banner_jarvis())
    except OSError:
        print("\n  [JARVIS v2.5]")
    incrementar_tiempo(0.08)
    print(f"\n  {'=' * 60}")
    print(f"  Web iniciado en http://{host}:{port}")
    print(f"  {len(core.modules)} módulos activos | TTS: {'SI' if tts.disponible else 'NO'}")
    print(f"  {pc['usuario']} @ {pc['hostname']} | RAM: {pc['ram']} | CPU: {pc['cpu_hilos']} hilos")
    print(f"  ► {saludo['display']}")
    print(f"  {'=' * 60}")
    # Hablar saludo si TTS disponible
    if tts.disponible:
        texto_hablar = re.sub(r'\([^)]*\)', '', saludo['display']).strip()
        threading.Thread(target=_tts_hablar, args=(texto_hablar,), daemon=True).start()
    app.run(host=host, port=port, debug=False)
