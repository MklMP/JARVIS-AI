"""
Plugin de ejemplo para Jarvis.
Copia este archivo a plugins/mi_plugin.py para tenerlo disponible.

Para crear tu propio plugin:
1. Crea un archivo .py en la carpeta plugins/
2. Define una función register() que devuelva un objeto con execute()
"""

from modules.base import ModuleBase


class MiPlugin(ModuleBase):
    """Plugin de ejemplo."""

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()
        if "hola" in cmd or "hello" in cmd or "buenas" in cmd:
            return "  Hola! Soy un plugin de Jarvis. Encantado de conocerte!"
        if "chiste" in cmd or "joke" in cmd or "risa" in cmd:
            return (
                "  Por qué los programadores prefieren el modo oscuro?\n"
                "  Porque la luz atrae a los bugs!"
            )
        return (
            "  Plugin de ejemplo. Comandos:\n"
            "  hola  - Saludo\n"
            "  chiste - Un chiste"
        )

    def help(self) -> str:
        return "Plugin de ejemplo: hola, chiste"


def register():
    """Registra el plugin - Jarvis llama a esta función."""
    return MiPlugin({"language": "es"}, {})
