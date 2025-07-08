# 📱 Guía para Crear Plantillas WhatsApp Business

## 🎯 ¿Por qué necesitas plantillas?

Las **políticas de Meta** requieren que el **primer contacto** con un cliente siempre use una **plantilla aprobada**. No puedes enviar mensajes de texto libre como primer contacto.

## 🚀 Cómo crear plantillas en Meta Business Manager

### Paso 1: Acceder a Meta Business Manager
1. Ve a [business.facebook.com](https://business.facebook.com/)
2. Inicia sesión con tu cuenta de Meta Business
3. Selecciona tu cuenta de negocio

### Paso 2: Navegar a WhatsApp
1. En el menú lateral, busca **"WhatsApp"**
2. Haz clic en **"Plantillas de mensaje"**
3. Verás la lista de plantillas existentes

### Paso 3: Crear nueva plantilla
1. Haz clic en **"Crear plantilla"**
2. Completa la información:

#### Información básica:
- **Nombre**: `saludo_lead` o `recordatorio_cita`
- **Categoría**: Selecciona `MARKETING` o `UTILITY`
- **Idioma**: `Español (ES)`

#### Contenido de la plantilla:

**Para `saludo_lead`:**
```
¡Hola {{1}}! 😊 

Soy César de Nissan. Me da mucho gusto saludarte. 

¿En qué modelo de Nissan estás interesado? Tengo excelentes promociones para ti.

¿Cuándo te viene bien platicar?
```

**Para `recordatorio_cita`:**
```
¡Hola {{1}}! 📅 

Te recuerdo que tienes una cita pendiente con nosotros en Nissan. 

¿Podrías confirmarme si sigues interesado? ¡Tengo muy buenas noticias para ti!

Espero tu respuesta.
```

### Paso 4: Configurar parámetros
- **{{1}}**: Será reemplazado por el nombre del cliente
- Los emojis son permitidos y recomendados
- Mantén el tono conversacional y amigable

### Paso 5: Enviar para aprobación
1. Revisa el contenido
2. Haz clic en **"Enviar"**
3. **Tiempo de aprobación**: 24-48 horas típicamente

## ✅ Verificar plantillas aprobadas

Una vez aprobadas, puedes verificar tus plantillas:

1. **En el dashboard**: Ve a `/plantillas_whatsapp`
2. **En Meta Business**: Revisa el estado en la sección de plantillas

## 🔧 Actualizar el sistema

Una vez que tengas plantillas aprobadas:

### 1. Actualizar nombres en el dropdown
Edita el archivo `app.py` línea ~2818:

```html
<select id="template_whatsapp" name="template_whatsapp" required>
    <option value="">Seleccione una plantilla</option>
    <option value="tu_plantilla_real_1">Descripción de plantilla 1</option>
    <option value="tu_plantilla_real_2">Descripción de plantilla 2</option>
</select>
```

### 2. Actualizar lógica de parámetros
En `services/contactos_proactivos.py`, actualiza la función `enviar_plantilla_whatsapp` con los nombres reales.

## 🚨 Consideraciones importantes

### Políticas de Meta:
- ✅ Primer contacto **SIEMPRE** con plantilla aprobada
- ✅ Después puedes usar mensajes de texto libre (dentro de 24 horas)
- ✅ Contenido debe ser relevante y no spam
- ❌ No puedes cambiar plantillas aprobadas sin nueva aprobación

### Mejores prácticas:
- 🎯 **Personalización**: Usa el nombre del cliente (`{{1}}`)
- 😊 **Tono amigable**: Incluye emojis y saludo cálido
- 📞 **Call to action**: Pregunta clara para generar respuesta
- ⏰ **Timing**: Respeta horarios comerciales

## 🔄 Sistema de Fallback

Si las plantillas no existen, el sistema automáticamente:

1. **Detecta el error** de plantilla no encontrada
2. **Cambia a mensaje personalizado** similar al contenido de la plantilla
3. **Mantiene la funcionalidad** sin interrumpir el flujo

## 📋 Plantillas recomendadas para Nissan

### Plantilla: `nissan_saludo_inicial`
```
¡Hola {{1}}! 👋

Soy César Arias, asesor de ventas Nissan.

Vi tu interés en nuestros vehículos. ¿Te puedo ayudar con información sobre algún modelo en particular?

¡Tenemos excelentes promociones este mes!
```

### Plantilla: `nissan_seguimiento_cotizacion`
```
¡Hola {{1}}! 😊

¿Qué tal? Te escribo para dar seguimiento a la cotización del {{2}} que platicamos.

¿Tienes alguna duda o te gustaría agendar una cita para ver el vehículo?

¡Estoy aquí para apoyarte!
```

### Plantilla: `nissan_recordatorio_cita`
```
¡Hola {{1}}! 📅

Te confirmo tu cita para mañana {{2}} para ver el {{3}}.

¿Necesitas cambiar el horario o tienes alguna pregunta específica?

¡Te esperamos en la agencia!
```

## 🛠️ Troubleshooting

### Error: "Template does not exist"
- ✅ Verifica que la plantilla esté **APROBADA** en Meta Business
- ✅ Confirma que el nombre coincide exactamente
- ✅ Revisa que el idioma sea `es` (español)

### Error: "Parameter mismatch"
- ✅ Verifica que envías el número correcto de parámetros
- ✅ Confirma que los parámetros son del tipo correcto (texto)

### Plantilla rechazada:
- 🔍 Revisa que el contenido no sea spam
- 🔍 Asegúrate de que sea relevante para tu negocio
- 🔍 Evita contenido promocional excesivo

## 📞 Soporte

Si necesitas ayuda:
- 📧 Meta Business Support
- 📚 [Documentación oficial de WhatsApp Business API](https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates)
- 🤖 Dashboard del sistema: `/plantillas_whatsapp`

---

**Fecha**: 2025-07-08  
**Versión**: 1.0  
**Sistema**: Nissan WhatsApp Bot con plantillas Meta