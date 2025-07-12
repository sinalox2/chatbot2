#!/usr/bin/env python3
"""
Script para generar token permanente de WhatsApp Business API usando System User
"""
import os
import requests
import json
from dotenv import load_dotenv, set_key

def generar_token_permanente():
    """Genera un token permanente usando System User"""
    load_dotenv()
    
    app_id = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    business_id = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID')
    
    if not all([app_id, app_secret, business_id]):
        print("❌ Faltan variables de entorno:")
        print("   - FACEBOOK_APP_ID")
        print("   - FACEBOOK_APP_SECRET") 
        print("   - WHATSAPP_BUSINESS_ACCOUNT_ID")
        return False
    
    print("🔧 Configuración de Token Permanente para WhatsApp")
    print("=" * 60)
    print(f"📱 App ID: {app_id}")
    print(f"🏢 Business ID: {business_id}")
    print()
    
    # Paso 1: Obtener App Access Token
    print("1️⃣ Obteniendo App Access Token...")
    try:
        app_token_url = f"https://graph.facebook.com/oauth/access_token"
        app_token_params = {
            'client_id': app_id,
            'client_secret': app_secret,
            'grant_type': 'client_credentials'
        }
        
        response = requests.get(app_token_url, params=app_token_params)
        if response.status_code != 200:
            print(f"❌ Error obteniendo app token: {response.text}")
            return False
            
        app_token = response.json().get('access_token')
        print(f"✅ App token obtenido: {app_token[:20]}...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Paso 2: Listar System Users
    print("\n2️⃣ Obteniendo System Users disponibles...")
    try:
        system_users_url = f"https://graph.facebook.com/v18.0/{business_id}/system_users"
        headers = {'Authorization': f'Bearer {app_token}'}
        
        response = requests.get(system_users_url, headers=headers)
        if response.status_code != 200:
            print(f"❌ Error obteniendo system users: {response.text}")
            return False
            
        system_users = response.json().get('data', [])
        
        if not system_users:
            print("❌ No se encontraron System Users.")
            print("   Debes crear uno en Business Manager > Business Settings > System Users")
            return False
            
        print(f"✅ Se encontraron {len(system_users)} System Users:")
        for i, user in enumerate(system_users):
            print(f"   {i+1}. {user.get('name')} (ID: {user.get('id')})")
        
        # Seleccionar System User
        if len(system_users) == 1:
            selected_user = system_users[0]
            print(f"📋 Usando automáticamente: {selected_user.get('name')}")
        else:
            print("\n¿Cuál System User quieres usar? (número): ", end="")
            try:
                selection = int(input()) - 1
                if 0 <= selection < len(system_users):
                    selected_user = system_users[selection]
                else:
                    print("❌ Selección inválida")
                    return False
            except ValueError:
                print("❌ Entrada inválida")
                return False
        
        system_user_id = selected_user.get('id')
        print(f"👤 System User seleccionado: {selected_user.get('name')} ({system_user_id})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Paso 3: Generar Token Permanente
    print("\n3️⃣ Generando token permanente...")
    try:
        token_url = f"https://graph.facebook.com/v18.0/{system_user_id}/access_tokens"
        token_data = {
            'business_app': app_id,
            'scope': 'whatsapp_business_management,whatsapp_business_messaging'
        }
        headers = {'Authorization': f'Bearer {app_token}'}
        
        response = requests.post(token_url, data=token_data, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Error generando token: {response.text}")
            return False
            
        result = response.json()
        permanent_token = result.get('access_token')
        
        if not permanent_token:
            print(f"❌ No se recibió token en la respuesta: {result}")
            return False
            
        print(f"✅ Token permanente generado: {permanent_token[:30]}...")
        
        # Paso 4: Verificar el token
        print("\n4️⃣ Verificando token permanente...")
        verify_url = "https://graph.facebook.com/v18.0/me"
        verify_headers = {'Authorization': f'Bearer {permanent_token}'}
        
        verify_response = requests.get(verify_url, headers=verify_headers)
        if verify_response.status_code == 200:
            print("✅ Token verificado y funcional")
            
            # Paso 5: Actualizar .env
            print("\n5️⃣ Actualizando archivo .env...")
            env_file = '.env'
            set_key(env_file, 'WHATSAPP_TOKEN', permanent_token)
            print("✅ Archivo .env actualizado con el token permanente")
            
            print("\n🎉 ¡ÉXITO! Token permanente configurado")
            print("=" * 60)
            print("📋 Resumen:")
            print(f"   • Token: {permanent_token[:30]}...")
            print("   • Tipo: Permanente (no expira)")
            print("   • System User:", selected_user.get('name'))
            print("   • Archivo .env actualizado")
            print("\n💡 Este token NO expira y no necesita renovación")
            
            return True
        else:
            print(f"❌ Error verificando token: {verify_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if generar_token_permanente():
        print("\n🚀 Ya puedes usar tu aplicación con el token permanente")
    else:
        print("\n❌ No se pudo generar el token permanente")
        print("Revisa que:")
        print("1. Tengas un System User creado en Business Manager")
        print("2. El System User tenga acceso a tu app de WhatsApp")
        print("3. Las variables de entorno estén correctas")