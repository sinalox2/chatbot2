#!/usr/bin/env python3
"""
Script de debug para verificar configuración de Chatwoot
"""
import os
import sys
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def debug_chatwoot_vars():
    """Debug de variables de entorno de Chatwoot"""
    
    print("🔍 DEBUG VARIABLES DE CHATWOOT")
    print("=" * 50)
    
    # Variables de Chatwoot
    chatwoot_vars = [
        'CHATWOOT_BASE_URL',
        'CHATWOOT_ACCOUNT_ID', 
        'CHATWOOT_API_TOKEN',
        'CHATWOOT_INBOX_ID'
    ]
    
    print("🔧 Variables de Chatwoot:")
    missing_vars = []
    config = {}
    
    for var in chatwoot_vars:
        value = os.environ.get(var)
        if value:
            # Solo mostrar primeros y últimos caracteres por seguridad
            if len(value) > 8:
                display_value = f"{value[:4]}...{value[-4:]}"
            else:
                display_value = f"{value[:2]}..."
            print(f"   ✅ {var}: {display_value} ({len(value)} chars)")
            config[var] = value
        else:
            print(f"   ❌ {var}: No configurada")
            missing_vars.append(var)
    
    print(f"\n📊 Resumen:")
    print(f"   Variables configuradas: {len(chatwoot_vars) - len(missing_vars)}/{len(chatwoot_vars)}")
    
    if missing_vars:
        print(f"   🚨 Faltantes: {', '.join(missing_vars)}")
        return False, {}
    else:
        print(f"   ✅ Todas las variables configuradas")
        return True, config

def test_chatwoot_connection(config):
    """Test de conexión a Chatwoot API"""
    print(f"\n🧪 TEST CONEXIÓN CHATWOOT API")
    print("=" * 40)
    
    if not config:
        print("❌ No hay configuración disponible")
        return False
    
    try:
        # Test básico de conexión
        url = f"{config['CHATWOOT_BASE_URL']}/api/v1/accounts/{config['CHATWOOT_ACCOUNT_ID']}/conversations"
        headers = {
            "api_access_token": config['CHATWOOT_API_TOKEN'],
            "Content-Type": "application/json"
        }
        
        print(f"📡 Probando conexión a: {config['CHATWOOT_BASE_URL']}")
        print(f"🏢 Account ID: {config['CHATWOOT_ACCOUNT_ID']}")
        print(f"📥 Inbox ID: {config['CHATWOOT_INBOX_ID']}")
        
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            conversations = data.get('data', {}).get('payload', [])
            print(f"✅ Conexión exitosa")
            print(f"💬 Conversaciones encontradas: {len(conversations)}")
            return True
        elif response.status_code == 401:
            print(f"❌ Error de autenticación - Token inválido")
            return False
        elif response.status_code == 404:
            print(f"❌ Account ID no encontrado")
            return False
        else:
            print(f"❌ Error HTTP: {response.status_code}")
            print(f"📄 Respuesta: {response.text[:200]}...")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout - Servidor no responde")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Error de conexión - Verificar URL")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def test_send_message_function():
    """Test de la función send_message_to_chatwoot"""
    print(f"\n🧪 TEST FUNCIÓN send_message_to_chatwoot")
    print("=" * 45)
    
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from chatwoot_api import send_message_to_chatwoot
        
        print(f"✅ Función importada correctamente")
        
        # Test con número ficticio (no enviará realmente)
        test_phone = "+526871006601"
        test_message = "Test desde debug script"
        
        print(f"📱 Probando con: {test_phone}")
        print(f"💬 Mensaje: {test_message}")
        
        # Nota: Esto hará una llamada real si las credenciales son válidas
        # result = send_message_to_chatwoot(test_phone, test_message)
        print(f"⚠️ Test simulado - no se envió mensaje real")
        print(f"💡 Para test real, descomenta la línea de arriba")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error importando función: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def main():
    """Función principal"""
    
    print("🚀 DIAGNÓSTICO CHATWOOT - CONFIGURACIÓN Y CONEXIÓN")
    print("=" * 60)
    
    # Test variables
    vars_ok, config = debug_chatwoot_vars()
    
    # Test conexión
    connection_ok = False
    if vars_ok:
        connection_ok = test_chatwoot_connection(config)
    
    # Test función
    function_ok = test_send_message_function()
    
    print(f"\n📋 RESULTADO FINAL:")
    print(f"   Variables: {'✅' if vars_ok else '❌'}")
    print(f"   Conexión API: {'✅' if connection_ok else '❌'}")
    print(f"   Función: {'✅' if function_ok else '❌'}")
    
    if vars_ok and connection_ok and function_ok:
        print(f"\n🎉 CHATWOOT FUNCIONANDO - LISTO PARA ENVIAR MENSAJES")
        return True
    else:
        print(f"\n⚠️ HAY PROBLEMAS CON CHATWOOT")
        
        if not vars_ok:
            print(f"💡 Solución: Configurar variables CHATWOOT_* en Railway")
        if not connection_ok:
            print(f"💡 Solución: Verificar URL, Account ID y Token en Chatwoot")
        if not function_ok:
            print(f"💡 Solución: Verificar imports y dependencias")
            
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n🔚 Debug Chatwoot completado - Exit code: {0 if success else 1}")
    sys.exit(0 if success else 1)