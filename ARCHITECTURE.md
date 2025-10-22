# 🏗️ Auditoría de Arquitectura - Chatbot Nissan

## 📋 Estado del Proyecto

**Última actualización:** 2025-10-22  
**Arquitectura:** Chatwoot-only WhatsApp Business Integration  
**Commit de seguridad:** `3b1b1ed` - feat: migrar a arquitectura Chatwoot-only

---

## 📁 Análisis de Archivos del Proyecto

### 🟢 ARCHIVOS PRINCIPALES (Activos)

#### `app.py` - **[CRÍTICO]** - Servidor Flask Principal
**Estado:** ✅ **ACTUALIZADO** - Nueva arquitectura Chatwoot-only  
**Tamaño:** ~1,700 líneas  
**Funciones principales:**
- `process_chatwoot_message()` - ✅ **ACTIVA** - Procesa mensajes de Chatwoot
- `webhook()` - ✅ **ACTIVA** - Webhook principal para Chatwoot
- APIs del dashboard - ✅ **ACTIVAS**

**Funciones deprecadas:**
- `process_whatsapp_message()` - ❌ **DEPRECADA** - Solo muestra warning
- `send_whatsapp_response()` - ❌ **DEPRECADA** - Redirige a Chatwoot
- `send_whatsapp_image()` - ❌ **DEPRECADA** - Redirige a Chatwoot
- `send_typing_indicator()` - ❌ **DEPRECADA** - Chatwoot lo maneja

#### `chatwoot_api.py` - **[CRÍTICO]** - Cliente API Chatwoot
**Estado:** ✅ **ACTUALIZADO** - SSL fix aplicado  
**Tamaño:** ~270 líneas  
**Funciones activas:**
- `buscar_contacto()` - ✅ Busca contactos por teléfono
- `crear_contacto()` - ✅ Crea nuevos contactos
- `crear_conversacion()` - ✅ Crea conversaciones
- `enviar_mensaje_publico()` - ✅ **PRINCIPAL** - Envía respuestas del bot
- `enviar_mensaje_incoming()` - ✅ Envía mensajes del cliente
- `obtener_conversacion_por_telefono()` - ✅ Busca conversaciones

**Mejoras aplicadas:**
- SSL verification disabled (`verify=False`)
- Timeout configurations
- Error handling robusto

#### `config.py` - **[CRÍTICO]** - Configuración Centralizada
**Estado:** ✅ **ACTUALIZADO** - Nueva configuración Chatwoot  
**Variables activas:**
```python
# Chatwoot (Obligatorio)
CHATWOOT_BASE_URL = "https://app.chatwoot.com"
CHATWOOT_ACCOUNT_ID = "139510"
CHATWOOT_API_TOKEN = "nuevo-token"
CHATWOOT_INBOX_ID = "81923"

# OpenAI (Obligatorio)
OPENAI_API_KEY = "sk-..."

# Supabase (Obligatorio)
SUPABASE_URL = "https://..."
SUPABASE_KEY = "..."
```

**Variables deprecadas:**
```python
# WHATSAPP_TOKEN - Ya no necesario
# PHONE_NUMBER_ID - Ya no necesario
```

#### `services/conversation_service.py` - **[CRÍTICO]** - Motor de IA
**Estado:** ✅ **FUNCIONAL** - Sistema de temperaturas activo  
**Funciones principales:**
- `generate_response()` - ✅ **PRINCIPAL** - Genera respuestas con GPT-4
- `analyze_message_intent()` - ✅ Analiza intención del mensaje
- `get_temperature_for_intent()` - ✅ Temperaturas dinámicas
- `detect_image_request()` - ✅ Detecta solicitudes de imágenes

**Sistema de temperaturas:**
- Precios: 0.2 (preciso)
- Financiamiento: 0.3 (balanceado)
- Saludos: 0.6 (natural)
- General: 0.4 (estándar)

#### `services/contactos_proactivos.py` - **[ACTIVO]** - Contactos Proactivos
**Estado:** ✅ **FUNCIONAL** - Sistema de plantillas WhatsApp  
**Funciones principales:**
- `procesar_contactos_pendientes()` - ✅ Procesa contactos pendientes
- `enviar_plantilla_whatsapp()` - ✅ Envía plantillas WhatsApp Business
- `generar_mensaje_personalizado()` - ✅ Genera mensajes personalizados
- `programar_mensaje_diferido()` - ✅ Programa mensajes diferidos

**Integración Chatwoot:**
- Crear contactos y conversaciones automáticamente
- Notas privadas para tracking
- Flujo completo de primer contacto

---

### 🟡 ARCHIVOS FUNCIONALES (Necesitan revisión)

#### `services/whatsapp_service.py` - **[DEPRECADO]** - Servicio WhatsApp Directo
**Estado:** ⚠️ **DEPRECADO** - Reemplazado por Chatwoot  
**Recomendación:** ❌ **ELIMINAR** o marcar como legacy  
**Uso actual:** Solo en servicios de contactos proactivos (fallback)

#### `prompt_sistema_nissan.txt` - **[FUNCIONAL]** - Prompt Legacy
**Estado:** ⚠️ **DUPLICADO**  
**Problema:** Existe `prompt_sistema_nissan.md` más actualizado  
**Recomendación:** ✅ **CONSOLIDAR** en archivo .md

