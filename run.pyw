#!/usr/bin/env pythonw
"""
run.pyw - Launcher único para Jarvis + Trading System (sin terminal)
Ejecutar: doble clic en este archivo, o pythonw run.pyw
"""
import os
import sys
import subprocess
import webbrowser
import time
import threading
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JARVIS_URL = "http://127.0.0.1:5000"

def _abrir_web():
    """Espera a que el servidor esté listo y abre el navegador."""
    for intento in range(30):
        time.sleep(1)
        try:
            urllib.request.urlopen(JARVIS_URL, timeout=2)
            break
        except Exception:
            continue
    webbrowser.open(JARVIS_URL)

if __name__ == '__main__':
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, 'pythonw.exe')
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    server_script = os.path.join(BASE_DIR, 'server.py')
    proc = subprocess.Popen(
        [pythonw, server_script],
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    threading.Thread(target=_abrir_web, daemon=True).start()
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait(5)
