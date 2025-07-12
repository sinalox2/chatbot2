#!/usr/bin/env python3
"""
Script para verificar el estado del token de WhatsApp
"""
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

def verificar_token_detallado():
    """Verifica el token actual con información detallada"""
    load_dotenv()
    
    token = os.getenv('WHATSAPP_TOKEN')
    phone_id = os.getenv('PHONE_NUMBER_ID')
    
    if not token:
        print("❌ No se encontró WHATSAPP_TOKEN en .env")
        return False
    
    print("🔍 Verificación Detallada del Token WhatsApp")
    print("=" * 55)
    print(f"🔑 Token: {token[:30]}...")
    print(f"📱 Phone ID: {phone_id}")
    print(f"⏰ Fecha verificación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 1. Verificar validez básica
        print("1️⃣ Verificando validez del token...")
        me_url = "https://graph.facebook.com/v18.0/me"
        headers = {'Authorization': f'Bearer {token}'}
        
        response = requests.get(me_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Token válido")
            print(f"   📱 App: {data.get('name', 'N/A')}")
            print(f"   🆔 App ID: {data.get('id', 'N/A')}")
        else:
            print(f"❌ Token inválido: {response.text}")
            return False
        
        # 2. Verificar acceso a WhatsApp Business
        if phone_id:
            print("\n2️⃣ Verificando acceso a WhatsApp Business...")
            wa_url = f"https://graph.facebook.com/v18.0/{phone_id}"
            
            response = requests.get(wa_url, headers=headers)
            
            if response.status_code == 200:
                wa_data = response.json()
                print("✅ Acceso a WhatsApp Business confirmado")
                print(f"   📞 Número: {wa_data.get('display_phone_number', 'N/A')}")
                print(f"   🏷️ Nombre: {wa_data.get('name_status', 'N/A')}")
                print(f"   ✅ Verificado: {wa_data.get('verified_name', 'N/A')}")
            else:
                print(f"⚠️ Sin acceso a WhatsApp Business: {response.text}")
        
        # 3. Verificar permisos
        print("\n3️⃣ Verificando permisos del token...")
        permissions_url = f"https://graph.facebook.com/v18.0/{data.get('id')}/permissions"
        
        response = requests.get(permissions_url, headers=headers)
        
        if response.status_code == 200:
            perms_data = response.json()
            permissions = perms_data.get('data', [])
            
            required_perms = [
                'whatsapp_business_management',
                'whatsapp_business_messaging'
            ]
            
            print("✅ Permisos encontrados:")
            for perm in permissions:
                status = "✅" if perm.get('status') == 'granted' else "❌"
                print(f"   {status} {perm.get('permission')}")
            
            # Verificar permisos requeridos
            granted_perms = [p.get('permission') for p in permissions if p.get('status') == 'granted']
            missing_perms = [p for p in required_perms if p not in granted_perms]
            
            if missing_perms:
                print(f"\n⚠️ Permisos faltantes: {', '.join(missing_perms)}")
            else:
                print("\n✅ Todos los permisos requeridos están presentes")
        
        # 4. Información sobre expiración
        print("\n4️⃣ Información de expiración...")
        debug_url = f"https://graph.facebook.com/v18.0/debug_token"
        debug_params = {
            'input_token': token,
            'access_token': token
        }
        
        response = requests.get(debug_url, params=debug_params)
        
        if response.status_code == 200:
            debug_data = response.json().get('data', {})
            expires_at = debug_data.get('expires_at')
            
            if expires_at and expires_at > 0:
                exp_date = datetime.fromtimestamp(expires_at)
                print(f"⏰ Token expira: {exp_date.strftime('%Y-%m-%d %H:%M:%S')}")
                
                days_left = (exp_date - datetime.now()).days
                if days_left > 30:
                    print(f"✅ Token válido por {days_left} días más")
                elif days_left > 0:
                    print(f"⚠️ Token expira en {days_left} días - considera renovar")
                else:
                    print("❌ Token expirado")
            else:
                print("✅ Token permanente (no expira)")
        
        print("\n🎉 Verificación completada")
        return True
        
    except Exception as e:
        print(f"❌ Error durante verificación: {e}")
        return False

if __name__ == "__main__":
    verificar_token_detallado()