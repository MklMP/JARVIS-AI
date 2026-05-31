import json
import os
from datetime import datetime


def formatear_fecha(dt: datetime = None) -> str:
    """Devuelve fecha formateada en español."""
    if dt is None:
        dt = datetime.now()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    dia_sem = dias[dt.weekday()]
    dia = dt.day
    mes = meses[dt.month - 1]
    anio = dt.year
    return f"{dia_sem}, {dia} de {mes} de {anio}"


def formatear_hora(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%H:%M:%S")


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")

def cargar_config(path: str = None) -> dict:
    if path is None:
        path = CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_config(data: dict, path: str = None):
    if path is None:
        path = CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cargar_api_keys(path: str = None) -> dict:
    """Carga API keys desde variables de entorno."""
    try:
        from dotenv import load_dotenv
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "..", ".env")
        load_dotenv(path)
    except ImportError:
        pass

    return {
        "openweathermap": os.getenv("OPENWEATHERMAP_API_KEY", ""),
        "newsapi": os.getenv("NEWSAPI_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", ""),
        "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
        "virustotal": os.getenv("VIRUSTOTAL_API_KEY", ""),
    }


def centrar(texto: str, ancho: int = 70) -> str:
    return texto.center(ancho)


def linea(ancho: int = 70, char: str = "=") -> str:
    return char * ancho
