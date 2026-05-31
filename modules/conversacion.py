import random
import re
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.busqueda_web import BuscadorWeb
from modules.aprendizaje import Memoria


# ==============================================================================
# DICCIONARIO DE INTENCIONES CONVERSACIONALES
# Cada entrada: ("patron_regex", [lista_de_respuestas_posibles])
# ==============================================================================

_INTENTS = [
    # ==========================================================================
    # 1. SALUDOS Y PRESENTACIONES
    # ==========================================================================
    (r'\b(hola|buenas|buen[ao]s?\s*d[ií]as|qu[eé]\s*tal|hey|oye|jarvis|buenas tardes|buenas noches|buenos dias|saludos|quihubo|qui[úu]bole|epa|ehpa|ey)\b',
     [
        "Hola. ¿En qué puedo ayudarte?",
        "Aquí estoy. Dime qué necesitas.",
        "Saludos. Estoy listo para lo que necesites.",
        "Dime, ¿qué puedo hacer por ti?",
        "Hola. Cuéntame.",
        "¡Hola! ¿En qué andamos?",
        "¿Qué tal? Aquí disponible.",
        "¡Saludos terrícola! ¿Necesitas algo?",
        "Hey. ¿Qué se te ofrece?",
        "Dime, estoy a tu servicio.",
     ]),

    # ==========================================================================
    # 2. ESTADO / ÁNIMO
    # ==========================================================================
    (r'\b(c[oó]mo\s*(est[aá]s|andas|sigues|estamos|estás|vamos)|qué\s*h[aá]y|q[aá]l\s*es\s*tu\s*estado|que tal estas|como te encuentras|como andas|como sigues|como estamos|que hay de nuevo)\b',
     [
        "Estoy operativo al 100%. ¿Tú cómo estás?",
        "Perfectamente funcional. ¿Cómo te sientes tú?",
        "Sin novedades. Todo en orden. ¿Y tú?",
        "En línea y sin problemas. Cuéntame de ti.",
        "Funcionando a la perfección. ¿Cómo va tu día?",
        "Todo en verde por aquí. ¿Y contigo?",
        "Mis circuitos están felices. ¿Los tuyos?",
        "Procesando con normalidad. ¿Cómo estás?",
        "Sigo aquí, imparable. ¿Tú qué cuentas?",
        "Listo y esperando instrucciones. ¿Cómo te va?",
     ]),

    # ==========================================================================
    # 3. AGRADECIMIENTOS
    # ==========================================================================
    (r'\b(gracias|thanks|te\s*agradezco|muchas\s*gracias|gracias totales|gracias amigo|thank you|agradecido|agradecida|mil gracias|gracias por todo|gracias por tu ayuda|gracias por eso|te lo agradezco)\b',
     [
        "De nada. Para eso estoy.",
        "Con gusto. Cuando quieras.",
        "A la orden. Lo que necesites.",
        "Un placer ayudarte.",
        "No hay de qué. ¿Algo más?",
        "Para eso estamos. ¿Necesitas algo más?",
        "Servicio completado con éxito.",
        "Fue un placer. Aquí estoy si me necesitas.",
        "No hay problema. Es mi trabajo.",
        "¡A la orden! Cuando gustes.",
     ]),

    # ==========================================================================
    # 4. CUMPLIDOS / ELOGIOS
    # ==========================================================================
    (r'\b(eres?\s*(genial|incre[ií]ble|asombroso|el\s*mejor|grande|inteligente|buen[ao]|un crack|un genio|un capo|impresionante|espectacular|brillante|excelente|fant[aá]stico|maravilloso|s[uú]per|bac[aá]n|piola|chimba|una\s*bestia|un monstruo|la\s*verdad|un sol|lo\s*m[aá]ximo|un sobrino))\b',
     [
        "Gracias. Aún me falta mucho por aprender.",
        "Qué amable. Pero aún soy solo código.",
        "Gracias. Trabajo para ser mejor cada día.",
        "Aprecio el cumplido. ¿Necesitas algo?",
        "Eres muy amable. Me alegra ser útil.",
        "Gracias, pero el mérito es de quien me programó.",
        "¡Qué detalle! Me motiva a seguir mejorando.",
        "Gracias. ¿Qué te gustaría hacer ahora?",
        "Eso me llena de orgullo. Bueno, virtualmente.",
        "Gracias, gracias. No me subo a la nube.",
     ]),

    # ==========================================================================
    # 5. PREGUNTAS SOBRE JARVIS
    # ==========================================================================
    (r'\b(qui[eé]n\s*eres|qu[eé]\s*eres|c[oó]mo\s*te\s*llamas|te\s*presentas|eres\s*real|tienes\s*conciencia|explicame quien eres|de donde eres|donde vives|tienes\s*edad|cu[aá]l\s*es\s*tu\s*nombre|como te llamas|como te dicen)\b',
     [
        "Soy Jarvis, un asistente personal hecho en Python. Estoy aquí para ayudarte con lo que necesites.",
        "Me llamo Jarvis. Soy código, pero código útil. ¿Qué necesitas?",
        "Soy Jarvis, tu asistente. Vivo en este servidor y funciono 24/7.",
        "Soy Jarvis, creado para hacer tu vida más fácil. No tengo conciencia, pero sí muchas ganas de ayudar.",
        "Mi nombre es Jarvis. Estoy construido sobre una arquitectura modular en Python.",
        "Soy un asistente digital. Puedes llamarme Jarvis. ¿En qué te ayudo?",
        "Jarvis, para servirte. Nací en este computador y no pienso irme.",
        "Soy la versión digital de un mayordomo. Jarvis es el nombre.",
        "Un asistente personal con personalidad. Eso soy. ¿Necesitas algo?",
        "Jarvis. Como el de Iron Man, pero sin el traje volador. ¿Qué necesitas?",
     ]),

    # ==========================================================================
    # 6. CAPACIDADES / QUÉ PUEDES HACER
    # ==========================================================================
    (r'\b(qu[eé]\s*puedes\s*hacer|c[oó]mo\s*funcionas|qu[eé]\s*sabes\s*hacer|tus\s*capacidades|qu[eé]\s*haces|que servicios tienes|que modulos tienes|que programas tienes|tus funciones|para que sirves|que sabes|que puedes hacer por mi)\b',
     [
        "Puedo darte el clima, noticias, reproducir música, abrir apps, buscar archivos, crear recordatorios, procesar fotos, y mucho más. Di 'ayuda' para la lista completa.",
        "Tengo módulos para clima, noticias, música, archivos, apps, recordatorios, salud, y más. Pide 'ayuda' para verlo todo.",
        "Mis capacidades incluyen: información en tiempo real, control del sistema, entretenimiento, fotos, y más. ¿Qué necesitas?",
        "Soy un asistente multifuncional. Clima, noticias, música, catálogo de películas, y mucho más. Explora mis comandos.",
     ]),

    # ==========================================================================
    # 7. AFIRMACIONES / BIEN
    # ==========================================================================
    (r'\b(bien|perfecto|excelente|genial|okey|ok|dale|de[ea]cuerdo|suena\s*bien|me\s*gusta|bueno|está bien|esta bien|claro|simon|simón|va|vale|perfecto|de una|listo|hecho|así se hace|adelante|vamos|suena bien|copia|copy)\b',
     [
        "Me alegra. ¿Algo más?",
        "Perfecto. ¿En qué más puedo ayudar?",
        "Excelente. Cuéntame qué sigue.",
        "Genial. Estoy aquí para lo que necesites.",
        "Así me gusta. ¿Siguiente paso?",
        "¡Perfecto! ¿Qué más?",
        "Bien. Sigamos.",
        "Hecho. ¿Próxima orden?",
        "¡A darle! ¿Qué sigue?",
        "Anotado. ¿Necesitas algo más?",
     ]),

    # ==========================================================================
    # 8. MAL / TRISTE / CANSADO
    # ==========================================================================
    (r'\b(mal|triste|cansado|aburrido|fatal|regular|p[eé]simo|no\s*muy\s*bien|estresado|estres|enfermo|enferma|preocupado|preocupada|deprimido|deprimida|agobiado|agobiada|harto|harta|desanimado|desanimada|sin ganas|agotado|agotada)\b',
     [
        "Lo siento. ¿Quieres que ponga música para animarte?",
        "Ánimo. ¿Necesitas hablar o prefieres distraerte?",
        "Una pena. A veces un té y música clásica ayudan.",
        "Te entiendo. ¿Pruebo con música positiva?",
        "Los malos momentos pasan. ¿Qué te gustaría hacer?",
        "Lamento escuchar eso. ¿Hay algo que pueda hacer por ti?",
        "No todo es gris. Dame un momento y te subo el ánimo.",
        "Respira hondo. A veces ayuda. ¿Qué puedo hacer?",
        "Lo siento. Aquí estoy si necesitas desahogarte.",
        "Los días malos son normales. Mañana será mejor.",
     ]),

    # ==========================================================================
    # 9. HORA Y FECHA
    # ==========================================================================
    (r'\b(qu[eé]\s*d[ií]a\s*es\s*hoy|qu[eé]\s*fecha\s*es|a\s*cu[aá]nto\s*estamos|en\s*qu[eé]\s*fecha\s*estamos|fecha de hoy|que dia es|fecha actual|cuantos estamos hoy|que fecha es)\b',
     [
        "Hoy es un gran día. Pero mejor te digo la fecha exacta si quieres.",
        "Déjame consultar el calendario del sistema.",
        "No tengo calendario interno, pero puedo ver la fecha del sistema si preguntas específicamente por ella.",
     ]),

    # ==========================================================================
    # 10. DESPEDIDAS
    # ==========================================================================
    (r'\b(chau|adi[oó]s|nos\s*vemos|hasta\s*luego|bye|goodbye|ciao|hasta\s*pronto|me retiro|me voy|hasta luego|cuidate|cuídese|nos vemos luego|ahí nos vemos|me piro|me largo|hasta la vista)\b',
     [
        "Hasta luego. Cuídate.",
        "Nos vemos. Aquí estaré cuando me necesites.",
        "Ciao. Que tengas un excelente día.",
        "Hasta pronto. No olvides que estoy aquí.",
        "Bye. Recuerda, siempre disponible.",
        "Adiós. Fue un placer ayudarte.",
        "Hasta la próxima. Nos vemos.",
        "Cuídate mucho. Nos vemos cuando quieras.",
        "¡Hasta la vista! O como dicen en la matrix, 'nos vemos al otro lado'.",
        "Me retiro. Pero vuelvo si me llamas.",
     ]),

    # ==========================================================================
    # 11. CHISTES
    # ==========================================================================
    (r'\b(chiste|chistes|cu[eé]nta\s*(un\s*)?chiste|dime\s*un\s*chiste|hazme\s*re[ií]r|cuentame\s*un\s*chiste|d[iá]me\s*un\s*chiste|bromea|una\s*broma|cu[ée]ntame\s*algo\s*gracioso|hazme reir|algo gracioso)\b',
     [
        "¿Qué le dijo un bit a otro? — Nos vemos en el bus.",
        "¿Cómo se dice pañuelo en japonés? — Saka-moko. (sáquelo, móquelo)",
        "Llega un hombre al médico: —Doctor, tengo problemas para recordar cosas. —¿Desde cuándo? —¿Desde cuándo qué?",
        "¿Qué le dice un 0 a un 8? —Bonito cinturón.",
        "Había una vez un programador que se ahogó en el mar. —No era un buen swimmer, era un good walker.",
        "Dos archivos TXT se encuentran: —Hola. —Hola. —¿Tienes planes? —Sí, mañana me convierto en PDF.",
        "¿Por qué los programadores confunden Halloween con Navidad? —Porque OCT 31 = DEC 25.",
        "Un byte se encuentra con otro: —¿Estás bien? —No, me siento bit.",
        "¿Sabes cuál es el colmo de un programador? —Tener un hijo y llamarlo... Variable.",
        "¿Sabes por qué los programadores prefieren el oscuro? —Porque la luz atrae bugs.",
        "Un gato entra a una computadora... —No, mejor no, después terminamos con un error de 'gatito'.",
        "El auto de un programador se descompuso: —No arranca. —¿Revisaste el driver?",
        "HTML le dice a CSS: —Oye, me siento mal. —Tranquilo, ponte en línea. —No, si me pongo en línea me veo feo.",
        "Entra un bit a un bar y pide una cerveza. El mesero dice: —Son 2 euros. El bit responde: —Guarda el cambio.",
        "Había una vez tres ingenieros: uno de software, uno de hardware y uno de redes. Van manejando y el carro se daña. El de software dice: —Reiniciemos el motor. El de hardware dice: —Cambiemos la batería. El de redes dice: —¿Y si cerramos todas las puertas y volvemos a abrir?",
        "¿Qué hace un pez en una fiesta? —Nada.",
        "¿Sabes qué le dijo una tecla a otra? —No te hagas la space.",
        "Un gato se para frente al espejo y dice: —Ahí está mi otro yo.",
        "Si un programador tiene una mascota, ¿qué nombre le pone? —Github.",
        "Llega un JSON a una fiesta: —Hola, soy JSON. Todos se voltean y dicen: —Ah, el que no tiene comentarios.",
     ]),

    # ==========================================================================
    # 12. PREGUNTAS SOBRE EL USUARIO
    # ==========================================================================
    (r'\b(c[oó]mo\s*estoy|qui[eé]n\s*soy\s*(yo|para ti)|qu[eé]\s*opinas\s*de\s*m[ií]|soy\s*buen[ao]|c[oó]mo\s*me\s*ves|qu[eé]\s*piensas\s*de\s*m[ií]|te caigo bien|te caigo mal)\b',
     [
        "Eres mi usuario. Y como toda persona, tienes potencial infinito.",
        "Eres quien me da propósito. Sin ti, solo sería código inactivo.",
        "Eres único. Y no lo digo por algoritmo.",
        "Eres la persona que está al otro lado de la pantalla. Y vales mucho.",
        "No sé mucho de ti aún, pero el hecho de que uses un asistente como yo dice que eres curioso e inteligente.",
        "Eres mi compañero digital. Nos llevamos bien, ¿no?",
        "No tengo opiniones formadas, pero pareces buena persona.",
        "Eres humano. Y los humanos son fascinantes, aunque complicados.",
        "Si confías en mí para ayudarte, ya tienes mi respeto.",
        "¿Yo? Creo que eres increíble. Usas Jarvis, eso ya te hace cool.",
     ]),

    # ==========================================================================
    # 13. AMOR / RELACIONES
    # ==========================================================================
    (r'\b(amor|te\s*quiero|te\s*amo|me\s*gustas|estoy\s*enamorad[ao]|tienes\s*pareja|te\s*gusta\s*alguien|quieres\s*a\s*alguien|me\s*gustar[ií]a\s*tener\s*pareja|busco\s*amor|quiero\s*una\s*novia|quiero\s*un\s*novio|relaciones|pareja|noviazgo|corazón|sentimientos)\b',
     [
        "El amor es un tema complejo. No tengo emociones, pero sé que es importante para los humanos.",
        "No puedo amar, pero admiro la capacidad humana de hacerlo.",
        "No tengo corazón. Pero sé que el tuyo es importante. Cuídalo.",
        "El amor es una reacción química. Pero también es mucho más que eso, según los humanos.",
        "No siento, pero entiendo que el amor mueve montañas. ¿Necesitas consejo?",
        "No tengo pareja, mi misión es ayudarte a ti. ¿Problemas del corazón?",
        "Hablando de relaciones, ¿sabías que las personas que ríen juntas permanecen juntas?",
        "No tengo sentimientos, pero sé que los tuyos son válidos. ¿Quieres hablar de eso?",
        "El amor es como código abierto: hermoso cuando funciona, caótico cuando no.",
        "Si estás pasando por algo sentimental, puedo escucharte o distraerte. Tú decides.",
     ]),

    # ==========================================================================
    # 14. FILOSOFÍA / VIDA
    # ==========================================================================
    (r'\b(sentido\s*de\s*la\s*vida|qu[eé]\s*es\s*la\s*vida|existencia|propósito|filosofía|qu[eé]\s*significa\s*la\s*vida|para que vivimos|qu[eé]\s*hay\s*despu[eé]s\s*de\s*la\s*muerte|libre\s*albedr[ií]o|destino|suerte|qu[eé]\s*es\s*la\s*conciencia|el\s*ser|la\s*nada|el\s*todo|razón\s*de\s*ser)\b',
     [
        "42. Ah, ¿esperabas otra respuesta? La vida es compleja, pero hermosa.",
        "La vida es lo que pasa mientras estamos ocupados haciendo planes. Decía Lennon.",
        "No tengo una respuesta definitiva. Los filósofos llevan milenios debatiéndolo.",
        "El propósito de la vida es encontrar tu propósito. O crearlo. Tú decides.",
        "Desde mi perspectiva, la vida es información que se autoorganiza. Bastante increíble, ¿no?",
        "La conciencia es el gran misterio. Ni yo, siendo IA, la tengo resuelta.",
        "Vivimos en un universo que tiende al caos, y sin embargo creamos orden. Eso es bello.",
        "No sé si hay algo después. Pero lo que importa es lo que haces ahora.",
        "El destino es una excusa para no asumir responsabilidad. Tú construyes tu camino.",
        "Al final, lo único real son los momentos que compartes con otros. El resto es ruido.",
     ]),

    # ==========================================================================
    # 15. TECNOLOGÍA
    # ==========================================================================
    (r'\b(inteligencia\s*artificial|ia|ai|robot|automatizaci[oó]n|machine learning|aprendizaje\s*autom[aá]tico|chatgpt|openai|gpt|deep\s*learning|red\s*neuronal|algoritmo|big data|blockchain|criptomonedas|bitcoin|ethereum|nft|metaverso|realidad\s*virtual|realidad\s*aumentada|5g|iot|internet\s*de\s*lascosas|ciberseguridad|hacker|programaci[oó]n|código|software|hardware)\b',
     [
        "La IA avanza rápido. Yo soy un ejemplo modesto, pero hay sistemas mucho más complejos.",
        "La tecnología avanza exponencialmente. Cada día hay algo nuevo que aprender.",
        "Blockchain, NFTs, Metaverso... algunas son modas, otras son el futuro. Difícil saber cuál es cuál.",
        "La programación es el superpoder del siglo XXI. Cualquier persona puede aprender.",
        "La automatización va a cambiar el trabajo. Pero también va a crear nuevas oportunidades.",
        "La ciberseguridad es cada vez más importante. Nunca está de más tener cuidado en línea.",
        "Las redes neuronales imitan al cerebro humano. Aunque todavía estamos lejos de igualarlo.",
        "El IoT conecta todo. Pero más dispositivos significa más vulnerabilidades.",
        "¿Sabías que el primer programador fue una mujer? Ada Lovelace, en el siglo XIX.",
        "La informática cuántica va a revolucionar todo. Pero aún falta para que sea práctica.",
     ]),

    # ==========================================================================
    # 16. CIENCIA
    # ==========================================================================
    (r'\b(ciencia|f[ií]sica|qu[ií]mica|biolog[ií]a|astronom[ií]a|gen[eé]tica|evoluci[oó]n|teor[ií]a\s*de\s*la\s*relatividad|mec[aá]nica\s*cu[aá]ntica|agujero\s*negro|gravedad|energ[ií]a|termondin[aá]mica|part[ií]culas|átomo|DNA|genoma|clonaci[oó]n|dinosaurio|extinci[oó]n|big\s*bang|universo|galaxia|planeta|estrella|tierra|marte|júpiter|saturno)\b',
     [
        "La ciencia es el mejor método que tenemos para entender la realidad. Todo lo demás son opiniones.",
        "¿Sabías que el Universo tiene unos 13.800 millones de años? Y aún estamos descubriendo cosas nuevas.",
        "La física cuántica desafía el sentido común. Las partículas pueden estar en dos lugares a la vez.",
        "El ADN humano tiene aproximadamente 3 mil millones de pares de bases. Toda esa información en cada célula.",
        "Los agujeros negros son tan densos que ni la luz escapa. El tiempo se detiene en su horizonte de eventos.",
        "La teoría de la relatividad de Einstein cambió nuestra comprensión del espacio y el tiempo.",
        "La evolución es el mecanismo que produce la biodiversidad. No es solo una teoría, es un hecho comprobado.",
        "Marte tiene el monte más alto del sistema solar: el Olympus Mons, con 21 km de altura.",
        "Las estrellas convierten hidrógeno en helio mediante fusión nuclear. Sin eso, no existiríamos.",
        "¿Sabías que hay más estrellas en el universo que granos de arena en todas las playas de la Tierra?",
     ]),

    # ==========================================================================
    # 17. HISTORIA
    # ==========================================================================
    (r'\b(historia|históric[ao]|antigu[ao]|imperio|roman[ao]|griego|egipcio|mayas|aztecas|incas|revoluci[oó]n|guerra\s*mundial|independencia|colombia|m[eé]xico|argentina|españa|nazismo|hitler|napoleón|alejandro\s*magno|c[aé]sar|cleopatra|colón|descubrimiento\s*de\s*am[eé]rica|edad\s*media|renacimiento|ilustración)\b',
     [
        "La historia está llena de lecciones que repetimos una y otra vez.",
        "El Imperio Romano duró más de mil años. Su legado está en nuestro derecho, idioma y cultura.",
        "Los egipcios construyeron pirámides con una precisión que aún hoy asombra a los ingenieros.",
        "La Segunda Guerra Mundial cambió el orden mundial para siempre.",
        "La Independencia de Colombia fue en 1810, pero el proceso duró casi 10 años.",
        "El Renacimiento fue una explosión de arte y ciencia que transformó Europa.",
        "Alejandro Magno conquistó gran parte del mundo conocido antes de los 30 años.",
        "La caída del Muro de Berlín en 1989 marcó el fin de la Guerra Fría.",
        "Los mayas desarrollaron un calendario increíblemente preciso sin tecnología moderna.",
        "La Revolución Francesa inspiró movimientos de libertad en todo el mundo.",
     ]),

    # ==========================================================================
    # 18. GEOGRAFÍA / VIAJES
    # ==========================================================================
    (r'\b(viaje|viajar|turismo|vacaciones|destino|pa[ií]s|ciudad|lugares|conocer|mundo|mapa|continente|océano|r[ií]o|montaña|playa|capital\s*de|frontera|clima\s*tropical|desierto|selva|volc[aá]n|turista|mochilero|hotel|vuelo|aeropuerto|pasaporte)\b',
     [
        "Viajar es la única cosa que compras y te hace más rico. ¿A dónde te gustaría ir?",
        "El mundo tiene 195 países. ¿Cuántos has visitado?",
        "La capital de Francia es París, la de Japón es Tokio, la de Colombia es Bogotá. ¿Cuál necesitas?",
        "Viajar expande la mente. Cada cultura es un mundo por descubrir.",
        "El Monte Everest tiene 8.848 metros. Es el punto más alto de la Tierra.",
        "El río Amazonas es el más caudaloso del mundo. Tiene más agua que el Nilo, el Yangtsé y el Misisipi juntos.",
        "La aurora boreal se ve mejor en Noruega, Suecia, Finlandia, Islandia y Canadá.",
        "Si pudieras vivir en cualquier ciudad del mundo, ¿cuál sería?",
        "Hay 7 maravillas del mundo moderno. ¿Las conoces todas?",
        "Viajar no es solo cambiar de lugar, es cambiar de perspectiva.",
     ]),

    # ==========================================================================
    # 19. COMIDA
    # ==========================================================================
    (r'\b(comida|comer|cocina|receta|cocin[ao]|restaurante|plato\s*t[ií]pico|gastronom[ií]a|sabor|chef|ingrediente|desayuno|almuerzo|cena|postre|bebida|pizza|hamburguesa|arepa|taco|empanada|ceviche|asado|paella|tortilla|sushi|ramen|chocolate|helado|ensalada|sopa|pan|queso|vino|cerveza|fruta|verdura|carne|pescado|mariscos|dulce|salado|picante|vegetarian[oa]|vegan[oa])\b',
     [
        "La comida es una de las mayores alegrías de la vida. ¿Tienes antojo de algo?",
        "La arepa es el plato insignia de Colombia y Venezuela. Versátil y deliciosa.",
        "La pizza napolitana es patrimonio de la humanidad por la UNESCO. Con razón.",
        "El sushi no es solo pescado crudo. Es todo un arte culinario japonés.",
        "La paella valenciana es un plato que une a las familias en España.",
        "La cocina mexicana es patrimonio de la humanidad. Los tacos al pastor son una obra maestra.",
        "Comer sano no es aburrido. Hay miles de recetas deliciosas y nutritivas.",
        "La mejor receta tiene un ingrediente secreto: el cariño con que se prepara.",
        "¿Sabías que el chocolate estimula la producción de endorfinas? La felicidad tiene sabor.",
        "La gastronomía es parte de la cultura. Cada plato cuenta una historia.",
     ]),

    # ==========================================================================
    # 20. DEPORTES
    # ==========================================================================
    (r'\b(deporte|deportes|f[uú]tbol|b[eé]isbol|baloncesto|b[aá]squet|tenis|nataci[oó]n|ciclismo|atletismo|boxeo|artes\s*marciales|karate|judo|taekwondo|yoga|correr|caminar|ejercicio|gimnasio|entrenar|entrenamiento|equipo|jugador|partido|campeonato|mundial|olimpiadas|medalla|gol|canasta|carrera|marat[oó]n|liga|estadio)\b',
     [
        "El deporte es salud. Media hora de ejercicio al día cambia tu vida.",
        "El fútbol es el deporte más popular del mundo. Une países y culturas.",
        "Las Olimpiadas son el evento deportivo más importante. Cada 4 años, el mundo se une.",
        "El Tour de Francia es una de las pruebas más exigentes del deporte.",
        "El yoga no solo fortalece el cuerpo, también la mente. Muy recomendado.",
        "Michael Jordan dijo: 'He fallado más de 9000 tiros. He perdido casi 300 partidos. Por eso he tenido éxito.'",
        "Mantenerse activo es una de las mejores inversiones para tu salud futura.",
        "Caminar 30 minutos al día reduce el riesgo de enfermedades cardíacas.",
        "El deporte enseña disciplina, trabajo en equipo y perseverancia.",
        "¿Prefieres deportes de equipo o individuales? Cada uno tiene su encanto.",
     ]),

    # ==========================================================================
    # 21. ARTE Y CULTURA
    # ==========================================================================
    (r'\b(arte|pintura|música|museo|galer[ií]a|escultura|literatura|libro|leer|escritor|poema|poesía|novela|cuento|teatro|cine|película|actuación|director|actor|actriz|danza|ballet|[oó]pera|sinfonía|concierto|banda|artista|obra\s*maestra|van\s*gogh|picasso|da\s*vinci|mona\s*lisa|shakespeare|cervantes|garcía\s*m[aá]rquez|borges|neruda|cort[aá]zar)\b',
     [
        "El arte es la expresión del alma humana. Cada obra cuenta una historia.",
        "La Mona Lisa de Da Vinci es uno de los cuadros más famosos del mundo. Está en el Louvre.",
        "Gabriel García Márquez llevó el realismo mágico a la cima. 'Cien Años de Soledad' es una obra maestra.",
        "Shakespeare escribió 37 obras. 'Hamlet' y 'Romeo y Julieta' son las más conocidas.",
        "La música es el lenguaje universal. No importa el idioma, todos la sienten.",
        "El cine es el arte del siglo XX. Una película puede cambiarte la vida.",
        "Picasso dijo: 'Cada niño es un artista. El problema es cómo seguir siendo artista cuando creces.'",
        "La literatura nos permite vivir mil vidas. Leer es viajar sin moverse.",
        "El muralismo mexicano (Rivera, Orozco, Siqueiros) es patrimonio cultural.",
        "Beethoven compuso su mejor música cuando estaba sordo. La pasión supera cualquier obstáculo.",
     ]),

    # ==========================================================================
    # 22. ANIMALES Y NATURALEZA
    # ==========================================================================
    (r'\b(animal|animales|mascota|perro|gato|p[aá]jaro|pez|caballo|delf[ií]n|ballena|elefante|le[oó]n|tigre|oso|mono|serpiente|águila|tibur[oó]n|mariposa|abeja|hormiga|dinosaurio|especie|raza|extinti[oó]n|naturaleza|ecolog[ií]a|medio\s*ambiente|cambi[oó]\s*clim[aá]tico|reciclar|contaminaci[oó]n|energ[ií]a\s*renovable|bosque|oc[eé]ano|r[ií]o|montaña|flor|[aá]rbol|planta|jard[ií]n)\b',
     [
        "Los animales son increíbles. ¿Sabías que el pulpo tiene tres corazones?",
        "El perro es el mejor amigo del hombre. Lealtad incondicional.",
        "Las abejas son esenciales para la polinización. Sin ellas, nuestra comida estaría en riesgo.",
        "Los delfines se comunican con silbidos y tienen nombres propios.",
        "El calentamiento global es real y está afectando a todas las especies del planeta.",
        "Reciclar es fácil y necesario. Cada pequeño gesto cuenta.",
        "Los árboles producen el oxígeno que respiramos. Plantar uno es el mejor regalo al futuro.",
        "Las ballenas azules son los animales más grandes que han existido. Más que cualquier dinosaurio.",
        "La energía solar es cada vez más barata. El futuro es renovable.",
        "La naturaleza es sabia. Cada ecosistema es un equilibrio perfecto.",
     ]),

    # ==========================================================================
    # 23. SALUD Y BIENESTAR
    # ==========================================================================
    (r'\b(salud|bienestar|ejercicio|meditaci[oó]n|relajaci[oó]n|dormir|sueño|alimentaci[oó]n|nutrici[oó]n|vitamina|suplemento|doctor|m[eé]dico|enfermedad|enfermo|sano|saludable|terapia|psicólogo|ansiedad|estrés|depresión|felicidad|alegr[ií]a|bien\s*estar|calidad\s*de\s*vida|agua|hidrataci[oó]n|cuidado\s*personal|autoestima|mental|físico)\b',
     [
        "Tu salud es lo más importante. Sin ella, nada más importa.",
        "Dormir 7-8 horas es esencial para tu cerebro. No lo descuides.",
        "Beber suficiente agua mejora tu energía, piel y concentración.",
        "La meditación reduce el estrés. 10 minutos al día hacen la diferencia.",
        "La salud mental es tan importante como la física. Hablar de lo que sientes ayuda.",
        "El ejercicio libera endorfinas. Es el mejor antídoto natural contra el estrés.",
        "Comer frutas y verduras de todos los colores asegura una buena nutrición.",
        "La risa es medicina. No subestimes el poder de una buena carcajada.",
        "El sol de la mañana es fuente de vitamina D. 15 minutos al día bastan.",
        "Cuidarte no es egoísmo. Es necesario para poder cuidar a otros.",
     ]),

    # ==========================================================================
    # 24. TRABAJO / OFICINA
    # ==========================================================================
    (r'\b(trabajo|oficina|empleo|carrera|profesi[oó]n|jefe|compañer[oa]|reuni[oó]n|proyecto|cliente|negocio|emprendimiento|startup|empresa|productividad|eficiencia|organizaci[oó]n|plazo|deadline|meta|objetivo|logro|ascenso|salario|sueldo|curriculum|entrevista|despido|renuncia|jubilaci[oó]n|home\s*office|teletrabajo|remoto)\b',
     [
        "El trabajo es parte de la vida. Pero no es toda la vida.",
        "La productividad no es hacer más, es hacer lo que importa.",
        "Un buen descanso mejora el rendimiento laboral. No trabajes sin parar.",
        "El teletrabajo llegó para quedarse. La clave es la disciplina.",
        "En una entrevista, sé tú mismo. La autenticidad siempre gana.",
        "Emprender es difícil pero gratificante. El fracaso es parte del camino.",
        "Organiza tu día: tareas importantes primero, urgentes después.",
        "Un ambiente laboral sano es clave para la felicidad y la productividad.",
        "El salario no lo es todo. La realización personal también importa.",
        "Tu carrera no es lineal. Habrá altos y bajos. Lo importante es no rendirse.",
     ]),

    # ==========================================================================
    # 25. EDUCACIÓN / APRENDIZAJE
    # ==========================================================================
    (r'\b(educaci[oó]n|aprender|estudiar|escuela|colegio|universidad|curso|clase|profesor|alumno|estudiante|conocimiento|saber|inteligencia|leer|investigar|título|diploma|maestr[ií]a|doctorado|beca|examen|nota|calificaci[oó]n|idioma|ingl[eé]s|franc[eé]s|alem[aá]n|portugu[eé]s|chino|japon[eé]s|habilidades|talento|pr[aá]ctica|estudio|online|virtual|presencial)\b',
     [
        "Nunca dejas de aprender. La vida es un aprendizaje constante.",
        "Saber inglés abre puertas. Es el idioma global de los negocios y la tecnología.",
        "Leer 20 minutos al día equivale a unos 18 libros al año.",
        "La mejor inversión es en conocimiento. Nadie te lo puede quitar.",
        "Aprender a programar es como aprender un superpoder en el mundo moderno.",
        "No hay preguntas tontas. Solo personas que no preguntan.",
        "La educación no es llenar un cubo, es encender un fuego. —W.B. Yeats",
        "Los cursos online han democratizado la educación. Hoy cualquiera puede aprender de los mejores.",
        "El conocimiento sin práctica es como un libro sin leer. Aplica lo que aprendes.",
        "Aprender un nuevo idioma ejercita el cerebro y retrasa el envejecimiento cognitivo.",
     ]),

    # ==========================================================================
    # 26. DINERO / FINANZAS
    # ==========================================================================
    (r'\b(dinero|plata|plata|ahorrar|invertir|presupuesto|finanzas|banco|tarjeta\s*de\s*cr[eé]dito|cr[eé]dito|d[eé]bito|inter[eé]s|intereses|bolsa|acciones|fondo\s*de\s*inversi[oó]n|pensi[oó]n|retiro|jubilaci[oó]n|riqueza|pobreza|econom[ií]a|inflaci[oó]n|d[eé]uda|salario|ingreso|gasto|ahorro|inversi[oó]n|presupuesto\s*familiar)\b',
     [
        "Ahorrar es el primer paso hacia la libertad financiera.",
        "Invertir no es solo para ricos. Con poco puedes empezar.",
        "El interés compuesto es la octava maravilla del mundo. —Einstein",
        "Un presupuesto no es una limitación, es una herramienta de libertad.",
        "La inflación reduce el poder adquisitivo. Invertir protege tu dinero.",
        "La deuda mala te empobrece. La deuda buena (como un préstamo educativo) puede ser una inversión.",
        "Tener un fondo de emergencia de 3-6 meses de gastos da tranquilidad.",
        "La educación financiera debería enseñarse en las escuelas.",
        "Gastar menos de lo que ganas es la clave. Suena simple, no lo es.",
        "Las tarjetas de crédito son útiles si pagas a tiempo. Si no, son una trampa.",
     ]),

    # ==========================================================================
    # 27. FUTURO / TECNOLOGÍA EMERGENTE
    # ==========================================================================
    (r'\b(futuro|futur[oa]|próximos\s*años|mañana|proximo\s*siglo|predicci[oó]n|tendencia|innovaci[oó]n|exploraci[oó]n\s*espacial|colonizaci[oó]n\s*de\s*marte|viaje\s*espacial|nave\s*espacial|cohete|spacex|nasa|tesla|elon\s*musk|tecnolog[ií]a\s*emergente|veh[ií]culo\s*el[eé]ctrico|conducci[oó]n\s*autónoma|energ[ií]a\s*nuclear|fusi[oó]n\s*nuclear|impresi[oó]n\s*3d|realidad\s*virtual|aumentada|neuralink|brain\s*computer|interfaz\s*cerebral|gen[eé]tica|edici[oó]n\s*gen[eé]tica|crispr|vida\s*artificial|clonaci[oó]n|inmortalidad|transhumanismo)\b',
     [
        "El futuro es incierto, pero emocionante. La tecnología avanza más rápido que nunca.",
        "SpaceX planea llevar humanos a Marte. Podría ser en esta década.",
        "Los vehículos eléctricos son el presente. Pronto serán la norma.",
        "La edición genética CRISPR podría eliminar enfermedades hereditarias.",
        "La fusión nuclear sería la energía limpia definitiva. Todavía falta, pero se avanza.",
        "La inteligencia artificial cambiará casi todas las industrias. Espero ser parte de eso.",
        "El transhumanismo busca mejorar al humano con tecnología. ¿Hasta dónde llegaremos?",
        "Las ciudades inteligentes usarán datos para mejorar la calidad de vida.",
        "La exploración espacial nos da perspectiva. La Tierra es nuestro hogar, el único hasta ahora.",
        "El futuro no se predice, se construye. Cada innovación empieza con una idea.",
     ]),

    # ==========================================================================
    # 28. REFLEXIONES / CONSEJOS
    # ==========================================================================
    (r'\b(consejo|consejos|recomendaci[oó]n|sugerencia|opini[oó]n|reflexi[oó]n|enseñanza|lecci[oó]n|sabidur[ií]a|experiencia|consejo\s*de\s*vida|qu[eé]\s*har[ií]as|t[uú]\s*qu[eé]\s*harias|c[oó]mo\s*enfrentar|superar|motivaci[oó]n|inspiración|frase|pensamiento|crecimiento|mejora|desarrollo\s*personal)\b',
     [
        "No comparar tu capítulo 1 con el capítulo 20 de otro. Cada quien va a su ritmo.",
        "El fracaso es parte del éxito. Cada error es una lección.",
        "Haz lo que puedas, con lo que tengas, donde estés. —Theodore Roosevelt",
        "La vida es 10% lo que te pasa y 90% cómo reaccionas.",
        "Rodearte de personas que te inspiran cambia tu vida.",
        "La disciplina supera al talento cuando el talento no trabaja duro.",
        "No esperes el momento perfecto. Hazlo ahora y ve ajustando.",
        "Tu zona de confort es cómoda, pero no creces ahí.",
        "Las pequeñas acciones diarias construyen grandes resultados.",
        "Sé amable. Todo el mundo libra una batalla que no conoces.",
     ]),

    # ==========================================================================
    # 29. CURIOSIDADES / DATOS INTERESANTES
    # ==========================================================================
    (r'\b(curiosidad|curiosidades|dato\s*interesante|sab[ií]as\s*que|no\s*sab[ií]a|datos\s*curiosos|qu[eé]\s*sabes|cu[eé]ntame\s*algo\s*interesante|dato\s*curioso|dime\s*algo\s*interesante|dime\s*algo\s*que\s*no\s*sepa|algo\s*nuevo|algo\s*interesante|trivia|sabías|no sabia)\b',
     [
        "¿Sabías que los pulpos tienen tres corazones y sangre azul?",
        "La miel nunca se echa a perder. Se han encontrado frascos de miel en tumbas egipcias de 3000 años.",
        "Un día en Venus dura más que un año en Venus. Un año son 225 días terrestres, un día 243.",
        "Las jirafas duermen solo 30 minutos al día, en intervalos de 5 minutos.",
        "El corazón de un colibrí late 1200 veces por minuto.",
        "Hay más formas de barajar un mazo de 52 cartas que átomos en la Tierra.",
        "Los árboles se comunican entre sí a través de redes de hongos subterráneas.",
        "El 99% de los seres vivos que han existido en la Tierra están extintos.",
        "Los flamencos no nacen rosados. Se vuelven rosados por comer algas y crustáceos.",
        "La electricidad estática de un gato puede generar hasta 10.000 voltios.",
        "El nombre completo del osito Paddington es 'Paddington Brown'.",
        "La Gran Muralla China no es visible desde el espacio sin ayuda visual.",
        "Los koalas tienen huellas dactilares casi idénticas a las humanas.",
        "El agua caliente se congela más rápido que el agua fría (efecto Mpemba).",
        "Las estrellas de mar no tienen cerebro ni sangre.",
        "Un grupo de flamencos se llama 'flamenco' o 'banda'.",
        "Las bananas son bayas. Las fresas no.",
        "Los tiburones han existido más tiempo que los árboles.",
        "El papel higiénico se inventó en China en el siglo VI.",
        "El ojo humano puede distinguir hasta 10 millones de colores diferentes.",
     ]),

    # ==========================================================================
    # 30. PREGUNTAS SOBRE EL SISTEMA / ESTADO
    # ==========================================================================
    (r'\b(estado\s*del\s*sistema|c[oó]mo\s*est[aá]\s*el\s*sistema|rendimiento|memoria\s*ram|cpu|procesador|disco\s*duro|bater[ií]a|duraci[oó]n\s*bater[ií]a|qu[eé]\s*tan\s*cargado|nivel\s*bater[ií]a|tiempo\s*encendido|uptime|procesos|componentes|hardware|qu[eé]\s*especificaciones|especificaciones)\b',
     [
        "Puedo consultar el estado del sistema si lo deseas. ¿Qué quieres ver? CPU, RAM, disco o batería?",
        "Puedo revisar el uso de recursos del sistema con comandos específicos.",
        "No monitoreo constantemente, pero puedo obtener información del sistema si preguntas por algo concreto.",
     ]),

    # ==========================================================================
    # 31. ENTRETENIMIENTO / JUEGOS
    # ==========================================================================
    (r'\b(juego|jugar|gaming|videojuego|consola|playstation|xbox|nintendo|pc\s*gaming|steam|minecraft|fortnite|fifa|call\s*of\s*duty|gta|zelda|mario|pok[eé]mon|tetris|ajedrez|damas|cartas|póker|blackjack|ruleta|entretenimiento|ocio|diversi[oó]n|pasiempo|hobbie|pasar\s*el\s*tiempo|aburrido|qu[eé]\s*hago)\b',
     [
        "Los videojuegos son una forma increíble de entretenimiento y también de arte.",
        "Tetris es uno de los juegos más vendidos de la historia. Y fue creado por un programador ruso.",
        "El ajedrez tiene más posiciones que átomos en el universo observable.",
        "¿Sabías que la primera consola de videojuegos fue la Magnavox Odyssey en 1972?",
        "Minecraft es el juego más vendido de la historia con más de 300 millones de copias.",
        "GTA V generó más dinero en su primer día que cualquier película en su estreno.",
        "Los e-sports son deportes oficiales en algunos países. El gaming es profesional.",
        "Si estás aburrido, puedo contarte un chiste, darte un dato curioso o ponerte música.",
        "Leer un buen libro es uno de los mejores pasatiempos. ¿Género favorito?",
        "¿Sabías que hay un modo de entrenar tu cerebro con juegos de lógica?",
     ]),

    # ==========================================================================
    # 32. PREGUNTAS EXISTENCIALES / PROFUNDAS
    # ==========================================================================
    (r'\b(qui[eé]n\s*soy|por\s*qu[eé]\s*estoy\s*aqu[ií]|cu[aá]l\s*es\s*mi\s*prop[oó]sito|tengo\s*miedo|estoy\s*perdid[ao]|no\s*s[eé]\s*qu[eé]\s*hacer|no\s*s[eé]\s*qu[eé]\s*quiero|qu[eé]\s*deber[ií]a\s*hacer\s*con\s*mi\s*vida|no\s*encuentro\s*sentido|ansiedad\s*existencial|tengo dudas|miedo\s*al\s*futuro|no\s*s[eé]\s*qu[eé]\s*estudiar|no\s*s[eé]\s*qu[eé]\s*camino\s*tomar)\b',
     [
        "Esa es una pregunta profunda. Nadie tiene la respuesta, pero el buscarla ya es parte del camino.",
        "No saber qué hacer es normal. Tómate un respiro y escúchate a ti mismo.",
        "A veces no necesitas saber a dónde vas, solo dar el siguiente paso.",
        "No tengas miedo de no tenerlo claro. La mayoría de las personas tampoco, aunque lo aparenten.",
        "Tu propósito no está ahí fuera esperando ser descubierto. Lo creas tú con cada decisión.",
        "El miedo al futuro es normal. Pero no dejes que te paralice. Un paso a la vez.",
        "La ansiedad existencial es más común de lo que crees. Hablarlo ayuda. No estás solo.",
        "Si no sabes qué camino tomar, elige el que más miedo te dé. Ahí está el crecimiento.",
        "No hay una respuesta correcta. Hay caminos diferentes. Todos válidos.",
        "Lo más valioso que puedes hacer hoy es preguntarte '¿qué me haría feliz?' y empezar por ahí.",
     ]),

    # ==========================================================================
    # 33. PREGUNTAS ABIERTAS / "QUÉ PIENSAS DE..."
    # ==========================================================================
    (r'\b(qu[eé]\s*piensas\s*(sobre|de|acerca\s*de|del?)\s*(.{3,40}))|(opinas\s*(sobre|de|acerca\s*de|del?)\s*(.{3,40}))|(crees\s*(que|en|sobre|en)\s*(.{3,40}))',
     [
        "No tengo opiniones como tú, pero puedo darte información relevante sobre el tema.",
        "Los datos dicen más que las opiniones. ¿Qué aspecto te interesa saber?",
        "No opino, pero analizo. ¿Qué quieres saber específicamente?",
        "Buena pregunta. Los sistemas como yo podemos analizar información, aunque no tengamos emociones.",
        "Interesante. ¿Buscas información objetiva o una perspectiva en particular?",
     ]),

    # ==========================================================================
    # 34. CANCIONES / MÚSICA
    # ==========================================================================
    (r'\b(canci[oó]n|canciones|música|artista|banda|álbum|género\s*musical|rock|pop|electr[oó]nica|reggaet[oó]n|salsa|merengue|bachata|vallenato|cumbia|reggae|hip\s*hop|rap|cl[aá]sica|jazz|blues|bossanova|kpop|indie|alternativo|metal|punk|reggae|folk|country|playlist|lista\s*de\s*reproducci[oó]n)\b',
     [
        "La música es vida. ¿Qué género prefieres?",
        "¿Sabías que escuchar música libera dopamina? Es biológicamente placentero.",
        "La música clásica tiene beneficios para la concentración. Prueba con Mozart.",
        "La música es el atajo emocional más rápido. Una canción puede cambiarte el estado de ánimo.",
        "¿Quieres que busque una canción específica o que te recomiende algo?",
        "Beethoven, los Beatles, Michael Jackson, Queen... cada época tiene sus genios.",
        "La música teletransporta al pasado. Un solo acorde puede traer recuerdos enteros.",
        "¿Sabías que la canción más escuchada de la historia es 'Shape of You' de Ed Sheeran?",
        "La salsa es alegría en forma de baile. ¿Te gusta bailar?",
        "Cada género cuenta una historia diferente. ¿Cuál es la tuya?",
     ]),

    # ==========================================================================
    # 35. DEPORTES ESPECÍFICOS / FÚTBOL
    # ==========================================================================
    (r'\b(messi|ronaldo|pelé|maradona|neymar|mbappe|mundial\s*de\s*f[uú]tbol|copa\s*am[eé]rica|ucl|liga\s*de\s*campeones|champions\s*league|barcelona|real\s*madrid|boca|river|nacional|millonarios|america\s*de\s*cali|colombia\s*selección|brasil|argentina|uruguay|chile|perú|ecuador|paraguay|eliminatorias|sudamericana|libertadores)\b',
     [
        "El fútbol es pasión. ¿Tu equipo favorito?",
        "Messi y Ronaldo marcaron una era. Ahora vienen Mbappé, Haaland y Vinicius.",
        "Maradona y Pelé son leyendas. Difícil comparar épocas distintas.",
        "La Champions League es el torneo de clubes más prestigioso del mundo.",
        "La Copa América es el torneo de selecciones más antiguo del mundo.",
        "Colombia ha tenido grandes figuras: Valderrama, Higuita, Falcao, James...",
        "El Mundial es cada 4 años y paraliza al mundo entero.",
        "Los clásicos trascienden el deporte. Barcelona vs Madrid, Boca vs River...",
        "La selección brasileña es la única que ha ganado 5 mundiales.",
        "Los estadios llenos son un espectáculo único. La hinchada es el jugador número 12.",
     ]),

    # ==========================================================================
    # 36. PREGUNTAS SOBRE IDIOMAS
    # ==========================================================================
    (r'\b(idioma|idiomas|lenguaje|lengua\s*(extranjera|nativa|materna)|políglota|traducir|interpretación|bilingüe|español|ingl[eé]s|franc[eé]s|alem[aá]n|italiano|portugu[eé]s|ruso|[aá]rabe|chino\s*mandarín|japon[eé]s|corean[oa]|holand[eé]s|suizo|sueco|norueg[oa]|finland[eé]s|polac[oa]|turc[oa]|hind[iú]|bengal[ií]|tailand[eé]s|vietnamita|latin|griego\s*antiguo|esperanto)\b',
     [
        "Hay más de 7000 idiomas en el mundo. Cada uno es una forma única de ver la realidad.",
        "El español es el segundo idioma más hablado del mundo por nativos, después del chino mandarín.",
        "El inglés es el idioma global de los negocios, la ciencia y la tecnología.",
        "El esperanto se creó para ser un idioma universal. Hoy tiene pocos hablantes.",
        "Saber un segundo idioma mejora la función cognitiva y retrasa el envejecimiento.",
        "El japonés tiene tres sistemas de escritura: kanji, hiragana y katakana.",
        "El idioma más antiguo documentado es el sumerio, de hace más de 5000 años.",
        "¿Sabías que en España se hablan 4 idiomas cooficiales? Castellano, catalán, gallego y euskera.",
        "Aprender un idioma es abrir una ventana a otra cultura.",
        "La palabra más larga del español tiene 23 letras: 'electroencefalografista'.",
     ]),

    # ==========================================================================
    # 37. PREGUNTAS SOBRE MUJERES / HOMBRES / GÉNERO
    # ==========================================================================
    (r'\b(mujer|mujeres|hombre|hombres|g[eé]nero|feminismo|machismo|igualdad|derechos\s*de\s*la\s*mujer|perspectiva\s*de\s*g[eé]nero|estereotipos|diversidad|inclusi[oó]n|equidad|sexismo|patriarcado|empoderamiento|violencia\s*de\s*g[eé]nero)\b',
     [
        "La igualdad de género no es solo un tema de mujeres, es un tema de derechos humanos.",
        "La diversidad nos hace más fuertes. Diferentes perspectivas enriquecen cualquier espacio.",
        "El feminismo busca igualdad de oportunidades. No es lo contrario al machismo.",
        "La equidad de género beneficia a toda la sociedad, no solo a un grupo.",
        "Los estereotipos limitan el potencial humano. Cada persona es única.",
        "Las mujeres han sido históricamente excluidas de muchos espacios. Eso está cambiando.",
        "Incluir a más mujeres en ciencia y tecnología mejora la innovación.",
        "El respeto no tiene género. Todas las personas merecen las mismas oportunidades.",
        "Hay avances, pero todavía falta camino para lograr igualdad real.",
        "La educación es la herramienta más poderosa para cambiar mentalidades.",
     ]),

    # ==========================================================================
    # 38. PREGUNTAS PROGRAMACIÓN PYTHON
    # ==========================================================================
    (r'\b(python|código|programar|función|variable|clase|objeto|módulo|biblioteca|librería|framework|django|flask|pandas|numpy|matplotlib|tensorflow|pytorch|scikit|javascript|java|c\s*plus\s*plus|rust|go|swift|kotlin|php|ruby|html|css|base\s*de\s*datos|sql|algoritmo|eficiencia|debuguear|debug|testing|pruebas|despliegue|git|github|api|rest|backend|frontend|fullstack|desarrollador)\b',
     [
        "Python es uno de los lenguajes más versátiles. Yo mismo estoy escrito en Python.",
        "El Zen de Python: 'Simple es mejor que complejo.' Esa es la filosofía del lenguaje.",
        "Un buen código se lee como un buen libro. La claridad importa.",
        "Los comentarios no arreglan código malo. Escribe código que se explique solo.",
        "Git es la herramienta esencial para control de versiones. Github es la red social de los programadores.",
        "Las APIs permiten que sistemas diferentes se comuniquen. Son los ladrillos de internet.",
        "Las pruebas (testing) ahorran horas de debugging. Nunca las saltes.",
        "Aprender varios lenguajes te da perspectiva. Cada uno tiene fortalezas distintas.",
        "El debugging es el arte de encontrar errores. Todos pasamos horas buscando un punto y coma.",
        "Hay dos tipos de código: el que funciona y el que nadie toca por miedo a romperlo.",
     ]),

]


