import re
import math
import traceback


class MathModule:
    """Resuelve expresiones matemáticas."""

    def __init__(self, config=None, api_keys=None):
        self._ne = None

    def _get_ne(self):
        if self._ne is None:
            import numexpr
            self._ne = numexpr
        return self._ne

    def execute(self, cmd: str) -> str:
        cmd = cmd.strip().lower()

        # Pregunta sobre capacidad
        if re.search(r'\b(puedes\s*resolver|sabes\s*.*matem[aá]ticas|eres\s*bueno\s*.*matem[aá]ticas|qu[eé]\s*matem[aá]ticas\s*sabes)\b', cmd):
            return (
                "  Puedo resolver operaciones matemáticas como:\n"
                "  • Aritmética básica: suma, resta, multiplicación, división\n"
                "  • Potencias y raíces: x^y, sqrt(x)\n"
                "  • Trigonometría: sin, cos, tan\n"
                "  • Logaritmos: log, ln\n"
                "  • Expresiones complejas con paréntesis\n\n"
                "  Solo dime 'cuánto es 2+2' o escribe la expresión directamente."
            )

        # Detectar expresión matemática
        expr = self._extraer_expresion(cmd)
        if not expr:
            return ""

        try:
            resultado = self._evaluar(expr)
            if resultado is not None:
                pasos = self._generar_pasos(expr, resultado)
                if pasos:
                    return f"  {pasos}"
                return f"  {expr} = {self._formatear(resultado)}"
        except Exception as e:
            return f"  No pude resolver '{expr}'. Error: {str(e)}"

        return ""

    def _extraer_expresion(self, cmd: str) -> str:
        """Extrae una expresión matemática del texto."""
        # Patrones tipo "cuanto es X", "calcula X", "resuelve X"
        m = re.search(r'\b(cu[aá]nto\s+(es|da|vale|ser[aí]a)|calcula|resuelve|halla|determina|encuentra|obt[eé]n|dame\s*el\s*resultado\s*de)\s+(.+)', cmd)
        if m:
            expr = m.group(m.lastindex).strip()
            return self._limpiar_expr(expr)

        # Patrones tipo "raiz cuadrada de X", "sqrt de X", "logaritmo de X"
        m = re.search(r'\b(ra[ií]z\s+cuadrada\s+de|ra[ií]z\s+de|sqrt\s+de|logaritmo\s+natural\s+de|log\s+natural\s+de|seno\s+de|coseno\s+de|tangente\s+de|ln\s+de|log\s+de|valor\s+absoluto\s+de)\s+(.+)', cmd)
        if m:
            func = m.group(1).strip().lower()
            arg = m.group(2).strip()
            mapa = {
                'raiz cuadrada de': 'sqrt', 'raiz de': 'sqrt', 'sqrt de': 'sqrt',
                'logaritmo natural de': 'log', 'log natural de': 'ln', 'ln de': 'log',
                'seno de': 'sin', 'coseno de': 'cos', 'tangente de': 'tan',
                'log de': 'log10', 'valor absoluto de': 'abs',
            }
            op = mapa.get(func, func)
            arg = self._limpiar_expr(arg)
            return f"{op}({arg})"

        # Potencias: "X elevado a la Y", "X a la Y", "X^Y"
        m = re.search(r'(.+?)\s+elevado\s+(a\s+la|al)\s+(.+)$', cmd)
        if m:
            base = self._limpiar_expr(m.group(1).strip())
            exp = self._limpiar_expr(m.group(3).strip())
            return f"{base}**{exp}"

        # Si el comando completo parece una expresión (solo números, operadores, funciones)
        limpio = self._limpiar_expr(cmd)
        if self._es_expresion(limpio):
            return limpio

        return ""

    def _limpiar_expr(self, s: str) -> str:
        """Limpia y normaliza una expresión."""
        s = s.strip().rstrip(",.!?¿¡")
        # Reemplazar palabras comunes
        s = s.replace('pi', str(math.pi)).replace('π', str(math.pi))
        s = s.replace('euler', str(math.e))
        # Reemplazar operadores literales
        s = s.replace('×', '*').replace('x', '*').replace('·', '*').replace('.', '.')
        s = s.replace('÷', '/').replace(':', '/')
        s = s.replace('^', '**').replace('elevado a', '**')
        # Quitar espacios
        s = re.sub(r'\s+', '', s)
        return s

    def _es_expresion(self, s: str) -> bool:
        """Determina si un texto parece una expresión matemática."""
        if not s or len(s) < 2:
            return False
        # Debe tener al menos un número y un operador, o funciones
        tiene_numero = bool(re.search(r'\d', s))
        tiene_operador = bool(re.search(r'[\+\-\*/\(\)\^]', s))
        tiene_funcion = bool(re.search(r'(sin|cos|tan|log|sqrt|abs)\s*\(', s))
        solo_chars = bool(re.match(r'^[\d\+\-\*\./\(\)\^\s,a-zπ]+$', s))
        return (tiene_numero or tiene_funcion) and (tiene_operador or tiene_funcion) and solo_chars

    def _evaluar(self, expr: str) -> float:
        """Evalúa una expresión matemática de forma segura."""
        ne = self._get_ne()
        return float(ne.evaluate(expr))

    def _formatear(self, n: float) -> str:
        """Formatea un número para mostrar."""
        if n == int(n):
            return str(int(n))
        return f"{n:,.6f}".rstrip('0').rstrip('.')

    def _generar_pasos(self, expr: str, resultado: float) -> str:
        """Genera pasos para expresiones simples."""
        r = self._formatear(resultado)
        # Detectar operación simple
        if '+' in expr and expr.count('+') == 1 and '**' not in expr:
            a, b = expr.split('+')
            return f"{expr} = {r}"
        if expr.count('*') == 1 and '**' not in expr:
            a, b = expr.split('*')
            if b.replace('.', '').isdigit() and a.replace('.', '').lstrip('-').isdigit():
                return f"{expr} = {r}"
        return f"{expr} = {r}"
