# 🚗 Nissan WhatsApp Bot - Sistema Avanzado de Ventas

## 📋 Descripción

Bot inteligente de WhatsApp para concesionario Nissan con funcionalidades avanzadas de:
- 🧠 **Análisis de sentimientos con IA**
- 📊 **Dashboard avanzado con ROI y predicciones**
- 🔔 **Sistema de notificaciones push**
- 🎯 **Seguimiento inteligente adaptativo**
- 💬 **Memoria de conversación mejorada**
- 📈 **Tracking completo de leads**

## 🚀 Funcionalidades Principales

### ✅ Completadas
- ✅ Sistema de conversación natural con OpenAI GPT-4
- ✅ Tracking completo de leads con estados y scoring
- ✅ Memoria de conversación persistente
- ✅ Base de conocimiento RAG con documentos Nissan
- ✅ Dashboard básico de métricas
- ✅ **NUEVO: Análisis de sentimientos avanzado**
- ✅ **NUEVO: Dashboard con métricas de ROI**
- ✅ **NUEVO: Sistema de notificaciones (Slack, Discord, Email)**
- ✅ **NUEVO: Seguimiento inteligente adaptativo**

### 🔄 En Desarrollo
- 🔄 Integración con CRM externo
- 🔄 Automatización de citas
- 🔄 Generación de reportes PDF

## 🛠️ Tecnologías

- **Backend**: Python 3.9+, Flask
- **IA**: OpenAI GPT-4, LangChain
- **Base de Datos**: Supabase (PostgreSQL)
- **Mensajería**: Twilio WhatsApp API
- **Vector DB**: FAISS
- **Notificaciones**: Slack, Discord, SMTP

## 📦 Instalación

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd chatbot
```

### 2. Crear entorno virtual
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crea un archivo `.env` con:

```env
# OpenAI
OPENAI_API_KEY=tu_api_key_openai

# Supabase
SUPABASE_URL=tu_url_supabase
SUPABASE_KEY=tu_key_supabase

# Twilio
TWILIO_ACCOUNT_SID=tu_account_sid
TWILIO_AUTH_TOKEN=tu_auth_token
TWILIO_WHATSAPP_NUMBER=+1234567890

# Notificaciones (opcionales)
SLACK_WEBHOOK_URL=tu_webhook_slack
DISCORD_WEBHOOK_URL=tu_webhook_discord
EMAIL_USER=tu_email
EMAIL_PASSWORD=tu_password_app
NOTIFICATION_EMAIL=destino@email.com

