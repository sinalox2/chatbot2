#!/usr/bin/env python3
"""
Script para migrar documentos del RAG local (FAISS) a Supabase
de manera limpia y optimizada.
"""

import os
import sys
import pickle
import numpy as np
from typing import List, Dict, Any
import openai
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import supabase

# Configurar OpenAI para generar embeddings
openai.api_key = os.getenv("OPENAI_API_KEY")

def cargar_datos_rag_local():
    """Carga los datos del RAG local (FAISS + pickle)"""
    
    print("📂 Cargando datos del RAG local...")
    
    try:
        # Rutas de archivos
        vector_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'vector_db_sicrea')
        faiss_path = os.path.join(vector_dir, 'index.faiss')
        pickle_path = os.path.join(vector_dir, 'index.pkl')
        
        # Verificar que existen los archivos
        if not os.path.exists(faiss_path) or not os.path.exists(pickle_path):
            raise FileNotFoundError("Archivos del RAG local no encontrados")
        
        # Cargar metadatos
        with open(pickle_path, 'rb') as f:
            metadata = pickle.load(f)
        
        print(f"   ✅ Metadatos cargados: {len(metadata)} chunks")
        
        # Cargar índice FAISS
        import faiss
        index = faiss.read_index(faiss_path)
        
        print(f"   ✅ Índice FAISS cargado: {index.ntotal} vectores")
        
        # Extraer vectores
        vectors = []
        for i in range(index.ntotal):
            vector = index.reconstruct(i)
            vectors.append(vector.tolist())
        
        print(f"   ✅ Vectores extraídos: {len(vectors)}")
        
        return metadata, vectors
        
    except Exception as e:
        print(f"   ❌ Error cargando RAG local: {e}")
        return None, None

def procesar_chunks_para_supabase(metadata: List[Dict], vectors: List[List[float]]):
    """Procesa los chunks para formato Supabase"""
    
    print("🔄 Procesando chunks para Supabase...")
    
    chunks_procesados = []
    
    for i, (meta, vector) in enumerate(zip(metadata, vectors)):
        try:
            # Extraer información del chunk
            contenido = meta.get('chunk', '')
            documento = meta.get('source', f'documento_{i}')
            
            # Limpiar nombre del documento
            if documento.startswith('rag/data/'):
                documento = documento.replace('rag/data/', '')
            
            chunk_data = {
                'documento': documento,
                'chunk_index': i,
                'contenido': contenido,
                'metadata': {
                    'source': meta.get('source', ''),
                    'chunk_size': len(contenido),
                    'original_index': i
                },
                'embedding': vector
            }
            
            chunks_procesados.append(chunk_data)
            
        except Exception as e:
            print(f"   ⚠️ Error procesando chunk {i}: {e}")
            continue
    
    print(f"   ✅ {len(chunks_procesados)} chunks procesados exitosamente")
    return chunks_procesados

def subir_chunks_a_supabase(chunks: List[Dict[str, Any]], batch_size: int = 50):
    """Sube los chunks a Supabase en lotes"""
    
    print(f"⬆️ Subiendo {len(chunks)} chunks a Supabase...")
    
    total_exitosos = 0
    total_errores = 0
    
    # Procesar en lotes
    for i in tqdm(range(0, len(chunks), batch_size), desc="Subiendo lotes"):
        lote = chunks[i:i + batch_size]
        
        try:
            # Insertar lote
            result = supabase.table('chunks').insert(lote).execute()
            
            if result.data:
                total_exitosos += len(result.data)
                print(f"   ✅ Lote {i//batch_size + 1}: {len(result.data)} chunks subidos")
            else:
                print(f"   ⚠️ Lote {i//batch_size + 1}: Sin datos retornados")
                
        except Exception as e:
            total_errores += len(lote)
            print(f"   ❌ Error en lote {i//batch_size + 1}: {e}")
            continue
    
    print(f"\n📊 Resumen de migración:")
    print(f"   ✅ Exitosos: {total_exitosos}")
    print(f"   ❌ Errores: {total_errores}")
    print(f"   📈 Tasa de éxito: {(total_exitosos/(total_exitosos+total_errores)*100):.1f}%")
    
    return total_exitosos > 0

def verificar_migracion():
    """Verifica que la migración fue exitosa"""
    
    print("\n🔍 Verificando migración...")
    
    try:
        # Contar chunks subidos
        result = supabase.table('chunks').select('id', count='exact').execute()
        total_chunks = result.count
        
        print(f"   📊 Total chunks en Supabase: {total_chunks}")
        
        # Verificar documentos únicos
        result = supabase.table('chunks').select('documento').execute()
        documentos_unicos = set([chunk['documento'] for chunk in result.data])
        
        print(f"   📚 Documentos únicos: {len(documentos_unicos)}")
        for doc in sorted(documentos_unicos):
            print(f"      - {doc}")
        
        # Probar búsqueda
        test_query = "precio"
        test_embedding = generar_embedding_test(test_query)
        
        if test_embedding:
            result = supabase.rpc('buscar_chunks_similares', {
                'query_embedding': test_embedding,
                'match_count': 3
            }).execute()
            
            print(f"   🔍 Prueba de búsqueda '{test_query}': {len(result.data)} resultados")
            
            for i, chunk in enumerate(result.data[:2]):
                print(f"      {i+1}. {chunk['documento']} (sim: {chunk['similarity']:.3f})")
                print(f"         {chunk['contenido'][:100]}...")
        
        return total_chunks > 0
        
    except Exception as e:
        print(f"   ❌ Error en verificación: {e}")
        return False

def generar_embedding_test(texto: str):
    """Genera embedding de prueba para verificación"""
    try:
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=texto
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"   ⚠️ No se pudo generar embedding de prueba: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Iniciando migración de RAG local a Supabase...")
    
    # Verificar conexiones
    if not supabase:
        print("❌ Error: No se pudo conectar a Supabase")
        sys.exit(1)
    
    if not openai.api_key:
        print("❌ Error: OPENAI_API_KEY no configurada")
        sys.exit(1)
    
    # 1. Cargar datos del RAG local
    metadata, vectors = cargar_datos_rag_local()
    
    if metadata is None or vectors is None:
        print("❌ No se pudieron cargar los datos del RAG local")
        sys.exit(1)
    
    # 2. Procesar chunks
    chunks_procesados = procesar_chunks_para_supabase(metadata, vectors)
    
    if not chunks_procesados:
        print("❌ No se pudieron procesar los chunks")
        sys.exit(1)
    
    # 3. Subir a Supabase
    if subir_chunks_a_supabase(chunks_procesados):
        # 4. Verificar migración
        if verificar_migracion():
            print("\n🎉 Migración completada exitosamente!")
            print("✅ RAG Supabase listo para usar")
        else:
            print("\n⚠️ Migración subida pero hay problemas en verificación")
    else:
        print("\n❌ Error en la migración")