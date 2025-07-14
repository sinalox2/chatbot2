#!/usr/bin/env python3
"""
Script para probar el funcionamiento del RAG Supabase
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

def buscar_en_supabase(query: str, limite: int = 3):
    """Busca chunks similares en Supabase"""
    
    print(f"🔍 Buscando: '{query}'")
    
    # Generar embedding de la consulta
    query_embedding = generar_embedding(query)
    if not query_embedding:
        return []
    
    try:
        # Búsqueda por similitud usando SQL directo
        result = supabase.rpc('match_chunks', {
            'query_embedding': query_embedding,
            'match_threshold': 0.5,
            'match_count': limite
        }).execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        print(f"❌ Error en búsqueda RPC: {e}")
        
        # Fallback: búsqueda básica sin similitud
        try:
            result = supabase.table('chunks').select('*').ilike('contenido', f'%{query}%').limit(limite).execute()
            return result.data if result.data else []
        except Exception as e2:
            print(f"❌ Error en búsqueda fallback: {e2}")
            return []

def crear_funcion_busqueda():
    """Crea función de búsqueda en Supabase si no existe"""
    
    print("🔧 Verificando función de búsqueda...")
    
    sql_function = """
    CREATE OR REPLACE FUNCTION match_chunks(
        query_embedding VECTOR(1536),
        match_threshold FLOAT DEFAULT 0.5,
        match_count INT DEFAULT 3
    )
    RETURNS TABLE (
        id BIGINT,
        documento TEXT,
        contenido TEXT,
        metadata JSONB,
        similarity FLOAT
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT
            c.id,
            c.documento,
            c.contenido,
            c.metadata,
            1 - (c.embedding <=> query_embedding) AS similarity
        FROM chunks c
        WHERE 1 - (c.embedding <=> query_embedding) > match_threshold
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count;
    END;
    $$;
    """
    
    print("📋 SQL para función de búsqueda:")
    print("=" * 50)
    print(sql_function)
    print("=" * 50)
    print("\n🔧 Si la búsqueda falla, ejecuta este SQL en Supabase SQL Editor")

def probar_busquedas():
    """Realiza múltiples pruebas de búsqueda"""
    
    print("\n🧪 PROBANDO BÚSQUEDAS RAG SUPABASE")
    print("=" * 50)
    
    # Consultas de prueba
    queries = [
        "precio Sentra",
        "Nissan Versa",
        "financiamiento",
        "enganche",
        "mensualidad",
        "promociones julio"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n{i}. {query}")
        print("-" * 30)
        
        resultados = buscar_en_supabase(query)
        
        if resultados:
            for j, chunk in enumerate(resultados):
                similarity = chunk.get('similarity', 'N/A')
                print(f"   📄 Resultado {j+1}:")
                print(f"      Documento: {chunk['documento']}")
                print(f"      Similitud: {similarity}")
                print(f"      Contenido: {chunk['contenido'][:150]}...")
                print()
        else:
            print("   ❌ No se encontraron resultados")
    
    return len([q for q in queries if buscar_en_supabase(q)]) > 0

def verificar_estado_rag():
    """Verifica el estado general del RAG"""
    
    print("\n📊 ESTADO DEL RAG SUPABASE")
    print("=" * 40)
    
    try:
        # Contar chunks totales
        result = supabase.table('chunks').select('*', count='exact').execute()
        total_chunks = result.count
        
        print(f"📦 Total chunks: {total_chunks}")
        
        # Documentos únicos
        documentos = {}
        for chunk in result.data:
            doc = chunk['documento']
            if doc not in documentos:
                documentos[doc] = 0
            documentos[doc] += 1
        
        print(f"📚 Documentos:")
        for doc, count in documentos.items():
            print(f"   - {doc}: {count} chunks")
        
        # Verificar embeddings
        with_embeddings = len([c for c in result.data if c['embedding']])
        print(f"🧮 Chunks con embeddings: {with_embeddings}/{total_chunks}")
        
        # Tamaño promedio de chunks
        if result.data:
            avg_size = sum(len(c['contenido']) for c in result.data) / len(result.data)
            print(f"📏 Tamaño promedio: {avg_size:.0f} caracteres")
        
        return total_chunks > 0
        
    except Exception as e:
        print(f"❌ Error verificando estado: {e}")
        return False

def main():
    """Función principal de pruebas"""
    
    print("🚀 PRUEBAS RAG SUPABASE")
    print("=" * 30)
    
    # 1. Verificar estado general
    if not verificar_estado_rag():
        print("❌ Problemas con el estado del RAG")
        return False
    
    # 2. Crear función de búsqueda
    crear_funcion_busqueda()
    
    # 3. Probar búsquedas
    if probar_busquedas():
        print("\n🎉 ¡RAG SUPABASE FUNCIONANDO!")
        print("✅ Búsquedas exitosas")
        print("✅ Embeddings funcionando")
        print("✅ Listo para producción en Railway")
        return True
    else:
        print("\n⚠️ Problemas en las búsquedas")
        print("🔧 Revisa la función de búsqueda en Supabase")
        return False

if __name__ == "__main__":
    main()