# Configuración de negocio
PRECIO_PROMEDIO_AUTO=350000
COMISION_PROMEDIO=0.05
COSTO_LEAD=50
META_DIARIA_LEADS=10
```

### 5. Ejecutar la aplicación
```bash
python app.py
```

## 🌐 Endpoints Disponibles

### Principales
- `/` - Dashboard principal
- `/whatsapp` - Webhook para Twilio
- `/dashboard` - Dashboard básico de leads
- `/advanced_dashboard` - **NUEVO: Dashboard avanzado con ROI**

### Testing
- `/test` - Prueba todos los servicios
- `/test_memoria` - Prueba memoria básica
- `/test_memoria_mejorada` - Prueba memoria avanzada
- `/test_sentiment` - **NUEVO: Prueba análisis de sentimientos**

## 🧠 Análisis de Sentimientos

El sistema detecta automáticamente:
- 😡 **Frustración**: "molesto", "cansado", "terrible"
- 😍 **Entusiasmo**: "excelente", "perfecto", "me encanta"  
- ⚡ **Urgencia**: "urgente", "ya", "inmediato"
- 🤔 **Dudas**: "no sé", "tal vez", "pensando"
- 💰 **Sensibilidad al precio**: "caro", "económico", "descuento"

### Estrategias de Respuesta
- **Frustracion** → Tono empático, sin emojis
- **Entusiasmo** → Tono entusiasta, aprovechar momentum
- **Urgencia** → Respuesta rápida, acción inmediata
- **Precio sensible** → Enfoque en valor y financiamiento

## 📊 Dashboard Avanzado

### Métricas de Conversión
- Funnel completo de ventas
- Tasas de conversión por estado
- Distribución por temperatura
- Score promedio de leads

### Análisis ROI
- Inversión total vs ingresos
- ROI actual y potencial
- Costo por lead/venta
- Valor del pipeline

### Análisis Predictivo
- Tendencias de leads y conversión
- Predicciones 30 días
- Recomendaciones automáticas

## 🔔 Sistema de Notificaciones

### Canales Soportados
- **Slack**: Notificaciones con attachments
- **Discord**: Mensajes con emojis contextuales
- **Email**: SMTP con HTML

### Tipos de Alertas
- 🔥 Lead caliente detectado
- ⏰ Lead sin respuesta (>24h)
- 🎯 Meta diaria alcanzada
- 🚨 Errores críticos del sistema

## 🎯 Seguimiento Inteligente

### Clasificación Automática
- **Caliente urgente**: 2-4-8-24 horas
- **Caliente normal**: 6-12-24-48 horas  
- **Tibio interesado**: 1-2-3 días, 1 semana
- **Tibio dudoso**: 2-4 días, 1 semana
- **Frío exploratorio**: 1-2-4 semanas

### Personalización
- Horarios óptimos por cliente
- Mensajes adaptados al contexto
- Canales preferidos (WhatsApp/llamada)
- Priorización automática

## 📁 Estructura del Proyecto

```
chatbot/
├── app.py                          # Aplicación principal
├── config.py                       # Configuración centralizada
├── requirements.txt                # Dependencias
├── .env                           # Variables de entorno
├── models/
│   ├── __init__.py
│   └── lead_tracking.py           # Modelos de datos
├── services/
│   ├── __init__.py
│   ├── lead_tracking_service.py   # Servicio de tracking
│   ├── sentiment_analyzer.py     # 🆕 Análisis de sentimientos
│   ├── advanced_dashboard.py     # 🆕 Dashboard avanzado
│   ├── notification_system.py    # 🆕 Notificaciones
│   └── intelligent_followup.py   # 🆕 Seguimiento inteligente
├── rag/
│   ├── buscador.py               # Búsqueda en documentos
│   ├── indexador.py              # Indexación vectorial
│   └── data/                     # Documentos Nissan
└── vector_db_sicrea/             # Base vectorial FAISS
```

## 🔧 Configuración Avanzada

### Webhooks de Notificaciones

#### Slack
1. Ir a https://api.slack.com/apps
2. Crear nueva app → Incoming Webhooks
3. Activar y crear webhook
4. Copiar URL al `.env`

#### Discord
1. Configuración servidor → Integraciones → Webhooks
2. Crear webhook
3. Copiar URL al `.env`

### Configuración Email
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=tu_email@gmail.com
EMAIL_PASSWORD=tu_app_password  # No tu contraseña normal
```

## 📈 Métricas de Rendimiento

### Objetivos por Defecto
- **Meta diaria**: 10 leads
- **Tasa de conversión objetivo**: 5%
- **Tiempo respuesta**: <5 minutos
- **ROI objetivo**: >200%

### KPIs Monitoreados
- Leads generados por día/semana/mes
- Tasa de conversión por canal
- Tiempo promedio de respuesta
- Score promedio de leads
- Valor del pipeline
- ROI real vs potencial

## 🐛 Troubleshooting

### Errores Comunes

**Error: Supabase no disponible**
- Verificar SUPABASE_URL y SUPABASE_KEY
- Confirmar que las tablas existen

**Error: OpenAI API**
- Verificar OPENAI_API_KEY
- Confirmar saldo disponible

**Error: Funcionalidades avanzadas no disponibles**
- Verificar instalación de dependencias
- Revisar imports en app.py

### Logs Importantes
```bash
# Ver logs en tiempo real
tail -f logs/app.log

# Ver errores específicos
grep "ERROR" logs/app.log
```

## 🚀 Deployment

### Desarrollo
```bash
python app.py
```

### Producción (Render/Heroku)
```bash
# Archivo Procfile
web: python app.py

# Variables de entorno en plataforma
FLASK_ENV=production
```

## 🤝 Contribución

1. Fork el proyecto
2. Crea feature branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push branch (`git push origin feature/nueva-funcionalidad`)
5. Abrir Pull Request

## 📝 Changelog

### v2.0.0 (Actual)
- ✅ Análisis de sentimientos con IA
- ✅ Dashboard avanzado con ROI
- ✅ Sistema de notificaciones push
- ✅ Seguimiento inteligente adaptativo
- ✅ Configuración centralizada
- ✅ Optimización de rendimiento

### v1.0.0
- ✅ Bot básico de WhatsApp
- ✅ Tracking de leads
- ✅ Memoria de conversación
- ✅ RAG con documentos

## 📞 Soporte

Para soporte técnico:
- 📧 Email: soporte@example.com
- 💬 Slack: #nissan-bot-support
- 📋 Issues: GitHub Issues

---

**Desarrollado con ❤️ para optimizar ventas de Nissan**
