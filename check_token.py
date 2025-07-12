#!/usr/bin/env python3
"""
Script para verificar el token de WhatsApp Business API
"""

import os
import requests
import sys
from datetime import datetime

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

def check_token():
    """Verifica el token de WhatsApp"""
    token = os.getenv("WHATSAPP_TOKEN")
    phone_number_id = os.getenv("PHONE_NUMBER_ID")
    
    if not token:
        print("❌ WHATSAPP_TOKEN no encontrado")
        return False
    
    if not phone_number_id:
        print("❌ PHONE_NUMBER_ID no encontrado")
        return False
    
    print(f"🔍 Verificando token...")
    print(f"Token: {token[:50]}...")
    print(f"Phone Number ID: {phone_number_id}")
    
    # Verificar el token con una llamada simple
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.ok:
            data = response.json()
            print("✅ Token es válido!")
            print(f"📱 Número verificado: {data.get('display_phone_number', 'N/A')}")
            print(f"🏢 Nombre: {data.get('name', 'N/A')}")
            return True
        else:
            print(f"❌ Token inválido: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando token: {e}")
        return False

def get_new_token_instructions():
    """Muestra instrucciones para obtener un nuevo token"""
    print("\n🔧 Para obtener un nuevo token:")
    print("1. Ve a https://developers.facebook.com/")
    print("2. Selecciona tu aplicación de WhatsApp")
    print("3. Ve a 'WhatsApp' > 'Getting Started'")
    print("4. En 'Temporary access token', haz clic en 'Generate'")
    print("5. Copia el nuevo token y actualiza tu archivo .env")
    print("\n📝 También puedes obtener un token permanente:")
    print("1. Ve a 'WhatsApp' > 'Configuration'")
    print("2. Configura Webhooks y verificación")
    print("3. Genera un Access Token de larga duración")

if __name__ == "__main__":
    print("🔑 Verificador de Token WhatsApp Business API")
    print("=" * 50)
    
    is_valid = check_token()
    
    if not is_valid:
        get_new_token_instructions()
        sys.exit(1)
    else:
        print("\n🎉 ¡Token listo para usar!")