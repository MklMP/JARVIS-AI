import requests
from .base import ModuleBase
from utils.emoji import PERIODICO


class NewsModule(ModuleBase):
    """MÃ³dulo de noticias - NewsAPI."""

    def execute(self, command: str, **kwargs) -> str:
        parts = command.lower().split()

        # Buscar categorÃ­a o tema
        tema = kwargs.get("tema", "")
        if not tema:
            for p in parts:
                if p not in ("noticias", "news", "noticia", "de", "sobre", "las", "los"):
                    tema = p
                    break

        categoria = kwargs.get("categoria", "general")
        if "tecnologÃ­a" in command.lower() or "tech" in command.lower():
            categoria = "technology"
            tema = ""
        elif "deportes" in command.lower() or "sports" in command.lower():
            categoria = "sports"
            tema = ""
        elif "negocios" in command.lower() or "business" in command.lower():
            categoria = "business"
            tema = ""
        elif "ciencia" in command.lower() or "science" in command.lower():
            categoria = "science"
            tema = ""
        elif "entretenimiento" in command.lower():
            categoria = "entertainment"
            tema = ""
        elif "salud" in command.lower() or "health" in command.lower():
            categoria = "health"
            tema = ""

        if tema:
            return self._buscar_por_tema(tema)
        return self._top_headlines(categoria)

    def _top_headlines(self, categoria: str = "general") -> str:
        api_key = self.api_keys.get("newsapi", "")
        if not api_key:
            return ("⚠️ API Key de NewsAPI no configurada.\n"
                    "    RegÃ­strate gratis en https://newsapi.org/register\n"
                    "    y agrega tu clave en el archivo .env:\n"
                    "    NEWSAPI_API_KEY=tu_clave_aqui")

        idioma = self.config.get("language", "es")

        # Free NewsAPI: top-headlines solo con country=us,
        # pero everything con query funciona en cualquier idioma
        if idioma == "es":
            return self._buscar_por_tema(categoria)

        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "country": "us",
            "category": categoria,
            "apiKey": api_key,
            "pageSize": 8,
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 426:
                return "⚠️ NewsAPI requiere un plan de pago para esta funciÃ³n. Prueba con una API Key deå¼€å‘è€… (developer tier)."
            resp.raise_for_status()
            data = resp.json()

            if data["status"] != "ok" or not data["articles"]:
                return f"No encontrÃ© noticias de '{categoria}'."

            resultado = f"  {PERIODICO}  TOP NOTICIAS - {categoria.upper()}\n"
            resultado += "  --------------------------------------------------\n"
            for i, art in enumerate(data["articles"][:8], 1):
                titulo = art["title"] or "Sin tÃ­tulo"
                fuente = art["source"]["name"] if art.get("source") else "Desconocida"
                resultado += f"  {i}. {titulo}\n"
                resultado += f"     ({fuente})\n\n"
            return resultado

        except requests.exceptions.Timeout:
            return "⚠️ No pude contactar el servidor de noticias (timeout)."
        except requests.exceptions.ConnectionError:
            return "⚠️ Error de conexiÃ³n. Â¿EstÃ¡s conectado a internet?"
        except Exception as e:
            return f"⚠️ Error obteniendo noticias: {e}"

    def _buscar_por_tema(self, tema: str) -> str:
        api_key = self.api_keys.get("newsapi", "")
        if not api_key:
            return ("⚠️ API Key de NewsAPI no configurada.\n"
                    "    RegÃ­strate gratis en https://newsapi.org/register")

        idioma = self.config.get("language", "es")

        # Mapeo de categorÃ­as tÃ©cnicas a espaÃ±ol para mejor bÃºsqueda
        mapa_cat = {
            "technology": "tecnologÃ­a",
            "sports": "deportes",
            "business": "negocios economÃ­a",
            "science": "ciencia",
            "entertainment": "entretenimiento",
            "health": "salud",
            "general": "noticias",
        }
        q = mapa_cat.get(tema, tema) if idioma == "es" else tema

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": q,
            "apiKey": api_key,
            "pageSize": 8,
            "language": idioma,
            "sortBy": "publishedAt",
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data["status"] != "ok" or not data["articles"]:
                return f"No encontrÃ© noticias sobre '{tema}'."

            resultado = f"  {PERIODICO}  NOTICIAS SOBRE: {tema.upper()}\n"
            resultado += "  -------------------------------------------------\n"
            for i, art in enumerate(data["articles"][:8], 1):
                titulo = art["title"] or "Sin tÃ­tulo"
                fuente = art["source"]["name"] if art.get("source") else "Desconocida"
                fecha = art["publishedAt"][:10] if art.get("publishedAt") else ""
                resultado += f"  {i}. {titulo}\n"
                resultado += f"     ({fuente}) - {fecha}\n\n"
            return resultado

        except Exception as e:
            return f"⚠️ Error buscando noticias: {e}"

    def help(self) -> str:
        return (
            "Uso: noticias [categorÃ­a|tema]\n"
            "CategorÃ­as: tecnologÃ­a, deportes, negocios, ciencia, entretenimiento, salud\n"
            "Ej:  noticias\n"
            "     noticias tecnologÃ­a\n"
            "     noticias inteligencia artificial\n\n"
            "Nota: Necesitas una API Key gratuita de NewsAPI.\n"
            "      RegÃ­strate en: https://newsapi.org/register"
        )

