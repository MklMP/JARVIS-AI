"""
MÃ³dulo de correo electrÃ³nico - leer y enviar emails (IMAP + SMTP).
"""

import os
import json
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from .base import ModuleBase
from utils.emoji import ARCHIVO


class EmailModule(ModuleBase):
    """Correo electrÃ³nico vÃ­a IMAP/SMTP."""

    CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "email_config.json")

    def __init__(self, config, api_keys):
        super().__init__(config, api_keys)
        self._cuentas = self._cargar_cuentas()
        self._cuenta_activa = 0

    def _cargar_cuentas(self) -> list:
        if not os.path.exists(self.CONFIG_PATH):
            return []
        try:
            with open(self.CONFIG_PATH, "r") as f:
                return json.load(f)
        except:
            return []

    def _guardar_cuentas(self):
        os.makedirs(os.path.dirname(self.CONFIG_PATH), exist_ok=True)
        with open(self.CONFIG_PATH, "w") as f:
            json.dump(self._cuentas, f, indent=2)

    def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if any(p in cmd for p in ["email", "correo", "mail", "bandeja", "inbox",
                                   "mensaje", "leer correo"]):
            if not self._cuentas:
                return self._ayuda_config()
            return self._leer_correos()
        elif any(p in cmd for p in ["enviar correo", "enviar email", "send email",
                                     "mandar correo", "enviar mail"]):
            if not self._cuentas:
                return self._ayuda_config()
            return self._enviar_correo(command)
        elif any(p in cmd for p in ["configurar correo", "configurar email",
                                     "aÃ±adir cuenta", "agregar cuenta"]):
            return self._configurar_cuenta(command)
        else:
            return self.help()

    def _ayuda_config(self) -> str:
        return (
            "  ⚠️ No hay cuentas de correo configuradas.\n\n"
            "  Para configurar, crea el archivo:\n"
            "  config/email_config.json\n\n"
            "  Con esta estructura:\n"
            '  [{\n'
            '    "email": "tu@email.com",\n'
            '    "password": "tu_contraseÃ±a_o_app_password",\n'
            '    "imap_server": "imap.gmail.com",\n'
            '    "imap_port": 993,\n'
            '    "smtp_server": "smtp.gmail.com",\n'
            '    "smtp_port": 587\n'
            '  }]\n\n'
            "  TambiÃ©n puedes decir: configurar correo\n"
            "  Para Gmail usa 'App Password' de 16 dÃ­gitos."
        )

    def _leer_correos(self, max_correos: int = 5) -> str:
        cuenta = self._cuentas[self._cuenta_activa]
        try:
            mail = imaplib.IMAP4_SSL(cuenta["imap_server"], cuenta["imap_port"])
            mail.login(cuenta["email"], cuenta["password"])
            mail.select("INBOX")

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                return "  ⚠️ Error al buscar correos."

            msg_ids = messages[0].split()
            if not msg_ids:
                # Leer Ãºltimos aunque estÃ©n leÃ­dos
                status, messages = mail.search(None, "ALL")
                msg_ids = messages[0].split()

            msg_ids = msg_ids[-max_correos:]
            msg_ids.reverse()

            salida = f"  {ARCHIVO}  BANDEJA DE ENTRADA ({cuenta['email']})\n"
            salida += "  ----------------------------------------\n"

            for mid in msg_ids:
                status, data = mail.fetch(mid, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(data[0][1])
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="replace")
                from_ = msg.get("From", "Desconocido")
                fecha = msg.get("Date", "")[:25]

                salida += f"  De: {from_}\n"
                salida += f"  Asunto: {subject}\n"
                salida += f"  [{fecha}]\n\n"

            mail.logout()
            return salida

        except imaplib.IMAP4.error as e:
            return f"  ⚠️ Error IMAP: {e}. Verifica tu contraseÃ±a o usa App Password."
        except Exception as e:
            return f"  ⚠️ Error leyendo correos: {e}"

    def _enviar_correo(self, command: str) -> str:
        import re

        # Extraer destinatario
        match_to = re.search(r'(?:a|para|to)\s+([\w.+-]+@[\w-]+\.[\w.]+)', command, re.IGNORECASE)
        if not match_to:
            return "  ⚠️ Â¿A quiÃ©n envÃ­o el correo? Ej: enviar correo a amigo@gmail.com"

        # Extraer asunto
        match_subj = re.search(r'(?:asunto|subject|sobre):?\s*"([^"]+)"', command, re.IGNORECASE)
        asunto = "Mensaje desde Jarvis"
        if match_subj:
            asunto = match_subj.group(1)

        # Extraer mensaje
        match_msg = re.search(r'(?:diciendo|mensaje|cuerpo|body|que diga):?\s*"([^"]+)"', command, re.IGNORECASE)
        mensaje = "Este mensaje fue enviado desde Jarvis."
        if match_msg:
            mensaje = match_msg.group(1)

        destino = match_to.group(1)
        cuenta = self._cuentas[self._cuenta_activa]

        try:
            msg = MIMEMultipart()
            msg["From"] = cuenta["email"]
            msg["To"] = destino
            msg["Subject"] = asunto
            msg.attach(MIMEText(mensaje, "plain", "utf-8"))

            server = smtplib.SMTP(cuenta["smtp_server"], cuenta["smtp_port"])
            server.starttls()
            server.login(cuenta["email"], cuenta["password"])
            server.send_message(msg)
            server.quit()

            return f"  Correo enviado a {destino} | Asunto: {asunto}"

        except smtplib.SMTPAuthenticationError:
            return "  ⚠️ Error de autenticaciÃ³n SMTP. Verifica tu contraseÃ±a."
        except Exception as e:
            return f"  ⚠️ Error enviando correo: {e}"

    def _configurar_cuenta(self, command: str) -> str:
        return (
            "  Para configurar el correo, crea el archivo:\n"
            "  config/email_config.json\n\n"
            '  Ejemplo para Gmail:\n'
            '  [{\n'
            '    "email": "tucuenta@gmail.com",\n'
            '    "password": "tu_app_password_16_caracteres",\n'
            '    "imap_server": "imap.gmail.com",\n'
            '    "imap_port": 993,\n'
            '    "smtp_server": "smtp.gmail.com",\n'
            '    "smtp_port": 587\n'
            '  }]\n\n'
            "  NOTA: Para Gmail necesitas crear una\n"
            "  'ContraseÃ±a de aplicaciÃ³n' en tu cuenta Google."
        )

    def help(self) -> str:
        return (
            "CORREO ELECTRÃ“NICO:\n"
            "  correo / bandeja           - Lee correos no leÃ­dos\n"
            "  enviar correo a <email>    - EnvÃ­a un correo\n"
            '    asunto:"..." diciendo:"..."  - Con asunto y mensaje\n'
            "  configurar correo          - Instrucciones de configuraciÃ³n\n\n"
            "Ej: correo\n"
            '    enviar correo a juan@gmail.com asunto:"ReuniÃ³n" diciendo:"MaÃ±ana a las 10"\n\n'
            "NOTA: Requiere config/email_config.json con tus credenciales."
        )