#### `requirements.txt` - **[NECESITA ACTUALIZACIÓN]**
**Estado:** ⚠️ **DESACTUALIZADO**  
**Problemas detectados:**
- LangChain deprecation warnings
- Posibles dependencias innecesarias de WhatsApp API

---

### 🔴 ARCHIVOS OBSOLETOS (Candidatos a eliminación)

#### `dashboard/` - **[LEGACY]** - Dashboard Anterior
**Estado:** ❓ **NO EVALUADO**  
**Contenido:** Sistema de dashboard anterior  
**Recomendación:** 🔍 **EVALUAR** si sigue siendo necesario

#### `models/lead_tracking.py` - **[FUNCIONAL]** - Modelos de Datos
**Estado:** ✅ **ACTIVO** - Usado por lead_tracking_service  
**Recomendación:** ✅ **MANTENER**

---

## 🔄 Flujo de Datos Actual

### 1. Recepción de Mensaje
```
Cliente WhatsApp → WhatsApp Business → Chatwoot → webhook /webhook
```

### 2. Procesamiento en app.py
```python
webhook() → process_chatwoot_message() → conversation_service.generate_response()
```

### 3. Generación de Respuesta
```python
analyze_message_intent() → recuperar_contexto() → OpenAI GPT-4 → respuesta
```

### 4. Envío de Respuesta
```python
enviar_mensaje_publico(conversation_id) → Chatwoot → WhatsApp Business → Cliente
```

---

## 🚨 Problemas Identificados

### 1. **Funciones Deprecadas Activas**
```python
# En app.py - ELIMINAR o refactorizar
def send_whatsapp_response()  # Deprecada pero aún referenciada
def send_whatsapp_image()     # Deprecada pero aún referenciada
def send_typing_indicator()   # Deprecada pero aún referenciada
```

### 2. **Dependencias Innecesarias**
```python
# En services/
whatsapp_service.py  # 90% deprecado, solo usado como fallback
```

### 3. **Archivos Duplicados**
```
prompt_sistema_nissan.txt  # Legacy
prompt_sistema_nissan.md   # Actual
```

### 4. **Variables de Entorno Obsoletas**
```bash
# En .env - pueden eliminarse
WHATSAPP_TOKEN=...
PHONE_NUMBER_ID=...
WHATSAPP_BUSINESS_ACCOUNT_ID=...
```

---

## ✅ Recomendaciones de Optimización

### 🧹 **FASE 1: Limpieza de Código**

1. **Eliminar funciones deprecadas:**
   ```python
   # app.py
   - send_whatsapp_response()
   - send_whatsapp_image() 
   - send_typing_indicator()
   - send_customer_message_to_chatwoot() (simplificar)
   ```

2. **Consolidar archivos de prompt:**
   ```bash
   rm prompt_sistema_nissan.txt
   # Usar solo prompt_sistema_nissan.md
   ```

3. **Limpiar imports innecesarios:**
   ```python
   # Remover imports de whatsapp_service donde no sea necesario
   ```

### 🔧 **FASE 2: Refactorización**

1. **Simplificar process_chatwoot_message():**
   - Remover código deprecado
   - Optimizar flujo solo para Chatwoot
   - Mejorar manejo de errores

2. **Optimizar conversation_service.py:**
   - Reducir límite de historial (actual: 6 mensajes)
   - Optimizar llamadas a Supabase
   - Cache de embeddings más eficiente

3. **Actualizar requirements.txt:**
   ```bash
   pip install -U langchain-openai  # Fix deprecation
   pip uninstall packages-not-needed
   ```

### 📊 **FASE 3: Mejoras de Rendimiento**

1. **Implementar cache de embeddings:**
   ```sql
   CREATE TABLE embedding_cache (
       id SERIAL PRIMARY KEY,
       text_hash VARCHAR(64) UNIQUE,
       text_content TEXT,
       embedding VECTOR(1536),
       created_at TIMESTAMP DEFAULT NOW()
   );
   ```

2. **Optimizar consultas RAG:**
   - Limitar chunks a 2 máximo
   - Cache de consultas frecuentes
   - Timeout más agresivo

3. **Reducir uso de tokens:**
   - Historial más corto (4 mensajes máximo)
   - Contexto más conciso
   - Sistema de respuestas predefinidas

---

## 📈 Métricas de Rendimiento Actuales

### **Tokens por Conversación:**
- Promedio: 1,500-2,000 tokens
- Con RAG: +500 tokens
- Sin RAG: ~1,000 tokens

### **Tiempo de Respuesta:**
- Análisis: ~1s
- OpenAI API: ~2-3s
- Total: ~4-5s

### **Arquitectura:**
- **Estabilidad:** ✅ Alta (Chatwoot-only)
- **Mantenibilidad:** ⚠️ Media (código deprecado)
- **Escalabilidad:** ✅ Alta (Chatwoot handles load)

---

## 🎯 Próximos Pasos Prioritarios

1. **✅ Commit de seguridad** - ✅ COMPLETADO
2. **🧹 Limpieza de código** - 📋 PLANEADO
3. **📝 Documentación completa** - 🔄 EN PROGRESO
4. **🔧 Optimización de rendimiento** - 📋 PLANEADO
5. **🧪 Testing automatizado** - 📋 FUTURO

---

**Estado General:** ✅ **SISTEMA FUNCIONAL**  
**Prioridad:** 🟡 **OPTIMIZACIÓN MEDIA**  
**Risk Level:** 🟢 **BAJO** - Sistema estable con Chatwoot
