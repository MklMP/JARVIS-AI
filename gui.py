#!/usr/bin/env python3
"""
JARVIS - Interfaz Gráfica
~~~~~~~~~~~~~~~~~~~~~~~~~~
GUI estilo HUD de Tony Stark con soporte de voz.
"""

import sys
import os
import threading
import queue
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
    import tkinter.font as tkfont
except ImportError:
    print("⚠️ tkinter no está instalado. En Windows viene con Python por defecto.")
    sys.exit(1)

from main import JarvisCore
from utils.voice import JarvisTTS, JarvisSTT
from utils.display import formatear_fecha, formatear_hora
from utils.emoji import ROBOT


# ====================================================================
# COLORES ESTILO JARVIS (HUD de Tony Stark)
# ====================================================================

class Colores:
    FONDO = "#0a0a0a"
    FONDO_CHAT = "#111118"
    TEXTO = "#e0e0e0"
    ACENTO = "#00d4ff"
    ACENTO_OSCURO = "#0099cc"
    VERDE = "#00ff88"
    NARANJA = "#ff8800"
    ROJO = "#ff3355"
    BURBUJA_USUARIO = "#1a2a3a"
    BURBUJA_JARVIS = "#0a1a2a"
    BORDE = "#005577"
    INPUT_FONDO = "#1a1a2e"
    TITLE_BG = "#0d0d1a"


# ====================================================================
# INTERFAZ GRÁFICA JARVIS
# ====================================================================

