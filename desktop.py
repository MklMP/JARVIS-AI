#!/usr/bin/env python3
"""
JARVIS - Aplicacion de Escritorio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Lanza el servidor web y el listener de voz en segundo plano.
Ejecutar: python desktop.py
"""

import os
import sys
import subprocess
import threading
import time
import signal

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)


def _iniciar_server():
    """Inicia el servidor Flask en un hilo."""
    from server import app
    host = os.getenv("JARVIS_HOST", "127.0.0.1")
    port = int(os.getenv("JARVIS_PORT", "5000"))
    app.run(host=host, port=port, debug=False, use_reloader=False)


def main():
    from utils.colors import banner_jarvis, incrementar_tiempo

    print(banner_jarvis())
    incrementar_tiempo(0.08)
    print(f"\n  {'=' * 60}")
    print("  Iniciando servidor...")
    hilo_server = threading.Thread(target=_iniciar_server, daemon=True)
    hilo_server.start()

    time.sleep(3)

    print(f"\n  {'=' * 60}")
    print("  JARVIS activo en http://127.0.0.1:5000")
    print("  Da DOS PALMADAS para activar el micro + comando")
    print("  O haz clic en el boton de microfono del navegador")
    print("  Presiona Ctrl+C para salir")
    print(f"  {'=' * 60}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  ** Apagando...")
        os._exit(0)


if __name__ == "__main__":
    main()
