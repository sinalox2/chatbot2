#!/usr/bin/env python3
"""
Script de debug para verificar variables de entorno en Railway
"""
import os
import sys

def debug_environment():
    """Debug de variables de entorno"""
    
    print("🔍 DEBUG VARIABLES DE ENTORNO EN RAILWAY")
    print("=" * 50)
    
    # Variables críticas
    critical_vars = [
        'OPENAI_API_KEY',
        'SUPABASE_URL', 
        'SUPABASE_KEY',
        'WHATSAPP_TOKEN',
        'PHONE_NUMBER_ID',
        'WHATSAPP_VERIFY_TOKEN',
        'PORT',
        'FLASK_ENV',
        'DEBUG'
    ]
    
    print("🔧 Variables críticas:")
    missing_vars = []
    
    for var in critical_vars:
        value = os.environ.get(var)
        if value:
            # Solo mostrar primeros y últimos caracteres por seguridad
            if len(value) > 8:
                display_value = f"{value[:4]}...{value[-4:]}"
            else:
                display_value = f"{value[:2]}..."
            print(f"   ✅ {var}: {display_value} ({len(value)} chars)")
        else:
            print(f"   ❌ {var}: No configurada")
            missing_vars.append(var)
    
    print(f"\n📊 Resumen:")
    print(f"   Variables configuradas: {len(critical_vars) - len(missing_vars)}/{len(critical_vars)}")
    print(f"   Variables faltantes: {len(missing_vars)}")
    
    if missing_vars:
        print(f"   🚨 Faltantes: {', '.join(missing_vars)}")
        return False
    else:
        print(f"   ✅ Todas las variables configuradas")
        return True

def test_openai_import():
    """Test import de OpenAI"""
    print(f"\n🧪 TEST IMPORT OPENAI")
    print("=" * 30)
    
    try:
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        
        if api_key:
            openai.api_key = api_key
            print(f"✅ OpenAI importado y configurado")
            print(f"✅ API Key configurada: {api_key[:10]}...")
            return True
        else:
            print(f"❌ OpenAI importado pero sin API key")
            return False
            
    except ImportError as e:
        print(f"❌ Error importando OpenAI: {e}")
        return False

def test_supabase_import():
    """Test import de Supabase"""
    print(f"\n🧪 TEST IMPORT SUPABASE")
    print("=" * 30)
    
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from supabase_client import supabase
        
        if supabase:
            print(f"✅ Supabase importado y conectado")
            return True
        else:
            print(f"❌ Supabase importado pero no conectado")
            return False
            
    except ImportError as e:
        print(f"❌ Error importando Supabase: {e}")
        return False

def main():
    """Función principal"""
    
    print("🚀 DIAGNÓSTICO RAILWAY - VARIABLES DE ENTORNO")
    print("=" * 60)
    
    # Test variables
    env_ok = debug_environment()
    
    # Test imports
    openai_ok = test_openai_import()
    supabase_ok = test_supabase_import()
    
    print(f"\n📋 RESULTADO FINAL:")
    print(f"   Variables: {'✅' if env_ok else '❌'}")
    print(f"   OpenAI: {'✅' if openai_ok else '❌'}")
    print(f"   Supabase: {'✅' if supabase_ok else '❌'}")
    
    if env_ok and openai_ok and supabase_ok:
        print(f"\n🎉 TODO FUNCIONANDO - LISTO PARA PRODUCCIÓN")
        return True
    else:
        print(f"\n⚠️ HAY PROBLEMAS - REVISAR CONFIGURACIÓN")
        
        if not env_ok:
            print(f"💡 Solución: Configurar variables faltantes en Railway")
        if not openai_ok:
            print(f"💡 Solución: Verificar OPENAI_API_KEY en Railway")
        if not supabase_ok:
            print(f"💡 Solución: Verificar SUPABASE_URL y SUPABASE_KEY")
            
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n🔚 Debug completado - Exit code: {0 if success else 1}")
    sys.exit(0 if success else 1)