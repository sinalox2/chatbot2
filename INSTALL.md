# 🚀 Guía de Instalación - Chatbot Nissan

## ⚡ Instalación Rápida

### 1. **Prerrequisitos**
```bash
# Python 3.9+
python --version

# Git
git --version
```

### 2. **Clonar y Configurar**
```bash
git clone [repository-url]
cd chatbot
pip install -r requirements.txt
cp .env.example .env
```

### 3. **Variables de Entorno Esenciales**
Editar `.env`:
```bash
# ✅ OBLIGATORIAS
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://...
SUPABASE_KEY=eyJ...
CHATWOOT_BASE_URL=https://app.chatwoot.com
CHATWOOT_ACCOUNT_ID=139510
CHATWOOT_API_TOKEN=your-token
CHATWOOT_INBOX_ID=81923

# ✅ OPCIONAL
FLASK_PORT=5001
FLASK_DEBUG=True
```

### 4. **Ejecutar**
```bash
python3 app.py
```

### 5. **Configurar Webhook**
```bash
# Con ngrok
ngrok http 5001

# En Chatwoot configurar:
# https://abc123.ngrok.io/webhook
```

---

## 🔧 Configuración Detallada

### **Chatwoot Setup**

1. **Obtener credenciales:**
   - URL: Desde `https://app.chatwoot.com/app/accounts/[ID]`
   - Account ID: Desde la URL del browser
   - Inbox ID: Desde webhook de Chatwoot
   - API Token: Settings → Integrations → API Access Tokens

2. **Configurar Webhook:**
   - Settings → Inboxes → [Tu WhatsApp Inbox]
   - Webhook URL: `https://your-ngrok.ngrok.io/webhook`

### **Supabase Setup**

1. **Crear proyecto en Supabase**
2. **Ejecutar SQL:**
```sql
-- Tabla opcional para cache (mejora rendimiento)
CREATE TABLE embedding_cache (
    id SERIAL PRIMARY KEY,
    text_hash VARCHAR(64) UNIQUE,
    text_content TEXT,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Crear índice
CREATE INDEX idx_embedding_cache_hash ON embedding_cache(text_hash);
```

3. **Obtener credenciales:**
   - URL: Settings → API
   - Key: Settings → API → `anon` `public` key

### **OpenAI Setup**

1. **Crear API key en OpenAI**
2. **Verificar que tengas acceso a GPT-4**

---

## 🧪 Verificación

### **Test de Conectividad**
```bash
# Test Supabase
curl -H "apikey: $SUPABASE_KEY" "$SUPABASE_URL/rest/v1/"

# Test Chatwoot
curl -H "api_access_token: $CHATWOOT_API_TOKEN" \
     "$CHATWOOT_BASE_URL/api/v1/accounts/$CHATWOOT_ACCOUNT_ID/conversations"

# Test OpenAI (desde Python)
python -c "import openai; print('OpenAI OK')"
```

### **Test del Bot**
1. Enviar mensaje de WhatsApp
2. Ver logs en consola
3. Verificar respuesta en WhatsApp

---

## 🚨 Troubleshooting

### **Error: SSL Certificate**
```bash
# Solución aplicada en código
# SSL verification disabled para Chatwoot
```

### **Error: Invalid Access Token**
```bash
# Regenerar token en Chatwoot
# Settings → Integrations → API Access Tokens
```

### **Error: Tabla no existe**
```bash
# Crear tablas requeridas en Supabase
# Ver scripts en sql/
```

### **Error: OpenAI Rate Limit**
```bash
# Verificar plan de OpenAI
# Reducir frecuencia de mensajes
```

---

## 📊 Estructura Mínima

```
chatbot/
├── app.py                    # ✅ Archivo principal
├── config.py                 # ✅ Configuración
├── chatwoot_api.py          # ✅ API Chatwoot
├── .env                     # ✅ Variables entorno
├── requirements.txt         # ✅ Dependencias
├── prompt_sistema_nissan.md # ✅ Prompt IA
└── services/
    └── conversation_service.py  # ✅ Motor IA
```

---

## 🎯 Configuraciones por Entorno

### **Desarrollo:**
```bash
FLASK_DEBUG=True
FLASK_PORT=5001
AI_TEMPERATURE_DEFAULT=0.4
```

### **Producción:**
```bash
FLASK_DEBUG=False
PORT=5001  # Railway/Heroku
AI_TEMPERATURE_DEFAULT=0.3  # Más preciso
```

---

## 🔄 Actualización

```bash
git pull origin main
pip install -r requirements.txt --upgrade
python3 app.py
```

---

## ✅ Checklist Final

- [ ] Variables de entorno configuradas
- [ ] Chatwoot webhook configurado
- [ ] Supabase conectado
- [ ] OpenAI API key válida
- [ ] ngrok funcionando
- [ ] Primer mensaje de prueba exitoso

---

**🎉 ¡Listo! Tu chatbot está funcionando.**