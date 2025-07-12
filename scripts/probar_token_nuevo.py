#!/usr/bin/env python3
"""
Script para probar un token nuevo antes de guardarlo
"""
import requests

def probar_token():
    print("🧪 Probador de Token WhatsApp")
    print("=" * 40)
    print()
    print("📝 Pega tu nuevo token aquí y presiona Enter:")
    
    try:
        token = input().strip()
    except (EOFError, KeyboardInterrupt):
        print("\n❌ Operación cancelada")
        return False
    
    if not token:
        print("❌ No se proporcionó token")
        return False
    
    print(f"\n🔍 Probando token: {token[:30]}...")
    
    try:
        # Test básico
        url = 'https://graph.facebook.com/v18.0/me'
        headers = {'Authorization': f'Bearer {token}'}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Token válido")
            print(f"📱 App: {data.get('name', 'N/A')}")
            print(f"🆔 App ID: {data.get('id', 'N/A')}")
            
            # Test específico de WhatsApp
            phone_id = "598295846709987"  # Tu phone_number_id
            wa_url = f'https://graph.facebook.com/v18.0/{phone_id}'
            wa_response = requests.get(wa_url, headers=headers)
            
            if wa_response.status_code == 200:
                wa_data = wa_response.json()
                print(f"📞 Acceso WhatsApp: ✅")
                print(f"📱 Número: {wa_data.get('display_phone_number', 'N/A')}")
                
                print(f"\n🎉 ¡Token funciona perfectamente!")
                print(f"\n📋 Para actualizarlo en .env, copia esta línea:")
                print(f"WHATSAPP_TOKEN={token}")
                return True
            else:
                print(f"❌ Sin acceso a WhatsApp: {wa_response.text}")
                return False
        else:
            print(f"❌ Token inválido: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    probar_token()