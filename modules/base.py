import importlib
import os
import sys


class ModuleBase:
    """Clase base para todos los mÃ³dulos de Jarvis."""

    def __init__(self, config: dict, api_keys: dict):
        self.config = config
        self.api_keys = api_keys
        self.name = self.__class__.__name__.lower()

    def execute(self, command: str, **kwargs) -> str:
        """Ejecuta el mÃ³dulo con un comando. Cada mÃ³dulo sobreescribe esto."""
        raise NotImplementedError("Cada mÃ³dulo debe implementar execute()")

    def help(self) -> str:
        """Devuelve texto de ayuda del mÃ³dulo."""
        return f"MÃ³dulo {self.name}: sin descripciÃ³n disponible."


class PluginManager:
    """Carga y gestiona plugins desde la carpeta plugins/."""

    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = plugins_dir
        self.plugins = {}

    def discover(self):
        if not os.path.isdir(self.plugins_dir):
            return
        sys.path.insert(0, os.path.dirname(self.plugins_dir))
        for f in os.listdir(self.plugins_dir):
            if f.endswith(".py") and not f.startswith("_"):
                mod_name = f[:-3]
                try:
                    mod = importlib.import_module(f"plugins.{mod_name}")
                    if hasattr(mod, "register"):
                        self.plugins[mod_name] = mod.register()
                except Exception as e:
                    print(f"  ⚠️ Error cargando plugin {mod_name}: {e}")

    def list_plugins(self) -> list:
        return list(self.plugins.keys())

    def execute(self, name: str, command: str, **kwargs) -> str:
        if name in self.plugins:
            return self.plugins[name].execute(command, **kwargs)
        return f"Plugin '{name}' no encontrado."

