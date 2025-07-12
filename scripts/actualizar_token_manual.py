#!/usr/bin/env python3
"""
Script para actualizar manualmente el token permanente en .env
"""
import os
from dotenv import set_key

def actualizar_token_manual():
    """Actualiza el token en .env de forma manual"""
    print("🔧 Actualización Manual de Token WhatsApp")
    print("=" * 50)
    print()
    print("📋 Instrucciones:")
    print("1. Ve a business.facebook.com")
    print("2. Business Settings > Users > System Users")
    print("3. Selecciona tu System User")
    print("4. Generate New Token para tu app de WhatsApp")
    print("5. Copia el token que se genere")
    print()
    
    # Solicitar el token
    print("📝 Pega aquí tu token permanente:")
    token = input().strip()
    
    if not token:
        print("❌ No se proporcionó token")
        return False
    
    if len(token) < 50:
        print("⚠️ El token parece muy corto. ¿Estás seguro? (y/n)")
        if input().lower() != 'y':
            return False
    
    try:
        # Actualizar .env
        env_file = '.env'
        set_key(env_file, 'WHATSAPP_TOKEN', token)
        
        print("✅ Token actualizado en .env")
        print(f"🔑 Token: {token[:30]}...")
        print()
        print("🧪 Probando token...")
        
        # Probar el token
        import requests
        verify_url = f"https://graph.facebook.com/v18.0/me"
        headers = {'Authorization': f'Bearer {token}'}
        
        response = requests.get(verify_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Token verificado exitosamente")
            print(f"📱 App: {data.get('name', 'N/A')}")
            print(f"🆔 ID: {data.get('id', 'N/A')}")
            print()
            print("🎉 ¡Token permanente configurado correctamente!")
            print("💡 Este token NO expira automáticamente")
            return True
        else:
            print(f"❌ Error verificando token: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    actualizar_token_manual()