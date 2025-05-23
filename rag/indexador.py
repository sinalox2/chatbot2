from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
import os


# Ruta raíz del proyecto
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Carga de variables de entorno
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

def cargar_documentos():
    data_path = ROOT_DIR
    loader = DirectoryLoader(data_path, glob="**/*.pdf", loader_cls=PyPDFLoader)
    return loader.load()

def crear_indice():
    documentos = cargar_documentos()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    docs = splitter.split_documents(documentos)

    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    db = FAISS.from_documents(docs, embeddings)
    db.save_local(os.path.join(ROOT_DIR, "vector_db_sicrea"))
    print("✅ Índice creado y guardado en /rag/vector_db_sicrea")

if __name__ == "__main__":
    crear_indice()