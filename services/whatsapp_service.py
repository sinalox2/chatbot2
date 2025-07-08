# services/whatsapp_service.py
import os
import requests
from typing import Dict, Optional

class WhatsAppService:
    """
    Servicio centralizado para envío de mensajes por WhatsApp Business API
    """
    
    def __init__(self):
        self.token = os.getenv("WHATSAPP_TOKEN")
        self.phone_number_id = os.getenv("PHONE_NUMBER_ID")
        self.enabled = bool(self.token and self.phone_number_id)
        
        if self.enabled:
            print("✅ WhatsApp Business API Service inicializado")
        else:
            print("⚠️ WhatsApp Business API no configurado (WHATSAPP_TOKEN o PHONE_NUMBER_ID faltantes)")
    
    def enviar_mensaje(self, telefono: str, mensaje: str) -> Dict[str, any]:
        """
        Envía un mensaje de WhatsApp a un número específico
        
        Args:
            telefono: Número de teléfono destino (formato: +52XXXXXXXXXX)
            mensaje: Mensaje de texto a enviar
            
        Returns:
            Dict con el resultado del envío
        """
        if not self.enabled:
            print(f"📱 SIMULADO - WhatsApp a {telefono}: {mensaje}")
            return {
                'success': True,
                'simulado': True,
                'telefono': telefono,
                'mensaje': mensaje
            }
        
        try:
            # Limpiar número de teléfono (remover espacios, guiones, etc.)
            telefono_limpio = self._limpiar_telefono(telefono)
            
            url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
            
            payload = {
                "messaging_product": "whatsapp",
                "to": telefono_limpio,
                "type": "text",
                "text": {"body": mensaje}
            }
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.ok:
                result = response.json()
                print(f"✅ WhatsApp enviado a {telefono}: {response.status_code}")
                return {
                    'success': True,
                    'telefono': telefono,
                    'mensaje': mensaje,
                    'message_id': result.get('messages', [{}])[0].get('id'),
                    'status_code': response.status_code
                }
            else:
                error_text = response.text
                print(f"❌ Error enviando WhatsApp a {telefono}: {response.status_code} - {error_text}")
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {error_text}",
                    'telefono': telefono,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            error_msg = f"Timeout enviando mensaje a WhatsApp ({telefono})"
            print(f"⏱️ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'telefono': telefono
            }
        except Exception as e:
            error_msg = f"Error enviando WhatsApp a {telefono}: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'telefono': telefono
            }
    
    def enviar_mensaje_template(self, telefono: str, template_name: str, parameters: Optional[Dict] = None) -> Dict[str, any]:
        """
        Envía un mensaje usando un template de WhatsApp Business
        
        Args:
            telefono: Número de teléfono destino
            template_name: Nombre del template aprobado
            parameters: Parámetros para el template
            
        Returns:
            Dict con el resultado del envío
        """
        if not self.enabled:
            print(f"📱 SIMULADO - Template '{template_name}' a {telefono}")
            return {
                'success': True,
                'simulado': True,
                'telefono': telefono,
                'template': template_name
            }
        
        try:
            telefono_limpio = self._limpiar_telefono(telefono)
            
            url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
            
            payload = {
                "messaging_product": "whatsapp",
                "to": telefono_limpio,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "es"}
                }
            }
            
            # Agregar parámetros si los hay
            if parameters:
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": param} for param in parameters.values()]
                    }
                ]
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.ok:
                result = response.json()
                print(f"✅ Template WhatsApp enviado a {telefono}: {template_name}")
                return {
                    'success': True,
                    'telefono': telefono,
                    'template': template_name,
                    'message_id': result.get('messages', [{}])[0].get('id'),
                    'status_code': response.status_code
                }
            else:
                error_text = response.text
                print(f"❌ Error enviando template a {telefono}: {response.status_code} - {error_text}")
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {error_text}",
                    'telefono': telefono,
                    'template': template_name
                }
                
        except Exception as e:
            error_msg = f"Error enviando template a {telefono}: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'telefono': telefono,
                'template': template_name
            }
    
    def obtener_plantillas_disponibles(self) -> Dict[str, any]:
        """
        Obtiene la lista de plantillas disponibles en WhatsApp Business
        
        Returns:
            Dict con las plantillas disponibles
        """
        if not self.enabled:
            return {
                'success': False,
                'plantillas': [],
                'message': 'WhatsApp Business API no configurado'
            }
        
        try:
            url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/message_templates"
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.ok:
                data = response.json()
                plantillas = []
                
                for template in data.get('data', []):
                    if template.get('status') == 'APPROVED':
                        plantillas.append({
                            'name': template.get('name'),
                            'status': template.get('status'),
                            'category': template.get('category'),
                            'language': template.get('language')
                        })
                
                print(f"✅ Encontradas {len(plantillas)} plantillas aprobadas")
                return {
                    'success': True,
                    'plantillas': plantillas,
                    'total': len(plantillas)
                }
            else:
                error_text = response.text
                print(f"❌ Error obteniendo plantillas: {response.status_code} - {error_text}")
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {error_text}",
                    'plantillas': []
                }
                
        except Exception as e:
            error_msg = f"Error obteniendo plantillas: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'plantillas': []
            }

    def _limpiar_telefono(self, telefono: str) -> str:
        """
        Limpia y formatea el número de teléfono
        """
        # Remover espacios, guiones, paréntesis
        telefono_limpio = ''.join(filter(str.isdigit, telefono))
        
        # Agregar código de país si no lo tiene
        if not telefono_limpio.startswith('52') and len(telefono_limpio) == 10:
            telefono_limpio = '52' + telefono_limpio
        
        return telefono_limpio
    
    def verificar_conexion(self) -> bool:
        """
        Verifica que la conexión con WhatsApp Business API funcione
        """
        if not self.enabled:
            return False
        
        try:
            url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}"
            headers = {"Authorization": f"Bearer {self.token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            return response.ok
        except:
            return False

# Instancia global para usar en toda la aplicación
whatsapp_service = WhatsAppService()

# Función de conveniencia para mantener compatibilidad
def enviar_whatsapp(telefono: str, mensaje: str) -> bool:
    """
    Función de conveniencia para enviar mensajes de WhatsApp
    """
    resultado = whatsapp_service.enviar_mensaje(telefono, mensaje)
    return resultado.get('success', False)