"""
MÃ³dulo de WhatsApp - enviar mensajes vÃ­a web.
Usa pywhatkit o selenium si estÃ¡n disponibles, o da instrucciones.
"""

import os
import re
from .base import ModuleBase
from utils.emoji import SI


class WhatsAppModule(ModuleBase):
    """WhatsApp - enviar mensajes."""

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self._pywhatkit = None
        self._inicializar()

    def _inicializar(self):
        try:
            import pywhatkit
            self._pywhatkit = pywhatkit
        except ImportError:
            self._pywhatkit = None

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["whatsapp", "wa", "whats", "mensaje whats"]):
            if self._pywhatkit:
                return self._enviar_whatsapp(command)
            return self._ayuda_pywhatkit()
        elif any(p in cmd for p in ["instalar whatsapp", "instalar wa"]):
            return self._ayuda_pywhatkit()
        else:
            return self.help()

    def _enviar_whatsapp(self, command: str) -> str:
        # Extraer nÃºmero
        match_num = re.search(r'(\+?\d{7,15})', command)
        if not match_num:
            return ("  ⚠️ Â¿A quÃ© nÃºmero? Ej: whatsapp +521234567890 hola\n"
                    "  Incluye cÃ³digo de paÃ­s sin espacios.")

        numero = match_num.group(1)

        # Extraer mensaje
        match_msg = re.search(r'(?:decir|mensaje|dile|que diga):?\s*"([^"]+)"', command, re.IGNORECASE)
        if not match_msg:
            # Tomar todo despuÃ©s del nÃºmero
            idx = command.find(numero)
            msg = command[idx + len(numero):].strip()
            if msg:
                match_msg = type('obj', (object,), {'group': lambda s, g: msg})()
            else:
                return "  ⚠️ Â¿QuÃ© mensaje quieres enviar?"

        mensaje = match_msg.group(1) if hasattr(match_msg, 'group') else match_msg

        hora = kwargs.get("hora", None)
        minuto = kwargs.get("minuto", None)

        try:
            self._pywhatkit.sendwhatmsg_instantly(
                numero, mensaje,
                wait_time=15,
                tab_close=True
            )
            return f"  {SI}  Mensaje enviado a {numero}: \"{mensaje}\""
        except Exception as e:
            return f"  ⚠️ Error enviando WhatsApp: {e}"

    def _ayuda_pywhatkit(self) -> str:
        return (
            "  ⚠️ WhatsApp requiere la librerÃ­a 'pywhatkit'.\n\n"
            "  Para instalarla:\n"
            "    pip install pywhatkit\n\n"
            "  TambiÃ©n necesitas:\n"
            "    1. Tener WhatsApp Web abierto en Chrome/Edge\n"
            "    2. Escanear el cÃ³digo QR\n"
            "    3. Mantener sesiÃ³n iniciada\n\n"
            "  Una vez instalado:\n"
            "    whatsapp +521234567890 hola\n"
            "    whatsapp +521234567890 decir:\"Mensaje entre comillas\""
        )

    def help(self) -> str:
        return (
            "WHATSAPP:\n"
            "  whatsapp +<numero> <mensaje>\n\n"
            "  Ej: whatsapp +521234567890 lleguÃ© bien\n"
            '      whatsapp +521234567890 decir:"Nos vemos maÃ±ana"\n\n'
            "  NOTA: Requiere 'pip install pywhatkit'\n"
            "  y tener WhatsApp Web abierto en el navegador."
        )

