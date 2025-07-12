# 🚗 Nissan WhatsApp Bot - Sistema Avanzado de Ventas

## 📋 Descripción

Bot inteligente de WhatsApp para concesionario Nissan con funcionalidades avanzadas de:
- 🧠 **Análisis de sentimientos con IA**
- 📊 **Dashboard moderno con diseño responsive**
- 🔔 **Sistema de notificaciones push**
- 🎯 **Seguimiento inteligente adaptativo**
- 💬 **Memoria de conversación mejorada**
- 📈 **Tracking completo de leads**
- 📱 **Sistema de plantillas WhatsApp Business**
- 🔄 **Gestión automática de tokens**

## 🚀 Funcionalidades Principales

### ✅ Dashboard Moderno Completo
- ✅ **Diseño responsive con navegación lateral**
- ✅ **Métricas en tiempo real con auto-refresh**
- ✅ **Gestión completa de contactos proactivos**
- ✅ **Carga masiva de contactos CSV/Excel**
- ✅ **Sistema de validación y preview**
- ✅ **Estado del sistema en tiempo real**
- ✅ **Gestión automática de tokens WhatsApp**

### ✅ Sistema de Contactos Proactivos
- ✅ **CRUD completo**: Crear, editar, eliminar contactos
- ✅ **Filtros avanzados**: Por estado, campaña, plantilla
- ✅ **Paginación**: Manejo eficiente de listas grandes
- ✅ **Envío individual/masivo**: Con confirmaciones
- ✅ **Integración con Chatwoot**: Para primer contacto
- ✅ **Plantillas WhatsApp**: Cumplimiento políticas Meta

### ✅ Sistema WhatsApp Business API
- ✅ **Envío de mensajes**: Con manejo robusto de errores
- ✅ **Soporte templates**: Mensajes pre-aprobados
- ✅ **Recarga automática de tokens**: Cuando expiran
- ✅ **Fallback inteligente**: Sistema de respaldo
- ✅ **Validación de números**: Formato internacional

### ✅ Funcionalidades Base
- ✅ Sistema de conversación natural con OpenAI GPT-4
- ✅ Tracking completo de leads con estados y scoring
- ✅ Memoria de conversación persistente
- ✅ Base de conocimiento RAG con documentos Nissan
- ✅ Análisis de sentimientos avanzado
- ✅ Sistema de notificaciones (Slack, Discord, Email)
- ✅ Seguimiento inteligente adaptativo

## 🛠️ Tecnologías

- **Backend**: Python 3.9+, Flask
- **Frontend**: Bootstrap 5, Chart.js, Font Awesome
- **IA**: OpenAI GPT-4, LangChain
- **Base de Datos**: Supabase (PostgreSQL)
- **Mensajería**: WhatsApp Business API, Twilio (fallback)
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

# WhatsApp Business API (Principal)
WHATSAPP_TOKEN=tu_whatsapp_business_token
PHONE_NUMBER_ID=tu_phone_number_id
WHATSAPP_BUSINESS_ACCOUNT_ID=tu_business_account_id

# Twilio (Fallback)
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

# Flask
PORT=5001
FLASK_DEBUG=False
```

### 5. Ejecutar la aplicación
```bash
python app.py
```

La aplicación estará disponible en: `http://localhost:5001`

## 🌐 Dashboard Moderno

