import openai
from dotenv import load_dotenv
import os

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un sistema de prueba"},
            {"role": "user", "content": "¿Puedes confirmarme que el API key funciona?"}
        ]
    )
    print("✅ API funcionando. Respuesta del modelo:\n")
    print(response.choices[0].message.content)
except Exception as e:
    print("❌ Error al conectar con OpenAI:")
    print(e)