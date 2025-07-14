# 🚀 Guía de Deploy en Railway

## 📋 Requisitos Completados

✅ **requirements.txt** - Todas las dependencias listadas
✅ **Procfile** - Configurado para gunicorn
✅ **.env.example** - Variables de entorno documentadas  
✅ **app.py** - Optimizado para producción
✅ **Supabase RAG** - Migrado y funcionando

## 🔧 Variables de Entorno Necesarias

### **Obligatorias para funcionamiento básico:**
```bash
OPENAI_API_KEY=sk-xxxxx
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJxxxxx
WHATSAPP_TOKEN=EAAxxxxx
PHONE_NUMBER_ID=123456789
PORT=5001
```

### **Configuración de producción:**
```bash
FLASK_ENV=production
DEBUG=False
FLASK_DEBUG=False
WHATSAPP_VERIFY_TOKEN=nissan_verify_token
```

### **Opcionales (notificaciones y email):**
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/xxx
EMAIL_USER=tu-email@gmail.com
EMAIL_PASSWORD=tu-app-password
```

## 🚀 Pasos para Deploy en Railway

### 1. **Conectar Repository**
```bash
# En Railway dashboard
1. New Project → Deploy from GitHub repo
2. Seleccionar tu repositorio del chatbot
3. Railway detectará automáticamente Python
```

### 2. **Configurar Variables de Entorno**
```bash
# En Railway Project Settings → Variables
- Agregar TODAS las variables obligatorias
- Usar los valores reales de tu .env local
- NO subir el archivo .env al repositorio
```

### 3. **Configurar Dominio (Opcional)**
```bash
# En Railway Project → Settings → Domains
- Generar dominio automático: xxx.railway.app
- O conectar dominio personalizado
```

### 4. **Webhook de WhatsApp**
```bash
# Actualizar webhook URL en Meta Developers
Webhook URL: https://tu-app.railway.app/webhook
Verify Token: nissan_verify_token
```

## ✅ Verificación Post-Deploy

### **1. Salud del servidor:**
```bash
GET https://tu-app.railway.app/health
# Debe retornar: {"status": "healthy"}
```

### **2. Dashboard funcional:**
```bash
GET https://tu-app.railway.app/dashboard
# Debe mostrar el dashboard
```

### **3. WhatsApp webhook:**
```bash
# Enviar mensaje de prueba desde WhatsApp
# Verificar respuesta con precios de Supabase RAG
```

### **4. Logs de Railway:**
```bash
# En Railway dashboard → View Logs
✅ "RAG Supabase system loaded successfully"
✅ "WhatsApp Business API Service inicializado"
✅ "Servicios inicializados"
```

## 🔍 Debugging Common Issues

### **App no inicia:**
- Verificar variables de entorno obligatorias
- Revisar logs en Railway dashboard
- Confirmar requirements.txt actualizado

### **RAG no funciona:**
- Verificar SUPABASE_URL y SUPABASE_KEY
- Confirmar que tabla 'chunks' existe en Supabase
- Verificar OPENAI_API_KEY válida

### **WhatsApp no responde:**
- Verificar WHATSAPP_TOKEN y PHONE_NUMBER_ID
- Confirmar webhook URL actualizada en Meta
- Revisar WHATSAPP_VERIFY_TOKEN correcto

## 🎯 URLs Importantes Post-Deploy

- **App principal:** `https://tu-app.railway.app`
- **Dashboard:** `https://tu-app.railway.app/dashboard` 
- **Health check:** `https://tu-app.railway.app/health`
- **WhatsApp webhook:** `https://tu-app.railway.app/webhook`

## 🔐 Seguridad

- ✅ Variables de entorno en Railway (no en código)
- ✅ .env en .gitignore 
- ✅ HTTPS automático con Railway
- ✅ Tokens de WhatsApp seguros
- ✅ Debug=False en producción

## 🎉 ¡Listo para Producción!

Tu chatbot está configurado con:
- ✅ **Typing indicator** de WhatsApp
- ✅ **Supabase RAG** con 177 chunks 
- ✅ **Dashboard** administrativo
- ✅ **Seguimiento de leads**
- ✅ **Escalabilidad** en Railway