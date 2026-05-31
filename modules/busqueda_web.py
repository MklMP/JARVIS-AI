import requests
import re
from urllib.parse import quote
from deep_translator import GoogleTranslator

DUCKDUCKGO_API = "https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
GOOGLE_SEARCH = "https://www.google.com/search?q={q}&hl=es"
WIKIPEDIA_API = "https://es.wikipedia.org/w/api.php?action=query&format=json&prop=extracts&exintro=1&explaintext=1&exsentences=6&titles={q}"
WIKIPEDIA_SEARCH = "https://es.wikipedia.org/w/api.php?action=query&format=json&list=search&srlimit=5&srsearch={q}"


class BuscadorWeb:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        })
        self._ddgs = None

    def _get_ddgs(self):
        if self._ddgs is None:
            from ddgs import DDGS
            self._ddgs = DDGS()
        return self._ddgs

    def _extraer_tema(self, query: str) -> str:
        """Extrae el tema principal de una pregunta para búsqueda en Wikipedia."""
        q = query.lower().strip()
        q = re.sub(r'[¿?¡!]', '', q)
        patrones = [
            r'^(en\s+)?qu[eé]\s+(es|son|fue|era|significa)\s+(.+)',
            r'^qui[eé]n\s+(es|fue|era)\s+(.+)',
            r'^(en\s+)?qu[eé]\s+añ?o\s+(naci[oó]|cre[oó]|invent[oó]|fund[oó])\s+(.+)',
            r'^cu[aá]ndo\s+(naci[oó]|cre[oó]|invent[oó]|fund[oó]|se\s+cre[oó]|se\s+invent[oó]|se\s+fund[oó])\s+(.+)',
            r'^d[oó]nde\s+(naci[oó]|queda|est[aá]|vive)\s+(.+)',
            r'^cu[aá]nt[oa]\s+(mide|pesa|vale|cuesta|tiene|cuesta)\s+(.+)',
            r'^c[oó]mo\s+se\s+(llama|llamaba|dice)\s+(.+)',
            r'^dime\s+(todo\s+)?(sobre|de|acerca\s+de)\s+(.+)',
            r'^expl[ií]ca\s+(qu[eé]\s+es\s+)?(.+)',
            r'^sabes\s+(de|sobre|acerca\s+de)\s+(.+)',
        ]
        for p in patrones:
            m = re.match(p, q)
            if m:
                return m.group(m.lastindex)
        return q

    def _traducir_a_espanol(self, texto: str) -> str:
        try:
            return GoogleTranslator(source="auto", target="es").translate(texto[:5000])
        except Exception:
            return texto

    def buscar_wikipedia(self, query: str, max_sentences: int = 6) -> dict:
        """Busca en Wikipedia en español."""
        try:
            tema = self._extraer_tema(query)
            url = f"https://es.wikipedia.org/w/api.php?action=query&format=json&prop=extracts&exintro=1&explaintext=1&exsentences={max_sentences}&titles={quote(tema)}"
            r = self._session.get(url, timeout=8)
            if r.status_code == 200:
                pages = r.json().get("query", {}).get("pages", {})
                for page_id, page in pages.items():
                    if page_id != "-1" and page.get("extract"):
                        extract = page["extract"].strip()
                        if extract:
                            return {"exito": True, "resultado": extract, "fuente": "Wikipedia"}
            # Si no encuentra, buscar el título primero
            search_url = f"https://es.wikipedia.org/w/api.php?action=query&format=json&list=search&srlimit=3&srsearch={quote(tema)}"
            r2 = self._session.get(search_url, timeout=8)
            if r2.status_code == 200:
                resultados = r2.json().get("query", {}).get("search", [])
                for sr in resultados[:3]:
                    title = sr.get("title", "")
                    if title:
                        url2 = f"https://es.wikipedia.org/w/api.php?action=query&format=json&prop=extracts&exintro=1&explaintext=1&exsentences={max_sentences}&titles={quote(title)}"
                        r3 = self._session.get(url2, timeout=8)
                        if r3.status_code == 200:
                            pages2 = r3.json().get("query", {}).get("pages", {})
                            for pid2, p2 in pages2.items():
                                if pid2 != "-1" and p2.get("extract"):
                                    return {"exito": True, "resultado": p2["extract"].strip(), "fuente": "Wikipedia"}
        except Exception:
            pass
        return {"exito": False, "resultado": ""}

    def buscar_multifuente(self, query: str) -> dict:
        """Busca en DDG + Wikipedia simultáneamente y combina resultados."""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            ddg_fut = pool.submit(self._buscar_ddgs, query, 3)
            wiki_fut = pool.submit(self.buscar_wikipedia, query, 4)
            ddg_result = ddg_fut.result(timeout=12)
            wiki_result = wiki_fut.result(timeout=12)
        partes = []
        fuentes = []
        if wiki_result["exito"]:
            partes.append(f"▸ {wiki_result['resultado'][:600]}")
            fuentes.append("Wikipedia")
        if ddg_result["exito"]:
            snippet = ddg_result["resultado"][:500]
            snippet = self._traducir_a_espanol(snippet)
            partes.append(f"▸ {snippet}")
            fuentes.append("DuckDuckGo")
        if partes:
            return {"exito": True, "resultado": "\n".join(partes), "fuente": "+".join(fuentes)}
        return {"exito": False, "resultado": ""}

    def _buscar_sitio(self, query: str, sitio: str, max_snippets: int = 3) -> dict:
        """Busca en DuckDuckGo con scope a un sitio específico (site:sitio query)."""
        return self._buscar_ddgs(f"site:{sitio} {query}", max_snippets)

    def buscar_con_motores(self, query: str, motores: list = None) -> dict:
        """Busca solo en los motores seleccionados por el usuario."""
        if not motores:
            motores = ["duckduckgo"]
        import concurrent.futures
        futuros = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for m in motores:
                if m == "duckduckgo":
                    futuros["duckduckgo"] = pool.submit(self._buscar_ddgs, query, 3)
                elif m == "wikipedia":
                    futuros["wikipedia"] = pool.submit(self.buscar_wikipedia, query, 5)
                elif m == "openrouter":
                    pass
                elif m == "yahoofinance":
                    futuros["yahoofinance"] = pool.submit(self._buscar_sitio, query, "finance.yahoo.com")
                elif m == "bloomberg":
                    futuros["bloomberg"] = pool.submit(self._buscar_sitio, query, "bloomberg.com")
                elif m == "investing":
                    futuros["investing"] = pool.submit(self._buscar_sitio, query, "investing.com")
                elif m == "youtube":
                    futuros["youtube"] = pool.submit(self._buscar_sitio, query, "youtube.com")
                elif m == "reddit":
                    futuros["reddit"] = pool.submit(self._buscar_sitio, query, "reddit.com")
                elif m == "xataka":
                    futuros["xataka"] = pool.submit(self._buscar_sitio, query, "xataka.com")
                elif m == "stackoverflow":
                    futuros["stackoverflow"] = pool.submit(self._buscar_sitio, query, "stackoverflow.com")
            partes = []
            fuentes = []
            todos_enlaces = []
            for nombre, fut in futuros.items():
                try:
                    res = fut.result(timeout=12)
                    if res["exito"]:
                        if nombre == "wikipedia":
                            partes.append(f"▸ {res['resultado'][:600]}")
                        else:
                            texto = res["resultado"][:500]
                            texto = self._traducir_a_espanol(texto)
                            partes.append(f"▸ {texto}")
                        fuentes.append(nombre)
                        if res.get("enlaces"):
                            todos_enlaces.extend(res["enlaces"])
                except Exception:
                    pass
        if partes:
            fuente_str = "+".join(sorted(set(fuentes)))
            enlaces_unicos = list(dict.fromkeys(todos_enlaces))[:3]
            return {"exito": True, "resultado": "\n".join(partes), "fuente": fuente_str, "enlaces": enlaces_unicos}
        return {"exito": False, "resultado": ""}

    FINANCE_KEYWORDS = ["bolsa", "accion", "acciones", "precio", "cotizacion", "cotización",
                         "mercado", "inversion", "inversión", "dividendo", "etf", "fondo",
                         "indice", "índice", "ibex", "s&p", "nasdaq", "dow jones",
                         "wall street", "cripto", "bitcoin", "ethereum", "blockchain",
                          "trading", "forex", "commodities", "futuros", "opciones"]

    CONCEPT_KEYWORDS = [
        "que es", "quien es", "qué es", "quién es", "quien fue", "quién fue",
        "que significa", "qué significa", "concepto", "definicion", "definición",
        "biografia", "biografía", "historia de", "historia del",
    ]

    YOUTUBE_KEYWORDS = [
        "video", "vídeo", "youtube", "mira este", "mira esto",
        "documental", "tutorial", "como hacer", "cómo hacer",
        "review", "reseña", "gameplay", "clip", "trailer",
        "canción", "cancion", "musica", "música", "escucha",
        "ver ", "veamos", "mira ", "muéstrame", "muestrame",
        "reproducir", "pon ", "ponme", "pasame", "pásame",
    ]

    REDDIT_KEYWORDS = [
        "opinion", "opinión", "recomienda", "recomendación", "recomendacion",
        "experiencia", "alternativa", "mejor", "peor", "vale la pena",
        "foro", "comunidad", "reddit", "que tal", "qué tal",
        "instalar", "configurar", "error", "problema", "solucion", "solución",
        "app", "aplicacion", "aplicación", "programa", "software",
        "windows", "linux", "android", "iphone", "ios",
    ]

    MATH_KEYWORDS = [
        "matematica", "matematicas", "matemática", "matemáticas",
        "calculo", "cálculo", "ecuacion", "ecuación", "derivada", "integral",
        "logaritmo", "seno", "coseno", "tangente", "trigonometria", "trigonometría",
        "algebra", "álgebra", "resolver", "solucion", "solución",
        "raiz", "raíz", "potencia", "elevado", "sqrt",
    ]

    TUTORIAL_KEYWORDS = [
        "como hacer", "cómo hacer", "como instalar", "cómo instalar",
        "como usar", "cómo usar", "como crear", "cómo crear",
        "pasos para", "tutorial", "guia", "guía", "manual",
    ]

    def _es_financiera(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self.FINANCE_KEYWORDS)

    def _es_concepto(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self.CONCEPT_KEYWORDS)

    def _es_youtube(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self.YOUTUBE_KEYWORDS)

    def _es_reddit(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self.REDDIT_KEYWORDS)

    def _es_matematicas(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self.MATH_KEYWORDS)

    def _es_tutorial(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self.TUTORIAL_KEYWORDS)

    def buscar_con_finanzas(self, query: str) -> dict:
        """Busca en motores financieros automáticamente si la query es financiera."""
        motores = ["yahoofinance", "bloomberg", "investing"]
        return self.buscar_con_motores(query, motores)

    def buscar(self, query: str, max_snippets: int = 3) -> dict:
        queries = self._generar_variantes(query)

        for q in queries:
            resultado = self._buscar_ddgs(q, max_snippets)
            if resultado["exito"]:
                resultado["resultado"] = self._traducir_a_espanol(resultado["resultado"])
                return resultado

            resultado = self._buscar_duckduckgo_api(q)
            if resultado["exito"]:
                resultado["resultado"] = self._traducir_a_espanol(resultado["resultado"])
                return resultado

        resultado = self._buscar_google(query, max_snippets)
        if resultado["exito"]:
            resultado["resultado"] = self._traducir_a_espanol(resultado["resultado"])
            return resultado

        return {"exito": False, "resultado": ""}

    def _generar_variantes(self, query: str) -> list:
        variantes = [query]
        q = query.lower().strip()
        q_clean = re.sub(r'[¿?¡!]', '', q).strip()
        if q_clean != q:
            variantes.append(q_clean)

        # For "que año" questions: "en que año nacio shakira" → keep verb + subject together
        m = re.match(r'^(en\s+)?que\s+añ?o\s+(.+)$', q_clean)
        if m:
            resto = m.group(2).strip()
            # Add full remainder (e.g., "nacio shakira")
            if resto and len(resto) > 3:
                variantes.append(resto)
            # Also add a well-formed query variant
            variantes.append(q_clean.replace('en que año', '').replace('que año', '').strip())
            return variantes

        prefijos = [
            r'^(en\s+)?que\s+(es|son|fue|era)\s+',
            r'^quien\s+(es|fue|era|creo|invento)\s+',
            r'^cuando\s+(fue|se|nacio|creo|invento)\s+',
            r'^como\s+(se\s+)?(llama|llamaba|dice)\s+',
            r'^donde\s+(esta|queda|nacio|vive)\s+',
            r'^cuanto\s+(mide|pesa|vale|cuesta|tiene)\s+',
            r'^dime\s+', r'^cuentame\s+(sobre|de)\s+',
            r'^explica\s+(que\s+es\s+)?',
            r'^sabes\s+(de|sobre|acerca\s+de)\s+',
        ]
        for patron in prefijos:
            m = re.search(patron, q_clean)
            if m:
                resto = q_clean[m.end():].strip()
                if resto and len(resto) > 5:
                    variantes.append(resto)
                    break

        return variantes

    def _buscar_ddgs(self, query: str, max_snippets: int) -> dict:
        try:
            ddgs = self._get_ddgs()
            results = list(ddgs.text(query, max_results=max_snippets))
            if results:
                textos = []
                enlaces = []
                for r in results[:max_snippets]:
                    body = r.get("body", "")
                    title = r.get("title", "")
                    link = r.get("link", r.get("url", ""))
                    if body:
                        textos.append(body[:400])
                    elif title:
                        textos.append(title[:400])
                    if link and link.startswith("http"):
                        enlaces.append(link)
                if textos:
                    texto = " | ".join(textos)
                    texto = re.sub(r'\s+', ' ', texto).strip()
                    return {"exito": True, "resultado": texto, "fuente": "DuckDuckGo", "enlaces": enlaces[:3]}
        except Exception:
            pass
        return {"exito": False, "resultado": ""}

    def _buscar_duckduckgo_api(self, query: str) -> dict:
        try:
            r = self._session.get(DUCKDUCKGO_API.format(q=quote(query)), timeout=8)
            if r.status_code in (200, 202):
                data = r.json()
                abstract = data.get("AbstractText", "")
                if abstract:
                    return {"exito": True, "resultado": abstract, "fuente": data.get("Source", "DuckDuckGo")}
                answer = data.get("Answer", "")
                if answer:
                    return {"exito": True, "resultado": answer, "fuente": ""}
                definition = data.get("Definition", "")
                if definition:
                    return {"exito": True, "resultado": definition, "fuente": ""}
                topics = data.get("RelatedTopics", [])
                textos = []
                for t in topics[:3]:
                    if isinstance(t, dict) and "Text" in t:
                        textos.append(t["Text"])
                    elif isinstance(t, dict) and "Topics" in t:
                        for st in t["Topics"][:2]:
                            if "Text" in st:
                                textos.append(st["Text"])
                if textos:
                    return {"exito": True, "resultado": " | ".join(textos), "fuente": "DuckDuckGo"}
        except Exception:
            pass
        return {"exito": False, "resultado": ""}

    def _buscar_google(self, query: str, max_snippets: int) -> dict:
        captcha_indicators = ["haz clic", "captcha", "no se te redirecciona", "unusual traffic",
                              "no eres un robot", "automated queries", "please show you're not a robot"]
        try:
            r = self._session.get(GOOGLE_SEARCH.format(q=quote(query)), timeout=10)
            page_text = r.text.lower()
            if any(c in page_text for c in captcha_indicators):
                return {"exito": False, "resultado": "", "error": "CAPTCHA"}
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            snippets = []
            selectores = [
                "div.VwiC3b", "span.aCOpRe", "span.st",
                "div[data-sncf]", "div.lEBKkf", "div.y93wG",
                "div[style*='-webkit-line-clamp']", "div.kno-rdesc span", "div.IZ6rdc",
            ]
            for sel in selectores:
                for el in soup.select(sel):
                    t = el.get_text(strip=True)
                    if t and len(t) > 30 and len(t) < 800:
                        snippets.append(t)
                        if len(snippets) >= max_snippets:
                            break
                if len(snippets) >= max_snippets:
                    break
            if snippets:
                texto = " | ".join(snippets)
                texto = re.sub(r'\s+', ' ', texto).strip()
                return {"exito": True, "resultado": texto, "fuente": "Google"}
        except Exception:
            pass
        return {"exito": False, "resultado": ""}