class VentanaJarvis:
    """Ventana principal estilo Jarvis HUD."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JARVIS - Asistente Personal")
        self.root.configure(bg=Colores.FONDO)
        self.root.minsize(800, 600)
        self.root.geometry("900x700+100+50")

        # Núcleo
        self.core = JarvisCore()
        self.tts = JarvisTTS()
        self.stt = JarvisSTT()

        # Obtener módulos específicos
        self.reminders_mod = self.core.modules.get("reminders", {}).get("instance")
        self.health_mod = self.core.modules.get("health", {}).get("instance")

        self.escuchando = False
        self.voz_activa = True
        self.cola_audio = queue.Queue()
        self._ventana_minimizada = False

        self._configurar_estilos()
        self._construir_ui()
        self._bind_teclas()

        # Escuchar respuesta de voz en segundo plano
        self.root.after(100, self._procesar_cola_audio)

        # Verificar recordatorios periódicamente
        self.root.after(5000, self._verificar_recordatorios)

        # Saludar al inicio
        self.root.after(500, self._saludar_inicio)

    def _configurar_estilos(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Jarvis.TButton", background=Colores.ACENTO_OSCURO,
                       foreground=Colores.TEXTO, borderwidth=0, focuscolor="none",
                       font=("Consolas", 10))
        style.map("Jarvis.TButton",
                 background=[("active", Colores.ACENTO)],
                 foreground=[("active", "#ffffff")])

    def _construir_ui(self):
        # ============================================================
        # BARRA SUPERIOR
        # ============================================================
        frame_top = tk.Frame(self.root, bg=Colores.TITLE_BG, height=50)
        frame_top.pack(fill=tk.X, side=tk.TOP)

        lbl_titulo = tk.Label(frame_top, text="◆  J A R V I S  ◆",
                              fg=Colores.ACENTO, bg=Colores.TITLE_BG,
                              font=("Consolas", 16, "bold"))
        lbl_titulo.pack(side=tk.LEFT, padx=20, pady=10)

        self.lbl_estado = tk.Label(frame_top, text="● EN LINEA",
                                   fg=Colores.VERDE, bg=Colores.TITLE_BG,
                                   font=("Consolas", 10, "bold"))
        self.lbl_estado.pack(side=tk.RIGHT, padx=20, pady=10)

        # Separador
        sep = tk.Frame(self.root, bg=Colores.ACENTO, height=2)
        sep.pack(fill=tk.X, side=tk.TOP)

        # ============================================================
        # ÁREA DE CHAT
        # ============================================================
        frame_chat = tk.Frame(self.root, bg=Colores.FONDO_CHAT)
        frame_chat.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        self.txt_chat = tk.Text(frame_chat, bg=Colores.FONDO_CHAT,
                                fg=Colores.TEXTO, font=("Consolas", 11),
                                relief=tk.FLAT, bd=0, wrap=tk.WORD,
                                state=tk.DISABLED, padx=10, pady=10,
                                insertbackground=Colores.ACENTO,
                                highlightthickness=0, cursor="arrow")
        self.txt_chat.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = tk.Scrollbar(frame_chat, command=self.txt_chat.yview,
                                 bg=Colores.FONDO, troughcolor=Colores.FONDO_CHAT,
                                 activebackground=Colores.ACENTO)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.txt_chat.config(yscrollcommand=scrollbar.set)

        # Tags de colores
        self.txt_chat.tag_config("sistema", foreground=Colores.ACENTO,
                                 font=("Consolas", 9, "italic"))
        self.txt_chat.tag_config("jarvis", foreground=Colores.ACENTO,
                                 font=("Consolas", 11, "bold"))
        self.txt_chat.tag_config("jarvis_body", foreground=Colores.TEXTO,
                                 font=("Consolas", 11))
        self.txt_chat.tag_config("usuario", foreground=Colores.VERDE,
                                 font=("Consolas", 11, "bold"))
        self.txt_chat.tag_config("error", foreground=Colores.NARANJA,
                                 font=("Consolas", 11))

        # ============================================================
        # BARRA INFERIOR (INPUT)
        # ============================================================
        frame_input = tk.Frame(self.root, bg=Colores.FONDO)
        frame_input.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(5, 10))

        # Botón micro
        self.btn_micro = tk.Button(frame_input, text="🎤",
                                   font=("Segoe UI", 12),
                                   bg=Colores.INPUT_FONDO, fg=Colores.TEXTO,
                                   relief=tk.FLAT, bd=0, padx=15, pady=8,
                                   activebackground=Colores.ACENTO_OSCURO,
                                   activeforeground="white",
                                   cursor="hand2",
                                   command=self._toggle_micro)
        self.btn_micro.pack(side=tk.LEFT, padx=(0, 10))

        # Botón toggle voz
        self.btn_voz = tk.Button(frame_input, text="🔊",
                                 font=("Segoe UI", 12),
                                 bg=Colores.INPUT_FONDO, fg=Colores.VERDE,
                                 relief=tk.FLAT, bd=0, padx=10, pady=8,
                                 activebackground=Colores.ACENTO_OSCURO,
                                 cursor="hand2",
                                 command=self._toggle_voz)
        self.btn_voz.pack(side=tk.LEFT, padx=(0, 10))

        # Campo de texto
        self.entry = tk.Entry(frame_input, bg=Colores.INPUT_FONDO,
                              fg=Colores.TEXTO, font=("Consolas", 12),
                              relief=tk.FLAT, bd=0, insertbackground=Colores.ACENTO,
                              highlightbackground=Colores.BORDE,
                              highlightcolor=Colores.ACENTO,
                              highlightthickness=1)
        self.entry.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 10))
        self.entry.bind("<Return>", self._enviar_comando)

        # Botón enviar
        btn_enviar = tk.Button(frame_input, text="▶ ENVIAR",
                               font=("Consolas", 10, "bold"),
                               bg=Colores.ACENTO_OSCURO, fg=Colores.TEXTO,
                               relief=tk.FLAT, bd=0, padx=15, pady=8,
                               activebackground=Colores.ACENTO,
                               activeforeground="white",
                               cursor="hand2",
                               command=lambda: self._enviar_comando(None))
        btn_enviar.pack(side=tk.RIGHT)

        # Indicador de grabación
        self.lbl_grabando = tk.Label(self.root, text="",
                                     fg=Colores.ROJO, bg=Colores.FONDO,
                                     font=("Consolas", 9, "bold"))

    def _bind_teclas(self):
        self.root.bind("<Control-q>", lambda e: self._salir())
        self.root.bind("<Control-l>", lambda e: self._limpiar_chat())
        self.root.bind("<Control-m>", lambda e: self._toggle_micro())
        self.root.bind("<Unmap>", lambda e: self._on_minimize(e))
        self.root.bind("<Map>", lambda e: self._on_restore(e))

    def _on_minimize(self, event):
        if self.root.state() == "iconic":
            self._ventana_minimizada = True

    def _on_restore(self, event):
        if self._ventana_minimizada:
            self._ventana_minimizada = False

    # ================================================================
    # MENSAJES EN EL CHAT
    # ================================================================

    def _escribir(self, texto: str, tag: str = "jarvis_body"):
        self.txt_chat.config(state=tk.NORMAL)
        if tag in ("jarvis", "usuario", "sistema"):
            self.txt_chat.insert(tk.END, f"  {texto}\n", tag)
        else:
            self.txt_chat.insert(tk.END, f"  {texto}\n", tag)
        self.txt_chat.see(tk.END)
        self.txt_chat.config(state=tk.DISABLED)

    def _escribir_jarvis(self, respuesta: str):
        self.txt_chat.config(state=tk.NORMAL)
        if respuesta.startswith("⚠️") or respuesta.startswith("  ⚠️"):
            self.txt_chat.insert(tk.END, f"\n  ⚠️ {respuesta}\n", "error")
        else:
            lineas = respuesta.strip().split("\n")
            self.txt_chat.insert(tk.END, f"\n  ▸ ", "jarvis")
            for i, linea in enumerate(lineas):
                tag = "jarvis_body" if i > 0 else "jarvis"
                self.txt_chat.insert(tk.END, f"{linea}\n", tag)
        self.txt_chat.see(tk.END)
        self.txt_chat.config(state=tk.DISABLED)

    def _escribir_usuario(self, comando: str):
        self.txt_chat.config(state=tk.NORMAL)
        ahora = datetime.now().strftime("%H:%M")
        self.txt_chat.insert(tk.END, f"\n  [{ahora}] ", "sistema")
        self.txt_chat.insert(tk.END, f"{comando}\n", "usuario")
        self.txt_chat.see(tk.END)
        self.txt_chat.config(state=tk.DISABLED)

    def _limpiar_chat(self):
        self.txt_chat.config(state=tk.NORMAL)
        self.txt_chat.delete(1.0, tk.END)
        self.txt_chat.config(state=tk.DISABLED)

    # ================================================================
    # ENVÍO DE COMANDOS
    # ================================================================

    def _enviar_comando(self, event):
        comando = self.entry.get().strip()
        if not comando:
            return
        self.entry.delete(0, tk.END)
        self._procesar_comando(comando)

    def _procesar_comando(self, comando: str):
        self._escribir_usuario(comando)

        if comando.lower() in ("salir", "exit", "quit"):
            self._salir()
            return

        # Procesar en hilo separado para no bloquear GUI
        threading.Thread(target=self._ejecutar_comando,
                        args=(comando,), daemon=True).start()

    def _ejecutar_comando(self, comando: str):
        try:
            respuesta = self.core.procesar(comando)
            if respuesta == "__EXIT__":
                self.root.after(0, self._salir)
                return
            self.root.after(0, self._mostrar_respuesta, respuesta)
        except Exception as e:
            self.root.after(0, self._mostrar_respuesta, f"⚠️ Error: {e}")

    def _mostrar_respuesta(self, respuesta: str):
        self._escribir_jarvis(respuesta)
        # Leer en voz alta si está activo
        if self.voz_activa:
            texto_voz = self._limpiar_para_voz(respuesta)
            if texto_voz:
                self.cola_audio.put(texto_voz)

    def _limpiar_para_voz(self, texto: str) -> str:
        """Limpia el texto para lectura por voz."""
        # Quitar emojis/iconos al inicio
        import re
        texto = re.sub(r'^\s*\[?\]?\[?\w*\]?\s*', '', texto, count=1)
        # Quitar líneas decorativas
        lineas = []
        for linea in texto.split("\n"):
            if not linea.strip().startswith("-") and not linea.strip().startswith("="):
                lineas.append(linea.strip())
        limpio = ". ".join(l for l in lineas if l).strip()
        return limpio[:300]  # Máximo 300 caracteres para voz

    # ================================================================
    # VOZ
    # ================================================================

    def _toggle_micro(self):
        if self.escuchando:
            self._detener_escucha()
        else:
            self._iniciar_escucha()

    def _iniciar_escucha(self):
        self.escuchando = True
        self.btn_micro.config(bg=Colores.ROJO, text="🔴")

        self.lbl_grabando.config(text="🎤 Escuchando... habla ahora")
        threading.Thread(target=self._capturar_voz, daemon=True).start()

    def _detener_escucha(self):
        self.escuchando = False
        self.btn_micro.config(bg=Colores.INPUT_FONDO, text="🎤")

        self.root.after(0, lambda: self.lbl_grabando.config(text="🎤 Escuchando..."))
        texto = self.stt.escuchar(timeout=5.0, phrase_limit=8.0)
        if texto and not texto.startswith("[Error"):
            self.root.after(0, lambda: self.entry.insert(0, texto))
            self.root.after(0, lambda: self.entry.focus())
            self.root.after(50, lambda: self._enviar_comando(None))
        elif texto:
            self.root.after(0, lambda: self._escribir(texto, "error"))
        self.root.after(0, self._detener_escucha)

    def _toggle_voz(self):
        self.voz_activa = not self.voz_activa
        if self.voz_activa:
            self.btn_voz.config(text="🔊", fg=Colores.VERDE)
        else:
            self.btn_voz.config(text="[TTS-off]", fg=Colores.NARANJA)

    def _procesar_cola_audio(self):
        """Procesa la cola de audio para TTS (en hilo principal)."""
        try:
            while True:
                texto = self.cola_audio.get_nowait()
                if self.voz_activa and self.tts.disponible and not self._ventana_minimizada:
                    threading.Thread(target=self.tts.decir,
                                   args=(texto,), daemon=True).start()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._procesar_cola_audio)

    # ================================================================
    # SALUDO INICIAL
    # ================================================================

    def _verificar_recordatorios(self):
        """Revisa recordatorios pendientes y muestra alertas."""
        if self.reminders_mod:
            alertas = self.reminders_mod.obtener_alertas()
            for alerta in alertas:
                texto = alerta.get("texto", "Recordatorio")
                self._escribir(f"\n  [t] RECORDATORIO: {texto}\n", "sistema")
                if self.voz_activa and self.tts.disponible:
                    self.tts.decir_async(f"Recordatorio: {texto}")
                # Notificación nativa
                from modules.notification_reader import NotificationsModule
                try:
                    notif_mod = NotificationsModule(self.core.config, self.core.api_keys)
                    notif_mod._mostrar_toast("Jarvis - Recordatorio", texto)
                except:
                    pass
        self.root.after(15000, self._verificar_recordatorios)

    def _saludar_inicio(self):
        n_mods = len(self.core.modules)
        estado_tts = "🔊" if self.tts.disponible else "🔇"
        estado_stt = "🎤" if self.stt.disponible else "🎤 (no disponible)"
        saludo = (
            f"\n  ◆ {ROBOT}  JARVIS v{self.core.config.get('version', '1.0')}  ◆\n"
            f"  {'='*45}\n"
            f"  Sistema: {sys.platform}\n"
            f"  TTS {estado_tts} | STT {estado_stt}\n"
            f"  {n_mods} módulos activos\n"
            f"  {'='*45}\n"
            f"  Escribe 'ayuda' para ver comandos\n"
            f"  {'='*45}\n"
        )
        self._escribir(saludo, "sistema")

        if self.health_mod:
            try:
                consejo = self.health_mod._consejo()
                self._escribir("\n" + consejo, "sistema")
            except:
                pass

        if self.voz_activa and self.tts.disponible:
            self.tts.decir_async("Jarvis en línea. ¿En qué puedo ayudarle?")

    # ================================================================
    # CONTROL DE VENTANA
    # ================================================================

    def _salir(self):
        if self.tts.disponible:
            self.tts.decir("Hasta luego.", esperar=False)
        self.root.destroy()

    def ejecutar(self):
        self.root.protocol("WM_DELETE_WINDOW", self._salir)
        self.root.mainloop()


# ====================================================================
# PUNTO DE ENTRADA
# ====================================================================

def main():
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass

    ventana = VentanaJarvis()
    ventana.ejecutar()


if __name__ == "__main__":
    main()
