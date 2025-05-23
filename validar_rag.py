from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from dotenv import load_dotenv
import os

def buscar_vector_db_path(root_dir, target_folder="vector_db_sicrea"):
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if target_folder in dirnames:
            return os.path.join(dirpath, target_folder)
    return None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
VECTOR_DB_PATH = buscar_vector_db_path(ROOT_DIR)

if not VECTOR_DB_PATH:
    print("❌ No se encontró la carpeta vector_db_sicrea en ninguna subcarpeta.")
    exit(1)
import openai

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Inicializa embeddings
embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

def validar_vector_db():
    try:
        db = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
        consulta = "¿Cuáles son los requisitos para obtener un crédito con SICREA?"
        resultados = db.similarity_search(consulta, k=3)

        if not resultados:
            print("⚠️ No se encontraron resultados. Verifica que los PDF tengan texto legible.")
        else:
            print("✅ Resultados encontrados:")
            for i, doc in enumerate(resultados, 1):
                print(f"\n🧩 Fragmento {i}:\n{doc.page_content.strip()[:1000]}")
    except Exception as e:
        print("❌ Error al validar la base vectorial:", e)

if __name__ == "__main__":
    print("🤖 Asistente RAG listo. Escribe tu pregunta (o 'salir' para terminar):")
    try:
        db = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
    except Exception as e:
        print("❌ Error al cargar la base vectorial:", e)
        exit(1)

    while True:
        consulta = input("\n💬 Tú: ")
        if consulta.strip().lower() in {"salir", "exit", "quit"}:
            print("👋 Hasta luego.")
            break
        try:
            resultados = db.similarity_search(consulta, k=3)
            if not resultados:
                print("⚠️ No se encontraron resultados.")
            else:
                print("🤖 Respuesta basada en contexto:")
                for i, doc in enumerate(resultados, 1):
                    print(f"\n🧩 Fragmento {i}:\n{doc.page_content.strip()[:1000]}")
        except Exception as e:
            print("❌ Error en la búsqueda:", e)