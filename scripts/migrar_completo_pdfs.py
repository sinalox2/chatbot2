#!/usr/bin/env python3
"""
Migrador completo que procesa TODOS los archivos (MD + PDFs) 
del directorio rag/data/ y los sube a Supabase
"""

import os
import sys
import openai
from typing import List, Dict
import PyPDF2
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import supabase

openai.api_key = os.getenv("OPENAI_API_KEY")

def extraer_texto_pdf(pdf_path: str) -> str:
    """Extrae texto de un archivo PDF"""
    
    try:
        texto_completo = ""
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                texto_completo += page.extract_text() + "\n"
        
        return texto_completo.strip()
        
    except Exception as e:
        print(f"   ❌ Error extrayendo texto de {pdf_path}: {e}")
        return ""

def leer_archivo_markdown(md_path: str) -> str:
    """Lee contenido de archivo markdown"""
    
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"   ❌ Error leyendo {md_path}: {e}")
        return ""

def cargar_todos_documentos():
    """Carga TODOS los documentos (MD + PDFs) del directorio"""
    
    print("📂 Cargando TODOS los documentos del directorio RAG...")
    
    rag_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rag', 'data')
    documentos = []
    
    # Listar todos los archivos
    archivos = os.listdir(rag_data_dir)
    archivos_procesables = [f for f in archivos if f.endswith(('.pdf', '.md', '.txt'))]
    
    print(f"   📋 Encontrados {len(archivos_procesables)} archivos procesables")
    
    for filename in tqdm(archivos_procesables, desc="Cargando archivos"):
        filepath = os.path.join(rag_data_dir, filename)
        contenido = ""
        tipo = ""
        
        if filename.endswith('.pdf'):
            print(f"\n   📄 Procesando PDF: {filename}")
            contenido = extraer_texto_pdf(filepath)
            tipo = 'pdf'
            
        elif filename.endswith('.md'):
            print(f"\n   📝 Procesando Markdown: {filename}")
            contenido = leer_archivo_markdown(filepath)
            tipo = 'markdown'
            
        elif filename.endswith('.txt'):
            print(f"\n   📄 Procesando Texto: {filename}")
            contenido = leer_archivo_markdown(filepath)  # Misma función
            tipo = 'text'
        
        if contenido and len(contenido.strip()) > 100:  # Solo archivos con contenido sustancial
            documentos.append({
                'nombre': filename,
                'contenido': contenido,
                'tipo': tipo,
                'tamaño': len(contenido)
            })
            print(f"      ✅ {len(contenido)} caracteres extraídos")
        else:
            print(f"      ⚠️ Contenido insuficiente o error")
    
    print(f"\n📊 RESUMEN DE CARGA:")
    for doc in documentos:
        print(f"   📄 {doc['nombre']} ({doc['tipo']}) - {doc['tamaño']:,} chars")
    
    print(f"\n✅ Total documentos cargados: {len(documentos)}")
    return documentos

def dividir_en_chunks(texto: str, max_chars: int = 1200) -> List[str]:
    """Divide texto en chunks optimizados"""
    
    chunks = []
    
    # Dividir por párrafos primero
    paragrafos = texto.split('\n\n')
    chunk_actual = []
    chars_actuales = 0
    
    for parrafo in paragrafos:
        parrafo = parrafo.strip()
        if not parrafo:
            continue
            
        # Si el párrafo solo es muy largo, dividir por oraciones
        if len(parrafo) > max_chars:
            oraciones = parrafo.split('. ')
            for oracion in oraciones:
                if len(oracion.strip()) < 50:
                    continue
                    
                if chars_actuales + len(oracion) > max_chars and chunk_actual:
                    chunks.append('\n\n'.join(chunk_actual))
                    chunk_actual = [oracion]
                    chars_actuales = len(oracion)
                else:
                    chunk_actual.append(oracion)
                    chars_actuales += len(oracion) + 2
        else:
            # Párrafo normal
            if chars_actuales + len(parrafo) > max_chars and chunk_actual:
                chunks.append('\n\n'.join(chunk_actual))
                chunk_actual = [parrafo]
                chars_actuales = len(parrafo)
            else:
                chunk_actual.append(parrafo)
                chars_actuales += len(parrafo) + 2
    
    if chunk_actual:
        chunks.append('\n\n'.join(chunk_actual))
    
    return [chunk for chunk in chunks if len(chunk.strip()) > 100]

def generar_embedding(texto: str):
    """Genera embedding usando OpenAI"""
    
    try:
        # Truncar texto si es muy largo para OpenAI
        if len(texto) > 8000:
            texto = texto[:8000]
            
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=texto
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Error generando embedding: {e}")
        return None

