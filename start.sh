#!/bin/bash

# Script de inicio para Railway
echo "🚀 Iniciando aplicación en Railway..."

# Debug: Mostrar todas las variables de entorno (sin valores sensibles)
echo "🔍 Variables de entorno disponibles:"
env | grep -E "(OPENAI|SUPABASE|WHATSAPP|PORT|FLASK)" | sed 's/=.*/=***/' | sort

# Función para verificar variable
check_var() {
    if [ -z "${!1}" ]; then
        echo "❌ ERROR: $1 no configurada"
        echo "🔍 Valor actual: '${!1}'"
        return 1
    else
        echo "✅ $1 configurada (${#1} caracteres)"
        return 0
    fi
}

# Verificar variables críticas una por una
echo "🔧 Verificando variables críticas..."

check_var "OPENAI_API_KEY"
OPENAI_OK=$?

check_var "SUPABASE_URL" 
SUPABASE_OK=$?

check_var "WHATSAPP_TOKEN"
WHATSAPP_OK=$?

# Configurar puerto con fallback
if [ -z "$PORT" ]; then
    echo "⚠️ PORT no definida, usando 8000"
    export PORT=8000
else
    echo "✅ Puerto configurado: $PORT"
fi

# Solo continuar si las variables críticas están disponibles
if [ $OPENAI_OK -ne 0 ] || [ $SUPABASE_OK -ne 0 ] || [ $WHATSAPP_OK -ne 0 ]; then
    echo ""
    echo "🚨 VARIABLES FALTANTES DETECTADAS"
    echo "📋 Instrucciones:"
    echo "   1. Ve a Railway Dashboard → Settings → Variables" 
    echo "   2. Agrega las variables faltantes"
    echo "   3. Redeploy la aplicación"
    echo ""
    echo "⏱️ Esperando 30 segundos antes de continuar..."
    sleep 30
    echo "🔄 Continuando con inicio (puede fallar si faltan variables)..."
fi

echo "✅ Iniciando aplicación..."

# Iniciar aplicación con gunicorn
echo "🔄 Iniciando gunicorn..."
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --access-logfile - --error-logfile -