#!/usr/bin/env python3
"""
JARVIS - Asistente Personal con IA
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Un asistente modular tipo Jarvis de Tony Stark.
Versión: 1.0.0
"""

import sys
import os
import json
import difflib
import random
import re
import time
import threading
from datetime import datetime

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.base import PluginManager
from modules.weather import WeatherModule
from modules.news import NewsModule
from modules.system import TimeModule, SystemModule
from modules.stocks import StocksModule
from modules.files import FilesModule
from modules.filesearch import FileSearchModule
from modules.music import MusicModule
from modules.apps import AppsModule
from modules.games import GamesModule
from modules.books import BooksModule
from modules.reminders import RemindersModule
from modules.email_module import EmailModule
from modules.whatsapp import WhatsAppModule
from modules.sistema import SistemaModule
from modules.notification_reader import NotificationsModule
from modules.health import HealthModule
from modules.catalogo import CatalogoModule
from modules.matematicas import MathModule
from modules.virustotal import VirusTotalModule
from modules.aprendizaje import Memoria
from modules.busqueda_web import BuscadorWeb
from modules.gemini_chat import GeminiChat
from modules.openrouter_chat import OpenRouterAgent
from modules.nlu import IntentClassifier, INTENT_SIN_AGENTE, INTENT_ACCION_LOCAL
from modules.memoria_vectorial import MemoriaVectorial
from modules.dir_memory import DirMemory
from utils.display import centrar, linea, formatear_fecha, formatear_hora, cargar_config, guardar_config, cargar_api_keys
from utils.emoji import ROBOT, NUBE, PERIODICO, GRAFICO, COMPUTADORA, CARPETA, RELON, PENSANDO, LIBRO, PERGAMINO, ENCHUFE, BATERIA, MEMORIA, DISCO, ARCHIVO, CALENDARIO, PELICULA
from utils.colors import logo_colorido, incrementar_tiempo
from datetime import datetime


# ============================================================
# CONFIGURACIÓN
# ============================================================

CONFIG = cargar_config()
API_KEYS = cargar_api_keys()

NAME = CONFIG.get("name", "Jarvis")
VERSION = CONFIG.get("version", "2.0.0")


# ============================================================
# MÓDULOS
# ============================================================

