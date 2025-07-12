import os
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.docstore.document import Document

# Cargar la base vectorial previamente guardada
def cargar_vectorstore():
    embeddings = OpenAIEmbeddings()
    # Path is relative to the main project directory
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vector_db_sicrea")
    db = FAISS.load_local(db_path, embeddings, allow_dangerous_deserialization=True)
    return db

# Recuperar contexto relevante dado un mensaje de usuario
def recuperar_contexto(pregunta_usuario, k=3):
    db = cargar_vectorstore()
    documentos_similares = db.similarity_search(pregunta_usuario, k=k)
    
    # Combinar el contenido en un solo string
    contexto = "\n".join([doc.page_content for doc in documentos_similares])
    return contexto

# Solo para pruebas
if __name__ == "__main__":
    pregunta = "¿Cuáles son los requisitos para obtener un financiamiento con SICREA?"
    contexto = recuperar_contexto(pregunta)
    print("🧠 Contexto recuperado:")
    print(contexto)