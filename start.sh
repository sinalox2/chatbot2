#!/bin/bash

# Script de inicio para Railway
echo "🚀 Iniciando aplicación en Railway..."

# Verificar variables de entorno críticas
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERROR: OPENAI_API_KEY no configurada"
    exit 1
fi

if [ -z "$SUPABASE_URL" ]; then
    echo "❌ ERROR: SUPABASE_URL no configurada"
    exit 1
fi

if [ -z "$WHATSAPP_TOKEN" ]; then
    echo "❌ ERROR: WHATSAPP_TOKEN no configurada"
    exit 1
fi

# Configurar puerto con fallback
if [ -z "$PORT" ]; then
    echo "⚠️ PORT no definida, usando 8000"
    export PORT=8000
fi

echo "✅ Puerto configurado: $PORT"
echo "✅ Variables de entorno verificadas"

# Iniciar aplicación con gunicorn
echo "🔄 Iniciando gunicorn..."
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --access-logfile - --error-logfile -