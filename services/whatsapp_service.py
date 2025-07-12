# services/whatsapp_service.py
import os
import requests
import logging
from dotenv import load_dotenv

class WhatsAppService:
    """
    Servicio para gestionar la conexión y el envío de mensajes
    a través de la API de WhatsApp Business.
    """
    def __init__(self):
        self.api_version = 'v19.0'
        self.base_url = None
        self.headers = None
        self.token = None
        self.phone_number_id = None
        self.enabled = False
        self.load_config()
        print("✅ WhatsApp Business API Service inicializado")

    def load_config(self):
        """
        Carga o recarga la configuración desde el archivo .env.
        La clave aquí es `override=True` para forzar la relectura del archivo.
        """
        load_dotenv(override=True) 
        
        # Try both variable naming conventions
        self.token = os.getenv("WHATSAPP_API_TOKEN") or os.getenv("WHATSAPP_TOKEN")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("PHONE_NUMBER_ID")
        
        if self.token and self.phone_number_id:
            self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            self.enabled = True
            print(f"🔑 Token cargado: {self.token[:20]}... (y phone_number_id)")
        else:
            self.enabled = False
            print("⚠️ WhatsApp no configurado. Faltan tokens de WhatsApp (WHATSAPP_TOKEN/WHATSAPP_API_TOKEN y PHONE_NUMBER_ID/WHATSAPP_PHONE_NUMBER_ID) en .env")

    def reload_token(self):
        """Recarga el token y la configuración desde el archivo .env."""
        print("🔄 Recargando token de WhatsApp...")
        token_anterior = self.token
        self.load_config() # Esta función ahora relee el .env gracias a override=True
        print(f"🔄 Token anterior: {token_anterior[:20] if token_anterior else 'N/A'}...")
        print(f"🔑 Token nuevo: {self.token[:20] if self.token else 'N/A'}...")
        return self.enabled

    def enviar_mensaje(self, telefono, mensaje):
        """Envía un mensaje de texto simple."""
        if not self.enabled:
            logging.error("❌ Error enviando WhatsApp: servicio no habilitado.")
            return {'success': False, 'error': 'Servicio no habilitado'}

        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "text",
            "text": {"body": mensaje}
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            if response.status_code == 200:
                logging.info(f"✅ Mensaje de texto enviado a {telefono}")
                return {'success': True, 'data': response.json()}
            else:
                logging.error(f"❌ Error enviando WhatsApp a {telefono}: {response.status_code} - {response.text}")
                return {'success': False, 'status_code': response.status_code, 'error': response.json()}
        except Exception as e:
            logging.error(f"❌ Excepción enviando WhatsApp: {e}")
            return {'success': False, 'error': str(e)}

    def enviar_mensaje_template(self, telefono, template_name, language_code='es_MX', parameters=None):
        """Envía un mensaje usando una plantilla de WhatsApp."""
        if not self.enabled:
            logging.error("❌ Error enviando plantilla: servicio no habilitado.")
            return {'success': False, 'error': 'Servicio no habilitado'}

        url = f"{self.base_url}/messages"
        
        # Construir payload base
        payload = {
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }

        # Agregar componentes con parámetros según la plantilla
        if parameters:
            components = self._build_template_components(template_name, parameters)
            if components:
                payload['template']['components'] = components

        try:
            response = requests.post(url, json=payload, headers=self.headers)
            if response.status_code == 200:
                logging.info(f"✅ Plantilla '{template_name}' enviada a {telefono}")
                return {'success': True, 'data': response.json()}
            else:
                logging.error(f"❌ Error enviando plantilla a {telefono}: {response.status_code} - {response.text}")
                return {'success': False, 'status_code': response.status_code, 'error': response.json()}
        except Exception as e:
            logging.error(f"❌ Excepción enviando plantilla: {e}")
            return {'success': False, 'error': str(e)}
    
    def _build_template_components(self, template_name, parameters):
        """Construye los componentes de la plantilla según el formato de Meta"""
        if template_name == "saludo_lead":
            return [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": parameters.get('nombre', 'Cliente')}
                    ]
                }
            ]
        elif template_name == "recordatorio_cita":
            return [
                {
                    "type": "body", 
                    "parameters": [
                        {"type": "text", "text": parameters.get('nombre', 'Cliente')},
                        {"type": "text", "text": parameters.get('fecha', 'Fecha por confirmar')},
                        {"type": "text", "text": parameters.get('hora', 'Hora por confirmar')},
                        {"type": "text", "text": parameters.get('direccion', 'Av. Revolución 123, Nissan Tijuana')}
                    ]
                }
            ]
        else:
            # Para plantillas desconocidas, intentar parámetros genéricos
            if parameters:
                return [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(value)} 
                            for value in parameters.values()
                        ]
                    }
                ]
        return None

    def verificar_conexion(self):
        """Verifica si el token y phone_number_id son válidos."""
        if not self.enabled: return False
        check_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        try: return requests.get(check_url, headers=self.headers, params={'fields': 'name'}).status_code == 200
        except Exception: return False

# Instancia única del servicio para ser importada en otros módulos
whatsapp_service = WhatsAppService()