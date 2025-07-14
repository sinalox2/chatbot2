import requests
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Configuración
CHATWOOT_BASE_URL = "https://crm.progreweb.com"
ACCOUNT_ID = "7"
BOT_TOKEN = "zqg549VjpbcR6S6vQ9C6CMJY"
INBOX_ID = 35  # ID del inbox de WhatsApp

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

def enviar_mensaje_incoming(conversation_id: int, mensaje: str, phone_number: str):
    """Envía un mensaje como si viniera del cliente (incoming message)."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/conversations/{conversation_id}/messages"
    data = {
        "content": mensaje,
        "private": False,
        "message_type": "incoming",
        "source_id": f"whatsapp_{phone_number}_{int(__import__('time').time())}"
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
    
    # Buscar conversaciones del contacto
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
        
        # Buscar conversación del contacto específico
        for conv in conversations:
            if conv.get('meta', {}).get('sender', {}).get('phone_number') == telefono:
                logging.info(f"Conversación encontrada para {telefono}: {conv['id']}")
                return conv
                
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error obteniendo conversación por teléfono: {e}")
        return None
