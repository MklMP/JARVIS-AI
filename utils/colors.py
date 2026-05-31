"""Colores ANSI y gradientes animados para la terminal."""

import os
import sys
import math

_soporta_color = os.name != "nt" or bool(os.environ.get("TERM_PROGRAM")) or "WT_SESSION" in os.environ

_shift = 0


def _ansi_256(code: int) -> str:
    return f"\033[38;5;{code}m" if _soporta_color else ""


def _rgb_aprox(r: int, g: int, b: int) -> int:
    """Aproxima RGB (0-255) al color ANSI 256 más cercano."""
    if r == g == b:
        gray = int(r / 255 * 23)
        return 232 + gray if gray < 24 else 231
    return 16 + (36 * (r // 51)) + (6 * (g // 51)) + (b // 51)


def hacer_gradiente(texto: str, t: float = 0.0) -> str:
    """Aplica un gradiente de colores al texto, desplazado por t (0-1).
    t se incrementa cada vez que se dibuja el banner.
    """
    if not _soporta_color or not texto:
        return texto
    RESET = "\033[0m"
    largo = len(texto)
    if largo == 0:
        return texto
    resultado = []
    for i, c in enumerate(texto):
        fase = (i / max(largo - 1, 1) + t) % 1.0
        r = int(100 + 155 * (0.5 + 0.5 * math.sin(fase * 6.283 - 0)))
        g = int(50 + 80 * (0.5 + 0.5 * math.sin(fase * 6.283 - 2.094)))
        b = int(200 + 55 * (0.5 + 0.5 * math.sin(fase * 6.283 - 4.188)))
        code = _rgb_aprox(r, g, b)
        resultado.append(f"{_ansi_256(code)}{c}")
    return "".join(resultado) + RESET


def incrementar_tiempo(delta: float = 0.05):
    global _shift
    _shift = (_shift + delta) % 1.0


def obtener_tiempo() -> float:
    return _shift


def logo_colorido(texto: str) -> str:
    """Envuelve el texto del logo con gradiente animado."""
    return hacer_gradiente(texto, obtener_tiempo())


_BANNER_ART = [
    "██████╗  █████╗ ██████╗ ██╗   ██╗██╗███████╗",
    "██╔════╝ ██╔══██╗██╔══██╗██║   ██║██║██╔════╝",
    "███████╗ ███████║██████╔╝██║   ██║██║███████╗",
    "╚════██║ ██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║",
    "███████║ ██║  ██║██║  ██║ ╚████╔╝ ██║███████║",
    "╚══════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝",
]

_SUBTITLE = "by Maykel Millán"


def banner_jarvis() -> str:
    """Devuelve el banner ASCII grande de JARVIS con gradiente animado.

    Muestra el arte ASCII en 6 líneas con colores degradados,
    seguido de 'by Maykel Millán' centrado debajo.
    """
    art_text = "\n".join(_BANNER_ART)
    gradient_art = hacer_gradiente(art_text, obtener_tiempo())
    ancho = max(len(l) for l in _BANNER_ART)
    subtitulo = _SUBTITLE.center(ancho)
    return f"{gradient_art}\n{subtitulo}"
