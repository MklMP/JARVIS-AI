"""
Módulo de voz para Jarvis.
- TTS: edge-tts (online) → WinRT (OneCore offline) → SAPI → PowerShell → silencioso
- STT: pyaudio + Google Web Speech API → fallback PowerShell
- Voces seleccionables desde UI
"""

import os
import subprocess
import threading
import io
import wave
import struct
import json
import requests


# ====================================================================
# TEXTO A VOZ (TTS)
# ====================================================================

class JarvisTTS:
    """Síntesis de voz con soporte multi-voz seleccionable."""

    VOCES_EDGE = {
        "es-CO-GonzaloNeural": "Gonzalo (Colombia, masc)",
        "es-CO-SalomeNeural": "Salomé (Colombia, fem)",
        "es-ES-AlvaroNeural": "Álvaro (España, masc)",
        "es-ES-ElviraNeural": "Elvira (España, fem)",
        "es-MX-JorgeNeural": "Jorge (México, masc)",
        "es-MX-DaliaNeural": "Dalia (México, fem)",
        "es-AR-TomasNeural": "Tomás (Argentina, masc)",
        "es-AR-ElenaNeural": "Elena (Argentina, fem)",
        "es-CL-CatalinaNeural": "Catalina (Chile, fem)",
        "es-CL-LorenzoNeural": "Lorenzo (Chile, masc)",
        "es-CU-ManuelNeural": "Manuel (Cuba, masc, gruesa)",
        "es-VE-SebastianNeural": "Sebastián (Venezuela, masc, gruesa)",
        "es-PR-VictorNeural": "Víctor (Puerto Rico, masc, gruesa)",
        "es-DO-EmilioNeural": "Emilio (Rep. Dominicana, masc, gruesa)",
        "en-US-GuyNeural": "Guy (EEUU, masc)",
        "en-US-JennyNeural": "Jenny (EEUU, fem)",
    }

    def __init__(self, preferir_natural=False, voz_config=""):
        self._engine = None
        self._synth_winrt = None
        self._usar_powershell = False
        self._usar_winrt = False
        self._usar_edge = False
        self._voz_disponible = False
        self._preferir_natural = preferir_natural
        self._voz_seleccionada = ""        # nombre elegido por el usuario
        self._voz_actual = voz_config or ""  # la que se está usando ahora
        self._voces = []                    # lista de voces disponibles
        self._edge_voice = "es-CO-GonzaloNeural"
        self._edge_disponible = False
        self._inicializar()

    def _inicializar_edge(self):
        try:
            import edge_tts
            self._edge_disponible = True
            self._usar_edge = True
            self._voz_disponible = True
            return True
        except Exception:
            return False

    def _inicializar(self):
        # Escanear voces disponibles
        self._escanear_voces()

        if self._preferir_natural:
            self._inicializar_edge()
            if self._voz_disponible:
                return

        # Estrategia 1: WinRT (OneCore)
        try:
            import winrt.windows.media.speechsynthesis as ws
            synth = ws.SpeechSynthesizer()
            for v in ws.SpeechSynthesizer.all_voices:
                if v.display_name == "Microsoft Pablo":
                    synth.voice = v
                    self._synth_winrt = synth
                    self._usar_winrt = True
                    self._voz_disponible = True
                    break
            if not self._synth_winrt:
                for v in ws.SpeechSynthesizer.all_voices:
                    if "spanish" in v.language.lower() or "es-" in v.language.lower():
                        synth.voice = v
                        self._synth_winrt = synth
                        self._usar_winrt = True
                        self._voz_disponible = True
                        break
            if self._usar_winrt:
                return
        except Exception:
            pass

        # Estrategia 2: win32com SAPI
        try:
            import win32com.client
            self._engine = win32com.client.Dispatch("SAPI.SpVoice")
            voices = self._engine.GetVoices()
            if voices.Count > 0:
                self._voz_disponible = True
                for i in range(voices.Count):
                    desc = voices.Item(i).GetDescription()
                    if "spanish" in desc.lower() or "español" in desc.lower() or "helena" in desc.lower():
                        self._engine.Voice = voices.Item(i)
                        break
                return
        except Exception:
            pass

        # Estrategia 3: PowerShell SAPI
        try:
            test = subprocess.run(
                ["powershell", "-c", "(New-Object -ComObject SAPI.SpVoice).Speak('test')"],
                capture_output=True, timeout=5
            )
            if test.returncode == 0:
                self._usar_powershell = True
                self._voz_disponible = True
                return
        except Exception:
            pass

        self._voz_disponible = False

    def _escanear_voces(self):
        """Escanea todas las voces disponibles del sistema."""
        self._voces = []
        vistos = set()

        # Voces edge-tts (online)
        for key, nombre in self.VOCES_EDGE.items():
            self._voces.append({
                "id": key,
                "nombre": nombre,
                "fuente": "edge",
                "online": True,
            })
            vistos.add(key)

        # Voces WinRT (OneCore)
        try:
            import winrt.windows.media.speechsynthesis as ws
            for v in ws.SpeechSynthesizer.all_voices:
                vid = f"winrt-{v.display_name}"
                if vid not in vistos:
                    self._voces.append({
                        "id": f"winrt:{v.display_name}",
                        "nombre": f"{v.display_name} ({v.language})",
                        "fuente": "winrt",
                        "online": False,
                    })
                    vistos.add(vid)
        except Exception:
            pass

        # Voces SAPI
        try:
            import win32com.client
            engine = win32com.client.Dispatch("SAPI.SpVoice")
            for i in range(engine.GetVoices().Count):
                v = engine.GetVoices().Item(i)
                desc = v.GetDescription()
                sid = f"sapi-{desc}"
                if sid not in vistos:
                    self._voces.append({
                        "id": f"sapi:{desc}",
                        "nombre": desc,
                        "fuente": "sapi",
                        "online": False,
                    })
                    vistos.add(sid)
        except Exception:
            pass

    def listar_voces(self) -> list:
        return list(self._voces)

    def seleccionar_voz(self, voz_id: str) -> bool:
        """Intenta cambiar a la voz especificada. Retorna True si tuvo éxito."""
        self._voz_seleccionada = voz_id
        if voz_id.startswith("winrt:"):
            nombre = voz_id.replace("winrt:", "")
            self._voz_actual = voz_id
            return self._seleccionar_winrt(nombre)
        elif voz_id.startswith("sapi:"):
            desc = voz_id.replace("sapi:", "")
            self._voz_actual = voz_id
            return self._seleccionar_sapi(desc)
        else:
            # edge-tts voice ID directa
            if voz_id in self.VOCES_EDGE:
                ok = self._inicializar_edge()
                if ok:
                    self._edge_voice = voz_id
                    self._voz_actual = voz_id
                    self._usar_edge = True
                    self._usar_winrt = False
                    self._engine = None
                    self._usar_powershell = False
                    return True
        return False

    def _seleccionar_winrt(self, nombre: str) -> bool:
        try:
            import winrt.windows.media.speechsynthesis as ws
            synth = ws.SpeechSynthesizer()
            for v in ws.SpeechSynthesizer.all_voices:
                if v.display_name == nombre:
                    synth.voice = v
                    self._synth_winrt = synth
                    self._usar_winrt = True
                    self._usar_edge = False
                    self._voz_disponible = True
                    self._engine = None
                    self._usar_powershell = False
                    return True
        except Exception:
            pass
        return False

    def _seleccionar_sapi(self, desc: str) -> bool:
        try:
            import win32com.client
            engine = win32com.client.Dispatch("SAPI.SpVoice")
            for i in range(engine.GetVoices().Count):
                v = engine.GetVoices().Item(i)
                if v.GetDescription() == desc:
                    engine.Voice = v
                    self._engine = engine
                    self._usar_winrt = False
                    self._usar_edge = False
                    self._usar_powershell = False
                    self._voz_disponible = True
                    return True
        except Exception:
            pass
        return False

    _lock = threading.Lock()

    def decir(self, texto: str, esperar: bool = True):
        if not texto or not self._voz_disponible:
            return
        if not self._lock.acquire(blocking=True, timeout=120):
            return
        try:
            if self._edge_voice and self._usar_edge:
                self._hablar_edge(texto, esperar)
            elif self._usar_winrt:
                self._hablar_winrt(texto)
            elif self._engine:
                import threading, ctypes
                done = threading.Event()
                def _speak():
                    try:
                        self._engine.Speak(texto, 0 if esperar else 1)
                    finally:
                        done.set()
                t = threading.Thread(target=_speak, daemon=True)
                t.start()
                if not done.wait(timeout=120):
                    try:
                        self._engine.Skip("Sentence", 1000000)
                    except Exception:
                        pass
            elif self._usar_powershell:
                ps_cmd = f"(New-Object -ComObject SAPI.SpVoice).Speak('{self._escapar(texto)}')"
                subprocess.run(["powershell", "-c", ps_cmd],
                             capture_output=True, timeout=120)
        except Exception:
            pass
        finally:
            self._lock.release()

    def _hablar_edge(self, texto: str, esperar: bool = True):
        import asyncio, edge_tts, tempfile, os, ctypes
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _sintetizar():
                communicate = edge_tts.Communicate(texto, self._edge_voice)
                fpath = os.path.join(tempfile.gettempdir(), "jarvis_tts.mp3")
                await asyncio.wait_for(communicate.save(fpath), timeout=60)
                winmm = ctypes.windll.winmm
                alias = "jarvis_tts"
                winmm.mciSendStringW(f'open "{fpath}" type mpegvideo alias {alias}', None, 0, 0)
                if esperar:
                    winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
                    winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                else:
                    winmm.mciSendStringW(f'play {alias}', None, 0, 0)
            loop.run_until_complete(_sintetizar())
        finally:
            loop.close()

    def _hablar_winrt(self, texto: str):
        import asyncio, tempfile, os, ctypes
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._sintetizar(texto))
        finally:
            loop.close()

    async def _sintetizar(self, texto: str):
        import winrt.windows.media.speechsynthesis as ws
        import winrt.windows.storage.streams as streams
        import tempfile, os, ctypes

        stream = await self._synth_winrt.synthesize_text_to_stream_async(texto)
        reader = streams.DataReader(stream.get_input_stream_at(0))
        await reader.load_async(stream.size)
        buffer = bytearray(stream.size)
        reader.read_bytes(buffer)

        fpath = os.path.join(tempfile.gettempdir(), "jarvis_tts.wav")
        with open(fpath, "wb") as f:
            f.write(bytes(buffer))

        winmm = ctypes.windll.winmm
        alias = "jarvis_tts"
        winmm.mciSendStringW(f'open "{fpath}" type waveaudio alias {alias}', None, 0, 0)
        winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
        winmm.mciSendStringW(f'close {alias}', None, 0, 0)

    def decir_async(self, texto: str):
        t = threading.Thread(target=self.decir, args=(texto, True), daemon=True)
        t.start()

    def _escapar(self, texto: str) -> str:
        return texto.replace("'", "''").replace('"', '""')

    def detener(self):
        try:
            import ctypes
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW("stop jarvis_tts", None, 0, 0)
            winmm.mciSendStringW("close jarvis_tts", None, 0, 0)
        except Exception:
            pass
        if self._engine:
            try:
                self._engine.Skip("Sentence", 1000000)
            except Exception:
                pass

    @property
    def disponible(self) -> bool:
        return self._voz_disponible

    @property
    def voz_actual(self) -> str:
        return self._voz_actual or ""

    @property
    def edge_voice(self) -> str:
        return self._edge_voice if hasattr(self, '_edge_voice') else ""


