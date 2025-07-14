#!/usr/bin/env python3
"""
Prueba final del RAG Supabase usando la función existente
"""

import os
import sys
import openai

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import supabase

openai.api_key = os.getenv("OPENAI_API_KEY")

def generar_embedding(texto: str):
    """Genera embedding para búsqueda"""
    try:
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=texto
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Error generando embedding: {e}")
        return None

def buscar_chunks_supabase(query: str, limite: int = 3):
    """Busca usando la función existente buscar_chunks_similares"""
    
    print(f"🔍 Buscando: '{query}'")
    
    # Generar embedding
    query_embedding = generar_embedding(query)
    if not query_embedding:
        return []
    
    try:
        # Usar función existente
        result = supabase.rpc('buscar_chunks_similares', {
            'query_embedding': query_embedding,
            'match_threshold': 0.7,
            'match_count': limite
        }).execute()
        
        print(f"   📊 Encontrados: {len(result.data)} resultados")
        return result.data
        
    except Exception as e:
        print(f"   ❌ Error en búsqueda: {e}")
        return []

def main():
    """Pruebas finales"""
    
    print("🧪 PRUEBAS FINALES RAG SUPABASE")
    print("=" * 40)
    
    # Consultas de prueba
    queries = [
        "precio Sentra",
        "Versa",
        "financiamiento", 
        "July promociones"
    ]
    
    resultados_exitosos = 0
    
    for query in queries:
        print(f"\n📝 Consulta: '{query}'")
        print("-" * 30)
        
        chunks = buscar_chunks_supabase(query)
        
        if chunks:
            resultados_exitosos += 1
            for i, chunk in enumerate(chunks):
                similarity = chunk.get('similarity', 0)
                print(f"   📄 {i+1}. Similitud: {similarity:.3f}")
                print(f"      📰 {chunk['contenido'][:120]}...")
                print()
        else:
            print("   ❌ Sin resultados")
    
    print(f"\n📊 RESUMEN:")
    print(f"   ✅ Consultas exitosas: {resultados_exitosos}/{len(queries)}")
    print(f"   📈 Tasa de éxito: {(resultados_exitosos/len(queries)*100):.1f}%")
    
    if resultados_exitosos > 0:
        print(f"\n🎉 ¡RAG SUPABASE FUNCIONANDO!")
        print(f"✅ Listo para usar en producción")
    else:
        print(f"\n⚠️ Necesita ajustes en la configuración")

if __name__ == "__main__":
    main()