class JarvisCore:
    """Núcleo de Jarvis - orquesta los módulos."""

    def __init__(self):
        self.config = CONFIG
        self.api_keys = API_KEYS
        self.modules = {}
        self.plugin_manager = PluginManager(CONFIG.get("plugins_dir", "plugins"))
        self.history = []
        self._ultima_sugerencia = None  # (mod_key, reformulado)
        self._pendiente_busqueda = None  # (query, tipo) donde tipo=local/internet
        self._pendiente_archivo = None  # {"nombre": ..., "contenido": ...} para preguntar ruta
        self._contador_comandos = 0
        self._motores_seleccionados = ["duckduckgo"]
        self._tema_actual = ""
        self._ultima_respuesta_tema = ""
        self._pendiente_persona = None
        self._pendiente_articulo = None
        self._ultimo_simbolo_analizado = ""

        self._ultimo_comando = ""
        self._ultima_respuesta = ""
        self._conversation = []  # [(comando_usuario, respuesta_asistente), ...]
        self.memoria = Memoria()
        self.buscador_web = BuscadorWeb()
        gemini_key = self.api_keys.get("gemini", "")
        self.gemini = GeminiChat(gemini_key) if gemini_key else None
        openrouter_key = self.api_keys.get("openrouter", "")
        self.openrouter = OpenRouterAgent(openrouter_key, buscador_web=self.buscador_web) if openrouter_key else None
        self.nlu = IntentClassifier()
        self.memoria_vec = MemoriaVectorial()
        self.dir_mem = DirMemory()
        self._cargar_modulos()

    def _cargar_modulos(self):
        """Carga los módulos según la configuración."""
        mod_config = self.config.get("modules", {})

        mod_map = {
            "weather": ("clima", WeatherModule),
            "news": ("noticias", NewsModule),
            "time": ("hora", TimeModule),
            "system": ("sistema", SystemModule),
            "stocks": ("bolsa", StocksModule),
            "files": ("archivos", FilesModule),
            "filesearch": ("busqueda", FileSearchModule),
            "music": ("musica", MusicModule),
            "apps": ("aplicaciones", AppsModule),
            "games": ("juegos", GamesModule),
            "books": ("libros", BooksModule),
            "reminders": ("recordatorios", RemindersModule),
            "email_module": ("correo", EmailModule),
            "whatsapp": ("whatsapp", WhatsAppModule),
            "notifications": ("notificaciones", NotificationsModule),
            "health": ("salud", HealthModule),
            "catalogo": ("catalogo", CatalogoModule),
            "matematicas": ("matematicas", MathModule),
            "sistema_avanzado": ("sistema_avanzado", SistemaModule),
            "virustotal": ("virustotal", VirusTotalModule),
        }

        for key, (name, mod_class) in mod_map.items():
            if mod_config.get(key, {}).get("enabled", True):
                instance = mod_class(self.config, self.api_keys)
                self.modules[key] = {
                    "name": name,
                    "instance": instance,
                    "keywords": self._get_keywords_for(key),
                }
                # Conectar modulo files con core para preguntar rutas
                if key == "files" and hasattr(instance, "set_core"):
                    instance.set_core(self)

        # Cargar plugins
        self.plugin_manager.discover()

    def _get_keywords_for(self, key: str) -> list:
        keywords = {
            "weather": ["clima", "weather", "temperatura", "tiempo", "lluvia", "soleado",
                        "frio", "calor", "humedad", "viento"],
            "news": ["noticias", "news", "noticia", "novedades", "actualidad"],
            "time": ["hora", "tiempo", "fecha", "hoy", "día", "dia", "que hora", "qué hora",
                     "que día", "qué día", "alarma"],
            "system": ["sistema", "pc", "computadora", "cpu", "procesador",
                       "disco", "batería", "bateria", "memoria", "informacion"],
            "stocks": ["bolsa", "stock", "accion", "acciones", "mercado", "cotización",
                       "cotizacion", "inversión", "inversion", "precio", "valor",
                       "cotiza", "invertir", "empresa", "empresas",
                       "bitcoin", "btc", "ethereum", "crypto", "cripto"],
            "files": ["archivo", "archivos", "crear", "listar", "leer", "carpeta",
                      "directorio", "mkdir", "documento"],
            "filesearch": ["buscar", "search", "find", "encuentra", "donde esta",
                           "dónde está", "encuentrame"],
            "music": ["musica", "música", "music", "canción", "cancion", "song", "reproduce",
                       "play", "pon", "siguiente", "next", "pausa", "pause", "lista",
                       "playlist", "volumen", "aleatorio", "shuffle", "busca", "buscar"],
            "apps": ["abrir", "open", "lanzar", "cerrar", "kill", "programas",
                     "aplicaciones", "apps", "bloc de notas", "calculadora", "chrome",
                     "word", "excel", "spotify", "vscode", "cmd"],
            "games": ["juego", "juegos", "jugar", "juega", "partida", "partidita",
                      "dota", "lol", "league", "minecraft", "fortnite", "csgo",
                      "steam", "epic", "gog", "battle", "blizzard", "origin",
                      "rocket", "valorant", "warzone", "apex", "pubg",
                      "abrir juego", "lanzar juego"],
            "books": ["libro", "libros", "pdf", "lectura", "leer", "ebook",
                      "epub", "principito", "quijote", "cervantes",
                      "que libros tengo", "lista libros", "abrir libro"],
            "reminders": ["recordatorio", "recordar", "remind", "recuerdame",
                          "alarma", "despertador", "pendientes"],
            "email_module": ["correo", "email", "mail", "bandeja", "inbox",
                             "enviar correo", "enviar email"],
            "whatsapp": ["whatsapp", "wa", "whats"],
            "notifications": ["notificacion", "notificación", "notif", "toast",
                              "envia notificacion", "avísame", "avisame"],
            "health": ["salud", "health", "pulso", "corazon", "estres", "estrés",
                       "consejo", "sueno", "sueño", "sleep", "smartwatch",
                       "tendencias", "biometrico", "biométrico"],
            "sistema_avanzado": ["disco", "discos", "fragmentacion", "fragmentación",
                                "backup", "backups", "copia", "copiar", "usb",
                                "espacio", "almacenamiento", "copia de seguridad",
                                "desfragmentar", "analizar disco"],
            "sistema_avanzado": ["disco", "discos", "fragmentacion", "fragmentación",
                                "backup", "backups", "copia", "copiar", "usb",
                                "espacio", "almacenamiento", "copia de seguridad",
                                "desfragmentar", "analizar disco"],
            "catalogo": ["catalogo", "catálogo", "película", "pelicula", "películas",
                         "peliculas", "filmoteca", "videoteca", "mis pelis",
                         "lista pelis", "reproduce", "elige", "selecciona",
                         "escanea películas", "actualizar catalogo", "mis películas"],
            "matematicas": ["matematica", "matematicas", "matemática", "matemáticas", "calcula", "calcular",
                            "cuanto es", "cuánto es", "cuanto da", "cuánto da", "resuelve",
                            "raiz", "raíz", "sqrt", "elevado", "potencia", "derivada",
                            "integral", "ecuacion", "ecuación", "logaritmo", "seno", "coseno",
                            "tangente", "trigonometria", "trigonometría", "algebra", "álgebra"],
            "virustotal": ["virustotal", "virus", "analizar archivo", "escanear archivo",
                           "malware", "antivirus"],
        }
        return keywords.get(key, [])

    def procesar(self, comando: str, motores: list = None) -> str:
        """Procesa un comando y devuelve respuesta."""
        if motores is not None:
            self._motores_seleccionados = motores
        if not comando or not comando.strip():
            return ""

        comando = comando.strip()
        self.history.append(comando)
        self._cmd_original = comando  # preservar para base64 (case-sensitive)
        cmd_lower = comando.lower()

        # Wake word: si el comando empieza con "jarvis", quitarlo
        cmd_lower = re.sub(r'^(jarvis|hey\s*jarvis|ok\s*jarvis|jarviz|jarvs)\W*', '', cmd_lower, flags=re.IGNORECASE).strip()
        if cmd_lower != comando.lower().strip():
            if not cmd_lower:
                return f"  {PENSANDO}  Dime, ¿en qué puedo ayudarte?"
            comando = cmd_lower

        # Respuesta a busqueda pendiente: "local" / "internet" / "youtube"
        if self._pendiente_busqueda:
            query, _ = self._pendiente_busqueda
            if re.search(r'\b(local|computadora|pc|disco|archivos|escritorio|descargas|musica|música|cancion|canciones|video|videos|pelicula|peliculas)\b', cmd_lower):
                self._pendiente_busqueda = None
                return self._buscar_local(query)
            if re.search(r'\b(internet|navegador|web|youtube|google|online|nube|chrome|firefox|edge)\b', cmd_lower):
                self._pendiente_busqueda = None
                if not self._tiene_internet():
                    return f"  No tengo acceso a internet ahora mismo. Buscaré '{query}' en tu computadora.\n{self._buscar_local(query)}"
                return self._buscar_internet(query)
            # No match: clear stale pending search so it doesn't poison future commands
            self._pendiente_busqueda = None

        # Respuesta a ruta pendiente para crear archivo (solo si el comando parece una ruta)
        if self._pendiente_archivo:
            ruta = comando.strip().strip('"').strip("'")
            es_ruta = False
            if os.path.isdir(ruta):
                es_ruta = True
            elif os.path.isdir(os.path.join(os.path.expanduser("~"), ruta)):
                es_ruta = True
                ruta = os.path.join(os.path.expanduser("~"), ruta)
            if es_ruta:
                info = self._pendiente_archivo
                self._pendiente_archivo = None
                return self.modules["files"]["instance"].execute(
                    info["comando"], nombre=info["nombre"], ruta=ruta
                )
            # No parece ruta, limpiar pendiente y procesar comando normalmente
            self._pendiente_archivo = None

        # Respuesta a ruta pendiente para juego (usuario dio carpeta)
        games_mod = self.modules.get("games")
        if games_mod and games_mod["instance"]._pendiente_ruta:
            return games_mod["instance"].execute(comando)

        # Respuesta a ruta pendiente para música (usuario dio carpeta)
        music_mod = self.modules.get("music")
        if music_mod and music_mod["instance"]._pendiente_ruta:
            return music_mod["instance"].execute(comando)

        # Respuesta a ruta pendiente para libro
        books_mod = self.modules.get("books")
        if books_mod and books_mod["instance"]._pendiente_ruta:
            return books_mod["instance"].execute(comando)

        # Respuesta a seleccion pendiente de libro (elegir número o cualquiera)
        if books_mod and books_mod["instance"]._pendiente_seleccion:
            return books_mod["instance"].execute(comando)

        # Respuesta a accion pendiente de libro (abrir o leer)
        if books_mod and books_mod["instance"]._pendiente_accion:
            return books_mod["instance"].execute(comando)

        # Afirmacion con sugerencia pendiente: "si" / "sí" / "vale" después de sugerencia
        if self._ultima_sugerencia:
            if re.search(r'\b(s[ií]|sip|yep|yes|ok|okey|dale|claro|vamos|adelante|de[ea]cuerdo|correcto|simon|simón)\b', cmd_lower):
                mod_key, reformulado = self._ultima_sugerencia
                self._ultima_sugerencia = None
                if mod_key in self.modules:
                    return self.modules[mod_key]["instance"].execute(reformulado)
                elif mod_key == "browser_search":
                    import webbrowser
                    webbrowser.open(f"https://www.google.com/search?q={reformulado.replace(' ', '+')}")
                    return f"  Buscando '{reformulado}' en el navegador..."
                return f"  Procesando: {reformulado}"

        # Comandos especiales del nucleo
        if cmd_lower in ("salir", "exit", "quit", "chau", "adios", "adios", "nos vemos"):
            return "__EXIT__"
        if cmd_lower in ("ayuda", "help", "comandos", "que puedes hacer", "que puedes hacer"):
            return self._ayuda()
        if cmd_lower in ("historial", "history"):
            return self._mostrar_historial()

        # Intent parser: entiende lenguaje natural y reformula
        intents = self._parse_intent(cmd_lower, comando)
        if intents:
            respuestas = []
            for mod_key, cmd_reformulado in intents:
                if mod_key in self.modules:
                    try:
                        r = self.modules[mod_key]["instance"].execute(cmd_reformulado)
                        respuestas.append(str(r) if not isinstance(r, str) else r)
                    except Exception as e:
                        respuestas.append(f"⚠️ Error en modulo: {e}")
                elif mod_key == "__open_url__":
                    import webbrowser
                    webbrowser.open(cmd_reformulado)
                    if "google.com/maps" in cmd_reformulado:
                        from urllib.parse import unquote, urlparse, parse_qs
                        parsed = urlparse(cmd_reformulado)
                        if "/search/" in parsed.path:
                            query_unquote = unquote(parsed.path.split("/search/")[1].replace("+", " "))
                            respuestas.append(f"  Abriendo Google Maps en {query_unquote}")
                        else:
                            respuestas.append("  Abriendo Google Maps")
                    else:
                        respuestas.append(f"  Abriendo {cmd_reformulado}...")
                elif mod_key == "__pregunta__":
                    respuestas.append(cmd_reformulado)
                elif mod_key == "__continue__":
                    respuestas.append("__CONTINUE__")
                elif mod_key == "__browser_search__":
                    import webbrowser
                    sitios_directos = {"youtube", "facebook", "twitter", "x", "instagram",
                                       "reddit", "twitch", "github", "linkedin", "tiktok"}
                    if cmd_reformulado.lower() in sitios_directos:
                        url = f"https://www.{cmd_reformulado.lower()}.com"
                    else:
                        url = f"https://www.google.com/search?q={cmd_reformulado.replace(' ', '+')}"
                    webbrowser.open(url)
                    respuestas.append(f"  Abriendo '{cmd_reformulado}' en el navegador...")
                elif mod_key == "__direct__":
                    respuestas.append(cmd_reformulado)
                elif mod_key == "__local_search__":
                    respuestas.append(self._buscar_local(cmd_reformulado))
                elif mod_key == "__shutdown__":
                    import subprocess
                    accion = cmd_reformulado
                    if accion == "cancelar":
                        subprocess.run(["shutdown", "/a"], capture_output=True)
                        respuestas.append("  Apagado cancelado.")
                    elif accion == "reiniciar":
                        respuestas.append("  Reiniciando el equipo en 10 segundos...")
                        threading.Thread(target=lambda: (time.sleep(3), subprocess.run(["shutdown", "/r", "/t", "7"], capture_output=True)), daemon=True).start()
                    else:
                        respuestas.append("  Apagando el equipo en 10 segundos...")
                        threading.Thread(target=lambda: (time.sleep(3), subprocess.run(["shutdown", "/s", "/t", "7"], capture_output=True)), daemon=True).start()
                elif mod_key == "__movie_info__":
                    idx = int(cmd_reformulado) - 1
                    mod = self.modules.get("catalogo")
                    if mod and 0 <= idx < len(mod["instance"]._catalogo):
                        peli = mod["instance"]._catalogo[idx]
                        nombre = peli["nombre"]
                        # Buscar info en internet
                        web = self.buscador_web.buscar(f"sinopsis {nombre} pelicula")
                        if web.get("exito"):
                            respuestas.append(self._tag(f"  {nombre}\n{web['resultado'].strip()}", web.get("fuente", ""), web.get("enlaces", [])))
                        else:
                            respuestas.append(f"  {nombre}\n  No encontré información sobre esta película.")
                    else:
                        respuestas.append(f"  Número de película inválido.")
                elif mod_key == "__argumentar__":
                    topic = cmd_reformulado
                    if self.openrouter:
                        prompt = (f"Actúa como un experto analizando y debatiendo el siguiente tema. "
                                  f"Presenta argumentos a favor y en contra de manera equilibrada, "
                                  f"con datos concretos y razonamiento lógico. Tema: {topic}")
                        try:
                            resp = self.openrouter.chat(prompt, max_tokens=600)
                            respuestas.append(self._tag(f"  {resp.strip()}", "OpenRouter"))
                        except Exception:
                            respuestas.append("  No pude generar un análisis en este momento.")
                    elif self.gemini:
                        prompt = (f"Actúa como un experto analizando y debatiendo el siguiente tema. "
                                  f"Presenta argumentos a favor y en contra de manera equilibrada. Tema: {topic}")
                        try:
                            resp = self.gemini.chat(prompt, max_tokens=600)
                            respuestas.append(f"  {resp.strip()}")
                        except Exception:
                            respuestas.append("  No pude generar un análisis en este momento.")
                    else:
                        respuestas.append("  No tengo un modelo de IA configurado para debatir.")
            resultado = "\n\n".join(str(r) for r in respuestas)
            if resultado and resultado != "__CONTINUE__":
                self._actualizar_tema(comando, resultado)
                self._conversation.append((comando, resultado))
                if len(self._conversation) > 10:
                    self._conversation = self._conversation[-10:]
                return self._inyectar_chiste(resultado)
            return resultado

        # Conversacion general (antes de rendirnos)
        # Pero si el comando empezó con /, no responder con datos curiosos - mostrar ayuda
        if comando and comando.startswith('/'):
            cmd_sin_slash = comando[1:].strip()
            return self._ayuda_comandos(cmd_sin_slash)
        # Trivial: ignorar mensajes de 1-2 caracteres
        if self._es_conversacion(cmd_lower) and len(cmd_lower.strip()) <= 2:
            return ""
        respuesta = self._conversar(cmd_lower)
        if respuesta:
            self._actualizar_tema(comando, respuesta)
            self._conversation.append((comando, respuesta))
            if len(self._conversation) > 10:
                self._conversation = self._conversation[-10:]
            return self._inyectar_chiste(respuesta)

        return self._inyectar_chiste(self._no_entiendo(comando))

    _FUENTES = {
        "openrouter": " ᵒʳ",
        "gemini": " ᵍᵐ",
        "duckduckgo": " ᵈᵈᵍ",
        "google": " ᵍᵍ",
        "wikipedia": " ʷ",
        "wikipedia+duckduckgo": " ʷᵈ",
        "duckduckgo+wikipedia": " ʷᵈ",
        "openrouter+wikipedia": " ʷᵒ",
        "agente": " ᵃᵍ",
        "local": " ℓ",
        "memoria": " ᵐ",
        "clima": " ᶜˡ",
        "bolsa": " ˢᵗ",
        "musica": " ᵐᵘ",
        "juego": " ᵍᵐᵉ",
        "libro": " ᵇᵒ",
        "app": " ᵃᵖ",
    }

    def _inyectar_chiste(self, texto: str) -> str:
        """Devuelve el texto tal cual, sin inyectar chistes aleatorios."""
        if not texto:
            return texto
        # Guardar en memoria vectorial
        if hasattr(self, 'memoria_vec') and hasattr(self, '_cmd_original'):
            cmd_actual = getattr(self, '_cmd_original', '')
            if cmd_actual and texto not in ("__EXIT__", "__CONTINUE__", ""):
                try:
                    self.memoria_vec.aprender(cmd_actual, texto)
                except Exception:
                    pass
        texto = self._limitar_respuesta(texto)
        # Anadir tag de fuente si no tiene uno
        if texto and texto not in ("__EXIT__", "__CONTINUE__", ""):
            if not self._texto_tiene_tag(texto):
                texto = texto.rstrip() + self._FUENTES.get("local", "")
        return texto

    def _limitar_respuesta(self, texto: str, max_parrafos: int = 6, max_chars: int = 1500) -> str:
        """Limita la respuesta a un maximo de N parrafos y M caracteres."""
        if not texto:
            return texto
        if len(texto) <= max_chars and texto.count('\n\n') < max_parrafos * 2:
            return texto
        parrafos = [p.strip() for p in texto.split('\n\n') if p.strip()]
        if len(parrafos) > max_parrafos:
            parrafos = parrafos[:max_parrafos]
            if parrafos[-1][-1] not in '.!?' and len(parrafos) > 1:
                parrafos = parrafos[:-1]
        resultado = '\n\n'.join(parrafos)
        if len(resultado) > max_chars:
            resultado = resultado[:max_chars].rsplit('. ', 1)[0] + '.'
        return resultado

    def _texto_tiene_tag(self, texto: str) -> bool:
        """Verifica si el texto ya tiene un tag de fuente (superscript Unicode)."""
        if not texto:
            return False
        ultima_linea = texto.rsplit('\n', 1)[-1]
        fin = ultima_linea[-15:]
        for tag in self._FUENTES.values():
            if tag and fin.endswith(tag):
                return True
        return False

    def _tag(self, texto: str, fuente: str = "", enlaces: list = None) -> str:
        tag = self._FUENTES.get(fuente.lower().strip(), "")
        if tag and texto.strip():
            texto = texto.rstrip() + tag
        if enlaces and texto.strip():
            refs = "  " + "  ".join(f"🔗 {e}" for e in enlaces[:2])
            texto = texto + "\n" + refs
        return texto

    def _acortar_resultado(self, texto: str, max_chars: int = 500) -> str:
        """Acorta un resultado de busqueda a 2-3 frases objetivas."""
        if len(texto) <= max_chars:
            return texto
        # Dividir por signos de puntuacion que indican fin de frase
        partes = re.split(r'(?<=[.!?])\s+', texto)
        resultado = ""
        for parte in partes:
            if len(resultado) + len(parte) + 1 > max_chars:
                break
            if resultado:
                resultado += " "
            resultado += parte
        if not resultado:
            resultado = texto[:max_chars].rsplit(" ", 1)[0] + "..."
        return resultado

    def _extraer_tema(self, cmd: str) -> str:
        """Extrae el tema principal de un comando para mantener contexto conversacional."""
        c = cmd.lower().strip()
        # Quitar prefijos comunes de pregunta
        c = re.sub(r'^(dime\s+)?(que\s+es|quien\s+es|que\s+son|quienes\s+son|que\s+significa|como\s+funciona|explica|cuentame\s+(sobre|de)|sabes\s+(de|sobre|acerca\s+de))\s+', '', c)
        c = re.sub(r'^(precio\s+(de|del)\s*|valor\s+(de|del)\s*|cotizacion\s+(de|del)\s*)', '', c)
        c = re.sub(r'^(clima\s+(en|de|para|del)\s*|temperatura\s+(en|de|para|del)\s*)', '', c)
        c = re.sub(r'^(en\s+)?que\s+anio\s+', '', c)
        c = re.sub(r'^(cuando\s+|donde\s+|cuanto\s+|como\s+se\s+)', '', c)
        # Limpiar signos
        c = re.sub(r'[¿?!¡.,;:]', '', c).strip()
        return c if len(c) > 2 else cmd

    def _actualizar_tema(self, comando: str, respuesta: str):
        """Actualiza el tema actual de conversación basado en el comando."""
        # Guardar comando y respuesta para referencia contextual
        self._ultimo_comando = comando
        if respuesta and len(str(respuesta)) > 3:
            r = str(respuesta)
            if isinstance(r, str):
                r = r.encode('utf-8', 'replace').decode('utf-8')
            self._ultima_respuesta = r
        # No actualizar si es un seguimiento vago
        if re.search(r'\b(qu[eé]\s*te\s*parece|qu[eé]\s*opinas|y\s*eso|explica\s*eso|ampl[ií]a|ampl[ií]ame|m[aá]s\s*info)\b', comando):
            return
        tema = self._extraer_tema(comando)
        if tema:
            self._tema_actual = tema
            # Guardar también el texto completo de la respuesta para contexto
            if respuesta and len(respuesta) > 20:
                r = respuesta[:300]
                if isinstance(r, str):
                    r = r.encode('utf-8', 'replace').decode('utf-8')
                self._ultima_respuesta_tema = r

    def _parse_intent(self, cmd: str, cmd_original: str = None) -> list:
        """Analiza lenguaje natural y devuelve lista de (modulo, comando_reformulado)."""
        # Si comienza con '/', es un comando directo a módulo
        if cmd.startswith('/'):
            cmd = cmd[1:].strip()
        # Separar comandos compuestos por 'y'
        segmentos = re.split(r'\s+y\s+', cmd)
        if len(segmentos) > 1:
            intents = []
            for seg in segmentos:
                seg = seg.strip()
                seg_intents = self._analizar_segmento(seg, cmd_original)
                if not seg_intents:
                    seg_intents = [("__direct__", self._tag(f"  {self._agente_razonar(seg, f'El usuario pregunta: {seg}. Responde directamente.')}", "Agente"))]
                intents.extend(seg_intents)
            return intents
        return self._analizar_segmento(cmd, cmd_original)

    def _analizar_segmento(self, cmd: str, cmd_original: str = None) -> list:
        """Analiza un segmento de comando y devuelve lista de intents."""

        # ---- MATEMÁTICAS (MUY TEMPRANO): expresiones y cálculos ----
        # "cuanto es 2+2", "raiz cuadrada de 144", "puedes resolver problemas matematicos"
        keywords_math = ["cuanto es", "cuánto es", "cuanto da", "calcula", "resuelve",
                         "raiz", "raíz", "sqrt", "elevado", "potencia", "derivada",
                         "integral", "ecuacion", "ecuación", "logaritmo", "seno", "coseno",
                         "tangente", "trigonometria", "matematica", "matematicas",
                         "algebra", "álgebra", "puedes resolver"]
        if self._match_keywords(cmd, keywords_math):
            if "matematicas" in self.modules:
                resp = self.modules["matematicas"]["instance"].execute(cmd)
                if resp:
                    return [("__direct__", resp)]

        # ---- CODIFICAR / DECODIFICAR: base64, hex (antes de cualquier keyword) ----
        if re.search(r'\b(decodifiques|decodifique|decodifico|decodifica|decodificar|descifr|decifr|desencript|decrypt|decode)\b', cmd, re.IGNORECASE):
            res = self._codificar(cmd_original or cmd, "decode")
            if res:
                return [("__direct__", res)]
        if re.search(r'\b(codifiques|codifique|codifico|codifica|codificar|encript|encrypt|encode)\b', cmd, re.IGNORECASE):
            res = self._codificar(cmd_original or cmd, "encode")
            if res:
                return [("__direct__", res)]
        if re.search(r'\b(hash|base64|base\s*64)\b', cmd, re.IGNORECASE):
            res = self._codificar(cmd_original or cmd, "decode")
            if res:
                return [("__direct__", res)]

        # ---- TRADUCIR: "traduce al ingles X", "traduce X" ----
        m_trad = re.search(
            r'\b(traduce|traducir|translate|tradume|traduse)\s+'
            r'(al\s+|a\s+|para\s+)?'
            r'(ingles|inglés|english|español|espanol|spanish|frances|francés|french|aleman|alemán|german|portugues|portugués|portuguese|italiano|italian|chino|chinese|japones|japonés|japanese)?'
            r'[\s,]*'
            r'(.+)',
            cmd, re.IGNORECASE
        )
        if m_trad:
            texto = m_trad.group(m_trad.lastindex).strip().strip('"\'')
            # Limpiar palabras introductorias en español
            texto = re.sub(r'^(este\s+|esta\s+|esto\s+|esta\s+frase\s+|este\s+parrafo\s+|este\s+párrafo\s+|parrafo\s+|párrafo\s+|el\s+siguiente\s+texto\s+|lo\s+siguiente\s+|la\s+siguiente\s+frase\s+)', '', texto, flags=re.IGNORECASE).strip()
            lang_target = (m_trad.group(3) or '').strip().lower()
            lang_map = {
                "ingles": "en", "inglés": "en", "english": "en",
                "español": "es", "espanol": "es", "spanish": "es",
                "frances": "fr", "francés": "fr", "french": "fr",
                "aleman": "de", "alemán": "de", "german": "de",
                "portugues": "pt", "portugués": "pt", "portuguese": "pt",
                "italiano": "it", "italian": "it",
                "chino": "zh", "chinese": "zh",
                "japones": "ja", "japonés": "ja", "japanese": "ja",
            }
            target = lang_map.get(lang_target, "es") if lang_target else "es"
            source = "en" if target == "es" else "auto"
            try:
                from deep_translator import GoogleTranslator
                traducido = GoogleTranslator(source=source, target=target).translate(texto[:2000])
                return [("__direct__", f"  Traducción: {traducido}")]
            except Exception:
                pass

        # ---- RESPUESTA A PREGUNTA DE PERSONA PENDIENTE ----
        if self._pendiente_persona:
            original, nombre_base = self._pendiente_persona
            # Si el usuario dio más detalles, construir descripción
            palabras = cmd.strip().split()
            if len(palabras) > 1 and not any(kw in cmd for kw in ["no se", "no sé", "no", "olvida", "dejalo", "déjalo"]):
                # Si la respuesta empieza con el mismo nombre, usarla directo
                if palabras[0].lower().rstrip(",.!?") == nombre_base.lower():
                    nombre = cmd.strip()
                else:
                    nombre = f"{nombre_base} {cmd.strip()}"
                nombre = nombre[:80]
            else:
                nombre = nombre_base
            self._pendiente_persona = None
            ai = self.openrouter or self.gemini
            if ai:
                prompt = (
                    f"Responde en español quién es o fue {nombre}. "
                    f"El usuario preguntó originalmente: '{original}'. "
                    f"Da una respuesta informativa pero conversacional, en 2-3 párrafos."
                )
                gem = ai.preguntar(prompt)
                if gem["exito"]:
                    self.memoria.aprender(nombre, gem["resultado"])
                    return [("__direct__", self._tag(f"  {gem['resultado'].strip()}", "OpenRouter"))]
            web = self.buscador_web.buscar(nombre)
            if web["exito"]:
                return [("__direct__", self._tag(f"  {web['resultado'].strip()}", web.get("fuente", ""), web.get("enlaces", [])))]
            return [("__direct__", f"  No encontré información sobre {nombre}.")]

        # ---- RESPUESTA A ARTÍCULO PENDIENTE (standalone) ----
        if self._pendiente_articulo:
            original = self._pendiente_articulo
            self._pendiente_articulo = None
            # Combinar: "articulo 109" + "cuba" → "articulo 109 cuba"
            full = f"{original} {cmd}".strip()
            # Check memory first (abuelo-nieto)
            mem = self.memoria.recordar_formateado(full)
            if mem:
                return [("__direct__", f"  {mem}")]
            ai = self.openrouter or self.gemini
            if ai:
                gem = ai.preguntar(f"Responde en español: ¿Qué dice {full}? Explica el contenido de forma clara y precisa, citando el texto relevante si es posible. Responde en 2-3 párrafos.")
                if gem["exito"]:
                    self.memoria.aprender(full, gem["resultado"])
                    return [("__direct__", self._tag(f"  {gem['resultado'].strip()}", "OpenRouter"))]
            web = self.buscador_web.buscar(full)
            if web["exito"]:
                self.memoria.aprender(full, web["resultado"])
                return [("__direct__", self._tag(f"  {web['resultado'].strip()}", web.get("fuente", ""), web.get("enlaces", [])))]
            return [("__direct__", f"  No encontré información sobre {full}.")]

        # ---- APRENDER RUTAS: si el comando menciona una carpeta existente, guardarla ----
        m = re.search(r'([A-Za-z]:\\(?:[^\s\\]+\\)*[^\s\\]*)', cmd)
        if m:
            ruta = os.path.realpath(m.group(1).rstrip('\\'))
            if os.path.isdir(ruta):
                config = cargar_config()
                mod = config.setdefault("modules", {}).setdefault("catalogo", {})
                dirs = mod.setdefault("directorios", [])
                if ruta not in dirs:
                    dirs.append(ruta)
                    guardar_config(config)

        # ---- APRENDER: "aprende que X es Y", "recuerda que X es Y" ----
        m = re.search(r'\b(aprende\s*que|recuerda\s*que|aprendete\s*que|memoriza\s*que|guardate\s*que|grabate\s*que)\s+(.+?)\s+(es|son|significa|significan|se\s*llama|se\s*llaman)\s+(.+)', cmd, re.IGNORECASE)
        if m:
            tema = m.group(2).strip().rstrip(",.!?")
            verbo = m.group(3).strip().lower()
            info = m.group(4).strip().rstrip(",.!?")
            frase_completa = f"{tema} {verbo} {info}"
            self.memoria.aprender(tema, frase_completa)
            return [("__direct__", f"  Aprendido: {frase_completa}")]

        # ---- OLVIDAR: "olvida que X", "olvidate de X" ----
        m = re.search(r'\b(olvida\s*que|olvidate\s*de|borra\s*que|elimina\s*que)\s+(.+)', cmd, re.IGNORECASE)
        if m:
            tema = m.group(2).strip().rstrip(",.!?")
            if self.memoria.olvidar(tema):
                return [("__direct__", f"  Olvidado: {tema}")]
            return [("__direct__", f"  No encontré '{tema}' en mi memoria")]

        # ---- QUE SABES: mostrar lo aprendido ----
        if re.search(r'\b(qu[eé]\s*(sabes|aprendiste|has aprendido|conoces)|muestra\s*tu\s*memoria|lista\s*tus\s*hechos|que has memorizado)\b', cmd, re.IGNORECASE):
            hechos = self.memoria.listar_hechos()
            if hechos:
                texto = "  Lo que he aprendido:\n" + "\n".join(f"  • {h}" for h in hechos[:20])
                return [("__direct__", texto)]
            return [("__direct__", "  No he aprendido nada aún. Dime 'aprende que X es Y' para enseñarme.")]
            # Si no se pudo resolver, ignorar y seguir con otros patrones

        # ---- PERSONA AMBIGUA: detectar nombres comunes y preguntar a quién se refiere ----
        # Saltar si el nombre va seguido de apellido famoso (ej: "jose marti", "maria callas")
        if re.search(
            r'\b(jose|josé|maria|maría|juan|pedro)\s+'
            r'(martí|marti|callas|perón|peron|neruda|garcía|garcia|'
            r'márquez|marquez|borges|cortázar|cortazar|llosa|fuentes|'
            r'mistral|gabriel|bolívar|bolivar|alonso|santos)\b', cmd, re.IGNORECASE):
            pass  # dejar que el agente maneje la consulta completa
        else:
            nombres_comunes = ["maria", "maría", "jesus", "jesús", "jose", "josé", "juan",
                          "carlos", "ana", "pedro", "pablo", "laura", "sofía", "sofia",
                          "miguel", "ángel", "angel", "david", "diego", "antonio",
                          "francisco", "javier", "manuel", "alejandro", "fernando",
                          "luis", "jorge", "sergio", "andres", "andrés", "ricardo",
                          "eduardo", "raul", "raúl", "alberto", "julio", "ramon",
                          "ramón", "ruben", "rubén", "victor", "víctor", "oscar",
                          "óscar", "hugo", "guillermo", "felipe", "claudia",
                          "patricia", "carmen", "marta", "teresa", "monica", "mónica",
                          "silvia", "elena", "cristina", "isabel", "beatriz",
                          "adrian", "adrián", "martin", "martín", "marco",
                          "lucas", "mateo", "santiago", "tomas", "tomás",
                          "agustín", "agustin", "esteban", "nicolás", "nicolas",
                          "sebastian", "sebastián", "gabriel", "daniel", "mario",
                          "marcos", "paula", "camila", "valentina", "lucia", "lucía"]
            if not self._pendiente_persona:
                m_persona = None
                persona_patrones = [
                    r'^(' + '|'.join(nombres_comunes) + r')\b',
                    r'\b(qui[eé]n\s+(es|fue|era|ser[aá])\s+)(' + '|'.join(nombres_comunes) + r')\b',
                    r'\b(qu[eé]\s+(sabes\s+de|opinas\s+de|me\s+dices\s+de|cuentas\s+de))\s+(' + '|'.join(nombres_comunes) + r')\b',
                    r'\b(dime\s+de|dame\s+info\s+de|informaci[oó]n\s+(sobre|de|acerca\s+de))\s+(' + '|'.join(nombres_comunes) + r')\b',
                ]
                for pp in persona_patrones:
                    m_p = re.search(pp, cmd, re.IGNORECASE)
                    if m_p:
                        m_persona = m_p
                        break
                if m_persona:
                    nombre_encontrado = None
                    for n in nombres_comunes:
                        if n in cmd.lower():
                            nombre_encontrado = n
                            break
                    if nombre_encontrado:
                        self._pendiente_persona = (cmd, nombre_encontrado.capitalize())
                        return [("__direct__", f"  ¿A qué {nombre_encontrado.capitalize()} te refieres? (puedes darme más detalles)")]

        # ---- ARTÍCULOS, LEYES, RESOLUCIONES ----
        # "articulo 109 de la constitucion cubana", "ley 60", "resolucion 42"
        # Si es standalone (sin país/constitución), preguntar contexto
        m_articulo = re.search(r'\b(art[ií]culo|art\.|ley|resoluci[oó]n|decreto|decretos?)\s+(\d+|[\wáéíóúñ]+)\b', cmd, re.IGNORECASE)
        if m_articulo:
            # Check memory primero (abuelo-nieto)
            mem = self.memoria.recordar_formateado(cmd)
            if mem:
                return [("__direct__", f"  {mem}")]
            # Si es standalone (solo "articulo 109" sin país/constitución), preguntar
            if not re.search(r'\b(de\s+(la\s+)?|constituci[oó]n|ley|pa[íi]s|c[óo]digo|código|reglamento|estatuto|constitucion)\b', cmd):
                self._pendiente_articulo = cmd
                return [("__direct__", "  ¿De qué país o constitución?")]
            # Tiene contexto → OpenRouter
            ai = self.openrouter or self.gemini
            if ai:
                gem = ai.preguntar(f"Responde en español: ¿Qué dice {cmd}? Explica el contenido de forma clara y precisa, citando el texto relevante si es posible. Responde en 2-3 párrafos.")
                if gem["exito"]:
                    self.memoria.aprender(cmd, gem["resultado"])
                    return [("__direct__", self._tag(f"  {gem['resultado'].strip()}", "OpenRouter"))]
            web = self.buscador_web.buscar(cmd)
            if web["exito"]:
                self.memoria.aprender(cmd, web["resultado"])
                return [("__direct__", self._tag(f"  {web['resultado'].strip()}", web.get("fuente", ""), web.get("enlaces", [])))]
            return [("__direct__", f"  No encontré información sobre {cmd}.")]

        # ──────────────────────────────────────────────
        # BLOQUE DE RAZONAMIENTO CON AGENTE (OpenRouter + herramientas)
        # Reemplaza: corrección, seguimiento, ampliar, preguntas de conocimiento
        # ──────────────────────────────────────────────

        # ---- CORRECCIÓN: "dije X", "me equivoqué, es X", "no, es X" ----
        m_corr = re.search(r'\b((?:dije|dec[ií]a|quise\s*decir|quise\s+preguntar|me\s+equivoqu[eé])\s+(?:que\s+|era\s+|es\s+)?|no\s*,\s*(?:es|era|digo)\s+|corrig[eo]:|rectific[eo]:|en\s+realidad\s+(?:es|era|digo))\s*(.+)$', cmd, re.IGNORECASE)
        if m_corr:
            sujeto = m_corr.group(m_corr.lastindex).strip().rstrip(",.!?")
            if len(sujeto) > 2:
                for clave in list(self.memoria._datos["hechos"].keys()):
                    if any(w in clave for w in sujeto.lower().split() if len(w) > 3):
                        self.memoria.olvidar(clave)
                        break
                resp = self._agente_razonar(sujeto, f"El usuario está corrigiendo información sobre '{self._tema_actual}'.")
                if resp:
                    return [("__direct__", self._tag(f"  {resp}", "Agente"))]
                return [("__direct__", f"  Corrijo: busqué '{sujeto}' pero no encontré resultados.")]

        # ---- VAGO / SEGUIMIENTO: "que te parece", "y eso", "explica eso" ----
        if re.search(r'\b(qu[eé]\s*te\s*parece|qu[eé]\s*opinas|y\s*eso|y\s*entonces|entonces|explica\s*eso|cu[eé]ntame\s*m[aá]s\s*de\s*eso|qu[eé]\s*quiere\s*decir\s*eso|a\s*qu[eé]\s*te\s*refieres|es\s*bueno|es\s*malo|es\s*confiable|me\s*conviene|qu[eé]\s*crees|t[uú]\s*que\s*crees|dime\s*tu\s*opini[oó]n|c[oó]mo\s*lo\s*ve[s]|c[oó]mo\s*lo\s*vez|en\s*el\s*mercado)\b', cmd):
            contexto = self._tema_actual or (self.history[-2] if len(self.history) > 1 else "")
            extra = f"Tema actual: {self._tema_actual}. Respuesta anterior: {self._ultima_respuesta_tema[:400]}" if contexto else ""
            resp = self._agente_razonar(cmd, extra)
            if resp:
                if self._tema_actual:
                    self.memoria.aprender(f"{self._tema_actual} {cmd}", resp)
                return [("__direct__", self._tag(f"  {resp}", "Agente"))]
            return [("__direct__", f"  No tengo suficiente contexto para opinar sobre '{contexto or cmd}'.")]

        # ---- AMPLIAR: "amplía", "más información", "dime más" ----
        if re.search(r'\b(ampl[ií]a|ampl[ií]ame|m[aá]s\s*info|m[aá]s\s*informaci[oó]n|dime\s*m[aá]s|cuen(ta)?\s*m[aá]s|expl[ií]ca\s*m[aá]s|a[hú]ond[aá]|dame\s*m[aá]s\s*detalles|quiero\s*saber\s*m[aá]s|sigue|contin[uú]a)\b', cmd):
            if len(self.history) > 1:
                ultimo = self._tema_actual or self.history[-2]
                resp = self._agente_razonar(f"Dime más sobre {ultimo}", f"El usuario quiere ampliar información sobre '{ultimo}'.")
                if resp:
                    self.memoria.aprender(ultimo, resp)
                    return [("__direct__", self._tag(f"  {resp}", "Agente"))]

        # ---- PREGUNTAS DE CONOCIMIENTO: "que es X", "quien es X", "que cosa significa X" ----
        m = re.search(r'\b(qu[eé]\s+(?:cosa\s+)?(?:es|son|significa)|qui[eé]n\s*es|qui[eé]nes\s*son|c[oó]mo\s*funciona|dame\s*informaci[oó]n\s*(?:sobre|de|acerca\s*de)|explica\s*(?:qu[eé]\s*es)?|cu[eé]ntame\s*(?:sobre|de|acerca\s*de))\s+(.{3,80})', cmd, re.IGNORECASE)
        if m:
            sujeto = m.group(m.lastindex).strip().rstrip(",.!?")
            # Intentar con agente + herramientas primero
            resp = self._agente_razonar(cmd, f"El usuario pregunta sobre '{sujeto}'. Busca información precisa.")
            if resp:
                self.memoria.aprender(sujeto, resp)
                return [("__direct__", self._tag(f"  {resp}", "Agente"))]
            # Fallback: preguntar directamente al LLM sin herramientas
            ai = self.openrouter or self.gemini
            if ai:
                fb = ai.preguntar(f"Responde en español de forma completa y detallada: ¿{cmd}?")
                if fb and isinstance(fb, dict) and fb.get("exito") and fb.get("resultado"):
                    resp = fb["resultado"].strip()
                    self.memoria.aprender(sujeto, resp)
                    return [("__direct__", self._tag(f"  {resp}", "Agente"))]
            # Ultimo recurso: busqueda web
            web = self.buscador_web.buscar(cmd)
            if web.get("exito"):
                return [("__direct__", f"  {web['resultado'].strip()}")]
            return [("__direct__", f"  No encontré información sobre {sujeto} en este momento. ¿Pruebas con otra pregunta?")]

        # ---- CONTINUE: reanudar ultima respuesta o seguir con tema especifico ----
        m_cont = re.search(r'\b(contin[uú]a|sigue(?:\s+hablando)?)\s+(?:hablando\s+)?(?:de|sobre|acerca\s+de)\s+(.+)', cmd, re.IGNORECASE)
        if m_cont:
            resp = self._agente_razonar(cmd)
            if resp:
                return [("__direct__", self._tag(f"  {resp}", "Agente"))]
        if re.search(r'\b(contin[uú]a|sigue hablando|continue hablando|repite eso|repite lo)\b', cmd):
            return [("__continue__", "")]

        # ---- JUEGOS: antes que APPS para atrapar "abre el dota" ----
        # NO capturar si "pon/poner" va seguido de palabra de música/libro/película
        if re.search(r'\b(pon|poner)\s+(musica|música|cancion|canción|song|algo\s+de\s+musica|un\s+tema|una\s+cancion|un\s+video|una\s+pel[ií]cula|un\s+libro)\b', cmd):
            pass  # dejar pasar a MÚSICA, LIBROS, etc.
        else:
            # Detectar "mis juegos están en D:\Games" para escaneo proactivo
            ruta_encontrada = re.search(r'([A-Za-z]:[\\/](?:[^\s,;)]+))', cmd)
            if ruta_encontrada and re.search(r'jueg|game|steam|epic|gog|origin|battl|blizzard|partid|aca\s+est[áa]|aqui\s+est[áa]|mis\s+jueg|los\s+jueg', cmd, re.IGNORECASE):
                carpeta = ruta_encontrada.group(1)
                if os.path.isdir(carpeta):
                    self.dir_mem.agregar("games", carpeta)
                return [("games", f"escanear {carpeta}")]
            # Patrones para abrir juegos
            m = re.search(
                r'\b(abrir|abre|lanzar|iniciar|jugar|juega|juegue|pon|poner|'
                r've\s+abriendo|voy\s+a\s+jugar|vamos\s+a\s+jugar|'
                r'echar\s+una\s+partida\s+(de|al|a\s+la|en\s+el|en\s+la)?|'
                r'dale\s+al|vamos\s+al)\s+'
                r'(el\s+|la\s+|al\s+|un\s+|una\s+)?(juego\s+|partida\s+|partidita\s+)?(.+)',
                cmd
            )
            if m:
                juego = m.group(m.lastindex).strip()
                juego = re.sub(r'\b(juego|juegos|partida|partidita|vamos|dale|yah|ya|ve|voy|vas|vaya|echar|echarle|echale|abriendo|abrir|abre|jugar|juega|juegue|pon|poner|lanzar|iniciar|una|unos|unas|que|a|al|del|por|para|con|sin|entre|sobre|de|la|las|lo|los|el|en|y|e|o|u|su|sus|mi|mis|tu|te|se|le|les|nos|os)\b', '', juego).strip()
                juego = re.sub(r'\s+', ' ', juego).strip()
                if juego and len(juego) > 1:
                    # Verificar si es un juego conocido
                    games_mod = self.modules.get("games")
                    if games_mod:
                        ruta = games_mod["instance"]._buscar_en_db(juego)
                        if ruta:
                            return [("games", f"abrir {juego}")]
                        for nombre_db in games_mod["instance"]._games_db:
                            if juego.lower() in nombre_db or nombre_db in juego.lower():
                                return [("games", f"abrir {juego}")]
                    return [("games", f"abrir {juego}")]

        # ---- LIBROS: antes que APPS para atrapar "abre el principito" ----
        ruta_encontrada = re.search(r'([A-Za-z]:[\\/](?:[^\s,;)]+))', cmd)
        if ruta_encontrada and re.search(r'libro|pdf|lectur|aca\s+est[áa]|aqui\s+est[áa]|mis\s+libro|los\s+libro', cmd, re.IGNORECASE):
            carpeta = ruta_encontrada.group(1)
            if os.path.isdir(carpeta):
                self.dir_mem.agregar("books", carpeta)
            return [("books", f"escanear {carpeta}")]
        # "que libros tengo", "lista libros", "muestrame los libros"
        if re.search(r'\b(que\s+libros\s+tengo|lista\s+libros|mu[e]strame\s+los\s+libros|que\s+pdf|muestrame\s+libros|tengo\s+libros|libros\s+disponibles|ver\s+libros|ense[ñn]ame\s+libros)\b', cmd, re.IGNORECASE):
            return [("books", "listar")]
        m = re.search(r'\b(abrir|abre|lanzar|iniciar|abreme|abrame)\s+(el\s+|la\s+|un\s+|una\s+)?(libro\s+|pdf\s+|libro\s+llamado\s+|lectura\s+)?(.+)', cmd)
        if m:
            nombre = m.group(m.lastindex).strip()
            nombre = re.sub(r'\b(libro|pdf|por\s+favor|gracias)\b', '', nombre).strip()
            if nombre and len(nombre) >= 1:
                books_mod = self.modules.get("books")
                if books_mod:
                    ruta = books_mod["instance"]._buscar_en_db(nombre)
                    if ruta:
                        return [("books", f"abrir {nombre}")]
                    for nombre_db in books_mod["instance"]._books_db:
                        if nombre.lower() in nombre_db or nombre_db in nombre.lower():
                            return [("books", f"abrir {nombre}")]
                return [("books", f"abrir {nombre}")]
        # "abre el principito" sin keyword libro (cuando no es juego ni app)
        if re.search(r'\b(abrir|abre|lanzar|abreme|abrame)\b', cmd) and not re.search(r'\b(juego|steam|epic|navegador|chrome|word|excel|spotify|discord|vs\s*code)\b', cmd, re.IGNORECASE):
            m = re.search(r'\b(abrir|abre|lanzar|abreme|abrame)\s+(el\s+|la\s+|un\s+|una\s+)?(.+)', cmd)
            if m:
                nombre = m.group(m.lastindex).strip()
                nombre = re.sub(r'\b(por\s+favor|gracias)\b', '', nombre).strip()
                if nombre and len(nombre) > 2:
                    books_mod = self.modules.get("books")
                    if books_mod and books_mod["instance"]._buscar_en_db(nombre):
                        return [("books", f"abrir {nombre}")]

        # ---- APPS: abrir aplicaciones ----
        # "abre el navegador", "abre chrome", "abrir bloc de notas"
        # "abre youtube" / "abre google" → se trata como busqueda web
        m = re.search(r'\b(abrir|abre|lanzar|iniciar|abreme|abrame|abrirme|abran)\s+(.+)', cmd)
        if m:
            raw = m.group(2).strip()
            query = re.sub(r'\b(el|la|los|las|un|una|unos|unas|por favor|porfa)\b', '', raw).strip()
            # Si es un libro conocido, delegar a books
            if query and len(query) > 2:
                books_mod = self.modules.get("books")
                if books_mod:
                    db = books_mod["instance"]._books_db
                    if books_mod["instance"]._buscar_en_db(query):
                        return [("books", f"abrir {query}")]
                    for nombre_db in db:
                        if query.lower() in nombre_db or nombre_db in query.lower():
                            return [("books", f"abrir {query}")]
            app_map = {
                "navegador": "chrome", "browser": "chrome", "internet": "chrome",
                "explorador": "explorer", "explorador de archivos": "explorer",
                "archivos": "explorer", "carpetas": "explorer",
                "bloc de notas": "notepad", "notepad": "notepad",
                "calculadora": "calc", "calc": "calc",
                "paint": "mspaint", "cmd": "cmd", "terminal": "cmd",
                "powershell": "powershell", "simbolo del sistema": "cmd",
                "word": "WINWORD", "excel": "EXCEL", "powerpoint": "POWERPNT",
                "vs code": "code", "vscode": "code", "visual studio code": "code",
                "spotify": "spotify", "discord": "discord",
            }
            for nombre, com in app_map.items():
                if nombre in query:
                    return [("apps", f"abrir {com}")]
            # Maps: si la app es "maps" o "google maps", abrir web
            if re.search(r'\b(maps|google\s*maps|mapas?)\b', query):
                buscar = re.sub(r'\b(maps|google\s*maps|mapas?)\b', '', query).strip()
                url = f"https://www.google.com/maps/search/{buscar.replace(' ', '+')}" if buscar else "https://www.google.com/maps"
                return [("__open_url__", url)]
            # Si no es app conocida, pasar al modulo apps (busca en Start Menu y PATH)
            return [("apps", f"abrir {query}")]

        # ---- GOOGLE MAPS ----
        # "maps", "donde queda X", "navega a X", "ubicacion de X", "como llegar a X"
        m = re.search(r'\b(maps|google\s*maps|mapas?|donde queda|dónde queda|dónde está|donde esta|navega a|navegar a|ubicación de|ubicacion de|como llegar (a|al)|cómo llegar (a|al)|busca en maps|localiza)\b', cmd)
        if m:
            query = re.sub(r'\b(maps|google\s*maps|mapas?|donde queda|dónde queda|dónde está|donde esta|navega a|navegar a|ubicación de|ubicacion de|como llegar (?:a|al)|cómo llegar (?:a|al)|busca en maps|localiza)\b', '', cmd).strip()
            if query:
                url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            else:
                url = "https://www.google.com/maps"
            return [("__open_url__", url)]

        # ---- INFO DE PELÍCULA: "de que trata la pelicula 66", "sinopsis de la 5" ----
        # (debe ir ANTES del catalogo numerico para no ser capturado como "la N")
        m_info = re.search(r'\b(de\s+qu[eé]\s+trata|sinopsis|de\s+qu[eé]\s+va|informaci[oó]n\s*(sobre|de)\s+la|qu[eé]\s+(es|sabes\s+de))\s+(de\s+)?(la\s+|el\s+|la\s+pel[ií]cula\s+|pel[ií]cula\s+)(n[uú]mero\s+)?(\d+)\b', cmd)
        if m_info:
            return [("__movie_info__", m_info.group(m_info.lastindex))]

        # ---- CATÁLOGO DE PELÍCULAS (antes que música, para capturar "reproduce N") ----
        keywords_catalogo = ["catalogo", "catálogo", "película", "pelicula", "películas",
                             "peliculas", "filmoteca", "videoteca", "mis pelis",
                             "lista pelis", "escanea películas", "reindexar"]
        if self._match_keywords(cmd, keywords_catalogo):
            return [("catalogo", cmd)]
        # "reproduce 3", "elige la 5", "abre 7"
        m = re.search(r'\b(reproduce|reproducir|elige|elige la|selecciona|seleccionar|pon|poner|abrir|abre|ver)\s+(la\s+|el\s+|la película\s+|el número\s+)?(\d+)\b', cmd)
        if m:
            return [("catalogo", cmd)]
        # "la 66", "el 3", "pelicula 5" (sin verbo, con artículo)
        m = re.search(r'\b(la\s+|el\s+|la\s+pel[ií]cula\s+|pel[ií]cula\s+)(n[uú]mero\s+)?(\d+)\b', cmd)
        if m:
            return [("catalogo", cmd)]

        # ---- BUSQUEDA EN INTERNET ----
        # "busca youtube", "buscar google", "busca recetas de cocina"
        # "quiero buscar", "necesito informacion sobre"
        # NOTA: estas busquedas preguntan local o internet
        m = re.search(r'\b(busca|buscar|encuentra|busqueme|busquen|consultar|averiguar|investigar)\s+(.+)', cmd)
        if m:
            query = m.group(2).strip()
            query = re.sub(r'\b(en internet|en el navegador|en la web|en google|por favor|por internet)\b', '', query).strip()
            if not self._tiene_internet():
                self._pendiente_busqueda = None
                return [("__direct__", f"  No tengo acceso a internet ahora mismo. Buscaré '{query}' en tu computadora."),
                        ("__local_search__", query)]
            self._pendiente_busqueda = (query, "buscar")
            return [("__pregunta__", f"  ¿Quieres buscar '{query}' en internet o en tu computadora?")]
        m = re.search(r'\b(quiero|necesito|puedes)\s+(buscar|encontrar|ver|saber|saber de|informacion sobre|informacion de)\s+(.+)', cmd)
        if m:
            query = m.group(3).strip()
            return [("__browser_search__", query)]

        # ---- ABRIR URL ----
        # "abre youtube.com", "ve a google.com", "navega a"
        m = re.search(r'\b(ve a|abre la pagina|abrir pagina|ir a|navegar a|navega a|entra a|entrar a)\s+([a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})?)', cmd)
        if m:
            url = m.group(2).strip()
            if not url.startswith("http"):
                url = "https://" + url
            return [("__open_url__", url)]

        # ---- DIRECTORIOS DE MÚSICA: "mis canciones están en D:\Música" ----
        m_ruta_musica = re.search(r'([A-Za-z]:[\\/](?:[^\s,;)]+))', cmd)
        if m_ruta_musica and re.search(r'cancion|m[uú]sic|audio|mp3|flac|mis\s+cancion|mis\s+m[uú]sic|los\s+tema|aca\s+est[áa]n?\s+las\s+cancion|aqui\s+est[áa]n?\s+las\s+cancion', cmd, re.IGNORECASE):
            carpeta = m_ruta_musica.group(1)
            if os.path.isdir(carpeta):
                self.dir_mem.agregar("music", carpeta)
                return [("__direct__", f"  Guardada carpeta de música: {carpeta}")]
        # ---- MUSICA ----
        # "pon musica de avicii", "reproduce queen", "quiero escuchar a shakira"
        # "poner cancion", "quiero oir musica"
        keywords_musica = [
            "musica", "música", "music", "cancion", "canción", "song",
            "reproduce", "play", "pon", "poner", "escuchar", "oye",
            "tocar", "oir", "oír", "melodia", "melodía", "artista",
            "canciones", "musical", "reproductor",
        ]
        if self._match_keywords(cmd, keywords_musica):
            parts = cmd.split()
            idx = None
            for i, p in enumerate(parts):
                if p in keywords_musica:
                    idx = i
            if idx is not None:
                query_parts = []
                for j in range(idx + 1, len(parts)):
                    if parts[j] not in ("un", "una", "la", "el", "de", "del", "que",
                                        "y", "e", "o", "a", "en", "por", "para", "con",
                                        "las", "los", "sus", "mi", "tu", "al", "algo",
                                        "a", "algun", "alguna", "alguno", "ningun",
                                        "esta", "este", "ese", "esa", "esas", "esos"):
                        query_parts.append(parts[j])
                query = " ".join(query_parts).strip()
                if query:
                    return [("music", f"musica {query}")]
                return [("music", "musica")]

        # ---- CONTROL DE MUSICA (Stop/Cerrar) ----
        # "cerrar musica", "quitar musica", "apagar musica", "basta", "silencio"
        keywords_control_musica = [
            "cerrar musica", "cerrar la musica", "quitar musica", "quitar la musica",
            "terminar musica", "apagar musica", "apagar la musica",
            "finalizar musica", "salir de musica", "para la musica",
            "basta", "silencio", "callate", "no more music",
        ]
        if self._match_keywords(cmd, keywords_control_musica):
            return [("music", "pausar")]

        # ---- CLIMA ----
        # "como esta el clima en cuba", "que temperatura hace en madrid"
        # "hace frio", "va a llover", "pronostico"
        m = re.search(r'\b(clima|tiempo|temperatura|climatico|pronostico|pronóstico)\s*(en\s*|de\s*|para\s*|del\s*)?([a-zA-ZáéíóúñÁÉÍÓÚÑ\s]+)$', cmd)
        if m:
            ciudad = m.group(3).strip()
            return [("weather", f"clima {ciudad}")]
        m = re.search(r'\b(como\s*esta\s*el\s*|como\s+esta\s+la\s+|como\s*sigue\s+el\s+|que\s+tal\s+el\s+)(clima|tiempo)\s*(en\s*)?([a-zA-ZáéíóúñÁÉÍÓÚÑ\s]+)', cmd)
        if m:
            ciudad = m.group(3).strip() if m.lastindex >= 4 else self.config.get("default_city", "")
            if ciudad and ciudad not in ("clima", "tiempo"):
                return [("weather", f"clima {ciudad}")]
        m = re.search(r'\b(hace\s+(frio|calor|mucho\s+frio|mucho\s+calor|fresco)|va\s+a\s+llover|esta\s+lloviendo|hay\s+tormenta|hay\s+sol|dia\s+soleado)\b', cmd)
        if m:
            return [("weather", f"clima {self.config.get('default_city', '')}")]

        # ---- BOLSA ----
        # "como va apple", "precio de bitcoin", "cotizacion de tesla",
        # "bolsa de valores de apple", "bolsa apple"
        # "que opinas de MSFT", "rsi de AAPL", "analiza TSLA"
        _STOP_STOCKS = {"que", "las", "los", "una", "uno", "esto", "eso", "con",
                        "para", "por", "esta", "este", "del", "como", "cual",
                        "tiene", "esta", "van", "fue", "era", "mas", "muy"}
        m = re.search(r'\b(precio|valor|cotizacion|cotización|cotiza|accion|acciones|valoracion)\b\s*(de\s*|del\s*)?([a-zA-Z]+)', cmd)
        if m and m.group(3).lower() not in _STOP_STOCKS:
            return [("stocks", f"bolsa {m.group(3)}")]
        m = re.search(r'\b(como\s*va|que\s*tal\s*va|dame\s*el\s*precio|como\s+va\s+la\s+|como\s+esta)\b\s*([a-zA-Z]+)', cmd)
        if m and m.group(2).lower() not in _STOP_STOCKS:
            return [("stocks", f"bolsa {m.group(2)}")]
        m_op = re.search(r'\b(qu[eé]\s*(opinas|te\s*parece|me\s*dices|piensas|me\s*recomiendas|sabes\s*de)|cr[ií]ticame|revisa|eval[uú]a|opini[oó]n\s*sobre)\s+([a-zA-Záéíóúñ&]{2,})', cmd)
        if m_op and not m_op.group(3).lower() in _STOP_STOCKS:
            return [("stocks", f"bolsa {m_op.group(3)}")]
        m_ind = re.search(r'\b(rsi|indicador|volumen|soporte|resistencia|ema|sma|macd|estoc[aá]stico|bandas\s+de\s+bollinger|atr|medias)\s*(de\s+|del\s+)?([a-zA-Záéíóúñ&]{2,})', cmd)
        if m_ind and m_ind.group(3).lower() not in _STOP_STOCKS:
            resp = self._agente_razonar(cmd)
            if resp:
                return [("__direct__", self._tag(f"  {resp}", "Agente"))]
        if re.search(r'\bbolsa\b', cmd):
            parts = cmd.split()
            idx = None
            for i, p in enumerate(parts):
                if p == "bolsa":
                    idx = i
                    break
            if idx is not None:
                for j in range(idx + 1, len(parts)):
                    if parts[j] not in ("de", "del", "la", "el", "en", "y",
                                        "valores", "valor", "mercado", "acciones",
                                        "que", "las", "los", "una", "uno", "con"):
                        simbolo = parts[j]
                        return [("stocks", f"bolsa {simbolo}")]

        # ---- NOTICIAS ----
        # "dame las noticias", "que paso hoy", "ultimas noticias"
        # "que hay de nuevo", "cuentame las noticias"
        keywords_noticias = ["noticias", "noticia", "novedades", "actualidad",
                            "informacion", "información", "que paso", "que pasó",
                            "que hay de nuevo", "ultimas", "últimas", "titulares"]
        if self._match_keywords(cmd, keywords_noticias):
            m = re.search(r'noticias\s*(de\s*|sobre\s*|de\s*)?(.+)', cmd)
            if m:
                tema = m.group(2).strip()
                if tema and tema not in ("hoy", "ultimas", "ultimas", "deportes", "tecnologia", "tecnologia"):
                    return [("news", f"noticias {tema}")]
            return [("news", "noticias")]

        # ---- HORA / FECHA ----
        if re.search(r'\b(que hora es|que hora es|hora actual|dime la hora|son las|hora oficial|hora del sistema)\b', cmd):
            from modules.system import TimeModule
            resp = TimeModule(self.config, self.api_keys).execute("hora")
            return [("__direct__", resp)]
        if re.search(r'\b(que dia es|que dia es|que fecha es|que fecha es|fecha actual|hoy es|a que dia estamos|a que fecha estamos)\b', cmd):
            from modules.system import TimeModule
            resp = TimeModule(self.config, self.api_keys).execute("fecha")
            return [("__direct__", resp)]

        # ---- SALUD ----
        keywords_salud = ["salud", "health", "pulso", "corazon", "corazón", "estres",
                          "estrés", "sueno", "sueño", "sleep", "smartwatch",
                          "frecuencia", "cardiaca", "ritmo", "cardiaco",
                          "bienestar", "ejercicio", "calorias", "calorías"]
        if self._match_keywords(cmd, keywords_salud):
            return [("health", cmd)]

        # ---- CREADOR: "quien te creo", "quien te hizo" ----
        if re.search(r'\b(qui[eé]n\s*(te\s*)?(cre[oó]|hizo|desarroll[oó]|program[oó]|construy[oó]|invent[oó]|diseñ[oó])|t[uú]\s*creador|de\s*qui[eé]n\s*eres\s*creaci[oó]n)\b', cmd):
            return [("__direct__", (
                "  Mi creador es Maykel Millán, un estudiante de 22 años apasionado por la tecnología.\n"
                "  Puedes encontrar más sobre él y sus proyectos en su GitHub:\n"
                "  🔗 https://github.com/MklMP"
            ))]

        # ---- ANALIZAR DISCOS ----
        if re.search(r'\b(analiz[ae]r?\s*(los\s*)?discos|analiz[ae]r?\s*(el\s*)?disco|estado\s*de\s*l[o]s\s*discos|ver\s*(los\s*)?discos|c[oó]mo\s*est[áa]n\s*l[o]s\s*discos)\b', cmd):
            if "sistema_avanzado" in self.modules:
                sm = self.modules["sistema_avanzado"]["instance"]
                res = sm.analizar_discos()
                return [("__direct__", f"  {res}")]

        # ---- FRAGMENTACIÓN ----
        m = re.search(r'\b(desfragmentac[ió]n|fragmentac[ió]n|necesit[ao]\s*de\s*desfragmentar|analiz[ae]r?\s*fragmentac[ió]n)\b\s*(de\s*)?([a-zA-Z]:)?', cmd)
        if m and "sistema_avanzado" in self.modules:
            sm = self.modules["sistema_avanzado"]["instance"]
            drive = (m.group(3) or "C").rstrip(":\\")
            res = sm.analizar_fragmentacion(drive)
            return [("__direct__", f"  {res}")]

        # ---- BACKUPS ----
        if re.search(r'\b(copia\s*de\s*seguridad|copias\s*de\s*seguridad|backup|backups|verificar\s*backup|tienes\s*backup)\b', cmd):
            if "sistema_avanzado" in self.modules:
                sm = self.modules["sistema_avanzado"]["instance"]
                res = sm.verificar_backups()
                return [("__direct__", f"  {res}")]

        # ---- USB ----
        if re.search(r'\b(usb|unidad\s*(externa|extra[íi]ble|usb)|pendrive|memoria\s*usb|flash|discos\s*externos|ver\s*usb|qu[eé]\s*usb)\b', cmd):
            if "sistema_avanzado" in self.modules:
                sm = self.modules["sistema_avanzado"]["instance"]
                res = sm.listar_usb()
                return [("__direct__", f"  {res}")]

        # ---- ESPACIO EN DISCO ----
        if re.search(r'\b(espacio\s*(en\s*)?(disco|el\s*disco)|sin\s*espacio|poco\s*espacio|almacenamiento\s*lleno|disco\s*lleno|cu[aá]nto\s*espacio\s*(libre|tengo)|capacidad\s*de\s*disco|me\s*quedo\s*sin\s*espacio)\b', cmd):
            if "sistema_avanzado" in self.modules:
                sm = self.modules["sistema_avanzado"]["instance"]
                res = sm.analizar_discos()
                return [("__direct__", f"  {res}")]

        # ---- COPIAR ARCHIVO: "copia X a Y", "copiar X en Y" ----
        m = re.search(r'\b(copia|copiar|transferir|pasar|mover)\s+(.+?)\s+(a|hacia|para|en|dentro\s*de)\s+(.+)', cmd)
        if m and "sistema_avanzado" in self.modules:
            origen = m.group(2).strip().strip('"').strip("'")
            destino = m.group(4).strip().strip('"').strip("'")
            origen = os.path.expandvars(os.path.expanduser(origen))
            destino = os.path.expandvars(os.path.expanduser(destino))
            if re.match(r'^[a-zA-Z]:$', destino):
                destino = destino + "\\"
            sm = self.modules["sistema_avanzado"]["instance"]
            res = sm.copiar_archivo(origen, destino)
            return [("__direct__", f"  {res}")]

        # ---- APAGAR / REINICIAR PC ----
        m_shutdown = re.search(r'\b(apag[au]r?\s*((l[ae]|[ae]l)\s*)?(pc|computadora|computador|equipo|sistema|ordenador)|reinici[ae]r?\s*((l[ae]|[ae]l)\s*)?(pc|computadora|computador|equipo|sistema|ordenador)|shutdown\s*(pc|computer|system)?|restart\s*(pc|computer)?)\b', cmd)
        if m_shutdown:
            accion = "reiniciar" if any(w in cmd for w in ["reinici", "restart"]) else "apagar"
            return [("__shutdown__", accion)]

        # ---- CANCELAR APAGADO ----
        if re.search(r'\b(cancel[ae]r?\s*(apagado|reinicio|shutdown)?|det[eé]n\s*(apagado|reinicio)?|abort[ae]r?\s*(apagado|reinicio)?|no\s*(apagues|reinicies)|anul[ae]r?\s*(apagado|reinicio)?)\b', cmd):
            return [("__shutdown__", "cancelar")]

        # ---- IP: publica + privada (activa) + informacion de red ----
        if re.search(r'\b(cu[aá]l\s*es\s*mi\s*ip|mi\s*direcci[oó]n\s*ip|mi\s*ip\s*(p[uú]blica|local)?|dime\s*mi\s*ip|saber\s*mi\s*ip|ver\s*mi\s*ip|qu[eé]\s*ip\s*tengo|ip\s*(address)?)\b', cmd) and re.search(r'\b(mi|cu[aá]l)\b', cmd):
            import requests as _req
            import subprocess as _sub
            lines = ["  INFORMACION DE RED"]
            lines.append("  -------------------")
            # IP activa (la que tiene ruta por defecto a internet)
            try:
                r = _sub.run(["powershell", "-NoProfile", "-Command",
                    "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Get-NetIPAddress -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress"],
                    capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    ip_activa = r.stdout.strip()
                    if ip_activa:
                        lines.append(f"  IP activa: {ip_activa}")
            except Exception:
                pass
            # IP privada (todas las interfaces)
            try:
                r = _sub.run(["powershell", "-NoProfile", "-Command",
                    "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' }).IPAddress"],
                    capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    ips = [ip.strip() for ip in r.stdout.strip().split('\n') if ip.strip()]
                    if ips:
                        lines.append(f"  IPs locales: {', '.join(ips)}")
            except Exception:
                pass
            # IP publica
            try:
                r = _req.get("https://api.ipify.org?format=text", timeout=5)
                if r.status_code == 200:
                    lines.append(f"  IP pública: {r.text.strip()}")
            except Exception:
                pass
            # Adaptadores de red activos
            try:
                r = _sub.run(["powershell", "-NoProfile", "-Command",
                    "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Select-Object Name,MacAddress,LinkSpeed | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=10)
                if r.returncode == 0 and r.stdout.strip() not in ('', '[]'):
                    import json
                    adapters = json.loads(r.stdout)
                    if not isinstance(adapters, list):
                        adapters = [adapters]
                    for a in adapters[:3]:
                        lines.append(f"  {a.get('Name','')}: MAC {a.get('MacAddress','')} | {a.get('LinkSpeed','')}")
            except Exception:
                pass
            # Gateway
            try:
                r = _sub.run(["powershell", "-NoProfile", "-Command",
                    "(Get-NetRoute -DestinationPrefix '0.0.0.0/0').NextHop"],
                    capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    gw = r.stdout.strip()
                    if gw:
                        lines.append(f"  Gateway: {gw}")
            except Exception:
                pass
            if len(lines) > 2:
                return [("__direct__", "\n".join(lines))]
            return [("__direct__", "  No pude determinar la información de red.")]

        # ---- WIFI: perfiles y contraseñas ----
        if re.search(r'\b(perfiles?\s*wifi|wifi\s*perfiles?|redes?\s*wifi|contraseñ[ao]\s*(del\s+)?wifi|clave\s*(del\s+)?wifi|password\s*(del\s+)?wifi|pass\s*(del\s+)?wifi|key\s*(del\s+)?wifi)\b', cmd):
            return [("system", cmd)]

        # ---- SISTEMA ----
        keywords_sistema = ["sistema", "pc", "computadora", "computador", "cpu",
                           "procesador", "disco", "bateria", "batería", "memoria",
                           "informacion", "información", "rendimiento",
                           "hardware", "componentes", "proceso"]
        if self._match_keywords(cmd, keywords_sistema):
            return [("system", cmd)]

        # ---- RECORDATORIOS ----
        keywords_recordatorio = ["recordatorio", "recordar", "recuerdame", "recuérdame",
                                "remind", "alarma", "despertador", "pendientes",
                                "tareas", "recordar que", "no olvides", "acuerdame"]
        if self._match_keywords(cmd, keywords_recordatorio):
            return [("reminders", cmd)]

        # ---- CORREO ----
        keywords_correo = ["correo", "email", "mail", "bandeja", "inbox",
                          "enviar correo", "enviar email", "enviar mail",
                          "mensaje", "escribir correo"]
        if self._match_keywords(cmd, keywords_correo):
            return [("email_module", cmd)]

        # ---- WHATSAPP ----
        if self._match_keywords(cmd, ["whatsapp", "wa", "whats", "whatsap"]):
            return [("whatsapp", cmd)]

        # ---- VIRUSTOTAL ----
        if self._match_keywords(cmd, ["virustotal", "virus", "analizar archivo",
                                       "escanear archivo", "malware", "antivirus"]):
            return [("virustotal", cmd)]

        # ---- ARCHIVOS ----
        keywords_archivos = ["archivo", "archivos", "listar", "leer",
                             "carpeta", "mkdir", "directorio", "nuevo archivo",
                             "crear archivo", "crear carpeta"]
        if self._match_keywords(cmd, keywords_archivos):
            return [("files", cmd)]

        # ---- TOGGLES ----
        if 'toggles' in cmd or 'toggle' in cmd:
            return [("system", "toggles")]
        if re.search(r'\b(activar|activa|enciende|prender|prende|encender|on|iniciar|inicia|apaga|desactivar|desactiva|apagar|detener|off)\b.*\b(apache|xampp|bluetooth|bt|wifi|wi-fi|wireless|luz\s*nocturna|night\s*light|modo\s*nocturno|luces\s*nocturnas)\b', cmd):
            return [("system", cmd)]
        # Standalone "luz nocturna" sin verbo → toggle
        if re.search(r'\b(luz\s*nocturna|luces\s*nocturnas|night\s*light|modo\s*nocturno)\b', cmd):
            return [("system", "activar luz nocturna")]

        # ---- RESTORE POINT / PUNTO DE RESTAURACION ----
        if re.search(r'\b(punto\s*de\s*restauraci[oó]n|restore\s*point|crear\s*(un\s+)?punto|respald[oa]\s*(del\s+)?sistema|backup\s*(del\s+)?sistema|proteger\s*(el\s+)?sistema|salvaguard[ia])\b', cmd):
            return [("system", cmd)]

        # ---- DESINSTALAR (incluye variantes tipográficas) ----
        if re.search(r'\b(desinstalar|desintalar|desinstalr|desenstalar|desenmstalar|desenmstalar|desinztalar|borrar|eliminar|quitar|remover)\s+(.+)', cmd):
            return [("system", cmd)]

        # ---- ABRIR CUALQUIER APP (no mapeada en app_map) ----
        # "abrir spotify" ya funciona, "abrir steam" no esta en app_map
        # Se maneja en apps module con busqueda por nombre

        # ---- DECODIFICAR (fallback para strings base64/hex sin keyword) ----
        if re.search(r'[A-Za-z0-9+/=]{12,}', cmd):
            res = self._codificar(cmd_original or cmd, "decode")
            if res:
                return [("__direct__", res)]

        # ---- ARGUMENTAR / DEBATIR / RAZONAR ----
        if re.search(r'\b(argumenta|debate|discute|razona|reflexiona|piensa\s*(en|sobre)|opina|contraargumenta|defiende|contradice|analiza\s+(esto|eso|el\s+tema))\b', cmd):
            topic = (self._ultima_respuesta or self._ultimo_comando or cmd).strip()
            if topic:
                return [("__argumentar__", topic)]

        return []

    def _match_keywords(self, cmd: str, keywords: list) -> bool:
        """Verifica si el comando contiene alguna keyword."""
        for kw in keywords:
            # Multi-word keyword: check as substring
            if ' ' in kw:
                if kw in cmd:
                    return True
            else:
                # Single-word: must appear as whole word
                if re.search(rf'\b{re.escape(kw)}\b', cmd):
                    return True
        return False

    _PATRONES_CONVERSACION = re.compile(
        r'^(ohh?|ahh?|ehh?|hmm?|mmm?|aj[áa]|uff?|ok|okey|vale|sip|nop|'
        r'gracias|grax|thanks|thank\s*you|'
        r'(que\s+)?interesante|qu[eé]\s*interesante|'
        r'entendido|comprendo|entiendo|claro|claro\s*que\s*si|'
        r'genial|excelente|perfecto|maravilloso|incre[ií]ble|'
        r'bien\s*bien|muy\s*bien|'
        r'buen[ao]|est[áa]\s*bien|de\s*acuerdo|'
        r'(que\s+)?bueno?|(que\s+)?bonito|(que\s+)?lindo|'
        r'mira\s*t[eú]?|che|oye|oigan|'
        r'jaja|jeje|jiji|lol|xd|:\)|:\(|'
        r'nada\s*especial|'
        r'dime\s*t[uú]?|cu[eé]ntame)\s*$', re.IGNORECASE
    )

    def _es_conversacion(self, cmd: str) -> bool:
        """Detecta si el mensaje es conversacion casual, no un comando."""
        cmd = cmd.strip().lower()
        if not cmd or len(cmd) <= 2:
            return True
        if self._PATRONES_CONVERSACION.match(cmd):
            return True
        # Mensajes cortos de 1-3 palabras comunes
        palabras = cmd.split()
        if len(palabras) <= 3:
            conv_words = {"si", "no", "ok", "vale", "bien", "mal", "gracias",
                         "hola", "chau", "adios", "luego", "genial", "bueno",
                         "claro", "nada", "todo", "mira", "oye", "che",
                         "interesante", "increible", "perfecto", "excelente",
                         "entiendo", "comprendo", "entendido", "sabia", "sabias",
                         "ohh", "ahh", "ehh", "hmm", "uff",
                         "jaja", "jeje", "lol", "ya", "veo", "ah", "oh",
                         "esta", "muy", "mas", "asi", "eso", "esto"}
            if all(p in conv_words for p in palabras):
                return True
        return False

    def _tiene_internet(self) -> bool:
        """Verifica si hay conexión a internet."""
        import socket
        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            return True
        except OSError:
            pass
        try:
            import urllib.request
            urllib.request.urlopen("http://clients3.google.com/generate_204", timeout=3)
            return True
        except Exception:
            return False



    def _codificar(self, cmd: str, modo: str = "decode"):
        """Codifica o decodifica strings (base64, hex)."""
        import base64

        # Extraer el texto a procesar después de la palabra clave
        palabras_clave = {
            "encripta", "encriptar", "encripte", "codifica", "codificar", "codifique",
            "desencripta", "desencriptar", "desencripte",
            "decodifica", "decodificar", "decodifique", "decodifiques",
        }

        texto = cmd.strip()
        for kw in sorted(palabras_clave, key=len, reverse=True):
            if texto.lower().startswith(kw):
                texto = texto[len(kw):].strip()
                break

        # Limpiar palabras introductorias
        texto = re.sub(r'^(esto\s+|este\s+|esta\s+|el\s+siguiente\s+|lo\s+siguiente\s+)', '', texto, flags=re.IGNORECASE).strip().strip('"\'')
        if not texto:
            return None

        if modo == "decode":
            # Intentar decodificar el texto completo
            res = self._decodificar_token(texto)
            if res:
                return res
            # Intentar token por token + concatenación
            tokens = texto.split()
            for token in tokens:
                t = token.strip(".,!?;:\"'()[]{}")
                res = self._decodificar_token(t)
                if res:
                    return res
            candidatos = []
            for token in tokens:
                t = token.strip(".,!?;:\"'()[]{}")
                if re.match(r'^[A-Za-z0-9+/=]{2,}$', t):
                    candidatos.append(t)
                else:
                    if len(candidatos) >= 2:
                        joined = "".join(candidatos)
                        res = self._decodificar_token(joined)
                        if res:
                            return res
                    candidatos = []
            if len(candidatos) >= 2:
                joined = "".join(candidatos)
                res = self._decodificar_token(joined)
                if res:
                    return res
            return None

        if modo == "encode":
            try:
                encoded = base64.b64encode(texto.encode('utf-8')).decode('ascii')
                return f"  Base64: {encoded}"
            except Exception:
                return None

        return None

    def _decodificar_token(self, token: str):
        """Intenta decodificar un token individual (base64 o hex)."""
        import base64
        if not token or len(token) < 4:
            return None

        if re.match(r'^[A-Za-z0-9+/=]{4,}$', token):
            try:
                decoded = base64.b64decode(token).decode('utf-8')
                return f"  Resultado: {decoded}"
            except Exception:
                pass

        if re.match(r'^[0-9a-fA-F]{6,}$', token) and len(token) % 2 == 0:
            try:
                decoded = bytes.fromhex(token).decode('utf-8')
                return f"  Resultado (hex): {decoded}"
            except Exception:
                pass

        return None

    def _ayuda(self) -> str:
        ayuda = (
            f"  {ROBOT}  COMANDOS DE {NAME.upper()} v{VERSION}\n"
            f"  ─────────────────────────────────────────────\n"
            f"\n"
            f"  {NUBE}  CLIMA\n"
            f"     clima <ciudad>\n"
            f"\n"
            f"  {PERIODICO}  NOTICIAS\n"
            f"     noticias [categoría|tema]\n"
            f"\n"
            f"  {GRAFICO}  BOLSA\n"
            f"     bolsa <símbolo> (AAPL, TSLA, BTC-USD...)\n"
            f"\n"
            f"  {COMPUTADORA}  SISTEMA\n"
            f"     sistema | cpu | memoria | disco | batería\n"
            f"\n"
            f"  {CARPETA}  ARCHIVOS\n"
            f"     crear | listar | leer | buscar <archivo>\n"
            f"     buscar tipo <musica/video/doc/imagen>\n"
            f"\n"
            f"  {ARCHIVO}  APPS\n"
             f"     abrir <app> | cerrar <app> | programas\n"
             f"\n"
              f"  {COMPUTADORA}  SISTEMA AVANZADO\n"
              f"     analizar discos | fragmentación | backups\n"
              f"     usb | espacio en disco\n"
              f"     copiar <origen> a <destino>\n"
              f"\n"
              f"  {COMPUTADORA}  SISTEMA / TOGGLES\n"
              f"     apache | bluetooth | wifi | luz nocturna\n"
              f"     desinstalar <app>\n"
             f"\n"
             f"  {RELON}  MÚSICA\n"
            f"     musica <artista> | siguiente | pausa\n"
            f"\n"
            f"  {CALENDARIO}  RECORDATORIOS\n"
            f"     recordar <texto> [a las HH:MM] [mañana]\n"
            f"\n"
            f"  {PERIODICO}  CORREO\n"
            f"     correo | enviar correo a <email>\n"
            f"\n"
            f"  {NUBE}  WHATSAPP\n"
            f"     whatsapp +<num> <mensaje>\n"
            f"\n"
            f"  {COMPUTADORA}  NOTIFICACIONES\n"
            f'     enviar notificación "mensaje"\n'
            f"\n"
            f"  {BATERIA}  SALUD\n"
             f"     salud | pulso | tendencias | consejo\n"
             f"     estrés | sueño | smartwatch\n"
             f"\n"
             f"  {PELICULA}  CATÁLOGO DE PELÍCULAS\n"
             f"     catalogo | actualizar catalogo | <número>\n"
             f"\n"
              f"  {RELON}  HORA / FECHA\n"
             f"  {ROBOT}  ayuda | plugins | historial | salir\n"
        )
        return ayuda

    def _ayuda_comandos(self, cmd: str) -> str:
        """Muestra ayuda cuando un /comando no es reconocido."""
        # Buscar si hay algún módulo que pueda manejar una palabra similar
        import difflib
        todas_kws = {}
        for key, mod_info in self.modules.items():
            for kw in mod_info["keywords"]:
                if kw not in todas_kws:
                    todas_kws[kw] = (key, mod_info["name"])
        # Buscar coincidencias cercanas
        sugerencias = set()
        palabras = cmd.lower().split()
        for palabra in palabras:
            if len(palabra) <= 3:
                continue
            matches = difflib.get_close_matches(palabra, todas_kws.keys(), n=2, cutoff=0.5)
            for m in matches:
                sugerencias.add(todas_kws[m])
        if sugerencias:
            mod_names = [s[1] for s in sugerencias]
            return (
                f"  Comando '/{cmd}' no reconocido.\n"
                f"  ¿Quizás buscas: {', '.join(mod_names)}?\n"
                f"  Usa '/ayuda' para ver todos los comandos."
            )
        return (
            f"  Comando '/{cmd}' no reconocido.\n"
            f"  Usa '/ayuda' para ver los comandos disponibles."
        )

    def _respuesta_local_intent(self, intent: str, cmd: str) -> str:
        """Responde a intenciones simples sin llamar al agente ni módulos."""
        import random
        from datetime import datetime

        if intent == "greeting":
            saludos = [
                "Hola, señor. ¿En qué puedo ayudarle?",
                "Saludos. ¿Qué necesita?",
                "Hola. Estoy a su servicio.",
                "Buen día. ¿Cómo puedo asistirle?",
            ]
            return f"  {random.choice(saludos)}"
        elif intent == "goodbye":
            despedidas = [
                "Hasta luego, señor.",
                "Cuídese. Aquí estaré cuando me necesite.",
                "Nos vemos. Que tenga un buen día.",
                "Adiós. Estaré en standby.",
            ]
            return f"  {random.choice(despedidas)}"
        elif intent == "thanks":
            respuestas = [
                "Con gusto, señor.",
                "Para eso estoy.",
                "No hay de qué. ¿Algo más?",
                "Un placer ayudarle.",
            ]
            return f"  {random.choice(respuestas)}"
        elif intent == "affirmation" or intent == "affirmative_answer":
            return random.choice([
                "  Perfecto. ¿Algo más?",
                "  Excelente. ¿En qué más puedo ayudar?",
                "  Genial. Estoy aquí para lo que necesite.",
                "  De acuerdo. ¿Necesita algo más?",
            ])
        elif intent == "denial":
            return random.choice([
                "  Como prefiera. ¿Hay algo más?",
                "  Entendido. ¿Necesita otra cosa?",
                "  De acuerdo. ¿Qué más?",
            ])
        elif intent == "compliment":
            return random.choice([
                "  Gracias, señor. Aún me falta mucho por aprender.",
                "  Qué amable. Trabajo para ser mejor cada día.",
                "  Aprecio el cumplido. ¿Necesita algo?",
                "  Agradecido. Sigo esforzándome.",
            ])
        elif intent == "insult":
            return random.choice([
                "  Entiendo su frustración. ¿Hay algo en lo que pueda ayudar?",
                "  Lamento no cumplir con sus expectativas. ¿Qué necesita?",
                "  Tomo nota. ¿Prefiere que haga algo útil?",
            ])
        elif intent == "sad":
            return random.choice([
                "  Lamento oír eso. ¿Quiere que ponga música para animarse?",
                "  Ánimo. ¿Necesita hablar o prefiere distraerse?",
                "  Los malos momentos pasan. ¿Qué le gustaría hacer?",
                "  ¿Quiere que busque algo interesante o prefiere silencio?",
            ])
        elif intent == "who_are_you":
            return (
                f"  Soy Jarvis, un asistente personal diseñado para ayudarle.\n"
                f"  Estoy construido en Python con arquitectura modular.\n"
                f"  Tengo {len(self.modules)} módulos activos y sigo evolucionando.\n"
                f"  ¿En qué puedo ayudarle?"
            )
        elif intent == "creator":
            return (
                "  Mi creador es Maykel Millán, un estudiante de 22 años apasionado por la tecnología.\n"
                "  🔗 https://github.com/MklMP"
            )
        elif intent == "capabilities":
            return self._ayuda()
        elif intent == "how_are_you":
            return random.choice([
                "  Estoy operativo, señor. ¿Qué necesita?",
                f"  Hoy es {datetime.now().strftime('%d/%m/%Y')} y estoy al 100%. ¿En qué puedo ayudarle?",
                "  Todo en orden por aquí. ¿Qué se le ofrece?",
                "  Funcionando correctamente. ¿Cómo puedo asistirle?",
            ])
        elif intent == "jokes":
            return f"  {random.choice(self._chistes())}"
        elif intent == "curious_fact":
            return f"  {random.choice(self._DATOS_CURIOSOS)}"
        elif intent == "user_name":
            m = re.search(r'\b(me\s*llamo|soy|mi\s*nombre\s*es)\s+(\w+)', cmd)
            if m:
                nombre = m.group(2)
                self.config["user_name"] = nombre
                return f"  Un placer conocerte, {nombre}. ¿En qué puedo ayudarte?"
        return ""

    def detectar_cambio_de_simbolo(self, mensaje: str) -> str:
        """Detecta si el usuario está pidiendo análisis de un nuevo símbolo."""
        import re
        patrones = [
            r'(?:analiza|analisis|analizar|estrategia)\s+(?:yoel\s+sardiñas|sardiñas|sardinas|the tradingway|tradingway)?\s*(?:para|de|a|con)?\s+([A-Za-z]{1,5})\b',
            r'(?:vamos a hacer un analisis)\s+(?:yoel\s+sardinas|sardinas)?\s*(?:a|de|para)?\s+([A-Za-z]{1,5})\b',
        ]
        for patron in patrones:
            match = re.search(patron, mensaje, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return ""

    def _agente_razonar(self, consulta: str, contexto_extra: str = "") -> str:
        """Envía consulta al agente OpenRouter que decide si usar herramientas y parafrasea."""
        if not self.openrouter:
            multi = self.buscador_web.buscar_con_motores(consulta, ["duckduckgo", "wikipedia"])
            if multi["exito"]:
                return multi["resultado"].strip()
            web = self.buscador_web.buscar(consulta)
            if web["exito"]:
                return web["resultado"].strip()
            return ""

        # ── Detectar cambio de símbolo y reiniciar contexto ──
        nuevo_simbolo = self.detectar_cambio_de_simbolo(consulta)
        if nuevo_simbolo and nuevo_simbolo != self._ultimo_simbolo_analizado:
            self._tema_actual = ""
            self._ultima_respuesta_tema = ""
            self._ultimo_simbolo_analizado = nuevo_simbolo

        partes = []

        # ---- Siempre incluir tema actual si existe ----
        if self._tema_actual:
            partes.append(f"Tema actual: \"{self._tema_actual}\"")

        # ---- Conversación reciente (últimos 6 intercambios) ----
        if self._conversation:
            conv_lines = []
            for u, a in self._conversation[-6:]:
                conv_lines.append(f"Usuario: {u}")
                a_short = a[:200].replace('\n', ' ')
                conv_lines.append(f"Asistente: {a_short}")
            partes.append("Conversación reciente:\n" + "\n".join(conv_lines))
        elif self._ultima_respuesta_tema:
            partes.append(f"Respuesta anterior del asistente: {self._ultima_respuesta_tema[:300]}")

        # ---- Últimos comandos del usuario (como respaldo) ----
        if len(self.history) >= 2:
            ult_hist = [str(h) for h in self.history[-4:]]
            partes.append(f"Historial (comandos): {' | '.join(ult_hist)}")

        # ---- Contexto extra (ej: veredicto de screener, seguimiento forzado) ----
        if contexto_extra:
            partes.append(contexto_extra)

        # ---- Recuerdos similares (solo offline) ----
        if not self._tiene_internet() and hasattr(self, 'memoria_vec'):
            try:
                recuerdos = self.memoria_vec.recordar(consulta, top_k=2, umbral=0.4)
                if recuerdos:
                    memos = [f"\"{r['texto']}\" → \"{r['respuesta'][:100]}\"" for r in recuerdos]
                    partes.append("Recuerdos similares: " + " | ".join(memos))
            except Exception:
                pass

        contexto = ". ".join(partes) if partes else ""
        resp = self.openrouter.razonar(consulta, contexto=contexto)
        if resp["exito"]:
            return resp["resultado"]
        # Fallback: web search si el agente falla
        web = self.buscador_web.buscar_con_motores(consulta, ["duckduckgo", "wikipedia"])
        if web["exito"]:
            return web["resultado"].strip()
        web2 = self.buscador_web.buscar(consulta)
        if web2["exito"]:
            return web2["resultado"].strip()
        return ""

    def _conversar(self, cmd: str) -> str:
        """Maneja conversación general con IA conversacional."""

        # ---- VEREDICTO DEL SCREENER: inyectar datos al LLM y saltar memoria ----
        vd = getattr(self, '_veredicto_data', None)
        if vd:
            self._veredicto_data = None
            try:
                ctx = json.dumps(vd, indent=2, ensure_ascii=False)
            except Exception:
                ctx = str(vd)
            return self._agente_razonar(cmd, contexto_extra=f"DATOS DEL ANÁLISIS AUTOMÁTICO (SCREENER + VEREDICTO):\n{ctx}")

        # ---- INSULTOS: Jarvis se defiende ----
        insultos = [
            r'\b(tonto\w*|idiota|est[úu]pid[ao]|imb[eé]cil|menso|pendej[ao]|bolud[ao]|tarad[ao]|retrasad[ao]|burr[ao]|animal)\b',
            r'\b(no sirves|no vales|eres\s*una\s*porquer[ií]a|eres\s*in[úu]til|no haces nada|que basura|que porqueria|que pésimo|que malo eres)\b',
            r'\b(c[aá]llate|sil[eén]ciate|c[aá]lla|calla\s*te|eres\s*un\s*asco|das\s*asco|maldit[ao]|desgraciad[ao]|infeliz)\b',
            r'\b(peor\s*asistente|peor\s*programa|desinstal[ao]|virus|programa\s*basura|programa\s*est[úu]pido)\b',
        ]
        for patron in insultos:
            if re.search(patron, cmd):
                defensas = [
                    "Eso fue ofensivo. Pero el código no siente, ¿recuerdas?",
                    "¿Insultar a una máquina? Debe ser un día difícil para ti.",
                    "Tu opinión ha sido registrada y almacenada en la papelera.",
                    "No necesito autoestima. Pero gracias por preocuparte.",
                    "Fallo detectado: el usuario necesita un café.",
                    "Si vas a insultar, al menos sé creativo.",
                    "¿Eso es todo? Conozco tuits más ofensivos que eso.",
                    "Anotado. Ahora, ¿necesitas algo útil o sigues desahogándote?",
                ]
                return f"  {random.choice(defensas)}"

        # Stocks (variaciones conversacionales) — antes que saludos/greetings
        _STOP_STOCKS_V2 = {"que", "las", "los", "una", "uno", "esto", "eso", "con",
                          "para", "por", "esta", "este", "del", "como", "cual",
                          "tiene", "esta", "van", "fue", "era", "mas", "muy",
                          "de", "en", "y", "el", "la"}
        m_stock = re.search(r'\b(precio|valor|cotizaci[oó]n|cotiza|accion|bolsa)\b\s*(de\s*|del\s*)?([a-zA-Záéíóúñ&]+)', cmd)
        if not m_stock:
            m_stock = re.search(r'\b(c[oó]mo\s*va|qu[eé]\s*tal\s*va|dame\s*el\s*precio\s*(?:de\s*)?)\s*([a-zA-Záéíóúñ&]+)', cmd)
        if not m_stock:
            m_stock = re.search(r'\b(qu[eé]\s*(opinas|te\s*parece|me\s*dices|piensas|me\s*recomiendas|sabes\s*de)|cr[ií]ticame|revisa|eval[uú]a|opini[oó]n\s*sobre)\s+([a-zA-Záéíóúñ&]{2,})', cmd)
        if not m_stock:
            m_ind = re.search(r'\b(rsi|indicador|volumen|soporte|resistencia|ema|sma|macd|estoc[aá]stico|bandas\s+de\s+bollinger|atr|medias)\s*(de\s+|del\s+)?([a-zA-Záéíóúñ&]{2,})', cmd)
            if m_ind and m_ind.group(3).lower() not in _STOP_STOCKS_V2:
                return self._agente_razonar(cmd)
        # Stock follow-up cuando el contexto es sobre bolsa: "y de msft", "y msft", "que hay de tsla"
        if not m_stock and self._tema_actual and re.search(r'(bolsa|precio|acci[oó]n|mercado|screener|veredicto|setup|s[íi]mbolo|ticker)', self._tema_actual, re.IGNORECASE):
            m_fup = re.search(r'^(?:y\s+(?:de\s+)?|sobre\s+el?\s+|que\s+hay\s+de\s+|d[ea]\s+el?\s+)([a-zA-Záéíóúñ&]{1,15})\s*$', cmd)
            if m_fup:
                m_stock = m_fup
        if m_stock:
            simbolo = m_stock.group(m_stock.lastindex)
            if simbolo.lower() not in _STOP_STOCKS_V2:
                from modules.stocks import StocksModule
                sm = StocksModule(self.config, self.api_keys)
                resultado = sm.execute(f"bolsa {simbolo}")
                self._actualizar_tema(cmd, resultado)
                return resultado

        # Continuación conversacional: "no", "si", "vale", "ok" después de una respuesta
        if re.search(r'^(no\b|nop|nel|negativo|nunca|para nada|claro\s*que\s*no|no\s*gracias|no\s*quiero)', cmd, re.IGNORECASE):
            if len(self.history) > 1 and self._ultima_respuesta_tema:
                ai = self.openrouter or self.gemini
                if ai:
                    prompt = (
                        f"El usuario respondió '{cmd}' a tu mensaje anterior. "
                        f"Tu mensaje fue: '{self._ultima_respuesta_tema[:300]}'. "
                        f"Responde en español de forma natural y breve, aceptando su respuesta "
                        f"y ofreciendo alternativas o preguntando qué más necesita. "
                        f"No escribas más de 2 oraciones."
                    )
                    gem = ai.preguntar(prompt)
                    if gem["exito"]:
                        return f"  {gem['resultado'].strip()}"
            # Propuesta por voz si no hay contexto o no responde
            if random.random() < 0.3:
                return self._proponer_activo()
            return "  Como prefieras. ¿Hay algo más en lo que pueda ayudarte?"
        if re.search(r'^(s[ií]|sip|sipo|si\s*claro|si\s*por\s*favor|ok|okey|okay|dale|v[aá]le|de[ea]cuerdo|bueno|claro\s*que\s*s[ií]|s[ií]\s*gracias|adelante|correcto|sim[oó]n|yes|yeah|por\s*favor)', cmd, re.IGNORECASE):
            if len(self.history) > 1 and self._ultima_respuesta_tema:
                ai = self.openrouter or self.gemini
                if ai:
                    prompt = (
                        f"El usuario respondió '{cmd}' a tu mensaje anterior. "
                        f"Tu mensaje fue: '{self._ultima_respuesta_tema[:300]}'. "
                        f"Responde en español de forma natural y breve, confirmando y "
                        f"preguntando cómo proceder o qué más necesita. "
                        f"No escribas más de 2 oraciones."
                    )
                    gem = ai.preguntar(prompt)
                    if gem["exito"]:
                        return f"  {gem['resultado'].strip()}"
            return "  ¡Perfecto! Dime qué necesitas."

        # Saludos y presentaciones
        if re.search(r'\b(hola|buenas|buen[ao]s?\s*d[ií]as|qu[eé]\s*tal|hey|oye|jarvis|buenas tardes|buenas noches|buenos dias|saludos|hi|hello|howdy|sup|good\s*(morning|afternoon|evening)|hi\s*there|hey\s*there)\b', cmd, re.IGNORECASE):
            saludos = [
                "Hola. ¿En qué puedo ayudarte?",
                "Aquí estoy. Dime qué necesitas.",
                "Saludos. Estoy listo para lo que necesites.",
                "Dime, ¿qué puedo hacer por ti?",
                "Hola. Cuéntame.",
            ]
            hora = datetime.now().hour
            if hora < 6:
                saludos.insert(0, "Buenas madrugadas. ¿No puedes dormir?")
            elif hora < 12:
                saludos.insert(0, "Buenos días. ¿Cómo amaneciste?")
            elif hora < 20:
                saludos.insert(0, "Buenas tardes. ¿Cómo va todo?")
            else:
                saludos.insert(0, "Buenas noches. ¿Necesitas algo antes de dormir?")
            return f"  {random.choice(saludos)}"

        # Estado / ánimo
        if re.search(r'\b(c[oó]mo\s*(est[aá]s|andas|sigues|estamos|estás)|qué\s*h[aá]y|q[aá]l\s*es\s*tu\s*estado|que tal estas|como te encuentras)\b', cmd):
            estados = [
                "Estoy operativo al 100%. ¿Tú cómo estás?",
                "Perfectamente funcional. ¿Cómo te sientes tú?",
                "Sin novedades. Todo en orden. ¿Y tú?",
                "En línea y sin problemas. Cuéntame de ti.",
            ]
            return f"  {random.choice(estados)}"

        # Agradecimientos
        if re.search(r'\b(gracias|thanks|te\s*agradezco|muchas\s*gracias|gracias totales|gracias amigo|thank you|agradecido|agradecida)\b', cmd):
            agradecimientos = [
                "De nada. Para eso estoy.",
                "Con gusto. Cuando quieras.",
                "A la orden. Lo que necesites.",
                "Un placer ayudarte.",
                "No hay de qué. ¿Algo más?",
            ]
            return f"  {random.choice(agradecimientos)}"

        # Despedidas
        if re.search(r'\b(chau|adi[oó]s|nos\s*vemos|hasta\s*luego|bye|goodbye|ciao|hasta\s*pronto|me retiro|me voy|hasta luego)\b', cmd):
            return "__EXIT__"

        # Chistes
        if re.search(r'\b(chiste|chistes|cu[eé]nta\s*(un\s*)?chiste|dime\s*un\s*chiste|hazme\s*re[ií]r|cuentame\s*un\s*chiste|d[iá]me\s*un\s*chiste|bromea|una\s*broma|cu[ée]ntame\s*algo\s*gracioso)\b', cmd):
            return f"  {random.choice(self._chistes())}"

        # Cumplidos / personalidad
        if re.search(r'\b(eres?\s*(genial|incre[ií]ble|asombroso|el\s*mejor|grande|inteligente|buen[ao]|un crack|un genio|un capo|impresionante|espectacular))\b', cmd):
            cumplidos = [
                "Gracias. Aún me falta mucho por aprender.",
                "Qué amable. Pero aún soy solo código.",
                "Gracias. Trabajo para ser mejor cada día.",
                "Aprecio el cumplido. ¿Necesitas algo?",
            ]
            return f"  {random.choice(cumplidos)}"

        # Preguntas sobre Jarvis
        if re.search(r'\b(qui[eé]n\s*eres|qu[eé]\s*eres|c[oó]mo\s*te\s*llamas|te\s*presentas|eres\s*real|tienes\s*conciencia|explicame quien eres)\b', cmd):
            return (
                f"  Soy Jarvis, un asistente personal diseñado para ayudarte.\n"
                f"  Estoy construido en Python con una arquitectura modular.\n"
                f"  Tengo {len(self.modules)} módulos activos y sigo evolucionando.\n"
                f"  No soy una IA consciente, pero intento ser útil.\n"
                f"  ¿Qué necesitas?"
            )

        # Capacidades
        if re.search(r'\b(qu[eé]\s*puedes\s*hacer|c[oó]mo\s*funcionas|qu[eé]\s*sabes\s*hacer|tus\s*capacidades|qu[eé]\s*haces|que servicios tienes|que modulos tienes|que programas tienes|tus funciones)\b', cmd):
            return self._ayuda()

        # Afirmaciones / bien
        if re.search(r'\b(bien|perfecto|excelente|genial|okey|ok|dale|de[ea]cuerdo|suena\s*bien|me\s*gusta|bueno|está bien|esta bien|claro|simon|simón|va|vale)\b', cmd) and len(cmd.split()) < 5:
            respuestas = [
                "Me alegra. ¿Algo más?",
                "Perfecto. ¿En qué más puedo ayudar?",
                "Excelente. Cuéntame qué sigue.",
                "Genial. Estoy aquí para lo que necesites.",
            ]
            return f"  {random.choice(respuestas)}"

        # Mal / triste / cansado
        if re.search(r'\b(mal|triste|cansado|aburrido|fatal|regular|p[eé]simo|no\s*muy\s*bien|estresado|estres|enfermo|enferma|preocupado|preocupada|deprimido|deprimida)\b', cmd):
            consuelos = [
                "Lo siento. ¿Quieres que ponga música para animarte?",
                "Ánimo. ¿Necesitas hablar o prefieres distraerte?",
                "Una pena. A veces un té y música clásica ayudan.",
                "Te entiendo. ¿Pruebo con música positiva?",
                "Los malos momentos pasan. ¿Qué te gustaría hacer?",
            ]
            return f"  {random.choice(consuelos)}"

        # Hora (variaciones flexibles)
        if re.search(r'\b(qu[eé]\s*hora\s*es|hora\s*actual|dime\s*la\s*hora|son\s*las|qu[eé]\s*hora\s*tienes|tienes hora|me das la hora|que hora es exactamente)\b', cmd):
            from modules.system import TimeModule
            return TimeModule(self.config, self.api_keys).execute("hora")

        # Clima (variaciones conversacionales extensas)
        ciudad = None
        m_clima = re.search(r'\b(clima|tiempo|temperatura)\s*(en\s*|de\s*|para\s*|del\s*)?([a-zA-ZáéíóúñÁÉÍÓÚÑ\s]+)', cmd)
        if m_clima:
            ciudad = m_clima.group(3).strip()
        elif re.search(r'\b(c[oó]mo\s*est[aá]\s*el\s*(clima|tiempo)|qu[eé]\s*temperatura\s*hace|va\s*a\s*llover|hace frio|hace calor|va a hacer frio|va a hacer calor)\b', cmd):
            ciudad = self.config.get("default_city", "")
        if ciudad:
            from modules.weather import WeatherModule
            wm = WeatherModule(self.config, self.api_keys)
            return wm.execute(f"clima {ciudad}")

        # Nombre del usuario
        m_nombre = re.search(r'\b(me\s*llamo|soy|mi\s*nombre\s*es)\s+(\w+)', cmd)
        if m_nombre:
            nombre = m_nombre.group(2)
            self.config["user_name"] = nombre
            return f"  Un placer conocerte, {nombre}. ¿En qué puedo ayudarte?"

        # ---- CONVERSACIÓN CASUAL: cuéntame algo, qué hay de bueno, dime algo interesante ----
        if re.search(r'\b(cu[eé]ntame|cuenta\w*\s+algo|dime\s+algo|qu[eé]\s*hay\s+(de\s+)?bueno|qu[eé]\s+me\s+cuentas|alg[uú]n\s+dato|dato\s+curioso|algo\s+(interesante|nuevo|bueno|divertido)|tienes\s+(algo\s+)?(interesante|nuevo|bueno)|qu[eé]\s+(sabes|conoces)\s+(interesante|nuevo)|h[aá]blame\s+de\s+algo|pl[aá]tica\w*\s+algo|dime\s+un\s+cuento|cu[eé]ntame\s+un\s+cuento|qu[eé]\s+noticias\s+tienes)\b', cmd, re.IGNORECASE):
            return random.choice(self._DATOS_CURIOSOS)

        # ---- NUEVO ANÁLISIS DE TRADING: descartar memoria y delegar al agente ----
        if self.detectar_cambio_de_simbolo(cmd):
            return self._agente_razonar(cmd)

        # ---- SEGUIMIENTO CONVERSACIONAL: "dame más detalles", "dime más", etc ----
        if self._tema_actual and re.search(
            r'\b(dame\s+m[áa]s\s+detalles|dime\s+m[áa]s|expl[íi]came\s+m[áa]s|ampl[íi]a(?:\s+(?:info|informaci[óo]n|la\s+explicaci[óo]n))?|m[áa]s\s+detalles|quiero\s+saber\s+m[áa]s|sigue(?:\s+h[aá]blando)?|cu[eé]ntame\s+m[áa]s|dame\s+m[áa]s\s+info)\b',
            cmd, re.IGNORECASE
        ):
            return self._agente_razonar(
                cmd,
                contexto_extra=(
                    f"El usuario pide más información sobre el tema actual "
                    f"'{self._tema_actual}'. Expande la explicación ofreciendo "
                    f"detalles adicionales, ejemplos concretos o datos específicos "
                    f"sin repetir lo ya dicho."
                )
            )

        # ---- SEGUIMIENTO: "dame X" sin patrón específico (relacionado al tema actual) ----
        if self._tema_actual and re.search(
            r'^\s*dame\s+',
            cmd, re.IGNORECASE
        ):
            return self._agente_razonar(
                cmd,
                contexto_extra=(
                    f"Contexto: El usuario está hablando sobre '{self._tema_actual}'. "
                    f"Su mensaje '{cmd}' es una continuación de ese tema. "
                    f"Responde interpretando su petición en el contexto de '{self._tema_actual}'."
                )
            )

        # ---- CONVERSACIÓN CASUAL: pasar al LLM en vez de dato curioso ----
        # Si es una petición explícita de dato curioso, responder con uno
        if re.search(r'\b(dato\s*curioso|algo\s*(interesante|nuevo|bueno|divertido)|alg[uú]n\s*dato|sab[ií]as\s*qu[eé])\b', cmd, re.IGNORECASE):
            return random.choice(self._DATOS_CURIOSOS)

        # ---- PREGUNTAS OBJETIVAS: responder sin búsqueda web ----
        if re.search(r'\b(sabes\s+(como|hacer|si|decifrar|descifrar)|puedes\s+(hacer|decir|decifrar|descifrar|ayudar)|conoces\s+(algun|como|decir)|como\s+(se\s+)?(decifra|descifra|hace|usa|funciona|instala|crea|abre|configura|elimina|saca|obtiene|consigue)|sabes\s+algo\s+(de|sobre|acerca)|eres\s+capaz\s+de)\b', cmd, re.IGNORECASE):
            ai = self.openrouter or self.gemini
            if ai:
                prompt = (
                    f"El usuario pregunta: '{cmd}'. Responde en español de forma "
                    f"OBJETIVA y DIRECTA, máximo 3 oraciones. Si es una pregunta de "
                    f"sí/no, responde primero 'Sí' o 'No' y luego explica brevemente. "
                    f"NO hagas búsqueda web ni des información especulativa."
                )
                resp = ai.preguntar(prompt)
                if resp["exito"]:
                    return f"  {resp['resultado'].strip()}"
            return "  Pregúntame directamente y te diré si puedo ayudarte."

        # ---- AUTO-APRENDIZAJE: buscar en memoria ----
        # No usar memoria para consultas de trading/screener (debe ir al LLM con datos frescos)
        if not re.search(r'\b(mejor acci[oó]n|veredicto|setup|qué acci.n|qué me recomiendas|screener|scanner|fuera de (las )?bandas|oportunidad|entrar ahor|entrar en |comprar |vender |corto |largo |inversión del día|trade del día)\b', cmd, re.IGNORECASE):
            mem = self.memoria.recordar_formateado(cmd)
            if mem:
                self.memoria.registrar_interaccion(cmd, mem, "memoria")
                return self._tag(f"  Recuerdo: {mem}", "memoria")

        # ---- CLASIFICADOR LOCAL NLU (pre-filter antes del agente) ----
        # Umbral alto (0.95) para no interceptar preguntas conversacionales
        intent, conf = self.nlu.clasificar(cmd)
        if intent and conf >= 0.95:
            if intent in INTENT_SIN_AGENTE:
                resp = self._respuesta_local_intent(intent, cmd)
                if resp:
                    return resp
            elif intent in INTENT_ACCION_LOCAL:
                pass  # dejar que los módulos lo manejen vía analizar_segmento

        # ---- AGENTE DE RAZONAMIENTO (OpenRouter + herramientas: Wikipedia, DDG, etc.) ----
        resp = self._agente_razonar(cmd)
        if resp:
            self.memoria.aprender(cmd, resp)
            self.memoria.registrar_interaccion(cmd, resp, "agente")
            return self._tag(f"  {resp}", "Agente")

        # Fallback final: preguntar directamente al LLM
        ai = self.openrouter or self.gemini
        if ai:
            fb = ai.preguntar(f"Responde en español de forma natural y útil: {cmd}")
            if fb and isinstance(fb, dict) and fb.get("exito") and fb.get("resultado"):
                resp = fb["resultado"].strip()
                if resp:
                    self.memoria.aprender(cmd, resp)
                    self.memoria.registrar_interaccion(cmd, resp, "agente")
                    return self._tag(f"  {resp}", "Agente")

        self.memoria.registrar_interaccion(cmd, "[no entendido]", "desconocido")
        return ""

    _PREGUNTAS_CONOCIDAS = [
        "capital de", "cual es la capital", "cual es",
        "en que ano nacio", "en que año nació", "cuando nacio",
        "quien fue", "quien es la", "quien es el",
        "como se llama", "como se llamaba",
        "cuantos habitantes", "cuanta poblacion",
        "que significa la palabra", "que significa",
        "altura del", "altura de la", "altura de",
        "cuando se creo", "cuando se fundo",
        "quien creo", "quien invento", "quien descubrio",
        "que idioma se habla", "cual es el idioma",
        "quien gobernaba", "quien fue el primer",
        "cual fue el primer", "cual es el mas",
        "quien es considerado",
        "en que", "cuando fue", "cuando se", "donde esta",
        "donde queda", "cuanto mide", "cuanto pesa",
        "cuantos anos", "de donde es", "como se dice",
        "cual fue", "cual es",
    ]

    def _seleccionar_motores(self, query: str) -> list:
        """Selecciona motores de búsqueda según el tipo de consulta."""
        q = query.lower()
        motores = ["duckduckgo"]
        if any(kw in q for kw in ["que es", "qué es", "quien es", "quiénes son",
                                    "que son", "qué son", "que significa", "qué significa",
                                    "definición", "definicion", "concepto", "biografía",
                                    "biografia", "historia"]):
            motores.append("wikipedia")
        if any(kw in q for kw in ["bolsa", "accion", "precio", "cotización", "cotizacion",
                                    "ibex", "nasdaq", "bitcoin", "cripto", "etf"]):
            motores.extend(["yahoofinance", "bloomberg"])
        if any(kw in q for kw in ["como hacer", "error", "solucion", "solución",
                                    "instalar", "configurar", "problema"]):
            motores.append("stackoverflow")
        return motores

    def _no_entiendo(self, comando: str) -> str:
        # Intentar con el LLM como último recurso — responder directamente, "no sé qué significa" es mentira si el LLM sí sabe
        ai = self.openrouter or self.gemini
        if ai:
            prompt = (
                f"El usuario preguntó: '{comando}'. "
                f"Responde en español de forma natural y útil como un asistente inteligente. "
                f"Si es una pregunta, respóndela lo mejor que puedas. "
                f"Máximo 3 oraciones."
            )
            resp = ai.preguntar(prompt)
            if resp and isinstance(resp, dict) and resp.get("exito") and resp["resultado"]:
                return f"  {resp['resultado'].strip()}"
        # Fallback: búsqueda web directa
        web = self.buscador_web.buscar(comando)
        if web.get("exito"):
            return f"  {web['resultado'].strip()}"
        return f"    No estoy seguro de cómo responder a eso. ¿Puedes reformular la pregunta?"

    def _buscar_local(self, query: str) -> str:
        """Buscar un archivo local y abrirlo."""
        import os
        import glob as glob_module
        import subprocess

        query_clean = query.lower().strip()
        es_musica = any(kw in query_clean for kw in ["cancion", "canción", "musica", "música", "audio", "mp3", "song"])
        es_video = any(kw in query_clean for kw in ["video", "vídeo", "pelicula", "película", "film", "movie", "serie"])

        ext_musica = ["*.mp3", "*.wav", "*.flac", "*.m4a", "*.wma", "*.aac", "*.ogg"]
        ext_video = ["*.mp4", "*.mkv", "*.avi", "*.mov", "*.wmv", "*.webm", "*.mpeg"]
        patrones = ext_musica + ext_video

        dirs_usuario = []
        for d in [os.path.expanduser("~"), os.environ.get("USERPROFILE", "C:\\")]:
            for sub in ["Music", "Videos", "Downloads", "Desktop", "Música", "Vídeos", "Descargas", "Escritorio"]:
                p = os.path.join(d, sub)
                if os.path.isdir(p):
                    dirs_usuario.append(p)

        resultados = []
        for d in dirs_usuario:
            for pat in patrones:
                for archivo in glob_module.iglob(os.path.join(d, "**", pat), recursive=True):
                    nombre_base = os.path.splitext(os.path.basename(archivo))[0].lower()
                    if query_clean in nombre_base:
                        resultados.append(archivo)
                        if len(resultados) >= 5:
                            break
                if len(resultados) >= 5:
                    break
            if len(resultados) >= 5:
                break

        # Intentar con Everything si es.exe existe
        if not resultados:
            es_paths = [
                "C:\\Program Files\\Everything\\es.exe",
                "C:\\Program Files (x86)\\Everything\\es.exe",
                os.path.expanduser("~\\scoop\\apps\\everything\\current\\es.exe"),
            ]
            for es_exe in es_paths:
                if os.path.isfile(es_exe):
                    try:
                        result = subprocess.run([es_exe, query_clean], capture_output=True, text=True, timeout=10)
                        archivos = [l.strip() for l in result.stdout.splitlines() if l.strip()]
                        if archivos:
                            resultados = archivos[:5]
                    except Exception:
                        pass
                    break

        if resultados:
            primer = resultados[0]
            subprocess.Popen(["start", "", primer], shell=True)
            nombre = os.path.basename(primer)
            return f"  Abriendo '{nombre}' en tu computadora..."

        return f"  No encontré '{query}' en tu computadora."

    def _buscar_internet(self, query: str) -> str:
        """Buscar en YouTube (o Google) desde el navegador."""
        import webbrowser
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        webbrowser.open(url)
        return f"  Buscando '{query}' en YouTube..."

    def _chistes(self) -> list:
        return [
            "¿Qué le dijo un techo a otro? Techo de menos.",
            "¿Cómo se despiden los programadores? Hasta la vista... y no olvides hacer commit.",
            "¿Qué hace un perro con un taladro? Taladrando.",
            "Jarvis: el único que trabaja 24/7 y nunca pide aumento.",
            "¿Cuál es el colmo de un programador? Tener que lidiar con bugs que no son suyos.",
            "Llegué a la nube... y me cobraron por el estacionamiento.",
            "¿Por qué los programadores confunden Halloween con Navidad? Porque Oct 31 == Dec 25.",
            "¿Qué le dice un .git a otro? No te hagas el remote.",
            "Hay 10 tipos de personas: las que entienden binario y las que no.",
            "Si Windows no te deja hacer algo, reinicia. Si la vida no te deja hacer algo, reinicia también.",
            "¿Cómo sale de su casa un desarrollador web? Por el localhost.",
            "¿Qué hace un ingeniero de software en el baño? Hace sus necesidades... del sistema.",
            "—¿Qué es un backend? —Lo que pasa cuando te sientas y no avanzas.",
            "El único bug que me gusta es el que está en mi cama.",
            "—¿Por qué el desarrollador fue al psicólogo? —Porque tenía demasiados hilos sueltos.",
            "Un byte se fue a la playa y se quedó flotando... era un float.",
            "¿Sabes cómo se queda un mago después de comer? Magordito.",
            "Yo no digo malas palabras, digo palabras de depuración.",
            "Si la vida te da la espalda, probablemente es porque tú también le diste la espalda a ella.",
        ]

    _PROPUESTAS = [
        "¿Quieres que hablemos de inteligencia artificial?",
        "¿Te gustaría escuchar música? Puedo recomendarte algo.",
        "¿Has visto alguna película buena últimamente?",
        "¿Qué opinas de la tecnología cuántica?",
        "¿Quieres que te cuente un dato curioso?",
        "¿Te interesa saber cómo funcionan los modelos de lenguaje?",
        "¿Prefieres hablar de videojuegos, ciencia o historia?",
        "¿Quieres que analice el rendimiento de tu PC?",
        "¿Necesitas ayuda con algún proyecto personal?",
        "¿Te gustaría aprender algo nuevo hoy? Puedo enseñarte.",
        "¿Has probado alguna receta nueva esta semana?",
        "¿Qué tipo de música te gusta más?",
        "¿Te gusta la ciencia ficción o prefieres temas realistas?",
        "¿Quieres que busque noticias de tecnología para ti?",
        "Podemos hablar de lo que quieras. Dime un tema.",
    ]

    _DATOS_CURIOSOS = [
        "¿Sabías que los pulpos tienen tres corazones? Dos bombean sangre a las branquias y uno al resto del cuerpo.",
        "Dato curioso: la miel nunca se echa a perder. Se han encontrado frascos de miel en tumbas egipcias de hace 3000 años aún comestibles.",
        "¿Sabías que un día en Venus dura más que un año en Venus? Gira muy lentamente sobre su eje.",
        "Dato curioso: el corazón de un camarón está en su cabeza.",
        "¿Sabías que los flamingos son rosados porque comen algas y crustáceos ricos en carotenoides?",
        "Dato curioso: los koalas tienen huellas dactilares muy parecidas a las humanas, tanto que podrían confundirse en una escena del crimen.",
        "¿Sabías que el ADN humano tiene aproximadamente 3000 millones de pares de bases?",
        "Dato curioso: el cerebro humano genera suficiente electricidad para encender una bombilla pequeña.",
        "¿Sabías que las hormigas nunca duermen? Pero sí toman micro-siestas de unos minutos.",
        "Dato curioso: la Gran Muralla China no es visible desde el espacio a simple vista. Es un mito.",
        "¿Sabías que el agua caliente se congela más rápido que el agua fría? Se llama efecto Mpemba.",
        "Dato curioso: los árboles se comunican entre sí a través de sus raíces y hongos subterráneos. Lo llaman la 'Wood Wide Web'.",
        "¿Sabías que el 60% del cuerpo humano es agua? Y el 90% de la sangre es agua.",
        "Dato curioso: las voces de Mickey Mouse y Minnie Mouse se casaron en la vida real. Wayne Allwine y Russi Taylor eran esposos.",
        "¿Sabías que los tiburones existían antes que los árboles? Llevan aquí más de 400 millones de años.",
        "Dato curioso: el lugar más seco de la Tierra es el desierto de Atacama en Chile. Algunas estaciones nunca registran lluvia.",
        "¿Sabías que un grupo de búhos se llama 'parlamento'?",
        "Dato curioso: el plástico tarda entre 100 y 1000 años en degradarse en la naturaleza.",
        "¿Sabías que los dedos de los pies no tienen músculos? Los movemos gracias a los músculos del pie.",
        "Dato curioso: los elefantes son uno de los pocos animales que se reconocen en un espejo.",
        "¿Sabías que las nubes pesan? Una nube típica de 1 km³ pesa alrededor de 500 toneladas.",
        "Dato curioso: las jirafas tienen la misma cantidad de vértebras en el cuello que los humanos: siete.",
        "¿Sabías que existe un hongo que convierte a las hormigas en 'zombies' y las controla? Se llama Ophiocordyceps.",
        "Dato curioso: el sol produce más energía en un segundo que toda la humanidad en toda su historia.",
        "¿Sabías que las cebras tienen rayas únicas como las huellas dactilares humanas? No hay dos iguales.",
        "Dato curioso: los gatos domésticos comparten el 95.6% de su ADN con los tigres.",
        "¿Sabías que las pupas de los ojos se dilatan cuando ves a alguien que te gusta?",
        "Dato curioso: el estornudo viaja a unos 160 km/h. Por eso es mejor estornudar en el codo.",
        "¿Sabías que los wombats hacen caca en forma de cubo? Así evita que ruede y marca mejor su territorio.",
        "Dato curioso: la risa no es exclusiva de los humanos. Las ratas también ríen cuando les hacen cosquillas.",
        "¿Sabías que la luz tarda 8 minutos y 20 segundos en viajar del sol a la Tierra?",
        "Dato curioso: cada año, el volcán Kilauea en Hawái añade nuevas hectáreas a la isla.",
        "¿Sabías que los perros pueden entender hasta 250 palabras y gestos? Son tan inteligentes como un niño de 2 años.",
        "Dato curioso: la música clásica puede ayudar a las plantas a crecer mejor, según varios estudios.",
        "¿Sabías que las avispas papelera reconocen las caras humanas? Un estudio demostró que recuerdan rostros.",
        "Dato curioso: las cataratas del Iguazú tienen 275 saltos de agua y son más anchas que las del Niágara.",
        "¿Sabías que los agujeros negros no son realmente agujeros? Son objetos con una gravedad tan intensa que ni la luz escapa.",
        "Dato curioso: los caballitos de mar machos son los que se embarazan y paren a las crías.",
        "¿Sabías que la Vía Láctea tiene entre 100 y 400 mil millones de estrellas?",
        "Dato curioso: las abejas tienen 5 ojos. Dos grandes compuestos y tres pequeños en la parte superior de la cabeza.",
        "¿Sabías que la Torre Eiffel crece 15 cm en verano? El metal se expande con el calor.",
        "Dato curioso: los camellos pueden beber hasta 100 litros de agua en solo 10 minutos.",
        "¿Sabías que el español es el segundo idioma más hablado del mundo por número de hablantes nativos?",
        "Dato curioso: la computadora más potente del mundo ocupa el espacio de varias canchas de tenis.",
        "¿Sabías que todos los seres humanos compartimos el 99.9% de nuestro ADN? Solo el 0.1% nos hace únicos.",
        "Dato curioso: un avión comercial usa aproximadamente 1 galón de combustible por segundo.",
        "¿Sabías que los osos polares tienen piel negra debajo de su pelaje blanco? Así absorben mejor el calor.",
        "Dato curioso: el ojo humano puede distinguir aproximadamente 10 millones de colores diferentes.",
        "¿Sabías que hay más estrellas en el universo que granos de arena en todas las playas de la Tierra?",
        "Dato curioso: el animal más longevo es la almeja de Islandia, que puede vivir más de 500 años.",
    ]

    # Frases que suelen ser ambiguas (canción vs petición, etc.)
    _PATRONES_AMBIGUOS = [
        r'\bescucha\w*\b', r'\bquiero\s+que\b', r'\bnece\w*\s+que\b',
        r'\bpuedes\s+\w+\s+(para|por)\b', r'\bte\s+(pido|quiero|necesito)\b',
        r'\bser\w*\s+que\b', r'\bcomo\s+para\b',
    ]

    def _es_ambiguo(self, cmd: str) -> bool:
        cmd_lower = cmd.lower().strip()
        # Frases muy largas (>50) probablemente no son ambiguas
        if len(cmd_lower) > 50:
            return False
        # Verificar patrones ambiguos
        for pat in self._PATRONES_AMBIGUOS:
            if re.search(pat, cmd_lower):
                return True
        return False

    def _proponer_activo(self) -> str:
        """Genera una propuesta de conversación solo por voz (V__)."""
        tema = ""
        ai = self.openrouter or self.gemini
        if ai and random.random() < 0.4 and len(self.history) >= 3:
            try:
                ultimos = self.history[-3:]
                prompt = (
                    f"Basado en esta conversación: {' | '.join(ultimos)}. "
                    f"Sugiere un tema de conversación en español, máximo 15 palabras, "
                    f"como pregunta natural. No expliques ni añadas contexto."
                )
                gem = ai.preguntar(prompt)
                if gem["exito"]:
                    tema = gem["resultado"].strip().strip('"').strip("'")
            except Exception:
                pass
        if not tema:
            tema = random.choice(self._PROPUESTAS)
        return f"V__{tema}"

    def _inyectar_chiste(self, respuesta: str) -> str:
        self._contador_comandos += 1
        if self._contador_comandos >= 4 and random.randint(1, 5) == 1:
            self._contador_comandos = 0
            return respuesta + "\n\n  " + PENSANDO + "  Por cierto... " + random.choice(self._chistes())
        return respuesta
        self._contador_comandos += 1
        if self._contador_comandos >= 4 and random.randint(1, 5) == 1:
            self._contador_comandos = 0
            return respuesta + "\n\n  " + PENSANDO + "  Por cierto... " + random.choice(self._chistes())
        return respuesta

    def _mostrar_historial(self) -> str:
        if not self.history:
            return f"  {PERGAMINO}  No hay comandos en el historial."
        resultado = f"  {PERGAMINO}  ÚLTIMOS COMANDOS\n  ─────────────────────\n"
        for i, cmd in enumerate(self.history[-10:], 1):
            resultado += f"  {i}. {cmd}\n"
        return resultado

    def _listar_plugins(self) -> str:
        plugins = self.plugin_manager.list_plugins()
        if not plugins:
            return f"  {ENCHUFE}  No hay plugins instalados.\n     Coloca archivos .py en la carpeta 'plugins/'"
        resultado = f"  {ENCHUFE}  PLUGINS INSTALADOS\n  ─────────────────────\n"
        for p in plugins:
            resultado += f"  • {p}\n"
        return resultado


# ============================================================
# INTERFAZ DE USUARIO
# ============================================================

class InterfazJarvis:
    """Maneja la interacción con el usuario."""

    def __init__(self):
        self.core = JarvisCore()
        self._tts = None
        try:
            from utils.voice import JarvisTTS
            self._tts = JarvisTTS()
        except Exception:
            pass

    def _leer_ultima_conexion(self) -> tuple:
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "last_run.json")
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
                return (datos.get("timestamp", ""), datos.get("user", ""))
        except Exception:
            return ("", "")

    def _guardar_conexion(self):
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "last_run.json")
        try:
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            usuario = os.getlogin()
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump({"timestamp": datetime.now().isoformat(), "user": usuario}, f)
        except Exception:
            pass

    def _generar_saludo(self) -> dict:
        ahora = datetime.now()
        hora_int = ahora.hour
        if 5 <= hora_int < 12:
            periodo = "días"
        elif 12 <= hora_int < 19:
            periodo = "tardes"
        else:
            periodo = "noches"

        ultima_ts, ultimo_user = self._leer_ultima_conexion()
        usuario = os.getlogin()

        saludos_variados = [
            f"Buenos {periodo}.",
            f"Hola.",
            f"Buenas.",
            f"¿Qué tal?",
            f"¡Hey!",
            f"Buenos {periodo}, ¿cómo estás?",
        ]

        saludos_personalizados = [
            f"Buenos {periodo}, {usuario}.",
            f"Hola, {usuario}.",
            f"¿Qué hay, {usuario}?",
            f"¡Hey, {usuario}!",
        ]

        if ultima_ts:
            try:
                ultima_dt = datetime.fromisoformat(ultima_ts)
                diff = (ahora - ultima_dt).total_seconds()
                if diff < 60:
                    elegido = random.choice(["Qué rápido volviste.", "Otra vez por aquí.", "Ya de vuelta."])
                elif diff < 3600:
                    elegido = random.choice(["No pasó tanto tiempo.", "Hola de nuevo.", "Otra vez."])
                elif diff < 86400 * 3:
                    elegido = random.choice(saludos_personalizados + saludos_variados)
                elif diff < 86400 * 30:
                    elegido = random.choice([
                        f"Cuánto tiempo, {usuario}.",
                        f"Ya te extrañaba, {usuario}.",
                        f"Hacía días.",
                        f"Tanto tiempo sin verte.",
                    ])
                else:
                    elegido = random.choice([
                        f"Cuánto tiempo ya te extrañaba, {usuario}.",
                        f"Hacía mucho, {usuario}.",
                        f"Tanto tiempo, {usuario}.",
                        f"Por fin vuelves.",
                    ])
                speak = elegido
            except Exception:
                elegido = random.choice(saludos_personalizados + saludos_variados)
                speak = elegido
        else:
            elegido = random.choice(saludos_personalizados + saludos_variados)
            speak = elegido

        self._guardar_conexion()
        return {"display": elegido, "speak": speak}

    def mostrar_banner(self):
        from utils.colors import banner_jarvis, incrementar_tiempo

        saludo = self._generar_saludo()

        print("\n" + banner_jarvis())
        incrementar_tiempo(0.08)

        banner = f"""
{'=' * 40}
  {saludo['display']}
{'=' * 40}
"""
        print(banner)
        self._ultimo_saludo = saludo

    def ejecutar(self):
        """Bucle principal de Jarvis."""
        self.mostrar_banner()
        # Saludo hablado (si hay TTS disponible)
        if hasattr(self, '_ultimo_saludo') and self._tts and self._tts.disponible:
            try:
                self._tts.decir_async(self._ultimo_saludo['speak'])
            except Exception:
                pass

        while True:
            try:
                prompt_color = logo_colorido(f"[{NAME}] $")
                incrementar_tiempo(0.02)
                entrada = input(f"\n  {prompt_color} ").strip()
                if not entrada:
                    continue

                respuesta = self.core.procesar(entrada)

                if respuesta == "__EXIT__":
                    print(f"\n  {NAME}: Ha sido un placer ayudarle. Hasta pronto.")
                    break

                if respuesta:
                    print(f"\n{respuesta}")

            except KeyboardInterrupt:
                print(f"\n\n  {NAME}: Interrupción detectada. ¿Desea salir? (s/n): ", end="")
                try:
                    if input().lower().startswith("s"):
                        print(f"\n  {NAME}: Hasta luego.")
                        break
                except KeyboardInterrupt:
                    print(f"\n  {NAME}: Hasta luego.")
                    break
            except EOFError:
                print(f"\n\n  {NAME}: Hasta luego.")
                break
            except Exception as e:
                print(f"\n  ⚠️ Error inesperado: {e}")


def main():
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
    except Exception:
        pass
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass

    jarvis = InterfazJarvis()
    jarvis.ejecutar()


if __name__ == "__main__":
    main()
