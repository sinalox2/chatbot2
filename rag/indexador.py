from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
import os
import sys

# Agregar el directorio padre al path para importar supabase_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from supabase_client import supabase
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

# Ruta raíz del proyecto
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Carga de variables de entorno
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

def cargar_documentos():
    data_path = os.path.join(ROOT_DIR, "rag", "data")
    if not os.path.exists(data_path):
        os.makedirs(data_path)
    
    # Cargar PDFs
    pdf_loader = DirectoryLoader(data_path, glob="**/*.pdf", loader_cls=PyPDFLoader)
    pdf_docs = pdf_loader.load()
    
    # Cargar Markdowns (como precios.md)
    from langchain_community.document_loaders import TextLoader
    md_loader = DirectoryLoader(data_path, glob="**/*.md", loader_cls=TextLoader)
    md_docs = md_loader.load()
    
    return pdf_docs + md_docs

def subir_a_supabase(docs, embeddings_model):
    """Sube los documentos a Supabase"""
    if not HAS_SUPABASE or not supabase:
        print("⚠️ Supabase no disponible, saltando indexación en nube")
        return
    
    print(f"⬆️ Subiendo {len(docs)} chunks a Supabase...")
    
    chunks_to_insert = []
    for i, doc in enumerate(docs):
        embedding = embeddings_model.embed_query(doc.page_content)
        chunk_data = {
            'documento': os.path.basename(doc.metadata.get('source', 'unknown')),
            'chunk_index': i,
            'contenido': doc.page_content,
            'metadata': doc.metadata,
            'embedding': embedding
        }
        chunks_to_insert.append(chunk_data)
    
    # Insertar en lotes de 50
    batch_size = 50
    for i in range(0, len(chunks_to_insert), batch_size):
        batch = chunks_to_insert[i:i + batch_size]
        try:
            supabase.table('chunks').insert(batch).execute()
            print(f"   ✅ Lote {i//batch_size + 1} subido")
        except Exception as e:
            print(f"   ❌ Error subiendo lote {i//batch_size + 1}: {e}")

def crear_indice(use_supabase=True):
    print("📂 Cargando documentos...")
    documentos = cargar_documentos()
    if not documentos:
        print("⚠️ No se encontraron documentos para indexar")
        return

    print(f"✂️ Dividiendo {len(documentos)} documentos en chunks...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    docs = splitter.split_documents(documentos)

    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    
    # Guardar localmente (FAISS)
    print("💾 Creando índice local FAISS...")
    db = FAISS.from_documents(docs, embeddings)
    db_path = os.path.join(ROOT_DIR, "vector_db_sicrea")
    db.save_local(db_path)
    print(f"✅ Índice local guardado en {db_path}")

    # Subir a Supabase
    if use_supabase:
        subir_a_supabase(docs, embeddings)
        print("✅ Indexación en Supabase completada")

if __name__ == "__main__":
    crear_indice()