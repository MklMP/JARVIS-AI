# Jarvis - Estructura del Proyecto

```
C:\Users\MKL\Jarvis\
├── main.py              # Punto de entrada - el cerebro de Jarvis
├── jarvis.bat           # Lanzador rápido (doble click en Windows)
├── requirements.txt     # Dependencias
├── .env                 # Tus API Keys (NUNCA compartir)
├── .env.example         # Plantilla de API Keys
│
├── config/
│   └── config.json      # Configuración de Jarvis
│
├── modules/
│   ├── __init__.py
│   ├── base.py          # Clase base ModuleBase + PluginManager
│   ├── weather.py       # Clima (necesita API Key)
│   ├── news.py          # Noticias (necesita API Key)
│   ├── system.py        # Hora, fecha, sistema, CPU, RAM, disco
│   ├── stocks.py        # Bolsa de valores (gratis, sin API Key)
│   └── files.py         # Archivos: crear, leer, listar, carpetas
│
├── utils/
│   ├── __init__.py
│   ├── emoji.py         # Emojis o ASCII según terminal
│   ├── api_client.py    # Cliente HTTP
│   └── display.py       # Formateo de fecha/hora
│
├── plugins/
│   ├── ejemplo.py       # Plugin de ejemplo
│   └── ...              # ¡Agrega tus plugins aquí!
│
└── docs/
    └── ...              # Documentación futura
```

## Cómo empezar

1. **Instalar dependencias:**
   ```powershell
   cd C:\Users\MKL\Jarvis
   pip install -r requirements.txt
   ```

2. **Configurar APIs (opcional):**
   - Ve a https://openweathermap.org/api (gratis)
   - Ve a https://newsapi.org/register (gratis)
   - Copia `.env.example` a `.env` y pega tus claves:
     ```
     OPENWEATHERMAP_API_KEY=tu_clave
     NEWSAPI_API_KEY=tu_clave
     ```

3. **Ejecutar Jarvis:**
   ```powershell
   cd C:\Users\MKL\Jarvis
   python main.py
   ```
   O haz doble click en `jarvis.bat`

## Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `clima <ciudad>` | Clima actual |
| `noticias` | Últimas noticias |
| `noticias <tema>` | Noticias sobre un tema |
| `noticias tecnología` | Noticias de tecnología |
| `bolsa <símbolo>` | Cotización (AAPL, TSLA, BTC-USD...) |
| `hora` | Hora actual |
| `fecha` | Fecha actual |
| `sistema` | Info del PC |
| `cpu` | Estado del procesador |
| `memoria` | Uso de RAM |
| `disco` | Almacenamiento |
| `batería` | Nivel de batería |
| `crear archivo llamado X` | Crea un archivo |
| `crear carpeta llamada X` | Crea una carpeta |
| `listar` | Lista archivos |
| `leer <archivo>` | Lee un archivo |
| `plugins` | Lista plugins instalados |
| `ayuda` | Muestra todos los comandos |
| `salir` | Cierra Jarvis |

## Crear plugins

Crea un archivo `.py` en `plugins/` con una función `register()`:

```python
from modules.base import ModuleBase

class MiPlugin(ModuleBase):
    def execute(self, command, **kwargs):
        return "Mi plugin respondió!"

def register():
    return MiPlugin({"language": "es"}, {})
```

## Notas importantes

- **API Keys**: Sin las claves de OpenWeatherMap y NewsAPI, los módulos de clima y noticias mostrarán instrucciones de configuración. El resto funciona sin API keys.
- **Bolsa**: Usa yfinance, no necesita API key. Símbolos válidos: AAPL, TSLA, MSFT, GOOGL, AMZN, MELI, BTC-USD.
- **Privacidad**: Jarvis corre 100% local. Tus archivos y datos nunca salen de tu máquina.
- **Seguridad**: La función de eliminar archivos está desactivada por seguridad.
