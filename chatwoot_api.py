import requests
import logging
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Configuración desde variables de entorno
CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "https://chat.progreweb.com")
ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID", "4")
BOT_TOKEN = os.getenv("CHATWOOT_API_TOKEN", "jCRjFAbN4RtUr8tKGT4vsA5L")
INBOX_ID = os.getenv("CHATWOOT_INBOX_ID", "35")

# Validar configuración esencial
if not all([CHATWOOT_BASE_URL, ACCOUNT_ID, BOT_TOKEN, INBOX_ID]):
    logging.critical("Faltan variables de entorno críticas para la API de Chatwoot. Por favor, configure CHATWOOT_BASE_URL, CHATWOOT_ACCOUNT_ID, CHATWOOT_API_TOKEN, y CHATWOOT_INBOX_ID.")
    # En un entorno real, podrías querer que la aplicación no inicie.
    # raise ValueError("Missing critical Chatwoot environment variables.")

headers = {
    "api_access_token": BOT_TOKEN,
    "Content-Type": "application/json"
}

def _handle_request_error(response):
    """Maneja y loguea errores de HTTP."""
    logging.error(f"Error en API de Chatwoot - Status: {response.status_code}")
    logging.error(f"Respuesta: {response.text}")
    response.raise_for_status()

def buscar_contacto(telefono: str):
    """Busca un contacto por número de teléfono."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/contacts/search"
    params = {'q': telefono.replace('+', '')}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if not response.ok:
            _handle_request_error(response)
        
        data = response.json()
        if data and len(data.get('payload', [])) > 0:
            logging.info(f"Contacto encontrado para {telefono}: {data['payload'][0]['id']}")
            return data['payload'][0]
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Excepción en la llamada a la API de Chatwoot (buscar): {e}")
        return None

def crear_contacto(nombre: str, telefono: str):
    """Crea un nuevo contacto en Chatwoot."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/contacts"
    data = {
        "name": nombre,
        "phone_number": telefono,
        "inbox_id": INBOX_ID
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 422: # Contacto ya existe
            logging.warning(f"El contacto {telefono} ya existe, buscándolo...")
            return buscar_contacto(telefono)
        
        if not response.ok:
            _handle_request_error(response)

        # La respuesta de creación anida el contacto en payload -> contact
        payload = response.json().get('payload', {})
        contact_data = payload.get('contact')
        logging.info(f"Contacto creado para {telefono}: {contact_data.get('id') if contact_data else 'N/A'}")
        return contact_data

    except requests.exceptions.RequestException as e:
        logging.error(f"Excepción en la llamada a la API de Chatwoot (crear): {e}")
        return None

def crear_conversacion(contact_id: int):
    """Crea una nueva conversación para un contacto."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/conversations"
    data = {
        "contact_id": contact_id,
        "inbox_id": INBOX_ID
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if not response.ok:
            _handle_request_error(response)
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Excepción en la llamada a la API de Chatwoot (conversación): {e}")
        return None

def crear_mensaje_privado(conversation_id: int, mensaje: str):
    """Crea un mensaje o nota privada en una conversación."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/conversations/{conversation_id}/messages"
    data = {
        "content": mensaje,
        "private": True,
        "message_type": "outgoing"
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if not response.ok:
            _handle_request_error(response)
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Excepción en la llamada a la API de Chatwoot (mensaje): {e}")
        return None

def enviar_mensaje_publico(conversation_id: int, mensaje: str):
    """Envía un mensaje público en una conversación (visible para el cliente)."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/conversations/{conversation_id}/messages"
    data = {
        "content": mensaje,
        "private": False,
        "message_type": "outgoing"
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if not response.ok:
            _handle_request_error(response)
        logging.info(f"✅ Mensaje público enviado a conversación {conversation_id}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Excepción enviando mensaje público a Chatwoot: {e}")
        return None

def enviar_mensaje_incoming(conversation_id: int, mensaje: str, phone_number: str, message_id: str = None):
    """Envía un mensaje como si viniera del cliente (incoming message)."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/conversations/{conversation_id}/messages"
    
    # Usar el message_id de WhatsApp si está disponible, si no, generar uno
    if message_id:
        source_id = message_id
    else:
        source_id = f"whatsapp_{phone_number}_{int(__import__('time').time())}"

    data = {
        "content": mensaje,
        "private": False,
        "message_type": "incoming",
        "source_id": source_id
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if not response.ok:
            _handle_request_error(response)
        logging.info(f"✅ Mensaje del cliente enviado a conversación {conversation_id}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Excepción enviando mensaje del cliente a Chatwoot: {e}")
        return None

def obtener_conversacion_por_telefono(telefono: str):
    """Obtiene la conversación activa de un contacto por teléfono."""
    contacto = buscar_contacto(telefono)
    if not contacto:
        return None
    
    contact_id = contacto.get('id')
    logging.info(f"Buscando conversaciones para contact_id: {contact_id}")
    
    # Buscar conversaciones del contacto específico
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/conversations"
    params = {
        'inbox_id': INBOX_ID,
        'status': 'open'  # Solo conversaciones abiertas
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if not response.ok:
            _handle_request_error(response)
        
        data = response.json()
        conversations = data.get('data', {}).get('payload', [])
        
        # Buscar conversación del contacto específico por contact_id
        for conv in conversations:
            conv_contact_id = conv.get('meta', {}).get('sender', {}).get('id')
            if conv_contact_id == contact_id:
                logging.info(f"Conversación encontrada para {telefono} (contact_id: {contact_id}): {conv['id']}")
                return conv
        
        # Si no se encuentra conversación abierta, buscar cualquier conversación del contacto
        logging.info(f"No hay conversación abierta, buscando cualquier conversación para contact_id: {contact_id}")
        
        # Buscar todas las conversaciones (no solo abiertas)
        params_all = {'inbox_id': INBOX_ID}
        response_all = requests.get(url, headers=headers, params=params_all, timeout=10)
        
        if response_all.ok:
            data_all = response_all.json()
            conversations_all = data_all.get('data', {}).get('payload', [])
            
            for conv in conversations_all:
                conv_contact_id = conv.get('meta', {}).get('sender', {}).get('id')
                if conv_contact_id == contact_id:
                    logging.info(f"Conversación existente encontrada para {telefono}: {conv['id']} (status: {conv.get('status')})")
                    return conv
                
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error obteniendo conversación por teléfono: {e}")
        return None

def send_message_to_chatwoot(telefono: str, mensaje: str):
    """
    Envía la respuesta del chatbot a Chatwoot como mensaje público.
    
    Args:
        telefono (str): Número de teléfono del contacto
        mensaje (str): Mensaje a enviar
        
    Returns:
        bool: True si el mensaje se envió exitosamente, False en caso contrario
    """
    try:
        # Buscar o crear contacto
        contacto = buscar_contacto(telefono)
        if not contacto:
            logging.info(f"Contacto {telefono} no encontrado, creando nuevo contacto...")
            contacto = crear_contacto("Cliente WhatsApp", telefono)
            if not contacto:
                logging.error(f"No se pudo crear contacto para {telefono}")
                return False
        
        # Buscar conversación existente
        conversacion = obtener_conversacion_por_telefono(telefono)
        if not conversacion:
            logging.info(f"Conversación no encontrada para {telefono}, creando nueva...")
            conversacion = crear_conversacion(contacto['id'])
            if not conversacion:
                logging.error(f"No se pudo crear conversación para {telefono}")
                return False
        
        # Enviar mensaje privado (nota interna) para evitar reenvío a WhatsApp
        conversation_id = conversacion.get('id')
        resultado = crear_mensaje_privado(conversation_id, f"🤖 Bot: {mensaje}")
        
        if resultado:
            logging.info(f"✅ Respuesta del chatbot enviada a Chatwoot para {telefono}")
            return True
        else:
            logging.error(f"❌ Error enviando respuesta del chatbot a Chatwoot para {telefono}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error en send_message_to_chatwoot para {telefono}: {e}")
        return False
