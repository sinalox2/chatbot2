import requests

# Configuración
CHATWOOT_BASE_URL = "https://crm.progreweb.com"
ACCOUNT_ID = "7"
BOT_TOKEN = "zqg549VjpbcR6S6vQ9C6CMJY"
INBOX_ID = "https://crm.progreweb.com/app/accounts/7/settings/inboxes/35P"  # ← Reemplaza con el ID real de tu inbox de WhatsApp

headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

def crear_contacto(nombre, telefono):
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/contacts"
    data = {
        "name": nombre,
        "phone_number": telefono,
        "inbox_id": INBOX_ID
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def crear_conversacion(contact_id):
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{ACCOUNT_ID}/conversations"
    data = {
        "source_id": contact_id,
        "inbox_id": INBOX_ID
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

# Ejemplo de uso
if __name__ == "__main__":
    nombre = "Juan Pérez"
    telefono = "+5216612345678"  # Debe tener formato internacional

    contacto = crear_contacto(nombre, telefono)
    print("✅ Contacto creado:", contacto)

    contacto_id = contacto.get("id")
    if contacto_id:
        conversacion = crear_conversacion(contacto_id)
        print("💬 Conversación creada:", conversacion)