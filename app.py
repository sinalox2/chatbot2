from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
from dotenv import load_dotenv
import openai
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from dotenv import load_dotenv
import os

load_dotenv()
openai_api_key="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"

client = openai.OpenAI(api_key=openai_api_key)
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

def recuperar_contexto(pregunta):
    vector_db_path = os.path.join(ROOT_DIR, "vector_db_sicrea")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True)
    resultados = db.similarity_search(pregunta, k=3)
    return "\n\n".join([doc.page_content for doc in resultados])

app = Flask(__name__)  # <-- ESTA LÍNEA ES CLAVE

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    print("== Encabezados ==")
    print(request.headers)
    print("== Formulario ==")
    print(request.form)

    incoming_msg = request.values.get("Body", "").lower()
    print(f"Mensaje entrante: {incoming_msg}")

    resp = MessagingResponse()
    msg = resp.message()

    try:
        contexto = recuperar_contexto(incoming_msg)

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un asesor virtual de Nissan. Tu objetivo es responder de forma breve, clara y útil a los clientes interesados en autos nuevos o seminuevos. "
                        "Evita dar explicaciones largas o demasiado técnicas. Sé profesional, amable y directo al punto. Usa emojis solo si ayudan a simplificar o hacer más amigable el mensaje, sin abusar. "
                        "No repitas información ya dicha."
                    )
                },
                {
                    "role": "user",
                    "content": f"Información útil:\n{contexto}\n\nPregunta del cliente:\n{incoming_msg}"
                }
            ]
        )

        respuesta = completion.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Error al generar respuesta:", e)
        respuesta = "Lo siento, tuvimos un problema técnico al procesar tu mensaje. Intenta nuevamente más tarde."

    msg.body(respuesta)
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)