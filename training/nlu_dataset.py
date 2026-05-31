"""Genera el dataset de intenciones para entrenar el clasificador NLU."""
import csv
import os

INTENTS = {
    "greeting": [
        "hola", "buenos días", "buenas tardes", "buenas noches", "qué tal",
        "hey jarvis", "saludos", "hola jarvis", "buenas", "hey",
        "good morning", "hi", "hello", "que tal jarvis", "oye jarvis",
    ],
    "how_are_you": [
        "cómo estás", "cómo andas", "qué hay", "cómo te encuentras",
        "cómo sigues", "cómo estás jarvis", "cómo andas hoy", "que tal estas",
        "cómo estás hoy", "cómo te va", "cómo estamos", "qué me cuentas",
    ],
    "time": [
        "qué hora es", "dime la hora", "hora actual", "son las",
        "qué día es hoy", "qué fecha es", "fecha actual", "a qué día estamos",
        "dime el día", "dame la hora", "qué hora tienes", "hora del sistema",
        "hora oficial", "me das la hora", "que hora es exactamente",
    ],
    "weather": [
        "clima en La Habana", "cómo está el clima", "qué temperatura hace",
        "va a llover hoy", "hace frío afuera", "hace calor en Madrid",
        "pronóstico para mañana", "cómo está el tiempo", "temperatura en Bogotá",
        "está lloviendo", "hay sol hoy", "clima en Barcelona",
        "qué tiempo hace", "pronóstico del clima", "va a hacer calor",
    ],
    "news": [
        "dame las noticias", "noticias de tecnología", "últimas noticias",
        "qué pasó hoy", "noticias de deportes", "actualidad",
        "titulares del día", "noticias sobre inteligencia artificial",
        "qué hay de nuevo", "noticias de ciencia", "novedades",
        "noticias de salud", "noticias de economía", "qué noticias hay",
    ],
    "stocks": [
        "cómo va Apple", "precio de bitcoin", "cotización de Tesla",
        "bolsa de Microsoft", "cómo va BTC", "dame el precio de Google",
        "qué tal va Amazon", "cotiza Apple", "valor de NVIDIA",
        "bolsa hoy", "acciones de Meta", "precio del petróleo",
        "cómo está el mercado", "cotización del dólar", "ibex 35",
    ],
    "music": [
        "pon música de Avicii", "reproduce Queen", "quiero escuchar a Shakira",
        "poner música relajante", "reproduce mi playlist", "música clásica",
        "pon canciones de los 80", "escuchar música", "toca algo de rock",
        "siguiente canción", "pausa la música", "volumen más alto",
        "cerrar la música", "silencio", "basta de música",
    ],
    "apps": [
        "abre Chrome", "abre el bloc de notas", "abre la calculadora",
        "abre Spotify", "abre Word", "abre Discord", "abre VSCode",
        "abre el navegador", "abre la terminal", "abre PowerPoint",
        "abre Excel", "abre Paint", "abre la papelera", "abre el explorador",
        "abre las carpetas",
    ],
    "games": [
        "abre el Dota", "jugar Fortnite", "abre el Minecraft",
        "lanzar CSGO", "echar una partida de Valorant",
        "dale al League of Legends", "ve abriendo el Dota",
        "voy a jugar Warzone", "vamos a jugar FIFA",
        "abre GTA V", "juega al Age of Empires", "pon el Call of Duty",
        "lanzar juego", "abrir el Among Us", "jugamos al Rocket League",
    ],
    "books": [
        "abre el principito", "qué libros tengo", "lista mis libros",
        "abre el PDF de física", "mis libros están en la carpeta Libros",
        "leer el quijote", "muéstrame los libros", "abre libro llamado harry potter",
        "tengo libros disponibles", "ver libros", "enseñame los libros",
        "abre el PDF de matemáticas", "que libros tengo en la biblioteca",
        "lista de libros", "quiero leer un libro",
    ],
    "catalogo": [
        "catálogo de películas", "muestra el catálogo", "películas disponibles",
        "mis pelis", "escanea películas", "actualizar catálogo",
        "lista pelis", "filmoteca", "videoteca", "reproduce la 3",
        "elige la 5", "la 12", "película 7", "abre la 2",
    ],
    "movie_info": [
        "de qué trata la película 5", "sinopsis de la 3",
        "información sobre la película 12", "qué sabes de la número 7",
        "de qué va la 9", "sinopsis de la película 2",
        "de qué trata la 4", "información de la peli 8",
        "qué es la película 6", "de qué trata el número 3",
    ],
    "jokes": [
        "cuéntame un chiste", "chiste", "hazme reír", "dime un chiste",
        "una broma", "cuéntame algo gracioso", "dime un chiste de programadores",
        "quiero reírme", "algo divertido", "un chiste corto",
        "bromea un poco", "dame un chiste malo", "cuenta un chiste",
    ],
    "curious_fact": [
        "cuéntame algo interesante", "dato curioso", "dime algo nuevo",
        "qué hay de bueno", "algo interesante", "háblame de algo curioso",
        "cuéntame un cuento", "qué sabes interesante", "dime un dato curioso",
        "algo que no sepa", "sabías algo", "tienes algo nuevo",
        "dato curioso del día",
    ],
    "user_name": [
        "me llamo Juan", "soy Pedro", "mi nombre es María",
        "me llamo Carlos", "soy Ana", "mi nombre es Javier",
        "soy Laura", "me llamo Roberto", "me llamo Sofía",
    ],
    "creator": [
        "quién te creó", "quién te hizo", "quién te programó",
        "quién te desarrolló", "tu creador", "de quién eres creación",
        "quién te diseñó", "quién te inventó", "quién te construyó",
    ],
    "who_are_you": [
        "quién eres", "qué eres", "cómo te llamas", "preséntate",
        "eres real", "tienes conciencia", "explícame quién eres",
        "dime quién eres", "qué eres exactamente", "te presentas",
    ],
    "capabilities": [
        "qué puedes hacer", "ayuda", "comandos", "cómo funcionas",
        "qué sabes hacer", "tus capacidades", "qué módulos tienes",
        "qué servicios tienes", "lista de comandos", "qué programas tienes",
        "tus funciones", "qué haces", "qué sabes", "muestra la ayuda",
    ],
    "thanks": [
        "gracias", "muchas gracias", "te agradezco", "thank you",
        "gracias totales", "agradecido", "gracias amigo", "thanks",
        "gracias jarvis", "muy agradecido", "de verdad gracias",
    ],
    "goodbye": [
        "chau", "adiós", "nos vemos", "hasta luego", "bye",
        "hasta pronto", "me retiro", "me voy", "salir", "exit",
        "goodbye", "ciao", "hasta la vista", "nos vemos luego",
        "que te vaya bien",
    ],
    "compliment": [
        "eres genial", "eres inteligente", "eres el mejor",
        "eres asombroso", "eres un crack", "eres impresionante",
        "eres grande", "eres increíble", "eres un genio",
        "eres un capo", "qué bueno eres", "eres espectacular",
    ],
    "insult": [
        "eres tonto", "eres inútil", "qué basura", "eres un idiota",
        "no sirves para nada", "eres un estúpido", "callate",
        "maldito programa", "eres un imbécil", "qué porquería",
        "peor asistente", "no haces nada", "desinstalado",
    ],
    "affirmation": [
        "ok", "dale", "perfecto", "excelente", "está bien",
        "de acuerdo", "suena bien", "genial", "vale", "claro",
        "bueno", "simón", "me gusta", "bien", "correcto",
    ],
    "sad": [
        "estoy triste", "estoy cansado", "me siento mal",
        "estoy aburrido", "fatal", "estresado", "preocupado",
        "deprimido", "no muy bien", "estoy enfermo", "regular",
        "estoy fatal", "qué estrés",
    ],
    "followup": [
        "qué te parece", "qué opinas", "y eso", "explica eso",
        "cuéntame más de eso", "es bueno", "es confiable",
        "tú qué crees", "cómo lo ves", "me conviene",
        "qué quiere decir eso", "es malo", "a qué te refieres",
        "en el mercado", "dime tu opinión",
    ],
    "amplify": [
        "amplía", "más información", "dime más", "explícame más",
        "ahonda en eso", "dame más detalles", "quiero saber más",
        "sigue", "amplíame", "continúa", "más detalles",
        "explícame más a fondo", "dame más datos",
    ],
    "correction": [
        "dije Apple, me equivoqué, era Microsoft",
        "no, es Tesla no Apple", "quise decir Google",
        "me equivoqué, es Madrid no Barcelona",
        "corrijo: era el 3 no el 5",
        "en realidad era María no Juan",
        "decía que era azul pero es rojo",
        "no, es verde no azul",
        "rectifico: el resultado es 42",
        "me equivoqué de persona",
    ],
    "memory_learn": [
        "aprende que mi color favorito es azul",
        "recuerda que mi perro se llama Toby",
        "memoriza que la capital de Francia es París",
        "guarda que mi cumpleaños es el 15 de mayo",
        "aprendete que 2+2 es 4",
        "graba que vivo en La Habana",
        "recuerda que no me gusta el café",
        "memoriza que mi novia se llama Ana",
    ],
    "memory_forget": [
        "olvida que mi color favorito es azul",
        "olvídate de Toby", "borra que la capital de Francia es París",
        "elimina ese recuerdo", "olvida lo que te dije de Ana",
        "borra mi cumpleaños", "olvida ese dato",
    ],
    "memory_show": [
        "qué sabes", "qué aprendiste", "qué has aprendido",
        "muestra tu memoria", "lista tus hechos", "qué has memorizado",
        "qué recuerdas", "qué conoces", "qué sabes de mí",
    ],
    "article": [
        "artículo 109 de la Constitución Cubana",
        "artículo 20", "ley 60", "resolución 42", "decreto 101",
        "artículo 15 de la Constitución", "ley general de educación",
        "artículo 10 del código penal", "decreto ley 300",
        "art 5 de la constitución",
    ],
    "web_search": [
        "busca recetas de cocina", "buscar inteligencia artificial",
        "encuentra el mejor restaurante en Madrid",
        "quiero buscar vuelos a Cancún",
        "necesito información sobre el cambio climático",
        "averiguar cuánto cuesta un iPhone",
        "busca hoteles en Varadero",
        "investiga sobre el telescopio James Webb",
        "buscar noticias de Cuba",
        "encuentra el precio de un coche eléctrico",
    ],
    "wikipedia_search": [
        "qué es la gravedad", "quién es Albert Einstein",
        "cómo funciona el motor de combustión",
        "qué significa fotosíntesis",
        "dame información sobre internet de las cosas",
        "explícame qué es la teoría de cuerdas",
        "qué es la inteligencia artificial",
        "quién fue Simón Bolívar",
        "qué son los agujeros negros",
        "cómo funciona un panel solar",
        "qué significa ADN",
        "dame información sobre el cambio climático",
    ],
    "maps": [
        "dónde queda La Habana", "maps", "navega a la plaza mayor",
        "ubicación de la Torre Eiffel", "cómo llegar a Madrid",
        "localiza restaurantes cerca", "busca en maps cafeterías",
        "dónde está el Capitolio", "navegar a mi casa",
        "cómo llegar al aeropuerto", "google maps",
    ],
    "system_info": [
        "estado del sistema", "información de la PC", "procesador",
        "memoria RAM", "batería", "disco", "componentes del equipo",
        "rendimiento del sistema", "hardware", "estado de la computadora",
        "qué PC tengo", "especificaciones",
    ],
    "disks": [
        "analiza los discos", "estado de los discos", "espacio en disco",
        "cuánto espacio libre tengo", "almacenamiento lleno",
        "cómo están los discos", "ver discos", "analizar el disco C",
        "espacio del disco duro", "capacidad de disco",
    ],
    "fragmentation": [
        "desfragmentar disco C", "analizar fragmentación",
        "fragmentación del disco D", "necesita desfragmentar",
        "estado de fragmentación", "desfragmentar el disco",
    ],
    "backups": [
        "verificar backups", "copia de seguridad", "cómo están los backups",
        "tienes backup", "copias de seguridad", "último backup",
        "crear copia de seguridad", "respaldar el sistema",
    ],
    "usb": [
        "ver USB", "unidades externas", "pendrive conectado",
        "qué USB tengo", "memorias USB", "discos externos",
        "dispositivos USB", "ver unidades extraíbles",
    ],
    "health": [
        "salud", "pulso", "tendencias de salud", "consejo de salud",
        "estrés", "sueño", "frecuencia cardíaca", "bienestar",
        "ejercicio", "calorías", "conectar reloj", "ritmo cardíaco",
    ],
    "reminders": [
        "recuerda que tengo reunión a las 3",
        "recordatorio en 10 minutos", "alarma a las 7:00",
        "despertador mañana a las 6", "lista de pendientes",
        "mis recordatorios", "no olvides comprar pan",
        "acordarme de llamar al médico",
        "recordar que mañana es cumpleaños",
        "recordatorio cada día a las 8",
    ],
    "email": [
        "correo", "bandeja de entrada", "enviar correo",
        "inbox", "escribir correo", "enviar mail",
        "revisar correo", "nuevo correo", "bandeja",
    ],
    "whatsapp": [
        "whatsapp a Juan", "enviar WhatsApp", "wa",
        "whatsapp +5351234567 Hola", "whatsap",
        "enviar mensaje por WhatsApp", "abre WhatsApp",
    ],
    "mathematics": [
        "cuánto es 2+2", "calcula 15 por 3", "raíz cuadrada de 144",
        "5 elevado a la 3", "seno de 30", "logaritmo de 100",
        "resuelve 2+3 por 4", "derivada de x al cuadrado",
        "25 por ciento de 200", "cuánto da 7 entre 3",
        "calcula 10 más 8", "raíz de 81",
    ],
    "how_to": [
        "sabes cómo se instala Python", "puedes hacer un café",
        "cómo se usa git", "cómo se configura el WiFi",
        "sabes algo de la luna", "eres capaz de dibujar",
        "cómo se hace una página web", "sabes programar",
        "cómo se descarga un video", "puedes ayudarme a aprender",
    ],
    "ip_info": [
        "cuál es mi IP", "mi dirección IP", "mi IP pública",
        "dime mi IP", "ver mi IP", "qué IP tengo",
        "mi IP local", "saber mi dirección IP",
    ],
    "wifi_info": [
        "perfiles wifi", "contraseña del wifi", "clave del wifi",
        "redes wifi disponibles", "password del wifi",
        "ver redes wifi", "contraseña de mi wifi",
    ],
    "toggles": [
        "enciende el wifi", "activa bluetooth", "apaga el bluetooth",
        "desactivar wifi", "activa la luz nocturna", "night light",
        "enciende el apache", "desactiva xampp", "apaga el wifi",
        "activa el modo nocturno", "encender bluetooth",
    ],
    "restore_point": [
        "crear punto de restauración", "restore point",
        "respaldo del sistema", "proteger el sistema",
        "crear un punto de restauración",
    ],
    "uninstall": [
        "desinstalar Chrome", "eliminar programa",
        "borrar aplicación", "desinstalar VLC",
        "quitar este programa", "desinstalar Firefox",
    ],
    "do_not_understand": [
        "naranja", "plutonio", "tornillo",
        "esternocleidomastoideo", "tricotilomanía",
        "xilófono", "bizcocho", "paralelepípedo",
    ],
    "encode_decode": [
        "codifica hola mundo a base64",
        "decodifica esto en base64",
        "codifica Hello World", "decodificar base64",
        "encode este texto",
    ],
    "shutdown": [
        "apaga la computadora", "reinicia el PC",
        "apagar el equipo", "restart", "shutdown",
        "reiniciar el sistema", "apagar pc",
        "cancela el apagado", "no apagues",
    ],
    "virustotal": [
        "analizar archivo con VirusTotal",
        "escanear archivo", "buscar virus",
        "analizar este archivo", "malware scan",
        "antivirus",
    ],
    "continue": [
        "continúa", "sigue hablando", "repite eso",
        "continue", "sigue", "repite lo que dijiste",
    ],
    "open_url": [
        "ve a youtube.com", "abre google.com",
        "navega a github.com", "entra a python.org",
        "abre la página stackoverflow.com",
        "ir a facebook.com",
    ],
    "denial": [
        "no", "no gracias", "nunca", "para nada",
        "no quiero", "nop", "nel", "negativo",
    ],
    "affirmative_answer": [
        "sí", "sí claro", "adelante", "simón", "sipo",
        "sí por favor", "yes", "yeah", "correcto",
    ],
    "argue": [
        "argumenta eso", "debate sobre IA",
        "razona sobre el cambio climático",
        "opina sobre la política", "analiza esto",
        "reflexiona sobre la vida", "contradice eso",
    ],
}

def generar_csv(ruta="intents.csv"):
    rows = []
    for intent, examples in INTENTS.items():
        for text in examples:
            rows.append({"texto": text, "intent": intent})
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["texto", "intent"])
        w.writeheader()
        w.writerows(rows)
    print(f"Dataset generado: {len(rows)} ejemplos, {len(INTENTS)} intenciones")
    return rows

if __name__ == "__main__":
    generar_csv()
