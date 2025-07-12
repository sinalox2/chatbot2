#!/usr/bin/env python3
"""
Script para renovar automáticamente el token de WhatsApp Business API
"""
import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key

def renovar_token_whatsapp():
    """Renueva el token de WhatsApp y actualiza el .env"""
    load_dotenv()
    
    # Configuración desde .env
    app_id = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    token_actual = os.getenv('WHATSAPP_TOKEN')
    
    if not all([app_id, app_secret, token_actual]):
        print("❌ Faltan variables de entorno: FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, WHATSAPP_TOKEN")
        return False
    
    try:
        # Intercambiar token por uno de larga duración
        url = "https://graph.facebook.com/oauth/access_token"
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': token_actual
        }
        
        print("🔄 Renovando token de WhatsApp...")
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            nuevo_token = data.get('access_token')
            expires_in = data.get('expires_in', 5184000)  # Default 60 días
            
            if nuevo_token:
                # Actualizar .env
                env_file = '.env'
                set_key(env_file, 'WHATSAPP_TOKEN', nuevo_token)
                
                # Calcular fecha de expiración
                expiracion = datetime.now() + timedelta(seconds=expires_in)
                
                print(f"✅ Token renovado exitosamente")
                print(f"🔑 Nuevo token: {nuevo_token[:20]}...")
                print(f"⏰ Expira: {expiracion.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"📝 Archivo .env actualizado")
                
                return True
            else:
                print("❌ No se recibió nuevo token en la respuesta")
                return False
        else:
            print(f"❌ Error renovando token: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error en renovación: {e}")
        return False

def verificar_token_expiracion():
    """Verifica si el token está próximo a expirar"""
    load_dotenv()
    token = os.getenv('WHATSAPP_TOKEN')
    
    if not token:
        print("❌ No se encontró WHATSAPP_TOKEN en .env")
        return False
    
    try:
        # Verificar validez del token
        url = f"https://graph.facebook.com/v18.0/me"
        headers = {'Authorization': f'Bearer {token}'}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            print("✅ Token actual es válido")
            return True
        elif response.status_code == 401:
            print("⚠️ Token expirado o inválido")
            return False
        else:
            print(f"⚠️ Error verificando token: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando token: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Script de Renovación de Token WhatsApp")
    print("=" * 50)
    
    # Verificar token actual
    if verificar_token_expiracion():
        print("Token actual válido. ¿Renovar de todas formas? (y/n)")
        if input().lower() != 'y':
            exit(0)
    
    # Renovar token
    if renovar_token_whatsapp():
        print("\n🎉 Renovación completada exitosamente")
    else:
        print("\n❌ Error en la renovación")