### 🎨 Características del Diseño
- **Navegación lateral moderna** con iconos y badges en tiempo real
- **Colores corporativos de Nissan** (rojo #e60012)
- **Tarjetas con hover effects** y animaciones suaves
- **Responsive design** para móviles y tablets
- **Indicadores en tiempo real** con animaciones

### 📊 Dashboard Principal (`/dashboard`)
- **Métricas en tiempo real**: Total leads, leads calientes, seguimientos, ingresos
- **Gráficos interactivos**: Tendencias y distribución con Chart.js
- **Actividad reciente**: Historial de interacciones
- **Acciones rápidas**: Botones para funciones principales
- **Estado del sistema**: Monitoreo de WhatsApp, BD y servicios

### 👥 Contactos Proactivos (`/contactos_proactivos`)
- **Gestión completa**: Crear, editar, eliminar contactos
- **Filtros avanzados**: Por estado, campaña, plantilla, búsqueda
- **Estados visuales**: Badges de colores para cada estado
- **Paginación**: 10 contactos por página con navegación
- **Envío individual/masivo**: Con confirmaciones y feedback

### 📤 Carga Masiva (`/carga_masiva`)
- **Drag & Drop**: Arrastra archivos CSV/Excel
- **Validación automática**: Duplicados y teléfonos
- **Vista previa**: Antes de importar
- **Configuración flexible**: Campaña, plantilla, programación
- **Historial de cargas**: Seguimiento de importaciones

## 🔄 APIs REST Disponibles

### Dashboard
- `GET /` - Redirige al dashboard principal
- `GET /dashboard` - Dashboard principal con métricas
- `GET /api/dashboard-data` - Datos del dashboard en tiempo real
- `GET /api/real-time-stats` - Stats para sidebar

### Contactos Proactivos
- `GET /api/contactos-proactivos` - Listar contactos (con paginación)
- `POST /api/contactos-proactivos` - Crear nuevo contacto
- `DELETE /api/contactos-proactivos/{id}` - Eliminar contacto
- `POST /api/contactos-proactivos/{id}/send` - Enviar contacto individual
- `GET /api/contactos-proactivos/stats` - Estadísticas de contactos
- `GET /api/contactos-proactivos/debug` - Debug de estructura de tabla

### Carga Masiva
- `POST /api/process-file` - Procesar archivo CSV/Excel
- `POST /api/validate-data` - Validar datos antes de importar
- `POST /api/import-contacts` - Importación masiva
- `GET /api/download-template` - Descargar plantilla CSV
- `GET /api/upload-history` - Historial de cargas

### WhatsApp Token Management
- `GET /api/whatsapp/status` - Estado del servicio WhatsApp
- `POST /api/whatsapp/reload-token` - Recargar token manualmente
- `POST /api/whatsapp/test-message` - Enviar mensaje de prueba

### Funcionalidades Originales
- `POST /webhook` - Webhook principal para Chatwoot
- `GET /test` - Prueba todos los servicios
- `POST /agregar_contacto_proactivo` - Agregar contacto (legacy)

## 🔑 Gestión Automática de Tokens WhatsApp

### 🔄 Recarga Automática
El sistema detecta automáticamente cuando un token de WhatsApp expira y lo recarga desde las variables de entorno:

```python
# Detección automática de token expirado
if response.status_code == 401 or 'expired' in error_text.lower():
    print("🔄 Token expirado detectado, recargando...")
    if self.reload_token():
        # Reintentar envío con nuevo token
```

### 🎛️ Gestión Manual desde Dashboard
En el dashboard principal:
- **Estado en tiempo real**: Visualización del estado del token
- **Botón de recarga**: Botón 🔑 para recargar manualmente
- **Preview del token**: Muestra los primeros/últimos caracteres
- **Test de conexión**: Verificación automática de conectividad
- **Mensaje de prueba**: Enviar mensajes de test

### 📋 Flujo de Recuperación
1. **Envío falla** con token expirado (error 401)
2. **Sistema detecta** error automáticamente
3. **Recarga** token desde `.env`
4. **Reintenta** envío con nuevo token
5. **Registra** la renovación en logs

## 📱 Sistema de Plantillas WhatsApp Business

### 🎯 Plantillas Implementadas
- **saludo_lead**: Primer contacto para nuevos leads
  ```
  ¡Hola {nombre}! Soy César de Nissan. ¿En qué modelo estás interesado?
  ```
- **recordatorio_cita**: Recordatorios de citas
  ```
  Hola {nombre}, tienes cita el {fecha} a las {hora} en {dirección}
  ```

### ✅ Cumplimiento Políticas Meta
- **Primer contacto**: Siempre con plantilla aprobada
- **Ventana 24h**: Mantenida con mensajes cada 20 horas
- **Máximo 5 mensajes**: De seguimiento automático
- **Detección automática**: Nuevo vs contacto existente

### 🔄 Sistema de Fallback Robusto
```python
# Si falla la plantilla, mensaje personalizado
if not template_success:
    mensaje_fallback = generar_mensaje_personalizado(contacto)
    return enviar_mensaje_whatsapp(telefono, mensaje_fallback)
```

## 🏗️ Estructura del Proyecto Actualizada

```
chatbot/
├── app.py                          # Aplicación principal modernizada
├── app_backup.py                   # Respaldo de versión anterior
├── config.py                       # Configuración centralizada
├── requirements.txt                # Dependencias
├── .env                           # Variables de entorno
├── dashboard/                      # 🆕 Dashboard moderno organizado
│   ├── __init__.py
│   ├── README.md                  # Documentación del dashboard
│   ├── routes/                    # Rutas organizadas por módulos
│   │   ├── __init__.py
│   │   ├── main_routes.py         # Rutas principales del dashboard
│   │   └── contacts_routes.py     # Rutas de contactos
│   ├── services/                  # Servicios específicos del dashboard
│   │   ├── __init__.py
│   │   └── advanced_dashboard.py  # Métricas avanzadas y ROI
│   ├── templates/                 # Templates HTML modernos
│   │   ├── base.html             # Template base con navegación
│   │   ├── dashboard_main.html   # Dashboard principal
│   │   ├── contactos_proactivos.html # Gestión de contactos
│   │   └── carga_masiva.html     # Importación masiva
│   ├── static/                   # Archivos estáticos (preparado)
│   │   ├── css/                  # Hojas de estilo
│   │   ├── js/                   # JavaScript
│   │   └── images/               # Imágenes
│   ├── components/               # Componentes reutilizables
│   ├── tests/                    # Pruebas del dashboard
│   │   └── test_dashboard_flow.py
│   └── utils/                    # Utilidades del dashboard
├── models/
│   ├── __init__.py
│   └── lead_tracking.py           # Modelos de datos
├── services/
│   ├── __init__.py
│   ├── lead_tracking_service.py   # Servicio de tracking
│   ├── sentiment_analyzer.py     # Análisis de sentimientos
│   ├── notification_system.py    # Notificaciones
│   ├── intelligent_followup.py   # Seguimiento inteligente
│   ├── contactos_proactivos.py   # Contactos proactivos mejorado
│   ├── whatsapp_service.py       # 🆕 Servicio WhatsApp con auto-reload
│   └── seguimiento_automatico.py # Seguimiento automático
├── rag/
│   ├── buscador.py               # Búsqueda en documentos
│   ├── indexador.py              # Indexación vectorial
│   └── data/                     # Documentos Nissan
└── vector_db_sicrea/             # Base vectorial FAISS
```

## 🔧 Consultas en Tiempo Real

### 📊 Auto-refresh
- **Datos cada 30 segundos**: Métricas actualizadas automáticamente
- **Indicadores visuales**: Punto verde de "tiempo real"
- **Badges dinámicos**: Contadores en sidebar
- **Sin reload**: Actualización AJAX transparente

### 🔍 Funciones de Debug
En la consola del navegador:
```javascript
// Ver información completa de contactos
debugContacts()

// Estructura de tabla en base de datos
fetch('/api/contactos-proactivos/debug')
  .then(r => r.json())
  .then(d => console.log(d))
```

## 🎯 Flujo de Contactos Proactivos

### 📥 Agregar Contacto
1. **Formulario completo**: Nombre, teléfono, campaña, plantilla
2. **Validación**: Campos requeridos y formato de teléfono
3. **Guardado**: En base de datos con estado 'pendiente'
4. **Feedback**: Confirmación y recarga automática de lista

### 📤 Envío de Contactos
1. **Individual**: Botón ✈️ en cada fila
2. **Masivo**: Botón "Enviar Pendientes"
3. **Con plantilla**: Primer contacto usa template aprobado
4. **Personalizado**: Contactos existentes usan mensaje custom

### 🔄 Estados de Contacto
- **Pendiente**: 🟡 Listo para enviar
- **Enviado**: 🟢 Mensaje enviado exitosamente
- **Respondido**: 🔵 Cliente respondió
- **Error**: 🔴 Error en envío

## 🧪 Testing y Debug

### 🔍 Endpoints de Debug
- `/api/contactos-proactivos/debug` - Estructura de tabla
- `/api/whatsapp/status` - Estado de WhatsApp
- `debugContacts()` - Función JavaScript de debug

### 🧪 Pruebas de WhatsApp
Desde el dashboard:
1. **Estado del sistema** → Ver estado del token
2. **Botón 🔑** → Recargar token manualmente
3. **Prueba de WhatsApp** → Enviar mensaje de test
4. **Logs del servidor** → Ver resultado en consola

### 📊 Validación de Datos
- **Formato teléfono**: Validación regex internacional
- **Duplicados**: Verificación automática en BD
- **Campos requeridos**: Validación frontend y backend
- **Vista previa**: Antes de importación masiva

## 🚨 Solución de Problemas

### ❌ Contactos no aparecen en lista
```bash
# Verificar estructura de tabla
curl http://localhost:5001/api/contactos-proactivos/debug

# Ver logs en consola del navegador
# Buscar errores de ordenamiento por columnas faltantes
```

### 🔑 Token WhatsApp expirado
```bash
# Verificar estado
curl http://localhost:5001/api/whatsapp/status

# Recargar manualmente
curl -X POST http://localhost:5001/api/whatsapp/reload-token

# El sistema se auto-repara automáticamente
```

### 📡 Problemas de conectividad
- Verificar variables de entorno en `.env`
- Confirmar que el token WhatsApp es válido
- Revisar logs del servidor para errores específicos

## 📈 Métricas y Rendimiento

### 🎯 KPIs Monitoreados
- **Contactos pendientes**: Tiempo real en sidebar
- **Tasa de envío**: Éxito vs errores
- **Respuestas**: Contactos que responden
- **Tiempo de procesamiento**: Milisegundos por operación

### 📊 Dashboard Analytics
- **Total leads**: Contador en tiempo real
- **Leads calientes**: Scoring automático
- **Pipeline value**: Valor estimado de ventas
- **Conversión**: Rates por estado

## 🚀 Deployment

### 🔧 Desarrollo Local
```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
nano .env

# Ejecutar
python app.py
```

### ☁️ Producción
```bash
# Variables importantes
PORT=5001                    # Puerto personalizado
FLASK_DEBUG=False           # Producción
WHATSAPP_TOKEN=xxx          # Token válido actualizado

# El sistema maneja automáticamente:
# - Recarga de tokens expirados
# - Fallbacks de conectividad
# - Logging de errores
```

## 📝 Changelog Reciente

### v3.0.0 (Actual) - Dashboard Moderno
- ✅ **Dashboard completamente rediseñado** con navegación lateral
- ✅ **Gestión automática de tokens** WhatsApp con recarga automática
- ✅ **Carga masiva** de contactos CSV/Excel con validación
- ✅ **Consultas en tiempo real** con auto-refresh cada 30 segundos
- ✅ **Sistema de filtros** avanzados para contactos
- ✅ **APIs REST** completas para todas las funcionalidades
- ✅ **Responsive design** para móviles y tablets
- ✅ **Debugging tools** integradas en frontend y backend

### v2.5.0 - Sistema de Contactos Proactivos
- ✅ Contactos proactivos con plantillas WhatsApp Business
- ✅ Integración con Chatwoot para primer contacto
- ✅ Sistema de fallback robusto para BD legacy
- ✅ Cumplimiento políticas Meta WhatsApp Business

### v2.0.0 - Funcionalidades Avanzadas
- ✅ Análisis de sentimientos con IA
- ✅ Dashboard avanzado con ROI
- ✅ Sistema de notificaciones push
- ✅ Seguimiento inteligente adaptativo

## 🤝 Contribución

1. Fork el proyecto
2. Crea feature branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push branch (`git push origin feature/nueva-funcionalidad`)
5. Abrir Pull Request

## 📞 Soporte

Para soporte técnico:
- 📧 **Issues**: GitHub Issues para reportar bugs
- 💬 **Logs**: Revisar consola del servidor para errores
- 🔍 **Debug**: Usar funciones de debug integradas

### 🛠️ Debug Rápido
```javascript
// En consola del navegador
debugContacts()  // Ver estado de contactos

// En terminal del servidor
curl http://localhost:5001/api/whatsapp/status  // Estado WhatsApp
curl http://localhost:5001/api/contactos-proactivos/debug  // Debug BD
```

---

**Desarrollado con ❤️ para optimizar ventas de Nissan**

*Sistema moderno con dashboard responsive, gestión automática de tokens y herramientas de debug integradas*