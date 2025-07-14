#!/usr/bin/env python3
"""
Migrador simplificado que usa el RAG local directamente
"""

import os
import sys
import json
import openai
from typing import List, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import supabase

# Configurar OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

def cargar_documentos_rag():
    """Carga documentos del directorio RAG"""
    
    print("📂 Cargando documentos del directorio RAG...")
    
    rag_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rag', 'data')
    documentos = []
    
    # Leer archivo de precios (markdown)
    precios_path = os.path.join(rag_data_dir, 'precios.md')
    if os.path.exists(precios_path):
        with open(precios_path, 'r', encoding='utf-8') as f:
            content = f.read()
            documentos.append({
                'nombre': 'precios.md',
                'contenido': content,
                'tipo': 'markdown'
            })
            print(f"   ✅ precios.md cargado ({len(content)} chars)")
    
    # Buscar otros archivos de texto
    for filename in os.listdir(rag_data_dir):
        if filename.endswith('.txt'):
            filepath = os.path.join(rag_data_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    documentos.append({
                        'nombre': filename,
                        'contenido': content,
                        'tipo': 'text'
                    })
                    print(f"   ✅ {filename} cargado ({len(content)} chars)")
            except Exception as e:
                print(f"   ⚠️ Error leyendo {filename}: {e}")
    
    print(f"   📊 Total documentos: {len(documentos)}")
    return documentos

def dividir_en_chunks(texto: str, max_chars: int = 1000) -> List[str]:
    """Divide texto en chunks más pequeños"""
    
    chunks = []
    palabras = texto.split()
    chunk_actual = []
    chars_actuales = 0
    
    for palabra in palabras:
        if chars_actuales + len(palabra) + 1 > max_chars and chunk_actual:
            chunks.append(' '.join(chunk_actual))
            chunk_actual = [palabra]
            chars_actuales = len(palabra)
        else:
            chunk_actual.append(palabra)
            chars_actuales += len(palabra) + 1
    
    if chunk_actual:
        chunks.append(' '.join(chunk_actual))
    
    return chunks

def generar_embedding(texto: str):
    """Genera embedding usando OpenAI"""
    
    try:
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=texto
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"   ❌ Error generando embedding: {e}")
        return None

def procesar_documentos(documentos: List[Dict]) -> List[Dict]:
    """Procesa documentos en chunks con embeddings"""
    
    print("\n🔄 Procesando documentos en chunks...")
    
    chunks_procesados = []
    
    for doc in documentos:
        print(f"\n   📄 Procesando: {doc['nombre']}")
        
        # Dividir en chunks
        chunks = dividir_en_chunks(doc['contenido'])
        print(f"      🔀 Dividido en {len(chunks)} chunks")
        
        for i, chunk_texto in enumerate(chunks):
            if len(chunk_texto.strip()) < 50:  # Skip chunks muy pequeños
                continue
                
            print(f"      🧮 Generando embedding para chunk {i+1}/{len(chunks)}...", end="")
            
            # Generar embedding
            embedding = generar_embedding(chunk_texto)
            
            if embedding:
                chunk_data = {
                    'documento': doc['nombre'],
                    'chunk_index': i,
                    'contenido': chunk_texto,
                    'metadata': {
                        'tipo': doc['tipo'],
                        'chars': len(chunk_texto),
                        'palabras': len(chunk_texto.split())
                    },
                    'embedding': embedding
                }
                
                chunks_procesados.append(chunk_data)
                print(" ✅")
            else:
                print(" ❌")
    
    print(f"\n   📊 Total chunks procesados: {len(chunks_procesados)}")
    return chunks_procesados

def subir_a_supabase(chunks: List[Dict]) -> bool:
    """Sube chunks a Supabase"""
    
    print(f"\n⬆️ Subiendo {len(chunks)} chunks a Supabase...")
    
    exitosos = 0
    errores = 0
    
    for i, chunk in enumerate(chunks):
        try:
            result = supabase.table('chunks').insert(chunk).execute()
            
            if result.data:
                exitosos += 1
                print(f"   ✅ Chunk {i+1}/{len(chunks)}: {chunk['documento']} [{chunk['chunk_index']}]")
            else:
                errores += 1
                print(f"   ❌ Error chunk {i+1}: Sin datos retornados")
                
        except Exception as e:
            errores += 1
            print(f"   ❌ Error chunk {i+1}: {e}")
    
    print(f"\n📊 Resumen:")
    print(f"   ✅ Exitosos: {exitosos}")
    print(f"   ❌ Errores: {errores}")
    print(f"   📈 Tasa de éxito: {(exitosos/(exitosos+errores)*100):.1f}%")
    
    return exitosos > 0

def verificar_supabase():
    """Verifica que la migración fue exitosa"""
    
    print("\n🔍 Verificando migración...")
    
    try:
        # Contar chunks
        result = supabase.table('chunks').select('*', count='exact').execute()
        total = result.count
        
        print(f"   📊 Total chunks: {total}")
        
        # Documentos únicos
        docs = set([chunk['documento'] for chunk in result.data])
        print(f"   📚 Documentos: {len(docs)}")
        for doc in sorted(docs):
            doc_chunks = [c for c in result.data if c['documento'] == doc]
            print(f"      - {doc}: {len(doc_chunks)} chunks")
        
        # Prueba de contenido
        if result.data:
            sample = result.data[0]
            print(f"\n   📄 Muestra del primer chunk:")
            print(f"      Documento: {sample['documento']}")
            print(f"      Contenido: {sample['contenido'][:100]}...")
            print(f"      Embedding: {'✅' if sample['embedding'] else '❌'}")
        
        return total > 0
        
    except Exception as e:
        print(f"   ❌ Error verificando: {e}")
        return False

def main():
    """Proceso principal"""
    
    print("🚀 MIGRACIÓN SIMPLIFICADA RAG → SUPABASE")
    print("="*50)
    
    # Verificar configuración
    if not openai.api_key:
        print("❌ OPENAI_API_KEY no configurada")
        return False
    
    if not supabase:
        print("❌ Supabase no conectado")
        return False
    
    # 1. Cargar documentos
    documentos = cargar_documentos_rag()
    if not documentos:
        print("❌ No se encontraron documentos")
        return False
    
    # 2. Procesar en chunks
    chunks = procesar_documentos(documentos)
    if not chunks:
        print("❌ No se procesaron chunks")
        return False
    
    # 3. Subir a Supabase
    if subir_a_supabase(chunks):
        # 4. Verificar
        if verificar_supabase():
            print("\n🎉 ¡MIGRACIÓN EXITOSA!")
            return True
        else:
            print("\n⚠️ Migración subida pero hay problemas")
            return False
    else:
        print("\n❌ Error en la migración")
        return False

if __name__ == "__main__":
    main()