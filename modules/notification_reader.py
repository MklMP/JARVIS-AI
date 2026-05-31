"""
Módulo de notificaciones del sistema - leer y enviar notificaciones.
"""

import os
import subprocess
import time
from .base import ModuleBase
from utils.emoji import ADVERTENCIA, COMPUTADORA


class NotificationsModule(ModuleBase):
    """Notificaciones del sistema Windows."""

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self._ultimas_notificaciones = []
        self._toast_disponible = self._verificar_toast()

    def _verificar_toast(self) -> bool:
        try:
            import winrt.windows.ui.notifications as notifications
            return True
        except ImportError:
            try:
                from plyer import notification
                return True
            except ImportError:
                return False

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["notificaciones", "notification", "alertas",
                                   "toast", "notif"]):
            if any(p in cmd for p in ["enviar", "send", "crear", "mostrar", "nueva"]):
                return self._enviar_notificacion(command)
            return self._leer_notificaciones()
        elif any(p in cmd for p in ["avísame", "avisame", "notifícame", "notificame",
                                     "cuando", "alerta"]):
            return self._ayuda_automatizacion()
        else:
            return self.help()

    def _enviar_notificacion(self, command: str) -> str:
        import re

        # Extraer título y mensaje
        match_title = re.search(r'(?:titulo|título|title):?\s*"([^"]+)"', command, re.IGNORECASE)
        match_msg = re.search(r'(?:mensaje|msg|message|dice|diciendo):?\s*"([^"]+)"', command, re.IGNORECASE)

        titulo = match_title.group(1) if match_title else "Jarvis"
        mensaje = match_msg.group(1) if match_msg else "Notificación desde Jarvis"

        if not match_title and not match_msg:
            # Tomar todo después de "enviar notificación"
            parts = command.split()
            idx = -1
            for i, p in enumerate(parts):
                if p.lower() in ("notificacion", "notificación", "notif"):
                    idx = i
                    break
            if idx >= 0 and idx + 1 < len(parts):
                resto = " ".join(parts[idx+1:])
                if '"' in resto:
                    quotes = re.findall(r'"([^"]+)"', resto)
                    if len(quotes) >= 1:
                        titulo = "Jarvis"
                        mensaje = quotes[0]
                    if len(quotes) >= 2:
                        titulo = quotes[0]
                        mensaje = quotes[1]
                else:
                    mensaje = resto

        self._mostrar_toast(titulo, mensaje)
        return f"  {COMPUTADORA}  Notificación enviada:\n     [{titulo}] {mensaje}"

    def _mostrar_toast(self, titulo: str, mensaje: str):
        try:
            from plyer import notification
            notification.notify(
                title=titulo,
                message=mensaje,
                app_name="Jarvis",
                timeout=8
            )
        except Exception:
            # Fallback: PowerShell balloon notification
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $textNodes = $template.GetElementsByTagName("text")
            $textNodes.Item(0).AppendChild($template.CreateTextNode("{titulo}")) > $null
            $textNodes.Item(1).AppendChild($template.CreateTextNode("{mensaje}")) > $null
            $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Jarvis").Show($toast)
            '''
            try:
                subprocess.run(["powershell", "-Command", ps_script],
                              capture_output=True, timeout=5)
            except:
                # Último fallback: msg.exe
                try:
                    subprocess.run(["msg", "*", f"{titulo}: {mensaje}"],
                                  capture_output=True, timeout=3)
                except:
                    pass

    def _leer_notificaciones(self) -> str:
        # Windows no expone fácilmente el historial de notificaciones
        return (
            f"  {COMPUTADORA}  NOTIFICACIONES DEL SISTEMA\n\n"
            "  Windows no permite leer notificaciones pasadas\n"
            "  de forma programática.\n\n"
            "  Pero puedo ENVIAR notificaciones:\n"
            '    enviar notificación "Mensaje"\n'
            '    enviar notificación titulo:"Jarvis" mensaje:"Hola"\n\n'
            "  También puedo avisarte de recordatorios,\n"
            "  clima y otros eventos automáticamente."
        )

    def _ayuda_automatizacion(self) -> str:
        return (
            "  AUTOMATIZACIÓN DE NOTIFICACIONES:\n\n"
            "  Jarvis puede enviarte notificaciones cuando:\n"
            "  • Un recordatorio está por vencer\n"
            "  • El clima cambia drásticamente\n"
            "  • Recibes un correo importante\n"
            "  • A una hora específica\n\n"
            "  Próximamente: reglas personalizadas.\n"
            "  Por ahora, usa: enviar notificación <mensaje>"
        )

    def help(self) -> str:
        return (
            "NOTIFICACIONES:\n"
            '  enviar notificación "mensaje"\n'
            '  enviar notificación titulo:"X" mensaje:"Y"\n\n'
            "  Ej: enviar notificación La pizza está lista\n"
            '      enviar notificación titulo:"Jarvis" mensaje:"Hora de la reunión"\n\n'
            "  NOTA: Muestra notificaciones nativas de Windows 10/11."
        )
