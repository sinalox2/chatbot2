from supabase_client import insertar_en_tabla

# Datos de prueba
datos = {
    "nombre": "Juan Pérez",
    "telefono": "6641234567",
    "modelo_interes": "Nissan Versa",
    "fecha_contacto": "2025-05-27"  # Puedes usar datetime.today() si prefieres
}

# Nombre de la tabla creada en Supabase
tabla = "leads_nissan"

# Ejecutar la inserción
respuesta = insertar_en_tabla(tabla, datos)

# Verificar la respuesta
if respuesta:
    print("✅ Inserción exitosa:", respuesta)
else:
    print("❌ Falló la inserción.")