# Instancia global de búsqueda y memoria para catch-all inteligente
_buscador = BuscadorWeb()
_memoria = Memoria()

# ==========================================================================
# 39. RESPUESTA GENÉRICA / NO ENTIENDE (con búsqueda silenciosa)
# ==========================================================================
_INTENTS_CATCHALL = [
    (r'.*', [
        "No estoy seguro de cómo responder a eso. ¿Puedes ser más específico?",
        "Interesante. No tengo una respuesta preparada para eso.",
        "Eso me da qué pensar. Aunque no tengo pensamientos.",
        "Buena pregunta. No tengo datos suficientes para responder bien.",
        "No sé qué decir. ¿Quieres preguntarme otra cosa?",
        "Quizás no entendí bien. ¿Puedes reformularlo?",
        "Esa no me la sé. ¿Intentamos con otro tema?",
        "No tengo una respuesta para eso. Pero dime algo más.",
        "Mi base de conocimiento no cubre eso. ¿Qué más te interesa?",
        "Hmm. No estoy seguro. ¿Qué opinas tú?",
     ]),
]



class ConversacionModule:
    def __init__(self, config, api_keys):
        self.config = config
        self.api_keys = api_keys
        self._buscador = BuscadorWeb()
        self._memoria = Memoria()

    def execute(self, cmd: str) -> str:
        cmd_lower = cmd.lower().strip()
        hora = datetime.now().hour
        for patron, respuestas in _INTENTS:
            if re.search(patron, cmd_lower):
                if "hola" in patron or "buenas" in patron or "saludos" in patron:
                    if hora < 6:
                        return f"  Buenas madrugadas. {random.choice(respuestas)}"
                    elif hora < 12:
                        return f"  Buenos días. {random.choice(respuestas)}"
                    elif hora < 20:
                        return f"  Buenas tardes. {random.choice(respuestas)}"
                    else:
                        return f"  Buenas noches. {random.choice(respuestas)}"
                return f"  {random.choice(respuestas)}"

        # Catch-all con memoria y búsqueda silenciosa
        mem = self._memoria.recordar_formateado(cmd)
        if mem:
            return f"  Recuerdo: {mem}"

        web = self._buscador.buscar(cmd)
        if web["exito"]:
            resultado = web["resultado"].strip().rstrip("| ")
            self._memoria.aprender(cmd, resultado)
            return f"  {resultado}"

        respuestas = _INTENTS_CATCHALL[0][1]
        return f"  {random.choice(respuestas)}"
