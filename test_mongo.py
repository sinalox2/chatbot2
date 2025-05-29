import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

# Cargar variables del archivo .env
load_dotenv()

# Conectar con MongoDB
try:
    
    uri = "mongodb+srv://sinalox:Ji1NaXlLBO3zt5RH@chatbotnissan.y2ml5q6.mongodb.net/?retryWrites=true&w=majority&appName=ChatBotNissan"
    client = MongoClient(uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client["nissan"]
    collection = db["leads"]

    # Documento de prueba
    lead_test = {
        "telefono": "+521234567890",
        "mensaje": "Este es un mensaje de prueba",
        "respuesta": "Gracias por tu interés en Nissan.",
        "timestamp": datetime.now().isoformat()
    }

    # Insertar en la colección
    result = collection.insert_one(lead_test)
    print("✅ Documento insertado con ID:", result.inserted_id)

except Exception as e:
    print("❌ Error al conectar o insertar en MongoDB:", e)