# ====================================================================
# VOZ A TEXTO (STT)
# ====================================================================

class JarvisSTT:
    """Reconocimiento de voz: graba con pyaudio + reconoce con PowerShell."""

    def __init__(self):
        self._disponible = False
        self._p = None
        self._mejor_device = None
        try:
            import pyaudio
            self._p = pyaudio.PyAudio()
            self._disponible = True
            self._cachear_mejor_device()
        except Exception:
            pass

    def _cachear_mejor_device(self):
        import pyaudio
        import struct
        import math
        import sys

        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000

        def probar_dev(dev_id):
            try:
                s = self._p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                                 input=True, input_device_index=dev_id,
                                 frames_per_buffer=CHUNK)
                frames = []
                for _ in range(6):
                    data = s.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                s.stop_stream()
                s.close()
                raw = b"".join(frames)
                samples = struct.unpack_from("<" + "h" * (len(raw) // 2), raw)
                if samples:
                    return int(math.sqrt(sum(x * x for x in samples) / len(samples)))
                return 0
            except Exception:
                return 0

        mejor_rms = 0
        mejor_id = None
        count = self._p.get_device_count()
        for i in range(count):
            try:
                info = self._p.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    name = info.get("name", "")
                    if "Sound Mapper" in name or "Controlador primario" in name:
                        continue
                    avg = probar_dev(i)
                    if avg > mejor_rms:
                        mejor_rms = avg
                        mejor_id = i
            except Exception:
                continue

        self._mejor_device = mejor_id if mejor_id is not None else 0
        sys.stderr.write(f"[STT] mejor dispositivo: #{self._mejor_device} (RMS={mejor_rms})\n")
        sys.stderr.flush()

    def escuchar(self, timeout: float = 8.0) -> str:
        script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "stt.ps1")
        if not os.path.exists(script):
            return ""
        segundos = max(3, min(int(timeout), 15))
        try:
            r = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", script, str(segundos)],
                capture_output=True, text=True, timeout=segundos + 8
            )
            salida = r.stdout.strip()
            if salida.startswith("OK:"):
                return salida[3:].strip()
        except Exception as e:
            import sys
            sys.stderr.write(f"[STT] error PowerShell: {e}\n")
            sys.stderr.flush()
        return ""

    def _normalizar_audio(self, raw_data: bytes) -> bytes:
        import struct, math
        samples = struct.unpack_from("<" + "h" * (len(raw_data) // 2), raw_data)
        if not samples:
            return raw_data
        max_val = max(abs(s) for s in samples)
        if max_val < 100 or max_val > 32000:
            return raw_data
        factor = 32767.0 / max_val
        norm = [max(-32768, min(32767, int(s * factor))) for s in samples]
        return struct.pack("<" + "h" * len(norm), *norm)

    @property
    def disponible(self) -> bool:
        return self._disponible
