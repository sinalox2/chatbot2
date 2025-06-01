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

# Verificar variables ANTES de cargar .env
print("🔍 ANTES de load_dotenv():")
api_key_antes = os.getenv("OPENAI_API_KEY")
if api_key_antes:
    print(f"❌ YA EXISTE una clave en el sistema: {api_key_antes[:10]}...{api_key_antes[-4:]}")
else:
    print("✅ No hay clave API en variables del sistema")

# Carga las variables de entorno
load_dotenv(override=True)  # override=True sobrescribe variables existentes

# Verificar que el archivo .env existe
env_path = os.path.join(os.getcwd(), '.env')
print(f"🔍 Buscando archivo .env en: {env_path}")
print(f"📁 ¿Existe el archivo .env? {os.path.exists(env_path)}")

# Leer directamente el archivo .env
try:
    with open('.env', 'r') as f:
        env_content = f.read()
    print("📄 Contenido del archivo .env:")
    for line in env_content.split('\n'):
        if 'OPENAI_API_KEY' in line:
            parts = line.split('=')
            if len(parts) >= 2:
                key_from_file = parts[1].strip()
                print(f"🔑 Clave en archivo .env: {key_from_file[:10]}...{key_from_file[-4:]}")
except Exception as e:
    print(f"❌ Error leyendo .env: {e}")

# Debug: Verificar que la clave API se carga correctamente
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    print("✅ Clave API de OpenAI cargada correctamente")
    print(f"🔑 Primeros 10 caracteres: {api_key[:10]}...")
    print(f"🔑 Últimos 4 caracteres: ...{api_key[-4:]}")
else:
    print("❌ No se pudo cargar la clave API de OpenAI")
    print("❌ Verifica que tu archivo .env contenga: OPENAI_API_KEY=tu_clave_aqui")

# Forzar la clave API directamente (temporal)
api_key_forzada = "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"  # Reemplaza con tu nueva clave después de cambiarla

# Inicializar el cliente OpenAI
try:
    client = openai.OpenAI(api_key=api_key_forzada)
    print(f"✅ Cliente OpenAI inicializado con clave forzada: {api_key_forzada[:10]}...{api_key_forzada[-4:]}")
except Exception as e:
    print(f"❌ Error al inicializar cliente OpenAI: {e}")

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))           # Obtiene la ruta absoluta del directorio donde se encuentra este archivo app.py
vector_db_path = os.path.join(ROOT_DIR, "vector_db_sicrea")     # Define la ruta local donde se encuentra almacenada la base de datos vectorial FAISS
embeddings = OpenAIEmbeddings(openai_api_key=api_key_forzada)          # Inicializa los embeddings de OpenAI con la clave API forzada
vector_db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True) # Carga la base de datos vectorial FAISS desde la ruta local

def recuperar_contexto(pregunta):                               # Función para recuperar contexto relevante basado en la pregunta del usuario mediante búsqueda semántica
    resultados = vector_db.similarity_search(pregunta, k=2)     # Realiza una búsqueda de similitud en el vectorstore usando la pregunta como consulta, recuperando los 2 documentos más similares
    return "\n\n".join([doc.page_content for doc in resultados])# Une el contenido de las páginas encontradas en un solo string separado por saltos de línea dobles para proporcionar contexto al modelo

# Creación de la aplicación Flask, que manejará las solicitudes entrantes
app = Flask(__name__)

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
        nombre_perfil = request.values.get("ProfileName", "desconocido")

        messages = [{"role": "system", "content": prompt_sistema}]
        
        # Obtener historial (orden correcto de parámetros)
        historial = obtener_historial_conversacion(telefono_limpio, "historial_conversaciones")
        
        for entrada in historial:
            messages.append({"role": "user", "content": entrada["mensaje"]})
            messages.append({"role": "assistant", "content": entrada["respuesta"]})
        
        messages.append({
            "role": "user",
            "content": f"Información útil:\n{contexto}\n\nPregunta del cliente:\n{incoming_msg}"
        })

        # Verificar cliente antes de hacer la llamada
        if not api_key:
            raise Exception("No hay clave API de OpenAI disponible")

        print("🤖 Enviando solicitud a OpenAI...")
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        respuesta = completion.choices[0].message.content.strip()
        print("✅ Respuesta recibida de OpenAI")

        # Crear el diccionario lead con todos los campos necesarios
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
            # Guardar en CSV
            with open("leads.csv", mode="a", newline="", encoding="utf-8") as file:
                fieldnames = ["telefono", "mensaje", "respuesta", "timestamp", "fecha_entrada", "modelo_interes", "canal"]
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                if file.tell() == 0:
                    writer.writeheader()
                writer.writerow(lead)
            print("✅ Guardado en CSV exitosamente")

            try:
                # Insertar en historial de conversaciones
                insertar_en_historial(telefono_limpio, lead["mensaje"], lead["respuesta"], lead["timestamp"], "historial_conversaciones")
                
                # Insertar en tabla de leads
                insertar_en_tabla_leads(
                    telefono_limpio,
                    nombre_perfil,
                    lead["fecha_entrada"],
                    lead["modelo_interes"],
                    lead["canal"],
                    "leads_nissan"
                )
                print("✅ Guardado en Supabase exitosamente")
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
    print("🚀 Iniciando aplicación Flask...")
    app.run(host="0.0.0.0", port=5001, debug=True)