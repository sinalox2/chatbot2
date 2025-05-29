from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def obtener_historial_conversacion(telefono, nombre_tabla="historial_conversaciones"):
    try:
        response = supabase.table(nombre_tabla).select("mensaje, respuesta").eq("telefono", telefono).order("timestamp", desc=False).execute()
        if response.data:
            return response.data
        else:
            return []
    except Exception as e:
        print("❌ Error al obtener historial:", e)
        return []



# Función para insertar datos en una tabla de Supabase
def insertar_en_tabla(nombre_tabla, datos):
    try:
        response = supabase.table(nombre_tabla).insert(datos).execute()
        if response.data:
            print("✅ Insertado correctamente en Supabase")
            return True
        else:
            print("❌ Falló la inserción.")
            return False
    except Exception as e:
        print("❌ Error al insertar en Supabase:", e)
        return False

# Función para insertar historial de conversación
def insertar_historial(telefono, mensaje, respuesta, timestamp, nombre_tabla="historial_conversaciones"):
    datos = {
        "telefono": telefono,
        "mensaje": mensaje,
        "respuesta": respuesta,
        "timestamp": timestamp
    }
    return insertar_en_tabla(nombre_tabla, datos)


# Función para verificar si un lead ya existe por número de teléfono
def existe_lead(nombre_tabla, telefono):
    try:
        response = supabase.table(nombre_tabla).select("telefono").eq("telefono", telefono).execute()
        return len(response.data) > 0
    except Exception as e:
        print("❌ Error al verificar existencia del lead:", e)
        return False

# Función para insertar o actualizar datos de lead en otra tabla
def insertar_lead(nombre_tabla, telefono, nombre, fecha_entrada, modelo_interes, canal):
    datos = {
        "telefono": telefono,
        "nombre": nombre,
        "fecha_entrada": fecha_entrada,
        "modelo_interes": modelo_interes,
        "canal": canal
    }
    try:
        if existe_lead(nombre_tabla, telefono):
            response = supabase.table(nombre_tabla).update(datos).eq("telefono", telefono).execute()
            print("🔄 Lead actualizado en Supabase")
        else:
            response = supabase.table(nombre_tabla).insert(datos).execute()
            print("✅ Lead insertado correctamente en Supabase")
        return True
    except Exception as e:
        print("❌ Error al insertar o actualizar lead en Supabase:", e)
        return False


# Alias para mantener consistencia con nombres en otros archivos
def insertar_en_tabla_leads(telefono, nombre, fecha_entrada, modelo_interes, canal, nombre_tabla="leads_nissan"):
    return insertar_lead(nombre_tabla, telefono, nombre, fecha_entrada, modelo_interes, canal)

def insertar_en_historial(telefono, mensaje, respuesta, timestamp, nombre_tabla="historial_conversaciones"):
    return insertar_historial(telefono, mensaje, respuesta, timestamp, nombre_tabla)


# Función para guardar datos adicionales de leads en otra tabla
def guardar_info_adicional(nombre_tabla, telefono, campo, valor):
    datos = {
        "telefono": telefono,
        campo: valor
    }
    try:
        if existe_lead(nombre_tabla, telefono):
            response = supabase.table(nombre_tabla).update(datos).eq("telefono", telefono).execute()
            print(f"🔄 {campo} actualizado correctamente para el lead")
        else:
            response = supabase.table(nombre_tabla).insert(datos).execute()
            print(f"✅ {campo} insertado para nuevo lead en Supabase")
        return True
    except Exception as e:
        print(f"❌ Error al guardar {campo} adicional del lead:", e)
        return False