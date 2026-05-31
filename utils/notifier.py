import threading
import subprocess
import os

_VENTANA_ACTIVA = True


def marcar_ventana(activa: bool):
    global _VENTANA_ACTIVA
    _VENTANA_ACTIVA = activa


def _mostrar_toast(titulo: str, mensaje: str):
    try:
        from plyer import notification
        notification.notify(title=titulo, message=mensaje, app_name="Jarvis", timeout=8)
        return
    except Exception:
        pass
    ps = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($template.CreateTextNode("{titulo}")) > $null
    $textNodes.Item(1).AppendChild($template.CreateTextNode("{mensaje}")) > $null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Jarvis").Show($toast)
    '''
    try:
        subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=5)
    except Exception:
        try:
            subprocess.run(["msg", "*", f"{titulo}: {mensaje}"], capture_output=True, timeout=3)
        except Exception:
            pass


def notificar(titulo: str, mensaje: str, solo_si_ausente: bool = False):
    if solo_si_ausente and _VENTANA_ACTIVA:
        return
    threading.Thread(target=_mostrar_toast, args=(titulo, mensaje), daemon=True).start()