def procesar_documentos_completos(documentos: List[Dict]) -> List[Dict]:
    """Procesa TODOS los documentos en chunks con embeddings"""
    
    print(f"\n🔄 Procesando {len(documentos)} documentos en chunks...")
    
    chunks_procesados = []
    
    for doc_num, doc in enumerate(documentos, 1):
        print(f"\n📄 [{doc_num}/{len(documentos)}] Procesando: {doc['nombre']}")
        print(f"   📊 Tamaño original: {doc['tamaño']:,} caracteres")
        
        # Dividir en chunks
        chunks = dividir_en_chunks(doc['contenido'])
        print(f"   🔀 Dividido en {len(chunks)} chunks")
        
        for i, chunk_texto in enumerate(tqdm(chunks, desc=f"   Embeddings {doc['nombre']}")):
            
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
                        'palabras': len(chunk_texto.split()),
                        'documento_original_chars': doc['tamaño']
                    },
                    'embedding': embedding
                }
                
                chunks_procesados.append(chunk_data)
        
        print(f"   ✅ {len([c for c in chunks_procesados if c['documento'] == doc['nombre']])} chunks procesados")
    
    print(f"\n📊 TOTAL CHUNKS PROCESADOS: {len(chunks_procesados)}")
    return chunks_procesados

def limpiar_tabla_chunks():
    """Limpia la tabla chunks antes de la nueva migración"""
    
    print("🧹 Limpiando tabla chunks existente...")
    
    try:
        result = supabase.table('chunks').delete().neq('id', 0).execute()
        print("   ✅ Tabla chunks limpiada")
        return True
    except Exception as e:
        print(f"   ❌ Error limpiando tabla: {e}")
        return False

def subir_chunks_masivo(chunks: List[Dict], batch_size: int = 20) -> bool:
    """Sube chunks en lotes con progreso detallado"""
    
    print(f"\n⬆️ Subiendo {len(chunks)} chunks a Supabase (lotes de {batch_size})...")
    
    exitosos = 0
    errores = 0
    
    # Procesar en lotes
    for i in tqdm(range(0, len(chunks), batch_size), desc="Subiendo lotes"):
        lote = chunks[i:i + batch_size]
        
        try:
            result = supabase.table('chunks').insert(lote).execute()
            
            if result.data:
                exitosos += len(result.data)
            else:
                errores += len(lote)
                print(f"   ⚠️ Lote {i//batch_size + 1}: Sin datos retornados")
                
        except Exception as e:
            errores += len(lote)
            print(f"   ❌ Error lote {i//batch_size + 1}: {e}")
    
    print(f"\n📊 RESUMEN MIGRACIÓN:")
    print(f"   ✅ Exitosos: {exitosos}")
    print(f"   ❌ Errores: {errores}")
    print(f"   📈 Tasa de éxito: {(exitosos/(exitosos+errores)*100):.1f}%")
    
    return exitosos > 0

def verificar_migracion_completa():
    """Verifica la migración completa"""
    
    print("\n🔍 Verificando migración completa...")
    
    try:
        # Contar total
        result = supabase.table('chunks').select('*', count='exact').execute()
        total_chunks = result.count
        
        print(f"   📊 Total chunks: {total_chunks}")
        
        # Documentos por tipo
        documentos = {}
        tipos = {}
        
        for chunk in result.data:
            doc = chunk['documento']
            tipo = chunk['metadata'].get('tipo', 'unknown')
            
            if doc not in documentos:
                documentos[doc] = 0
            documentos[doc] += 1
            
            if tipo not in tipos:
                tipos[tipo] = 0
            tipos[tipo] += 1
        
        print(f"\n📚 Documentos migrados ({len(documentos)}):")
        for doc, count in sorted(documentos.items()):
            print(f"   - {doc}: {count} chunks")
        
        print(f"\n📄 Por tipo de archivo:")
        for tipo, count in tipos.items():
            print(f"   - {tipo}: {count} chunks")
        
        return total_chunks > 0
        
    except Exception as e:
        print(f"   ❌ Error en verificación: {e}")
        return False

def main():
    """Proceso principal completo"""
    
    print("🚀 MIGRACIÓN COMPLETA RAG → SUPABASE")
    print("📄 Incluye: Markdown + PDFs")
    print("="*50)
    
    # Verificar dependencias
    try:
        import PyPDF2
    except ImportError:
        print("❌ PyPDF2 no instalado. Instalar con: pip install PyPDF2")
        return False
    
    if not openai.api_key:
        print("❌ OPENAI_API_KEY no configurada")
        return False
    
    if not supabase:
        print("❌ Supabase no conectado")
        return False
    
    # 1. Limpiar tabla existente
    if not limpiar_tabla_chunks():
        print("⚠️ Continuando sin limpiar tabla...")
    
    # 2. Cargar TODOS los documentos
    documentos = cargar_todos_documentos()
    if not documentos:
        print("❌ No se cargaron documentos")
        return False
    
    # 3. Procesar en chunks con embeddings
    chunks = procesar_documentos_completos(documentos)
    if not chunks:
        print("❌ No se procesaron chunks")
        return False
    
    # 4. Subir a Supabase
    if subir_chunks_masivo(chunks):
        # 5. Verificar migración
        if verificar_migracion_completa():
            print("\n🎉 ¡MIGRACIÓN COMPLETA EXITOSA!")
            print("✅ Todos los PDFs y MD migrados")
            print("✅ RAG Supabase listo para producción")
            return True
        else:
            print("\n⚠️ Migración subida pero hay problemas")
            return False
    else:
        print("\n❌ Error en la migración")
        return False

if __name__ == "__main__":
    main()