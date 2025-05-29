from flask import Flask, request                                # Importación del framework Flask para crear la aplicación web y manejar solicitudes HTTP
from flask import Response                                      # Importación de Response para construir respuestas HTTP personalizadas
import html                                                     # Importación del módulo html para escapar caracteres HTML y evitar inyección de código
from twilio.twiml.messaging_response import MessagingResponse   # Importación de MessagingResponse para construir respuestas compatibles con Twilio WhatsApp
import os                                                       # Importación del módulo os para manejar rutas y variables de entorno
from dotenv import load_dotenv                                  # Importación de load_dotenv para cargar variables de entorno desde un archivo .env
import openai                                                   # Importación de la biblioteca OpenAI para interactuar con la API de OpenAI
from langchain_community.vectorstores import FAISS              # Importación del vectorstore FAISS para búsqueda semántica eficiente
from langchain_openai import OpenAIEmbeddings                   # Importación de OpenAIEmbeddings para generar embeddings con OpenAI
import csv                                                      # Importación del módulo csv para manejar archivos CSV
from datetime import datetime                                   # Importación de datetime para registrar marcas de tiempo
from supabase_client import insertar_en_tabla_leads, insertar_en_historial, obtener_historial_conversacion, guardar_lead

load_dotenv()                                                   # Carga las variables de entorno definidas en un archivo .env al entorno del sistema

openai.api_key = os.getenv("OPENAI_API_KEY")   #<---- clave opanai # Configuración de la clave API de OpenAI obtenida de las variables de entorno para autenticación
client = openai                                                 # Alias para el cliente OpenAI para facilitar llamadas posteriores


ROOT_DIR = os.path.abspath(os.path.dirname(__file__))           # Obtiene la ruta absoluta del directorio donde se encuentra este archivo app.py
vector_db_path = os.path.join(ROOT_DIR, "vector_db_sicrea")     # Define la ruta local donde se encuentra almacenada la base de datos vectorial FAISS
embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY")) # Inicializa los embeddings de OpenAI con la clave API para convertir texto en vectores
vector_db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True) # Carga la base de datos vectorial FAISS desde la ruta local, permitiendo deserialización peligrosa (por seguridad, debe usarse con precaución)


def recuperar_contexto(pregunta):                               # Función para recuperar contexto relevante basado en la pregunta del usuario mediante búsqueda semántica

    resultados = vector_db.similarity_search(pregunta, k=2)     # Realiza una búsqueda de similitud en el vectorstore usando la pregunta como consulta, recuperando los 2 documentos más similares

    return "\n\n".join([doc.page_content for doc in resultados])# Une el contenido de las páginas encontradas en un solo string separado por saltos de línea dobles para proporcionar contexto al modelo

# Creación de la aplicación Flask, que manejará las solicitudes entrantes
app = Flask(__name__)  # <-- ESTA LÍNEA ES CLAVE

# Definición de la ruta '/whatsapp' que aceptará solicitudes POST provenientes de Twilio WhatsApp
@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    print("== Encabezados ==")
    print(request.headers)
    print("== Formulario ==")
    print(request.form)

    with open("prompt_sistema_nissan.txt", "r", encoding="utf-8") as f:
        prompt_sistema = f.read().strip()

    incoming_msg = request.values.get("Body", "").lower()
    print(f"Mensaje entrante: {incoming_msg}")

    resp = MessagingResponse()
    msg = resp.message()

    try:
        contexto = recuperar_contexto(incoming_msg)

        telefono = request.values.get("From", "")
        telefono_limpio = telefono.replace("whatsapp:", "")

        messages = [{"role": "system", "content": prompt_sistema}]
        historial = obtener_historial_conversacion("historial_conversaciones", telefono_limpio)
        for entrada in historial:
            messages.append({"role": "user", "content": entrada["mensaje"]})
            messages.append({"role": "assistant", "content": entrada["respuesta"]})
        messages.append({
            "role": "user",
            "content": f"Información útil:\n{contexto}\n\nPregunta del cliente:\n{incoming_msg}"
        })
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        respuesta = completion.choices[0].message.content.strip()

        lead = {
            "telefono": telefono_limpio,
            "mensaje": incoming_msg,
            "respuesta": respuesta,
            "timestamp": datetime.now().isoformat(),
            "fecha_entrada": datetime.now().date().isoformat(),
            "modelo_interes": "desconocido",
            "canal": "whatsapp"
        }

        try:
            with open("leads.csv", mode="a", newline="", encoding="utf-8") as file:
                fieldnames = ["telefono", "mensaje", "respuesta", "timestamp", "fecha_entrada", "modelo_interes", "canal"]
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                if file.tell() == 0:
                    writer.writeheader()
                writer.writerow(lead)

            try:
                insertar_en_historial("historial_conversaciones", telefono_limpio, lead["mensaje"], lead["respuesta"], lead["timestamp"])
                insertar_en_tabla_leads("leads_nissan", lead)
            except Exception as e:
                print("⚠️ Error al insertar en Supabase:", e)

        except Exception as e:
            print("⚠️ Error al guardar en CSV:", e)

    except Exception as e:
        print("❌ Error al generar respuesta:", e)
        respuesta = "Lo siento, tuvimos un problema técnico al procesar tu mensaje. Intenta nuevamente más tarde."

    print(f"🟢 Respuesta enviada: {respuesta}")
    msg.body(html.escape(respuesta))
    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)