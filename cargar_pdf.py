from supabase import create_client
import os
import numpy as np
from langchain.embeddings import OpenAIEmbeddings
from scipy.spatial.distance import cosine 
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter


# Conexión con Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Embeddings
embedding_model = OpenAIEmbeddings()

def cargar_documentos_en_supabase(directorio):
    print("📥 Cargando documentos desde:", directorio)
    loader = PyPDFLoader(directorio)
    documentos = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_documents(documentos)

    for chunk in chunks:
        texto = chunk.page_content
        metadata = chunk.metadata
        vector = embedding_model.embed_query(texto)

        supabase.table("rag_chunks").insert({
            "contenido": texto,
            "embedding": vector,
            "fuente": metadata.get("source", "desconocido")
        }).execute()
    print("✅ Documentos cargados correctamente.")

def buscar_documentos_similares(query, k=3):
    print("🔎 Buscando documentos similares en Supabase...")
    query_vector = embedding_model.embed_query(query)

    # Obtener todos los chunks desde Supabase
    response = supabase.table("rag_chunks").select("*").execute()
    data = response.data

    if not data:
        print("⚠️ No hay documentos en Supabase.")
        return []

    # Calcular similitud
    resultados = []
    for row in data:
        chunk_vector = row.get("embedding")
        if chunk_vector:
            similitud = 1 - cosine(query_vector, chunk_vector)
            resultados.append((similitud, row.get("contenido"), row.get("fuente")))

    # Ordenar por similitud
    resultados.sort(reverse=True, key=lambda x: x[0])
    return resultados[:k]

if __name__ == "__main__":
    modo = input("Selecciona modo: [c] Cargar documentos | [q] Consultar RAG\n> ").lower()

    if modo == "c":
        ruta = input("📁 Ruta del documento PDF: ")
        cargar_documentos_en_supabase(ruta)
    elif modo == "q":
        pregunta = input("🧠 Escribe tu pregunta: ")
        resultados = buscar_documentos_similares(pregunta)

        for idx, (sim, contenido, fuente) in enumerate(resultados):
            print(f"\n🔹 Resultado {idx+1} ({fuente}) - Similitud: {sim:.4f}")
            print(f"{contenido[:400]}...")