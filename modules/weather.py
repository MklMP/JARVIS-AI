import requests
from .base import ModuleBase
from utils.emoji import NUBE


class WeatherModule(ModuleBase):
    """MÃ³dulo de clima - OpenWeatherMap."""

    def execute(self, command: str, **kwargs) -> str:
        parts = command.lower().split()
        ciudad = kwargs.get("ciudad", "")

        if not ciudad:
            # Buscar ciudad DESPUÃ‰S de "clima", ignorando palabras anteriores
            idx = None
            for i, p in enumerate(parts):
                if p in ("clima", "weather", "temperatura"):
                    idx = i
                    break
            if idx is not None:
                for j in range(idx + 1, len(parts)):
                    if parts[j] not in ("en", "de", "para", "el", "la", "los", "las"):
                        ciudad = " ".join(parts[j:])
                        break
            else:
                # Fallback: primer palabra que no sea stop word
                for p in parts:
                    if p not in ("clima", "weather", "temperatura", "en", "de", "el", "la", "como", "esta", "estÃ¡", "cÃ³mo"):
                        ciudad = p
                        break

        if not ciudad:
            return self.help()

        return self._obtener_clima(ciudad)

    def _obtener_clima(self, ciudad: str) -> str:
        api_key = self.api_keys.get("openweathermap", "")
        if not api_key:
            return ("⚠️ API Key de OpenWeatherMap no configurada.\n"
                    "    RegÃ­strate gratis en https://openweathermap.org/api\n"
                    "    y agrega tu clave en el archivo .env:\n"
                    "    OPENWEATHERMAP_API_KEY=tu_clave_aqui")

        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": ciudad,
            "appid": api_key,
            "units": self.config.get("units", "metric"),
            "lang": self.config.get("language", "es"),
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 404:
                return f"No encontrÃ© la ciudad '{ciudad}'. Â¿Seguro que estÃ¡ bien escrito?"
            if resp.status_code == 401:
                return "API Key invÃ¡lida. Revisa tu OPENWEATHERMAP_API_KEY en el .env"
            resp.raise_for_status()
            data = resp.json()

            temp = data["main"]["temp"]
            sensacion = data["main"]["feels_like"]
            humedad = data["main"]["humidity"]
            desc = data["weather"][0]["description"].capitalize()
            viento = data["wind"]["speed"]
            nombre = data["name"]
            pais = data["sys"]["country"]

            unidad = "Â°C" if self.config.get("units") == "metric" else "Â°F"
            viento_unidad = "m/s" if self.config.get("units") == "metric" else "mph"

            return (
                f"  {NUBE}  Clima en {nombre}, {pais}:\n"
                f"  ----------------------------\n"
                f"  Estado:     {desc}\n"
                f"  Temperatura: {temp}{unidad} (sensaciÃ³n {sensacion}{unidad})\n"
                f"  Humedad:    {humedad}%\n"
                f"  Viento:     {viento} {viento_unidad}\n"
            )
        except requests.exceptions.Timeout:
            return "⚠️ No pude contactar el servidor del clima (timeout)."
        except requests.exceptions.ConnectionError:
            return "⚠️ Error de conexiÃ³n. Â¿EstÃ¡s conectado a internet?"
        except Exception as e:
            return f"⚠️ Error obteniendo clima: {e}"

    def help(self) -> str:
        return (
            "Uso: clima <ciudad>\n"
            "Ej:  clima Londres\n"
            "     clima Mexico City\n"
            "     clima Buenos Aires\n\n"
            "Nota: Necesitas una API Key gratuita de OpenWeatherMap.\n"
            "      RegÃ­strate en: https://openweathermap.org/api"
        )

