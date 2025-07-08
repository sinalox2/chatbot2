# 📊 Directorio del Dashboard - Nissan WhatsApp Bot

## 🎯 Dashboard Principal
**URL:** [http://localhost:5001/](http://localhost:5001/)

### Descripción
Dashboard principal con resumen general del sistema y navegación a todas las funcionalidades.

### Funcionalidades
- Resumen de métricas principales
- Navegación rápida a dashboards especializados
- Estado del sistema
- Enlaces directos a funciones clave

---

## 📈 Dashboard de Leads
**URL:** [http://localhost:5001/dashboard](http://localhost:5001/dashboard)

### Descripción
Dashboard básico para seguimiento de leads con memoria mejorada.

### Funcionalidades
- ✅ Métricas generales de leads
- ✅ Top leads prioritarios
- ✅ Estado de memoria de conversación
- ✅ Información de temperatura de leads
- ✅ Días sin interacción

### Columnas Mostradas
| Columna | Descripción |
|---------|-------------|
| Nombre | Nombre del lead |
| Teléfono | Número de contacto |
| Score | Puntuación de calificación |
| Estado | Estado actual del lead |
| Temperatura | Caliente/Tibio/Frío |
| Modelo | Modelo de auto de interés |
| Días sin interacción | Tiempo desde último contacto |
| Memoria | Estado de memoria de conversación |

---

## 🚀 Dashboard Avanzado con ROI
**URL:** [http://localhost:5001/advanced_dashboard](http://localhost:5001/advanced_dashboard)

### Descripción
Dashboard avanzado con métricas de negocio, ROI y análisis predictivo.

### Funcionalidades
- ✅ Métricas de conversión y funnel
- ✅ Análisis ROI detallado
- ✅ Análisis predictivo con tendencias
- ✅ Recomendaciones automáticas
- ✅ Distribución por canales de origen

### Secciones Principales
1. **Métricas de Conversión**
   - Funnel completo de ventas
   - Tasas de conversión por estado
   - Distribución por temperatura

2. **Análisis ROI**
   - Inversión total vs ingresos
   - ROI actual y potencial
   - Costo por lead/venta
   - Valor del pipeline

3. **Análisis Predictivo**
   - Tendencias de leads y conversión
   - Predicciones 30 días
   - Recomendaciones de acción

---

## 🤖 Dashboard de Contactos Proactivos
**URL:** [http://localhost:5001/contactos_proactivos](http://localhost:5001/contactos_proactivos)

### Descripción
Dashboard especializado para gestión de contactos proactivos con sistema de plantillas WhatsApp Business.

### Funcionalidades Principales
- ✅ **Formulario de agregar contactos** con plantillas obligatorias
- ✅ **Vista de contactos pendientes** con información completa
- ✅ **Estadísticas de envío** y respuesta
- ✅ **Seguimiento automático** configurable
- ✅ **Envío masivo** de contactos pendientes

### Sección 1: Estadísticas Generales
| Métrica | Descripción |
|---------|-------------|
| Total | Total de contactos en sistema |
| Pendientes | Contactos pendientes de envío |
| Enviados | Contactos ya procesados |
| Respondidos | Contactos que han respondido |
| Errores | Contactos con errores de envío |

### Sección 2: Contactos Pendientes
**Tabla con columnas:**
| Columna | Descripción |
|---------|-------------|
| Prioridad | 🔴 Alta / 🟡 Media / 🟢 Baja |
| Nombre | Nombre del contacto |
| Teléfono | Número con +52 |
| Tipo | Tipo de campaña |
| **Plantilla** | Plantilla WhatsApp a usar |
| Contexto | Información del lead (truncada) |
| Programado | Tiempo de envío |
| Observaciones | Notas adicionales |

**Acciones disponibles:**
- 🚀 **Enviar Todos Ahora** - Procesa todos los contactos pendientes
- 🧪 **Enviar Prueba** - Envía contacto de prueba

### Sección 3: Formulario Agregar Contacto

#### Campos Obligatorios
- **Teléfono**: Formato +52XXXXXXXXXX
- **Nombre**: Nombre del contacto
- **Plantilla WhatsApp**: Selección obligatoria
  - `saludo_lead` - Primer contacto general
  - `recordatorio_cita` - Para citas agendadas
- **Contexto**: Descripción detallada del lead

#### Campos Opcionales
- **Tipo de Campaña**: seguimiento, promoción, reactivación, prospecto_nuevo
- **Prioridad**: Alta (inmediato), Media (próximo ciclo), Baja (conveniente)
- **Mensaje Personalizado**: Mensaje específico (opcional)
- **Observaciones**: Notas adicionales
- **Seguimiento Automático**: ✅ Activar mensajes cada 20 horas (máx 5)

### Sección 4: Distribución por Tipo
Lista de cantidad de contactos por tipo de campaña.

---

## 🔧 Endpoints de Gestión

### Contactos Proactivos
- `POST /agregar_contacto_proactivo` - Agregar nuevo contacto con plantilla
- `GET /enviar_contactos_ahora` - Enviar todos los contactos pendientes
- `GET /test_contacto_proactivo` - Enviar contacto de prueba

### Testing y Validación
- `GET /test` - Prueba todos los servicios
- `GET /test_memoria` - Prueba memoria básica
- `GET /test_memoria_mejorada` - Prueba memoria avanzada
- `GET /test_sentiment` - Prueba análisis de sentimientos

---

## 📱 Sistema de Plantillas WhatsApp

### Plantillas Disponibles
1. **saludo_lead** - Para primer contacto con nuevos leads
2. **recordatorio_cita** - Para recordatorios de citas agendadas

### Lógica de Uso
- **Nuevo contacto**: Obligatorio usar plantilla (políticas Meta)
- **Contacto existente**: Puede usar mensaje personalizado
- **Seguimiento automático**: Mensajes cada 20 horas para mantener ventana de 24h

### Cumplimiento Meta
- ✅ Primer contacto siempre con plantilla aprobada
- ✅ Ventana de 24 horas mantenida
- ✅ Máximo 5 mensajes de seguimiento
- ✅ Detección automática nuevo vs existente

---

## 🚨 Indicadores de Estado

### Prioridades de Contacto
- 🔴 **Alta**: Envío inmediato
- 🟡 **Media**: Próximo ciclo de envío
- 🟢 **Baja**: Cuando sea conveniente

### Estados de Lead
- **Contacto Inicial** → **Calificando** → **Calificado** → **Interesado Alto** → **Cita Agendada** → **Vendido**
- **Estados de pérdida**: Perdido por precio, crédito, interés, descalificado

### Temperatura de Lead
- 🔥 **Caliente**: Alta probabilidad de compra
- 🌡️ **Tibio**: Interés moderado
- ❄️ **Frío**: Interés exploratorio

---

## 📊 Navegación Rápida

| Dashboard | URL | Propósito Principal |
|-----------|-----|-------------------|
| Principal | `/` | Vista general del sistema |
| Leads | `/dashboard` | Seguimiento básico de leads |
| Avanzado | `/advanced_dashboard` | ROI y métricas de negocio |
| Contactos Proactivos | `/contactos_proactivos` | Gestión de plantillas WhatsApp |

---

**Actualizado:** 2025-07-08  
**Versión:** 3.0.0 con Sistema de Plantillas WhatsApp Business