import os


def cargar_api_keys(path: str = None) -> dict:
    """Carga API keys desde variables de entorno o .env"""
    try:
        from dotenv import load_dotenv
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(path):
            load_dotenv(path)
    except ImportError:
        pass

    return {
        "openweathermap": os.getenv("OPENWEATHERMAP_API_KEY", ""),
        "newsapi": os.getenv("NEWSAPI_API_KEY", ""),
    }
