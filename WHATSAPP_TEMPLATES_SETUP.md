# WhatsApp Business Templates Setup

## Templates que necesitas crear en Meta Business Manager

### 1. Template: `saludo_lead`
- **Nombre**: saludo_lead
- **Categoría**: MARKETING
- **Idioma**: Español (es)
- **Contenido**:
```
¡Hola! 😊 Soy César de Nissan. Vi que andas buscando auto, ¿te gustaría que te platique sobre nuestros modelos y promociones actuales?
```

### 2. Template: `recordatorio_cita`
- **Nombre**: recordatorio_cita
- **Categoría**: MARKETING
- **Idioma**: Español (es)
- **Contenido**:
```
¡Hola! 😊 Te recuerdo que tienes una cita con nosotros en Nissan. ¿Sigues disponible o necesitas reagendar?
```

## Pasos para crear templates en Meta Business Manager:

1. **Ir a Business Manager**
   - Visita: https://business.facebook.com/
   - Selecciona tu cuenta de negocio

2. **Navegar a WhatsApp Manager**
   - En el menú lateral, busca "WhatsApp" o "WhatsApp Manager"
   - Selecciona tu número de teléfono comercial

3. **Ir a Message Templates**
   - En WhatsApp Manager, ve a "Message Templates"
   - Haz clic en "Create Template"

4. **Crear cada template**:
   - **Name**: Usar exactamente `saludo_lead` o `recordatorio_cita`
   - **Category**: MARKETING
   - **Language**: Spanish (es)
   - **Header**: Dejar vacío
   - **Body**: Copiar el contenido exacto de arriba
   - **Footer**: Dejar vacío
   - **Buttons**: No agregar

5. **Enviar para aprobación**
   - Haz clic en "Submit"
   - Espera la aprobación de Meta (puede tomar 24-48 horas)

## Variables de entorno necesarias:

Para obtener plantillas via API, necesitas:

```bash
# En tu archivo .env
WHATSAPP_TOKEN=tu_token_aquí
PHONE_NUMBER_ID=tu_phone_number_id
WHATSAPP_BUSINESS_ACCOUNT_ID=tu_business_account_id
```

### Cómo obtener WHATSAPP_BUSINESS_ACCOUNT_ID:

1. Ve a https://developers.facebook.com/
2. Selecciona tu app de WhatsApp
3. Ve a "WhatsApp" > "Getting Started"
4. Copia el "WhatsApp Business Account ID"

## Verificación:

Una vez creados y aprobados, verifica que funcionan:

1. Ejecuta el endpoint: `GET /plantillas_whatsapp`
2. Deberías ver tus templates en la respuesta
3. Prueba enviar un contacto proactivo con template

## Troubleshooting:

- Si ves error 132001: El template no existe o no está aprobado
- Si ves error 100: Problema con permisos o Business Account ID
- Si ves error 131000: Problema con el formato del template

## Fallback automático:

El sistema ya tiene fallback automático - si los templates no funcionan, enviará mensajes personalizados automáticamente.