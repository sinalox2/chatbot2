#!/usr/bin/env python3
"""
Script para encontrar información de la app desde el token
"""

import requests
import os
from dotenv import load_dotenv
load_dotenv(override=True)

def find_app_info():
    """Encuentra información de la app"""
    token = os.getenv("WHATSAPP_TOKEN")
    
    if not token:
        print("❌ Token no encontrado")
        return
    
    print("🔍 Buscando información de la app...")
    print(f"Token: {token[:50]}...")
    
    # Obtener info del token
    try:
        url = "https://graph.facebook.com/v18.0/me"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers)
        
        if response.ok:
            data = response.json()
            print("✅ Información encontrada:")
            print(f"📱 App ID: {data.get('id', 'No disponible')}")
            print(f"📱 Name: {data.get('name', 'No disponible')}")
            print(f"📱 Category: {data.get('category', 'No disponible')}")
            
            # Intentar obtener más detalles
            app_url = f"https://graph.facebook.com/v18.0/{data.get('id')}"
            app_response = requests.get(app_url, headers=headers)
            
            if app_response.ok:
                app_data = app_response.json()
                print(f"📱 Display Name: {app_data.get('display_name', 'No disponible')}")
                print(f"📱 Namespace: {app_data.get('namespace', 'No disponible')}")
            
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # También buscar Business Account ID
    print("\n🏢 Buscando Business Account ID...")
    try:
        # Intentar obtener info del phone number
        phone_id = os.getenv("PHONE_NUMBER_ID")
        if phone_id:
            url = f"https://graph.facebook.com/v18.0/{phone_id}"
            response = requests.get(url, headers=headers)
            
            if response.ok:
                data = response.json()
                print("✅ Información del teléfono:")
                print(f"📞 Número: {data.get('display_phone_number', 'No disponible')}")
                print(f"🏢 Business Account ID: {data.get('business_account_id', 'No disponible')}")
                print(f"📱 Nombre: {data.get('name', 'No disponible')}")
                
                # Agregar al .env si encontramos el Business Account ID
                business_id = data.get('business_account_id')
                if business_id:
                    print(f"\n💡 Agrega esto a tu .env:")
                    print(f"WHATSAPP_BUSINESS_ACCOUNT_ID={business_id}")
                    
            else:
                print(f"❌ Error obteniendo info del teléfono: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Error buscando Business Account: {e}")

if __name__ == "__main__":
    find_app_info()