#!/usr/bin/env python3
"""
Script maestro para configurar RAG Supabase desde cero.
Ejecuta todo el proceso de limpieza y migración.
"""

import os
import sys
import subprocess

def ejecutar_script(script_path, descripcion):
    """Ejecuta un script Python y maneja errores"""
    
    print(f"\n{'='*60}")
    print(f"🔧 {descripcion}")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print(result.stdout)
            print(f"✅ {descripcion} completado exitosamente")
            return True
        else:
            print(f"❌ Error en {descripcion}:")
            print(result.stderr)
            print(result.stdout)
            return False
            
    except Exception as e:
        print(f"❌ Excepción ejecutando {descripcion}: {e}")
        return False

def main():
    """Proceso principal"""
    
    print("🚀 SETUP RAG SUPABASE - DESDE CERO")
    print("🧹 Limpieza completa y migración optimizada")
    
    # Directorio de scripts
    scripts_dir = os.path.dirname(__file__)
    
    # Scripts a ejecutar en orden
    scripts = [
        {
            'path': os.path.join(scripts_dir, 'limpiar_rag_supabase.py'),
            'descripcion': 'Limpieza de tabla chunks existente'
        },
        {
            'path': os.path.join(scripts_dir, 'migrar_rag_local_a_supabase.py'),
            'descripcion': 'Migración de RAG local a Supabase'
        }
    ]
    
    # Ejecutar scripts secuencialmente
    resultados = []
    
    for script in scripts:
        exito = ejecutar_script(script['path'], script['descripcion'])
        resultados.append(exito)
        
        if not exito:
            print(f"\n❌ Error crítico en: {script['descripcion']}")
            print("🛑 Deteniendo proceso...")
            break
    
    # Resumen final
    print(f"\n{'='*60}")
    print("📊 RESUMEN FINAL")
    print('='*60)
    
    if all(resultados):
        print("🎉 ¡PROCESO COMPLETADO EXITOSAMENTE!")
        print("\n✅ RAG Supabase configurado y listo")
        print("✅ Datos migrados desde RAG local")
        print("✅ Funciones de búsqueda optimizadas")
        print("\n🔄 Ahora puedes:")
        print("   1. Probar búsquedas con el nuevo sistema")
        print("   2. Actualizar conversation_service.py para usar Supabase")
        print("   3. Deployar en Railway sin problemas de persistencia")
        
    else:
        print("❌ PROCESO INCOMPLETO")
        print("\n⚠️ Algunos pasos fallaron:")
        for i, (script, exito) in enumerate(zip(scripts, resultados)):
            estado = "✅" if exito else "❌"
            print(f"   {estado} {script['descripcion']}")
        
        print("\n🔧 Revisa los errores y ejecuta manualmente:")
        for i, (script, exito) in enumerate(zip(scripts, resultados)):
            if not exito:
                print(f"   python {script['path']}")

if __name__ == "__main__":
    main()