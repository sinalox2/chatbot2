# app.py - Versión final completa con memoria mejorada Y sistema de citas
from flask import Flask, request, Response, jsonify
import html
from twilio.twiml.messaging_response import MessagingResponse
import os
from dotenv import load_dotenv
import openai
from datetime import datetime, timedelta
import re
import sys

# Cargar variables de entorno
load_dotenv(override=True)

# Verificar que los directorios existen
if not os.path.exists('models'):
    os.makedirs('models')
if not os.path.exists('services'):
    os.makedirs('services')

# Intentar importar los servicios
try:
    from services.lead_tracking_service import LeadTrackingService
    from models.lead_tracking import EstadoLead, TipoInteraccion, Interaccion, TemperaturaMercado
    from supabase_client import supabase
    TRACKING_AVAILABLE = True
    print("✅ Servicios de tracking importados correctamente")
except ImportError as e:
    print(f"⚠️ Error importando servicios de tracking: {e}")
    TRACKING_AVAILABLE = False
    supabase = None

# Intentar importar seguimiento automático
try:
    from services.seguimiento_automatico import SeguimientoAutomaticoService
    SEGUIMIENTO_AVAILABLE = True
    print("✅ Servicio de seguimiento automático importado")
except ImportError as e:
    print(f"⚠️ Error importando seguimiento automático: {e}")
    SEGUIMIENTO_AVAILABLE = False

# ========= AGREGAR AL INICIO DEL ARCHIVO (DE app_with_calendar.py) =========
# Importar el nuevo servicio de calendario
try:
    from services.calendar_service import CalendarService, procesar_solicitud_cita, confirmar_cita_seleccionada
    CALENDAR_AVAILABLE = True
    print("✅ Servicio de calendario importado correctamente")
except ImportError as e:
    print(f"⚠️ Error importando servicio de calendario: {e}")
    CALENDAR_AVAILABLE = False

# Configurar OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ No se encontró OPENAI_API_KEY en variables de entorno")
    sys.exit(1)

client = openai.OpenAI(api_key=api_key)

# Configurar RAG (opcional)
try:
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings

    ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
    vector_db_path = os.path.join(ROOT_DIR, "vector_db_sicrea")

    if os.path.exists(vector_db_path):
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vector_db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True)
        RAG_AVAILABLE = True
        print("✅ RAG (base de conocimiento) cargado correctamente")
    else:
        RAG_AVAILABLE = False
        print("⚠️ No se encontró vector_db_sicrea, funcionando sin RAG")

except ImportError as e:
    print(f"⚠️ Error importando RAG: {e}")
    RAG_AVAILABLE = False

# Importar nuevas funcionalidades
try:
    from services.sentiment_analyzer import SentimentAnalyzer
    from services.advanced_dashboard import AdvancedDashboard, generar_reporte_completo
    from services.notification_system import NotificationSystem, notificar_evento
    from services.intelligent_followup import IntelligentFollowup, generar_plan_seguimiento_para_lead
    ADVANCED_FEATURES = True
    print("✅ Funcionalidades avanzadas importadas correctamente")
except ImportError as e:
    print(f"⚠️ Error importando funcionalidades avanzadas: {e}")
    ADVANCED_FEATURES = False

def recuperar_contexto(pregunta):
    """Recupera contexto de la base de conocimiento si está disponible"""
    if RAG_AVAILABLE:
        try:
            resultados = vector_db.similarity_search(pregunta, k=2)
            return "\n\n".join([doc.page_content for doc in resultados])
        except Exception as e:
            print(f"Error en RAG: {e}")

    return """
    SICREA ofrece financiamiento automotriz con:
    - Plan Sí Fácil: Para personas con mal buró o sin comprobación de ingresos
    - Plan Cronos: Financiamiento tradicional
    - Enganches desde $15,000 pesos
    - Mensualidades competitivas
    """

def obtener_prompt_sistema_mejorado():
    """Obtiene el prompt del sistema mejorado"""
    prompt_path = "prompt_sistema_nissan.txt"
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    else:
        return """
        Eres César Arias, asesor de ventas Nissan. Responde de forma amigable y profesional.
        Mantén respuestas cortas (máximo 2 líneas). Usa emoji 😁.
        Tu objetivo es calificar leads y agendar citas. Teléfono: 6644918078.
        Tienes memoria completa de conversaciones anteriores.
        """

def obtener_historial_conversacion_completo(telefono):
    """Obtiene historial completo con información enriquecida del lead"""
    historial_completo = []

    try:
        # 1. Obtener de la tabla antigua historial_conversaciones
        if supabase:
            response_antiguo = supabase.table('historial_conversaciones').select('mensaje, respuesta, timestamp').eq('telefono', telefono).order('timestamp', desc=False).execute()

            for entrada in response_antiguo.data:
                historial_completo.append({
                    "role": "user",
                    "content": entrada["mensaje"],
                    "timestamp": entrada.get("timestamp", "")
                })
                historial_completo.append({
                    "role": "assistant",
                    "content": entrada["respuesta"],
                    "timestamp": entrada.get("timestamp", "")
                })

        # 2. Obtener de la nueva tabla interacciones_leads (más recientes)
        if supabase and TRACKING_AVAILABLE:
            response_nuevo = supabase.table('interacciones_leads').select('tipo, descripcion, fecha').eq('telefono', telefono).order('fecha', desc=False).execute()

            for interaccion in response_nuevo.data:
                if interaccion['tipo'] == 'mensaje_entrante':
                    descripcion = interaccion['descripcion']
                    if descripcion.startswith('Cliente: '):
                        mensaje = descripcion.replace('Cliente: ', '')
                        historial_completo.append({
                            "role": "user",
                            "content": mensaje,
                            "timestamp": interaccion['fecha']
                        })
                elif interaccion['tipo'] == 'respuesta_bot':
                    descripcion = interaccion['descripcion']
                    if descripcion.startswith('Bot: '):
                        respuesta = descripcion.replace('Bot: ', '')
                        historial_completo.append({
                            "role": "assistant",
                            "content": respuesta,
                            "timestamp": interaccion['fecha']
                        })

        # 3. Ordenar por timestamp y limitar a últimas 20 interacciones
        historial_completo.sort(key=lambda x: x.get('timestamp', ''))
        return historial_completo[-20:]

    except Exception as e:
        print(f"❌ Error obteniendo historial: {e}")
        return []

def extraer_info_relevante_historial(historial):
    """Extrae información clave del historial para contexto resumido"""
    info_relevante = {
        'modelos_mencionados': set(),
        'montos_enganche': [],
        'citas_previas': False,
        'cotizaciones_previas': False,
        'ultimo_tema': None
    }

    for entrada in historial:
        contenido = entrada['content'].lower()

        # Detectar modelos mencionados
        modelos = ['sentra', 'versa', 'march', 'frontier', 'kicks', 'x-trail', 'pathfinder', 'altima']
        for modelo in modelos:
            if modelo in contenido:
                info_relevante['modelos_mencionados'].add(modelo.title())

        # Detectar montos
        montos = re.findall(r'\$?\d+(?:,\d{3})*(?:\.\d{2})?', contenido)
        if montos:
            info_relevante['montos_enganche'].extend(montos)

        # Detectar citas o cotizaciones previas
        if any(palabra in contenido for palabra in ['cita', 'agendar', 'visitar']):
            info_relevante['citas_previas'] = True
        if any(palabra in contenido for palabra in ['cotización', 'precio', 'costo']):
            info_relevante['cotizaciones_previas'] = True

    if historial:
        info_relevante['ultimo_tema'] = historial[-1]['content'][:50]

    return info_relevante

def construir_contexto_conversacion_mejorado(telefono, mensaje_actual):
    """Construye contexto enriquecido con información del lead y resumen del historial"""
    try:
        historial = obtener_historial_conversacion_completo(telefono)
        info_historial = extraer_info_relevante_historial(historial)

        lead_info = None
        if TRACKING_AVAILABLE and lead_tracker: # Asegúrate que lead_tracker esté definido
            lead = lead_tracker.obtener_lead(telefono)
            if lead:
                lead_info = {
                    'nombre': lead.nombre,
                    'estado': lead.estado.value,
                    'temperatura': lead.temperatura.value,
                    'score': lead.score_calificacion,
                    'dias_sin_contacto': lead.dias_sin_interaccion(),
                    'modelo_interes': lead.info_prospecto.modelo_interes,
                    'enganche': lead.info_prospecto.monto_enganche,
                    'uso_vehiculo': lead.info_prospecto.uso_vehiculo,
                    'comprobacion_ingresos': lead.info_prospecto.comprobacion_ingresos,
                    'historial_credito': lead.info_prospecto.historial_credito
                }

        messages = []
        prompt_sistema = obtener_prompt_sistema_mejorado()

        if lead_info:
            contexto_lead = f"\n\n📋 INFORMACIÓN DEL CLIENTE:\n"
            contexto_lead += f"- Nombre: {lead_info['nombre']}\n"
            contexto_lead += f"- Estado actual: {lead_info['estado']}\n"
            contexto_lead += f"- Temperatura: {lead_info['temperatura']}\n"
            contexto_lead += f"- Score: {lead_info['score']:.1f}\n"

            if lead_info['dias_sin_contacto'] > 0:
                contexto_lead += f"- Días sin contacto: {lead_info['dias_sin_contacto']}\n"

            if lead_info['modelo_interes']:
                contexto_lead += f"- Modelo de interés: {lead_info['modelo_interes']}\n"

            if lead_info['enganche']:
                contexto_lead += f"- Enganche disponible: ${lead_info['enganche']:,.0f}\n"

            if lead_info['uso_vehiculo']:
                contexto_lead += f"- Uso del vehículo: {lead_info['uso_vehiculo']}\n"

            if lead_info['comprobacion_ingresos']:
                contexto_lead += f"- Comprobación ingresos: {lead_info['comprobacion_ingresos']}\n"

            if lead_info['historial_credito']:
                contexto_lead += f"- Historial crediticio: {lead_info['historial_credito']}\n"

            prompt_sistema += contexto_lead

        if info_historial['modelos_mencionados'] or info_historial['citas_previas']:
            contexto_historial = f"\n\n💬 HISTORIAL RELEVANTE:\n"

            if info_historial['modelos_mencionados']:
                contexto_historial += f"- Modelos discutidos: {', '.join(info_historial['modelos_mencionados'])}\n"

            if info_historial['citas_previas']:
                contexto_historial += f"- Ha mostrado interés en agendar cita\n"

            if info_historial['cotizaciones_previas']:
                contexto_historial += f"- Ha solicitado cotizaciones\n"

            if info_historial['montos_enganche']:
                contexto_historial += f"- Montos mencionados: {', '.join(info_historial['montos_enganche'][:3])}\n"

            prompt_sistema += contexto_historial

        messages.append({"role": "system", "content": prompt_sistema})

        for entrada in historial[-6:]: # Mantener el historial corto para el prompt
            if entrada['role'] in ['user', 'assistant']:
                messages.append({
                    "role": entrada['role'],
                    "content": entrada['content']
                })

        messages.append({
            "role": "user",
            "content": mensaje_actual
        })

        return messages, lead_info

    except Exception as e:
        print(f"❌ Error construyendo contexto mejorado: {e}")
        return [
            {"role": "system", "content": obtener_prompt_sistema_mejorado()},
            {"role": "user", "content": mensaje_actual}
        ], None

def generar_respuesta_con_contexto_inteligente(mensaje, telefono, lead_info, siguiente_paso=None):
    """Genera respuesta con OpenAI considerando el contexto y siguiente paso"""
    try:
        # Construir contexto base
        messages, lead_info_completa = construir_contexto_conversacion_mejorado(telefono, mensaje)

        # Agregar instrucciones específicas según la acción
        instrucciones_extra = ""

        if siguiente_paso:
            accion = siguiente_paso.get('accion', '')

            if accion == 'saludo_inicial':
                instrucciones_extra = """
                INSTRUCCIÓN: Es el primer contacto. Saluda de forma amigable y casual.
                NO preguntes todo de jalón. Solo menciona que vendes Nissan y pregunta
                qué le interesa o en qué le puedes ayudar.
                """
            elif accion == 'obtener_info_sutil':
                info_faltante = siguiente_paso.get('info_faltante', '')
                if info_faltante == 'uso_vehiculo':
                    instrucciones_extra = """
                    INSTRUCCIÓN: En algún momento natural de la conversación,
                    pregunta sutilmente si el carro es para uso personal o trabajo.
                    Pero NO lo hagas de forma directa o robótica.
                    """
                elif info_faltante == 'monto_enganche':
                    instrucciones_extra = """
                    INSTRUCCIÓN: Menciona casualmente los enganches y pregunta
                    si ya tiene idea de cuánto podría dar de entrada.
                    Hazlo parte natural de la plática, no como interrogatorio.
                    """
            elif accion == 'responder_precio':
                instrucciones_extra = """
                INSTRUCCIÓN: El cliente pregunta por precios. Dale rangos generales
                y menciona que depende del modelo y plan de financiamiento.
                Invítalo a platicar más detalles.
                """
            elif accion == 'conversacion_natural':
                instrucciones_extra = """
                INSTRUCCIÓN: Mantén una conversación natural y amigable.
                NO forces preguntas de calificación. Solo platica y ve conociendo
                al cliente poco a poco.
                """
            elif accion == 'cerrar_cita':
                instrucciones_extra = """
                INSTRUCCIÓN: El cliente está interesado. Propón una cita o llamada
                de forma entusiasta pero sin presionar. Dale opciones.
                Si CALENDAR_AVAILABLE es True, el sistema ya habrá ofrecido slots,
                tu respuesta debe guiar al usuario si no eligió uno.
                Si CALENDAR_AVAILABLE es False, ofrece agendar manualmente.
                """
            # ========= NUEVO: INSTRUCCIONES PARA CITAS (DE app_with_calendar.py) =========
            elif accion == 'mostrar_opciones_cita' or accion == 'mostrar_opciones_cita_avanzada':
                 instrucciones_extra = """
                 INSTRUCCIÓN: El sistema ha presentado opciones de cita.
                 Tu rol es reforzar que elija una opción o pregunte por alternativas.
                 Sé breve y amigable. No repitas los horarios.
                 """
            elif accion == 'cita_confirmada':
                instrucciones_extra = """
                INSTRUCCIÓN: La cita ha sido confirmada por el sistema.
                Felicita al cliente y reitera entusiasmo.
                Puedes preguntar si tiene alguna duda antes de la cita.
                """
            elif accion == 'error_cita' or accion == 'error_calendario':
                instrucciones_extra = """
                INSTRUCCIÓN: Hubo un problema agendando la cita con el sistema.
                Discúlpate brevemente y ofrece agendar manualmente o intentar de nuevo.
                """
            elif accion == 'aclarar_seleccion_cita':
                instrucciones_extra = """
                INSTRUCCIÓN: El cliente no seleccionó una opción de cita válida.
                Recuérdale amablemente que elija un número de las opciones dadas.
                """

        # Agregar instrucciones al prompt del sistema
        if instrucciones_extra and len(messages) > 0:
            messages[0]['content'] += f"\n\n🎯 CONTEXTO ACTUAL:\n{instrucciones_extra}"

        # Agregar recordatorio de NO ser repetitivo
        if len(messages) > 0:
            messages[0]['content'] += """

            ⚠️ IMPORTANTE: NUNCA repitas preguntas que ya hiciste.
            Revisa el historial y si ya tienes información, NO la vuelvas a pedir.
            Si el cliente ya te dio el enganche, NO preguntes por el enganche otra vez.
            Sé creativo y varía tus respuestas.
            Si se están agendando citas, sigue el flujo de citas.
            """

        # Generar respuesta
        completion = client.chat.completions.create(
            model="gpt-4o", # o "gpt-3.5-turbo" si prefieres
            messages=messages,
            max_tokens=150,
            temperature=0.8
        )

        respuesta = completion.choices[0].message.content.strip()

        # Guardar en historial
        if supabase:
            try:
                supabase.table('historial_conversaciones').insert({
                    'telefono': telefono,
                    'mensaje': mensaje,
                    'respuesta': respuesta,
                    'timestamp': datetime.now().isoformat()
                }).execute()
            except Exception as e:
                print(f"⚠️ Error guardando historial: {e}")

        return respuesta

    except Exception as e:
        print(f"❌ Error generando respuesta inteligente: {e}")
        return "¡Ups! 😁 Se me fue la onda... ¿Me repites qué necesitas?"

def generar_respuesta_openai(mensaje, lead_info, telefono=None):
    """Genera respuesta usando OpenAI - SIEMPRE con memoria mejorada"""

    if telefono:
        print(f"🧠 Usando memoria mejorada para: {telefono}")
        return generar_respuesta_con_contexto_inteligente(mensaje, telefono, lead_info, None)

    try:
        prompt_sistema = obtener_prompt_sistema_mejorado()
        contexto = recuperar_contexto(mensaje)
        nombre = 'amigo'
        if isinstance(lead_info, dict):
            nombre = lead_info.get('nombre', 'amigo')
        elif hasattr(lead_info, 'nombre'): # Para objetos lead
            nombre = lead_info.nombre


        messages = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Cliente: {nombre}\n\nInformación útil:\n{contexto}\n\nPregunta del cliente:\n{mensaje}"}
        ]

        completion = client.chat.completions.create(
            model="gpt-4o", # o "gpt-3.5-turbo"
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        print(f"❌ Error generando respuesta OpenAI: {e}")
        return f"Hola {nombre}! 😁 Disculpa, tuve un pequeño problema. ¿Puedes repetir tu pregunta?"


class LeadManager:
    """
    Clase base para manejo de leads.
    Define la interfaz común para todos los managers de leads.
    """
    def __init__(self, lead_tracker=None):
        self.lead_tracker = lead_tracker

    def procesar_mensaje_lead(self, telefono, mensaje, nombre_perfil):
        """
        Procesa un mensaje entrante de un lead.
        Debe ser implementado por las clases hijas.
        """
        raise NotImplementedError("Las clases hijas deben implementar este método")

    def extraer_informacion_mensaje(self, mensaje, lead):
        """
        Extrae información relevante del mensaje.
        Debe ser implementado por las clases hijas.
        """
        raise NotImplementedError("Las clases hijas deben implementar este método")

    def determinar_siguiente_paso(self, lead, mensaje):
        """
        Determina el siguiente paso en el flujo de ventas.
        Debe ser implementado por las clases hijas.
        """
        raise NotImplementedError("Las clases hijas deben implementar este método")

    def programar_seguimiento_automatico(self, lead):
        """
        Programa seguimiento automático para el lead.
        Debe ser implementado por las clases hijas.
        """
        raise NotImplementedError("Las clases hijas deben implementar este método")

# ========= MODIFICAR LA CLASE ConversationalLeadManager (DE app_with_calendar.py) =========
class ConversationalLeadManager(LeadManager):
    """
    Manager conversacional avanzado para leads - CON INTEGRACIÓN DE CITAS
    """
    def __init__(self, lead_tracker, seguimiento_auto=None):
        self.lead_tracker = lead_tracker
        self.seguimiento_auto = seguimiento_auto
        # Inicializar calendar_service solo si CALENDAR_AVAILABLE es True
        self.calendar_service = CalendarService() if CALENDAR_AVAILABLE else None
        print(f"🤖 ConversationalLeadManager inicializado. Calendar Service: {'Activado' if self.calendar_service else 'Desactivado'}")


        # Estados de conversación para citas
        self.estados_cita = {}  # telefono -> {estado: 'solicitando'/'confirmando', slots: [...]}

    def procesar_mensaje_lead(self, telefono, mensaje, nombre_perfil):
        lead = self.lead_tracker.obtener_lead(telefono)
        if not lead:
            lead = self.lead_tracker.crear_lead(telefono, nombre_perfil, "whatsapp")
            print(f"✅ Nuevo lead creado: {telefono}")

        interaccion = Interaccion(
            telefono=telefono,
            tipo=TipoInteraccion.MENSAJE_ENTRANTE,
            descripcion=f"Cliente: {mensaje}",
            fecha=datetime.now(),
            usuario='cliente'
        )
        self.lead_tracker.registrar_interaccion(interaccion)

        info_extraida = self.extraer_informacion_mensaje(mensaje, lead)
        if info_extraida:
            for campo, valor in info_extraida.items():
                self.lead_tracker.actualizar_info_prospecto(telefono, campo, valor)
                print(f"📝 Actualizado {campo}: {valor}")

        siguiente_paso = self.determinar_siguiente_paso(lead, mensaje)
        if siguiente_paso.get('nuevo_estado'):
            self.lead_tracker.cambiar_estado(
                telefono,
                siguiente_paso['nuevo_estado'],
                siguiente_paso.get('notas', '')
            )
        
        # Si la acción es 'cita_confirmada', el mensaje ya viene del calendar_service
        # y no necesita ser generado por la IA.
        if siguiente_paso.get('accion') == 'cita_confirmada' or \
           siguiente_paso.get('accion') == 'mostrar_opciones_cita' or \
           siguiente_paso.get('accion') == 'mostrar_opciones_cita_avanzada' or \
           siguiente_paso.get('accion') == 'error_calendario' or \
           siguiente_paso.get('accion') == 'cita_manual' or \
           siguiente_paso.get('accion') == 'aclarar_seleccion_cita' or \
           siguiente_paso.get('accion') == 'error_cita':
            respuesta_directa = siguiente_paso.get('mensaje')
            if respuesta_directa:
                 # Devolver el lead, el siguiente paso y la respuesta directa para que no la genere la IA
                return lead, siguiente_paso, respuesta_directa

        return lead, siguiente_paso, None # None indica que la IA debe generar la respuesta

    def extraer_informacion_mensaje(self, mensaje, lead):
        """
        Extrae información relevante del mensaje del cliente para enriquecer el lead.
        """
        info_extraida = {}
        mensaje_lower = mensaje.lower()
        print(f"📝 Extrayendo info de: {mensaje}")

        # Uso del vehículo
        if not lead.info_prospecto.uso_vehiculo:
            if any(word in mensaje_lower for word in ['particular', 'personal', 'familia', 'casa', 'diario']):
                info_extraida['uso_vehiculo'] = 'particular'
            elif any(word in mensaje_lower for word in ['trabajo', 'uber', 'didi', 'taxi', 'negocio', 'comercial', 'chambear', 'chamba']):
                info_extraida['uso_vehiculo'] = 'trabajo'

        # Comprobación de ingresos
        if not lead.info_prospecto.comprobacion_ingresos:
            if any(word in mensaje_lower for word in ['nomina', 'nómina', 'formal', 'empresa', 'empleado', 'recibo', 'comprobante']):
                info_extraida['comprobacion_ingresos'] = 'formal'
            elif any(word in mensaje_lower for word in ['informal', 'negocio', 'independiente', 'sin recibos', 'propio', 'no tengo comprobantes']):
                info_extraida['comprobacion_ingresos'] = 'informal'
            elif any(word in mensaje_lower for word in ['no tengo', 'sin ingresos', 'no compruebo', 'no puedo comprobar']):
                info_extraida['comprobacion_ingresos'] = 'ninguna'

        # Monto de enganche
        if not lead.info_prospecto.monto_enganche:
            numeros = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', mensaje.replace(' ', ''))
            if numeros:
                for numero in numeros:
                    try:
                        numero_limpio = numero.replace(',', '').replace('.', '')
                        monto = float(numero_limpio)
                        if 100 <= monto <= 999: # Asumir que son miles si es un número pequeño
                            monto *= 1000
                        if 5000 <= monto <= 500000: # Rango razonable para enganche
                            info_extraida['monto_enganche'] = monto
                            print(f"💰 Enganche detectado: ${monto:,.0f}")
                            break
                    except ValueError:
                        pass # Ignorar si no se puede convertir a float

        # Historial crediticio
        if not lead.info_prospecto.historial_credito:
            if any(word in mensaje_lower for word in ['bueno', 'bien', 'excelente', 'sin problemas', 'limpio', 'al corriente']):
                info_extraida['historial_credito'] = 'bueno'
            elif any(word in mensaje_lower for word in ['regular', 'mas o menos', 'más o menos', 'normal', 'algunos problemas', 'algún problema']):
                info_extraida['historial_credito'] = 'regular'
            elif any(word in mensaje_lower for word in ['malo', 'mal', 'problemas', 'buro', 'buró', 'deudas', 'atrasado']):
                info_extraida['historial_credito'] = 'malo'

        # Modelo de interés
        modelos_nissan = ['sentra', 'versa', 'march', 'frontier', 'kicks', 'x-trail', 'pathfinder', 'altima', 'murano', 'rogue']
        for modelo in modelos_nissan:
            if modelo in mensaje_lower:
                info_extraida['modelo_interes'] = modelo.title()
                break

        # Urgencia de compra
        if any(word in mensaje_lower for word in ['ya', 'pronto', 'inmediato', 'rapido', 'rápido', 'urgente', 'ahorita']):
            info_extraida['urgencia_compra'] = 'inmediata'
        elif any(word in mensaje_lower for word in ['mes', 'meses', '3 meses', 'proximamente', 'próximamente']):
            info_extraida['urgencia_compra'] = '3meses'
        elif any(word in mensaje_lower for word in ['año', 'tiempo', 'pensando', 'futuro']):
            info_extraida['urgencia_compra'] = 'año'

        print(f"📊 Info extraída: {info_extraida}")
        return info_extraida

    def determinar_siguiente_paso(self, lead, mensaje):
        """
        Determina el siguiente paso - INCLUYENDO MANEJO DE CITAS
        """
        mensaje_lower = mensaje.lower()
        telefono = lead.telefono
        info = lead.info_prospecto # Asegúrate que lead.info_prospecto existe
        print(f"📊 Estado Lead: {lead.estado.value}")
        # print(f"📊 Info Prospecto: uso={info.uso_vehiculo}, ingresos={info.comprobacion_ingresos}, enganche={info.monto_enganche}, credito={info.historial_credito}")

        # ========= NUEVO: MANEJO DE CITAS (DE app_with_calendar.py) =========

        # Verificar si está en proceso de agendar cita
        if telefono in self.estados_cita:
            estado_cita_actual = self.estados_cita[telefono]

            if estado_cita_actual['estado'] == 'esperando_seleccion':
                # Cliente está eligiendo horario
                if mensaje.strip().isdigit():
                    # El lead que se pasa a confirmar_cita_seleccionada debe tener la estructura esperada
                    lead_data_for_calendar = {
                        'nombre': lead.nombre,
                        'telefono': telefono,
                        'email': f"{telefono}@whatsapp.lead", # Email de placeholder
                        # Otros campos que CalendarService pueda necesitar, ej: 'modelo_interes'
                        'metadata': {'modelo_interes': info.modelo_interes if info else 'No especificado'}
                    }
                    resultado = confirmar_cita_seleccionada(
                        mensaje.strip(),
                        lead_data_for_calendar,
                        estado_cita_actual['slots']
                    )

                    if resultado['tipo'] == 'cita_confirmada':
                        # Actualizar estado del lead
                        self.lead_tracker.cambiar_estado(
                            telefono,
                            EstadoLead.CITA_AGENDADA,
                            f"Cita agendada via WhatsApp - Booking ID: {resultado.get('booking_id')}"
                        )
                        # Limpiar estado de cita
                        del self.estados_cita[telefono]
                        return {
                            'accion': 'cita_confirmada',
                            'nuevo_estado': EstadoLead.CITA_AGENDADA,
                            'mensaje': resultado['mensaje']
                        }
                    else:
                        # Error agendando
                        del self.estados_cita[telefono] # Limpiar para evitar bucles
                        return {
                            'accion': 'error_cita',
                            'mensaje': resultado['mensaje'] # Mensaje de error del servicio de calendario
                        }

                elif any(word in mensaje_lower for word in ['otro', 'diferente', 'cambio', 'no puedo', 'no me sirve']):
                    # Cliente quiere otro horario o no puede en los ofrecidos
                    del self.estados_cita[telefono]
                    return {
                        'accion': 'solicitar_cita_personalizada', # La IA debe manejar esto
                        'mensaje': f"Entendido {lead.nombre}. ¿Qué día y hora te vendrían bien para revisar la disponibilidad?"
                    }
                else:
                    # No entendió la opción, la IA debe pedir que aclare
                    return {
                        'accion': 'aclarar_seleccion_cita',
                         # El mensaje para la IA, no para el usuario directamente
                        'mensaje': f"Recuérdale a {lead.nombre} que elija una opción numérica o pida otro horario."
                    }

        # Detectar solicitud inicial de cita
        # Palabras clave más amplias para detectar intención de cita
        palabras_clave_cita = ['cita', 'agendar', 'visita', 'venir', 'ir', 'agencia', 'cuándo puedo', 'cuando puedo', 'ver los carros', 'disponibilidad']
        if any(word in mensaje_lower for word in palabras_clave_cita):
            if CALENDAR_AVAILABLE and self.calendar_service: # Asegurar que el servicio está disponible e inicializado
                print(f"📅 Detectada solicitud de cita para {telefono}. CALENDAR_AVAILABLE: {CALENDAR_AVAILABLE}")
                # Prepara la información del lead para el servicio de calendario
                lead_data_for_calendar = {
                    'nombre': lead.nombre,
                    'telefono': telefono,
                    'email': f"{telefono}@whatsapp.lead", # Email de placeholder
                    'metadata': {'modelo_interes': info.modelo_interes if info else 'No especificado'}
                }
                resultado = procesar_solicitud_cita(
                    mensaje,
                    lead_data_for_calendar
                )

                if resultado['tipo'] == 'opciones_cita':
                    # Guardar estado para próxima respuesta
                    self.estados_cita[telefono] = {
                        'estado': 'esperando_seleccion',
                        'slots': resultado['slots_disponibles']
                    }
                    return {
                        'accion': 'mostrar_opciones_cita', # Este mensaje SÍ va al usuario
                        'mensaje': resultado['mensaje']
                    }
                else: # 'error_calendario' o similar
                    return {
                        'accion': 'error_calendario', # La IA debe manejar esto
                        'mensaje': resultado.get('mensaje', f"Lo siento {lead.nombre}, parece que hay un problema con el sistema de citas en este momento. ¿Podemos intentarlo más tarde o te ayudo a coordinar manualmente?")
                    }
            else:
                print(f"📅 Solicitud de cita para {telefono}, pero CALENDAR_AVAILABLE es False o servicio no inicializado.")
                return { # Flujo manual si el calendario no está disponible
                    'accion': 'cita_manual', # La IA debe manejar esto
                    'mensaje': f"¡Perfecto {lead.nombre}! 😊 Para agendar tu cita, ¿qué día y hora te acomoda? También puedes llamarme al 6644918078."
                }

        # ========= RESTO DE LA LÓGICA ORIGINAL (DE app.py) =========
        # Asegurarse que 'info' (lead.info_prospecto) no sea None antes de acceder a sus atributos
        if not info:
            # Si no hay info_prospecto, podría ser un lead muy nuevo o un error.
            # Aquí se podría solicitar información básica o manejarlo como un contacto inicial.
            # Por ahora, asumiremos que si no hay 'info', es como un contacto inicial general.
             if lead.estado == EstadoLead.CONTACTO_INICIAL or lead.estado.value == 'contacto_inicial': # Comparar con el enum y el valor string
                return {
                    'accion': 'saludo_inicial', # Acción para la IA
                    # 'mensaje': será generado por la IA
                }
             else: # Si no es contacto inicial pero no hay info, la IA debe conversar naturalmente
                return {
                    'accion': 'conversacion_natural',
                    # 'mensaje': será generado por la IA
                }


        # Flujo avanzado según estado (asegurarse que lead.estado es el Enum y no el string)
        # Convertir a Enum si es string para comparación segura
        current_lead_estado_value = lead.estado.value if isinstance(lead.estado, EstadoLead) else lead.estado

        if current_lead_estado_value not in ['contacto_inicial', 'calificando']:
            if any(palabra in mensaje_lower for palabra in ['precio', 'cotización', 'modelo', 'plan', 'financiamiento', 'duda', 'consulta', 'versión']):
                return {
                    'accion': 'responder_duda_modelo', # Para la IA
                    # 'mensaje': f"¡Hola {lead.nombre}! 😁 Claro, dime qué modelo o plan te interesa y te paso toda la info."
                }
            else:
                return {
                    'accion': 'conversacion_ligera', # Para la IA
                    # 'mensaje': f"¡Hola {lead.nombre}! 😄 ¿Cómo vas con la decisión? ¿Tienes alguna duda sobre algún auto o plan?"
                }

        # Primer contacto
        if current_lead_estado_value == EstadoLead.CONTACTO_INICIAL.value: # Comparar con el valor del Enum
            # Ampliar palabras clave para el primer contacto
            if any(word in mensaje_lower for word in ['hola', 'info', 'informacion', 'precio', 'cotizar', 'ayuda', 'nissan', 'carro', 'auto']):
                return {
                    'accion': 'saludo_inicial', # Cambiado para que la IA salude primero de forma general
                    'nuevo_estado': EstadoLead.CALIFICANDO,
                    # 'mensaje': f"¡Qué onda {lead.nombre}! 😁 ¿El auto lo necesitas para chambear o para uso personal?"
                }

        # Proceso de calificación
        elif current_lead_estado_value == EstadoLead.CALIFICANDO.value: # Comparar con el valor del Enum
            if not info.uso_vehiculo:
                # La IA debe preguntar por el uso del vehículo
                return {
                    'accion': 'obtener_info_sutil',
                    'info_faltante': 'uso_vehiculo',
                    # 'mensaje': f"¿Para qué ocuparías el carro principalmente, {lead.nombre}? 😁"
                }
            elif not info.comprobacion_ingresos:
                 # La IA debe preguntar por la comprobación de ingresos
                return {
                    'accion': 'obtener_info_sutil',
                    'info_faltante': 'comprobacion_ingresos',
                    # 'mensaje': f"¿Cómo está tu situación con los comprobantes de ingresos, {lead.nombre}?"
                }
            elif not info.monto_enganche:
                # La IA debe preguntar por el monto de enganche
                return {
                    'accion': 'obtener_info_sutil',
                    'info_faltante': 'monto_enganche',
                    # 'mensaje': f"¿Más o menos cuánto tienes guardado para el enganche?"
                }
            elif not info.historial_credito:
                # La IA debe preguntar por el historial crediticio
                return {
                    'accion': 'obtener_info_sutil',
                    'info_faltante': 'historial_credito',
                    # 'mensaje': f"¿Todo bien con tu historial o hay algún detalle que deba saber?"
                }
            else: # Toda la información de calificación básica está completa
                return {
                    'accion': 'finalizar_calificacion', # Para la IA
                    'nuevo_estado': EstadoLead.CALIFICADO,
                    # 'mensaje': f"¡Ya quedó {lead.nombre}! 😁 Tengo varias opciones para ti... ¿te marco ahorita o prefieres que te mande la info por aquí?"
                }

        elif current_lead_estado_value == EstadoLead.CALIFICADO.value: # Comparar con el valor del Enum
            if any(word in mensaje_lower for word in ['si', 'sí', 'claro', 'dale', 'órale', 'va', 'llamame', 'llama', 'márcame', 'marca', 'ok']):
                return {
                    'accion': 'agendar_llamada', # Para la IA
                    'nuevo_estado': EstadoLead.INTERESADO_ALTO,
                    # 'mensaje': f"¡Órale! Te marco en unos minutos {lead.nombre} 😁 Mientras, ¿ya tienes en mente algún modelo en especial?"
                }
            elif any(word in mensaje_lower for word in ['precio', 'costo', 'cuanto', 'cuánto', 'cotizar', 'info', 'información', 'modelo']):
                return {
                    'accion': 'solicitar_cotizacion', # Para la IA
                    'nuevo_estado': EstadoLead.INTERESADO_ALTO,
                    # 'mensaje': f"Claro que sí {lead.nombre}! 😁 ¿Qué modelo te late? ¿Versa, Sentra, Kicks...?"
                }
            elif any(word in mensaje_lower for word in ['no', 'luego', 'después', 'despues', 'ahorita no', 'pensar']):
                return {
                    'accion': 'mantener_interes', # Para la IA
                    # 'mensaje': f"No hay bronca {lead.nombre}, aquí andamos cuando gustes 😁 ¿Te mando la info de las promos actuales por si acaso?"
                }

        elif current_lead_estado_value == EstadoLead.INTERESADO_ALTO.value: # Comparar con el valor del Enum
            # La lógica de citas ya se maneja al inicio de esta función.
            # Si no es una solicitud de cita, la IA puede cotizar o conversar.
            if any(modelo in mensaje_lower for modelo in ['versa', 'sentra', 'march', 'kicks', 'frontier', 'x-trail']):
                return {
                    'accion': 'cotizar_modelo', # Para la IA
                    # 'mensaje': f"¡Buena elección! El {info.modelo_interes if info and info.modelo_interes else 'auto que mencionas'} está padrísimo 😁 Te mando los números..."
                }

        # Si ninguna condición anterior se cumple, la IA debe continuar la conversación.
        return {
            'accion': 'conversacion_natural', # Acción genérica para la IA
            # 'mensaje': será generado por la IA
        }


    def programar_seguimiento_automatico(self, lead):
        """
        Programa seguimiento automático basado en el estado del lead.
        """
        if not self.seguimiento_auto or not SEGUIMIENTO_AVAILABLE:
            print("📋 Seguimiento automático no disponible o no configurado.")
            return

        # Asegurarse que lead.temperatura es el Enum y no el string
        current_lead_temperatura = lead.temperatura
        if isinstance(lead.temperatura, str):
            try:
                current_lead_temperatura = TemperaturaMercado(lead.temperatura)
            except ValueError:
                print(f"⚠️ Temperatura desconocida '{lead.temperatura}' para lead {lead.telefono}. Usando FRÍO por defecto.")
                current_lead_temperatura = TemperaturaMercado.FRIO


        dias = 3 # Default frío
        if current_lead_temperatura == TemperaturaMercado.CALIENTE:
            dias = 1
        elif current_lead_temperatura == TemperaturaMercado.TIBIO:
            dias = 2

        # Asegurarse que lead.estado es el Enum y no el string
        current_lead_estado_value = lead.estado.value if isinstance(lead.estado, EstadoLead) else lead.estado

        try:
            self.seguimiento_auto.programar_seguimiento_especifico(
                lead.telefono,
                f'auto_{current_lead_estado_value}', # Usar el valor del estado
                dias,
                prioridad=3 if current_lead_temperatura == TemperaturaMercado.CALIENTE else (2 if current_lead_temperatura == TemperaturaMercado.TIBIO else 1)
            )
            print(f"🤖 Seguimiento automático programado para {lead.telefono} en {dias} días (estado: {current_lead_estado_value}).")
        except Exception as e:
            print(f"❌ Error programando seguimiento automático para {lead.telefono}: {e}")
# FIN: Clase ConversationalLeadManager

class SimpleLeadManager:
    """Manager simplificado para cuando no está disponible el tracking completo"""

    def __init__(self):
        self.leads_basicos = {} # telefono -> lead_data

    def procesar_mensaje_lead(self, telefono, mensaje, nombre_perfil):
        if telefono not in self.leads_basicos:
            self.leads_basicos[telefono] = {
                'nombre': nombre_perfil,
                'telefono': telefono,
                'mensajes': [],
                'info': {}, # Para almacenar datos como uso_vehiculo, etc.
                'fecha_creacion': datetime.now()
            }

        lead_basico = self.leads_basicos[telefono]
        lead_basico['mensajes'].append({
            'mensaje': mensaje,
            'fecha': datetime.now(),
            'tipo': 'entrante'
        })

        # Extracción básica de información (si aplica)
        info_extraida = self.extraer_informacion_basica(mensaje, lead_basico)
        if info_extraida:
            lead_basico['info'].update(info_extraida) # Actualizar info del lead básico

        siguiente_paso = self.determinar_siguiente_paso_basico(lead_basico, mensaje)
        
        # Para SimpleLeadManager, la respuesta viene directamente de 'siguiente_paso'
        # y no necesita ser generada por IA, a menos que el mensaje sea None.
        respuesta_directa = siguiente_paso.get('mensaje')

        return lead_basico, siguiente_paso, respuesta_directa


    def extraer_informacion_basica(self, mensaje, lead):
        info = {}
        mensaje_lower = mensaje.lower()

        if 'uso_vehiculo' not in lead['info']: # Solo extraer si no existe ya
            if any(word in mensaje_lower for word in ['particular', 'personal', 'familia']):
                info['uso_vehiculo'] = 'particular'
            elif any(word in mensaje_lower for word in ['trabajo', 'uber', 'didi', 'taxi']):
                info['uso_vehiculo'] = 'trabajo'

        if 'comprobacion_ingresos' not in lead['info']:
            if any(word in mensaje_lower for word in ['nomina', 'formal', 'empresa']):
                info['comprobacion_ingresos'] = 'formal'
            elif any(word in mensaje_lower for word in ['informal', 'negocio', 'independiente']):
                info['comprobacion_ingresos'] = 'informal'
        
        # Captura cualquier monto de enganche y permite avanzar el flujo.
        if 'monto_enganche' not in lead['info']:
            numeros = re.findall(r'\d+', mensaje.replace(',', '').replace('.', ''))
            if numeros:
                try:
                    monto = float(numeros[0])
                    if monto < 1000: # Si es un número como 20, 50, asumir que son miles
                        monto *= 1000
                    if monto > 0 : # Cualquier monto positivo
                        info['monto_enganche'] = monto
                except:
                    pass # Ignorar si no se puede convertir

        if 'historial_credito' not in lead['info']:
            if any(word in mensaje_lower for word in ['bueno', 'bien', 'excelente']):
                info['historial_credito'] = 'bueno'
            elif any(word in mensaje_lower for word in ['regular', 'mas o menos']):
                info['historial_credito'] = 'regular'
            elif any(word in mensaje_lower for word in ['malo', 'mal', 'problemas']):
                info['historial_credito'] = 'malo'
        return info

    def determinar_siguiente_paso_basico(self, lead, mensaje):
        # Este es un flujo MUY simplificado y directo, no usa IA para estas respuestas.
        mensaje_lower = mensaje.lower()
        info = lead['info']
        nombre = lead['nombre']

        # Flujo de calificación simplificado
        if len(lead['mensajes']) == 1: # Primer mensaje del lead
             return {
                'mensaje': f"¡Hola {nombre}! 😁 Soy César, tu asesor Nissan. ¿Buscas auto para uso particular o para trabajo?"
            }

        if 'uso_vehiculo' not in info:
            # El mensaje anterior ya preguntó esto, si el lead no contestó, la IA debería intervenir.
            # O aquí podrías tener una respuesta genérica si no se extrajo.
            # Para este manager simple, si no se extrajo, es probable que la IA deba generar la respuesta.
            # Si se extrajo en el mensaje actual, el siguiente if se activará.
            # Si no, necesitamos que la IA maneje esto.
            if not self.extraer_informacion_basica(mensaje, lead).get('uso_vehiculo'):
                 return {'mensaje': None} # Dejar que la IA lo maneje

        if 'comprobacion_ingresos' not in info:
            return {
                'mensaje': f"Entendido, {nombre}. ¿Tus ingresos los compruebas de manera formal (nómina, estados de cuenta) o informal (efectivo, negocio propio)?"
            }
        elif 'monto_enganche' not in info:
             return {
                'mensaje': f"¡Muy bien! ¿Tienes algún monto de enganche en mente? Desde $15,000 podemos empezar."
            }
        elif 'historial_credito' not in info: # Asumimos que si hay enganche, el siguiente es buró.
            return {
                'mensaje': f"¡Perfecto! Y para terminar, ¿cómo está tu historial en buró de crédito? (Bueno, regular o con detalles)"
            }
        
        # Si ya tenemos toda la info básica:
        if all(k in info for k in ['uso_vehiculo', 'comprobacion_ingresos', 'monto_enganche', 'historial_credito']):
            # Verificar si el enganche es suficiente
            if info.get('monto_enganche', 0) < 15000:
                 return {
                    'mensaje': (f"Gracias {nombre}. Veo que tu enganche es de ${info['monto_enganche']:,.0f}. "
                                f"Para la mayoría de los planes se recomienda un mínimo de $15,000. "
                                f"¿Podrías llegar a ese monto o buscamos alternativas?")
                }
            else: # Calificado básico!
                return {
                    'mensaje': (f"¡Excelente {nombre}! 😁 Con esta información ya podemos ver opciones. "
                                f"¿Te gustaría que te llame al {lead['telefono']} para platicar sobre los modelos y planes que te convienen, o prefieres seguir por aquí?")
                }

        # Si el cliente dice que sí a la llamada después de la calificación
        if any(word in mensaje_lower for word in ['si', 'sí', 'claro', 'llamame', 'llama', 'ok', 'dale']):
            # Verificar si ya se hizo la pregunta de calificación final
            if 'historial_credito' in info: # Asumimos que es la última pregunta
                 return {
                    'mensaje': f"¡Perfecto {nombre}! Te marco en un momento. 😁"
                }
        
        # Si no se cumple ninguna condición, la IA debe generar la respuesta.
        return {'mensaje': None}


# Inicializar servicios
if TRACKING_AVAILABLE:
    lead_tracker = LeadTrackingService()
else:
    lead_tracker = None

if SEGUIMIENTO_AVAILABLE:
    seguimiento_auto = SeguimientoAutomaticoService()
else:
    seguimiento_auto = None

# Inicializar manager apropiado
if TRACKING_AVAILABLE and lead_tracker:
    print("🎯 Usando sistema completo de tracking (ConversationalLeadManager)")
    # Pasar seguimiento_auto si está disponible
    lead_manager = ConversationalLeadManager(lead_tracker, seguimiento_auto if SEGUIMIENTO_AVAILABLE else None)
else:
    print("🔧 Usando sistema básico simplificado (SimpleLeadManager)")
    lead_manager = SimpleLeadManager()


app = Flask(__name__)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    try:
        incoming_msg = request.values.get("Body", "").strip()
        telefono = request.values.get("From", "").replace("whatsapp:", "")
        nombre_perfil = request.values.get("ProfileName", "desconocido")

        print(f"📱 Mensaje de {telefono} ({nombre_perfil}): {incoming_msg}")

        if not incoming_msg:
            return Response("", mimetype="application/xml")

        respuesta_final = None
        
        # Usar el manager apropiado (Conversational o Simple)
        # El método procesar_mensaje_lead ahora devuelve (lead, siguiente_paso, respuesta_directa_opcional)
        lead_data, siguiente_paso, respuesta_directa = lead_manager.procesar_mensaje_lead(telefono, incoming_msg, nombre_perfil)

        if respuesta_directa:
            # Si el manager proporcionó una respuesta directa (ej. opciones de cita, flujo simple), usarla.
            respuesta_final = respuesta_directa
            print(f"🗣️ Usando respuesta directa del manager: {respuesta_final}")
        else:
            # Si no hay respuesta directa, generar con IA usando el contexto del manager.
            # 'lead_data' puede ser un objeto Lead completo o un dict básico.
            # 'siguiente_paso' ayuda a la IA a contextualizar su respuesta.
            print(f"🧠 Generando respuesta con IA. Acción sugerida: {siguiente_paso.get('accion') if siguiente_paso else 'N/A'}")
            respuesta_final = generar_respuesta_con_contexto_inteligente(
                incoming_msg,
                telefono,
                lead_data, # Pasar el objeto lead o el dict del lead básico
                siguiente_paso
            )

        if not respuesta_final:
            # Fallback si la IA no genera respuesta (poco probable con el actual `generar_respuesta_con_contexto_inteligente`)
            print("⚠️ No se generó respuesta final, usando fallback.")
            respuesta_final = "No entendí bien tu mensaje. ¿Podrías repetirlo? 😊"


        # Registrar respuesta si se usa el tracking completo
        if TRACKING_AVAILABLE and lead_tracker and isinstance(lead_manager, ConversationalLeadManager):
            interaccion_bot = Interaccion(
                telefono=telefono,
                tipo=TipoInteraccion.RESPUESTA_BOT,
                descripcion=f"Bot: {respuesta_final}",
                fecha=datetime.now(),
                usuario='bot'
            )
            lead_tracker.registrar_interaccion(interaccion_bot)
        elif isinstance(lead_manager, SimpleLeadManager) and lead_data: # Para SimpleLeadManager
             lead_data['mensajes'].append({ # Guardar respuesta en el historial básico
                'mensaje': respuesta_final,
                'fecha': datetime.now(),
                'tipo': 'saliente_bot'
            })


        # Enviar respuesta
        resp = MessagingResponse()
        msg = resp.message()
        msg.body(html.escape(respuesta_final)) # Escapar HTML para seguridad

        print(f"🤖 Respuesta para {telefono}: {respuesta_final}")
        return Response(str(resp), mimetype="application/xml")

    except Exception as e:
        print(f"❌ Error en whatsapp_reply: {e}")
        import traceback
        traceback.print_exc()

        # Respuesta de error genérica para el usuario
        resp = MessagingResponse()
        msg = resp.message()
        msg.body("¡Uy! 😁 Algo falló de mi lado... ¿Me das un momento y lo intentas de nuevo?")
        return Response(str(resp), mimetype="application/xml")

# ========= MODIFICACIÓN DEL ENDPOINT PRINCIPAL HOME (DE app_with_calendar.py) =========
@app.route("/")
def home():
    """Página de inicio CON INFORMACIÓN DE CITAS"""
    status = "🟢 Funcionando"

    servicios = []
    if TRACKING_AVAILABLE:
        servicios.append("✅ Sistema de tracking completo")
    else:
        servicios.append("⚠️ Sistema básico (sin tracking completo)")

    if SEGUIMIENTO_AVAILABLE:
        servicios.append("✅ Seguimiento automático")
    else:
        servicios.append("⚠️ Sin seguimiento automático")

    if RAG_AVAILABLE:
        servicios.append("✅ Base de conocimiento (RAG)")
    else:
        servicios.append("⚠️ Sin base de conocimiento")

    if CALENDAR_AVAILABLE:
        servicios.append("✅ Sistema de agendado de citas (Cal.com)")
    else:
        servicios.append("⚠️ Sin sistema de citas automático")

    # Estado de memoria mejorada
    servicios.append("✅ Memoria de conversación MEJORADA activada")

    # Obtener métricas si están disponibles
    metricas_html = ""
    if TRACKING_AVAILABLE and lead_tracker:
        try:
            metricas = lead_tracker.obtener_dashboard_metricas()
            # Asegurarse que las claves existen antes de acceder
            por_temperatura = metricas.get('por_temperatura', {})
            por_estado = metricas.get('por_estado', {})
            metricas_html = f"""
            <h2>📊 Métricas Actuales</h2>
            <ul>
                <li><strong>Total leads:</strong> {metricas.get('total_leads', 0)}</li>
                <li><strong>Leads calientes:</strong> {por_temperatura.get('caliente', 0)}</li>
                <li><strong>Leads tibios:</strong> {por_temperatura.get('tibio', 0)}</li>
                <li><strong>Leads fríos:</strong> {por_temperatura.get('frio', 0)}</li>
                <li><strong>Citas agendadas:</strong> {por_estado.get(EstadoLead.CITA_AGENDADA.value, 0)}</li>
            </ul>
            """
        except Exception as e:
            print(f"⚠️ Error obteniendo métricas para home: {e}")
            metricas_html = "<p>⚠️ Error obteniendo métricas</p>"

    # Información de citas
    citas_info_html = ""
    if CALENDAR_AVAILABLE:
        citas_info_html = """
        <div class="feature calendar-feature">
            <strong>📅 SISTEMA DE CITAS INTEGRADO:</strong><br>
            • Agenda automática via WhatsApp<br>
            • Integración con Cal.com (si está configurado)<br>
            • Confirmaciones automáticas<br>
            • Visualización de disponibilidad
        </div>
        """

    return f"""
    <html>
    <head>
        <title>Nissan WhatsApp Bot - Con Sistema de Citas</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
            .status {{ color: green; font-weight: bold; }}
            .service-ok {{ color: green; }}
            .service-warning {{ color: orange; }}
            .metrics {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .memory-status {{ background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 5px solid #4caf50; }}
            .feature {{ background: #e3f2fd; padding: 10px; border-radius: 5px; margin: 10px 0; border-left: 5px solid #2196f3;}}
            .calendar-feature {{ background: #fff3e0; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 5px solid #ff9800; }}
            ul {{ padding-left: 20px; }}
            h1, h2 {{ color: #333; }}
        </style>
    </head>
    <body>
        <h1>🚗 Bot WhatsApp Nissan</h1>
        <p class="status"><strong>Estado:</strong> {status}</p>

        <div class="memory-status">
            <strong>🧠 MEMORIA MEJORADA ACTIVADA:</strong>
            <ul>
                <li>✅ Recuerda conversaciones completas (últimas 20 interacciones)</li>
                <li>✅ Analiza historial de modelos y montos mencionados</li>
                <li>✅ Detecta interés previo en citas y cotizaciones</li>
                <li>✅ Contexto enriquecido con información del lead (si tracking activo)</li>
            </ul>
        </div>

        {citas_info_html}

        <h2>🔧 Servicios Disponibles:</h2>
        <ul>
        {"".join([f"<li class='{'service-ok' if '✅' in servicio else 'service-warning'}'>{html.escape(servicio)}</li>" for servicio in servicios])}
        </ul>

        <div class="metrics">
        {metricas_html if TRACKING_AVAILABLE else "<p>El sistema de tracking detallado no está activo.</p>"}
        </div>

        <h2>🔗 Enlaces Útiles:</h2>
        <ul>
            <li><a href="/test">🧪 Probar servicios</a></li>
            <li><a href="/dashboard">📊 Dashboard de leads</a></li>
            <li><a href="/citas">📅 Dashboard de citas</a> (si calendario activo)</li>
            <li><a href="/test_calendar">🧪 Probar sistema de citas</a> (si calendario activo)</li>
            <li><a href="/disponibilidad">📅 Ver disponibilidad</a> (si calendario activo)</li>
            <li><a href="/seguimientos">🚦 Estado de seguimientos</a> (si seguimientos activos)</li>
            <li><a href="/ejecutar_seguimientos">🚀 Ejecutar seguimientos ahora</a> (si seguimientos activos)</li>
            <li><a href="/test_memoria_mejorada">🧠 Probar memoria MEJORADA</a></li>
        </ul>

        <p><small>⏰ Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
    </body>
    </html>
    """

@app.route("/test_memoria_mejorada")
def test_memoria_mejorada():
    """Endpoint para probar la memoria mejorada del bot"""
    test_telefono = "+5216641234567"  # Teléfono de prueba

    try:
        historial = obtener_historial_conversacion_completo(test_telefono)
        info_relevante = extraer_info_relevante_historial(historial)

        # Simular construcción de contexto
        messages, lead_info = construir_contexto_conversacion_mejorado(test_telefono, "Test de memoria")

        # Construcción del HTML de forma más segura
        lead_info_html_parts = []
        if lead_info:
            if 'nombre' in lead_info: lead_info_html_parts.append(f"<p><strong>Nombre:</strong> {html.escape(str(lead_info['nombre']))}</p>")
            if 'estado' in lead_info: lead_info_html_parts.append(f"<p><strong>Estado:</strong> {html.escape(str(lead_info['estado']))}</p>")
            if 'temperatura' in lead_info: lead_info_html_parts.append(f"<p><strong>Temperatura:</strong> {html.escape(str(lead_info['temperatura']))}</p>")
            if 'score' in lead_info: lead_info_html_parts.append(f"<p><strong>Score:</strong> {lead_info['score']:.1f}</p>") # Score es float
        else:
            lead_info_html_parts.append("<p>Sin información de lead (tracking podría no estar activo o lead no existe).</p>")
        
        lead_info_html = "".join(lead_info_html_parts)

        historial_display_html_parts = []
        for msg in historial[-5:]: # Últimos 5 mensajes
            role_display = '👤 Cliente' if msg['role'] == 'user' else '🤖 Bot'
            content_display = html.escape(msg['content'][:100]) + ('...' if len(msg['content']) > 100 else '')
            historial_display_html_parts.append(f"<p><strong>{role_display}:</strong> {content_display}</p>")
        historial_display_html = "".join(historial_display_html_parts)


        return f"""
        <html>
        <head>
            <title>Test Memoria Mejorada</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .section {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .highlight {{ background: #e8f5e8; padding: 10px; border-radius: 5px; }}
                h1, h2, h3 {{ color: #333; }}
            </style>
        </head>
        <body>
        <h1>🧠 Test de Memoria MEJORADA del Bot</h1>

        <h2>📞 Teléfono de prueba: {html.escape(test_telefono)}</h2>
        <p><strong>Mensajes en historial (DB):</strong> {len(historial)}</p>

        <div class="section">
            <h3>📋 Información Relevante Extraída del Historial:</h3>
            <p><strong>Modelos mencionados:</strong> {html.escape(', '.join(info_relevante['modelos_mencionados'])) if info_relevante['modelos_mencionados'] else 'Ninguno'}</p>
            <p><strong>Montos mencionados (ejemplos):</strong> {html.escape(', '.join(info_relevante['montos_enganche'][:5])) if info_relevante['montos_enganche'] else 'Ninguno'}</p>
            <p><strong>Interés en citas previas:</strong> {'✅ Sí' if info_relevante['citas_previas'] else '❌ No'}</p>
            <p><strong>Interés en cotizaciones previas:</strong> {'✅ Sí' if info_relevante['cotizaciones_previas'] else '❌ No'}</p>
        </div>

        <div class="section">
            <h3>🤖 Información del Lead (si tracking activo):</h3>
            {lead_info_html}
        </div>

        <div class="section">
            <h3>💬 Contexto Construido para la IA:</h3>
            <p><strong>Total mensajes en contexto para IA:</strong> {len(messages)}</p>
            <p><strong>Prompt del sistema (caracteres):</strong> {len(messages[0]['content']) if messages and messages[0] and 'content' in messages[0] else 0}</p>
            <p><em>Nota: El contexto para la IA incluye el prompt del sistema, información del lead (si existe), historial relevante resumido y los últimos mensajes.</em></p>
        </div>

        <div class="highlight">
            <h3>🗨️ Últimas 5 interacciones del historial (DB):</h3>
            {historial_display_html if historial else "<p>No hay historial para este número.</p>"}
        </div>

        <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
        </html>
        """

    except Exception as e:
        print(f"❌ Error en test_memoria_mejorada: {e}")
        return f"❌ Error probando memoria mejorada: {html.escape(str(e))}"

@app.route("/test_memoria")
def test_memoria():
    """Endpoint para probar la memoria básica del bot (obtención de historial)"""
    test_telefono = "+5216641234567"  # Teléfono de prueba

    try:
        historial = obtener_historial_conversacion_completo(test_telefono) # Esta función ya existe y es la base

        historial_html_parts = []
        for msg in historial[-10:]: # Últimos 10 mensajes
            role_display = '👤 Cliente' if msg['role'] == 'user' else '🤖 Bot'
            content_display = html.escape(msg['content'])
            historial_html_parts.append(f"<p><strong>{role_display}:</strong> {content_display}</p>")
        historial_html = "".join(historial_html_parts)


        return f"""
        <html>
        <head>
            <title>Test Memoria (Historial)</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .historial-box {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
        <h1>🧠 Test de Obtención de Historial del Bot</h1>
        <p>Este test verifica la capacidad de recuperar el historial de conversación para un número.</p>

        <h2>📞 Teléfono de prueba: {html.escape(test_telefono)}</h2>
        <p><strong>Total de interacciones (mensajes/respuestas) recuperadas:</strong> {len(historial)}</p>

        <h3>🗨️ Últimas 10 interacciones del historial:</h3>
        <div class="historial-box">
        {historial_html if historial else "<p>No se encontró historial para este número.</p>"}
        </div>

        <p><a href="/test_memoria_mejorada">🧠 Ver test de memoria MEJORADA (contexto IA)</a></p>
        <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
        </html>
        """

    except Exception as e:
        print(f"❌ Error en test_memoria: {e}")
        return f"❌ Error probando la obtención de memoria: {html.escape(str(e))}"

@app.route("/test")
def test():
    """Endpoint para probar todos los servicios incluyendo memoria mejorada y calendario"""
    resultado = {"timestamp": datetime.now().isoformat()}

    # Probar OpenAI
    try:
        test_completion = client.chat.completions.create(
            model="gpt-4o", # o gpt-3.5-turbo
            messages=[{"role": "user", "content": "Di 'funciona'"}],
            max_tokens=5
        )
        resultado["openai"] = "✅ Funcionando"
    except Exception as e:
        resultado["openai"] = f"❌ Error: {str(e)}"

    # Probar tracking
    if TRACKING_AVAILABLE and lead_tracker:
        try:
            metricas = lead_tracker.obtener_dashboard_metricas()
            resultado["tracking"] = f"✅ Funcionando - {metricas.get('total_leads', 0)} leads"
        except Exception as e:
            resultado["tracking"] = f"❌ Error: {str(e)}"
    else:
        resultado["tracking"] = "⚠️ No disponible o lead_tracker no inicializado"

    # Probar seguimiento automático
    if SEGUIMIENTO_AVAILABLE and seguimiento_auto:
        try:
            estado = seguimiento_auto.mostrar_estado()
            resultado["seguimiento_automatico"] = f"✅ Funcionando - {estado.get('seguimientos_pendientes', 'N/A')} pendientes"
        except Exception as e:
            resultado["seguimiento_automatico"] = f"❌ Error: {str(e)}"
    else:
        resultado["seguimiento_automatico"] = "⚠️ No disponible o seguimiento_auto no inicializado"

    # Probar RAG
    if RAG_AVAILABLE:
        try:
            contexto = recuperar_contexto("Información sobre Sentra")
            resultado["rag_conocimiento"] = f"✅ Funcionando - {len(contexto)} caracteres recuperados"
        except Exception as e:
            resultado["rag_conocimiento"] = f"❌ Error: {str(e)}"
    else:
        resultado["rag_conocimiento"] = "⚠️ No disponible (vector_db no cargada)"

    # Probar memoria mejorada (construcción de contexto)
    try:
        test_telefono = "+5216640000000" # Usar un número que no genere muchas queries a DB
        messages_context, _ = construir_contexto_conversacion_mejorado(test_telefono, "Hola, quiero info")
        resultado["memoria_mejorada_contexto"] = f"✅ Funcionando - {len(messages_context)} mensajes en contexto inicial"
    except Exception as e:
        resultado["memoria_mejorada_contexto"] = f"❌ Error: {str(e)}"
        
    # ========= NUEVO: TEST DE CALENDARIO (DE app_with_calendar.py) =========
    if CALENDAR_AVAILABLE:
        try:
            # Usar una instancia si es necesario o llamar funciones directamente
            if 'calendar_service' in locals() and calendar_service: # Si se inicializó globalmente
                 slots_test = calendar_service.obtener_slots_disponibles_humanos(dias_a_futuro=1, max_slots=1)
            elif lead_manager and hasattr(lead_manager, 'calendar_service') and lead_manager.calendar_service: # Si está en el manager
                 slots_test = lead_manager.calendar_service.obtener_slots_disponibles_humanos(dias_a_futuro=1, max_slots=1)
            else: # Crear instancia temporal para test si es seguro hacerlo
                temp_calendar_service = CalendarService()
                slots_test = temp_calendar_service.obtener_slots_disponibles_humanos(dias_a_futuro=1, max_slots=1)

            if slots_test:
                 resultado["calendar_service"] = f"✅ Funcionando - Ejemplo slot: {slots_test[0]}"
            else:
                 resultado["calendar_service"] = "⚠️ Funcionando pero no hay slots en la próxima hora o Cal.com no responde/configurado."
        except Exception as e:
            resultado["calendar_service"] = f"❌ Error: {str(e)}"
    else:
        resultado["calendar_service"] = "⚠️ No disponible (CALENDAR_AVAILABLE es False)"


    return jsonify(resultado)

@app.route("/dashboard")
def dashboard():
    """Dashboard con información de memoria mejorada y citas"""
    if not TRACKING_AVAILABLE or not lead_tracker:
        return "❌ Sistema de tracking no disponible o no inicializado. No se puede mostrar el dashboard."

    try:
        metricas = lead_tracker.obtener_dashboard_metricas()
        leads_prioritarios = lead_tracker.obtener_leads_por_prioridad(15) # Top 15

        # Preparar HTML de forma segura
        metricas_generales_html_parts = [
            f"<p><strong>Total Leads:</strong> {metricas.get('total_leads', 0)}</p>"
        ]
        por_temperatura = metricas.get('por_temperatura', {})
        metricas_generales_html_parts.extend([
            f"<p><strong>Leads Calientes:</strong> {por_temperatura.get(TemperaturaMercado.CALIENTE.value, 0)}</p>",
            f"<p><strong>Leads Tibios:</strong> {por_temperatura.get(TemperaturaMercado.TIBIO.value, 0)}</p>",
            f"<p><strong>Leads Fríos:</strong> {por_temperatura.get(TemperaturaMercado.FRIO.value, 0)}</p>"
        ])
        por_estado = metricas.get('por_estado', {})
        metricas_generales_html_parts.append(
            f"<p><strong>Citas Agendadas (Estado '{EstadoLead.CITA_AGENDADA.value}'):</strong> {por_estado.get(EstadoLead.CITA_AGENDADA.value, 0)}</p>"
        )
        metricas_generales_html = "".join(metricas_generales_html_parts)


        leads_table_rows_html = []
        for lead in leads_prioritarios:
            clase_temp = lead.temperatura.value if isinstance(lead.temperatura, TemperaturaMercado) else str(lead.temperatura)
            modelo_interes = lead.info_prospecto.modelo_interes if lead.info_prospecto and lead.info_prospecto.modelo_interes else "Sin definir"
            dias_sin_contacto = lead.dias_sin_interaccion()

            # Memoria status (simplificado para no hacer query por cada lead aquí)
            memoria_status = "Revisar en test" # Evitar queries pesadas en dashboard

            leads_table_rows_html.append(f"""
            <tr class="{html.escape(clase_temp)}">
                <td>{html.escape(lead.nombre)}</td>
                <td>{html.escape(lead.telefono)}</td>
                <td>{lead.score_calificacion:.1f}</td>
                <td>{html.escape(lead.estado.value if isinstance(lead.estado, EstadoLead) else str(lead.estado))}</td>
                <td>{html.escape(clase_temp)}</td>
                <td>{html.escape(modelo_interes)}</td>
                <td>{dias_sin_contacto}</td>
                <td>{memoria_status}</td>
            </tr>
            """)
        leads_table_html = "".join(leads_table_rows_html)

        citas_info_dashboard = ""
        if CALENDAR_AVAILABLE:
            citas_info_dashboard = """
            <div class="feature calendar-feature" style="margin-top: 20px;">
                <strong>📅 Sistema de Citas Activo:</strong> Las citas agendadas se reflejan en el estado del lead.
                Visita el <a href="/citas">Dashboard de Citas</a> para más detalles.
            </div>
            """

        return f"""
        <html>
        <head>
            <title>Dashboard Nissan - Leads y Citas</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .caliente {{ background-color: #ffebee !important; }} /* Rojo claro */
                .tibio {{ background-color: #fff3e0 !important; }}   /* Naranja claro */
                .frio {{ background-color: #e3f2fd !important; }}    /* Azul claro */
                .cita_agendada {{ background-color: #e8f5e9 !important; font-weight: bold; }} /* Verde claro */
                .memory-info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 5px solid #2196f3; }}
                .calendar-feature {{ background: #fff3e0; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 5px solid #ff9800; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
        <h1>📊 Dashboard de Leads Nissan - {datetime.now().strftime('%d/%m/%Y %H:%M')}</h1>

        <div class="memory-info">
            <strong>🧠 MEMORIA MEJORADA ACTIVADA:</strong> El bot utiliza el historial para conversaciones más contextuales.
        </div>
        {citas_info_dashboard}

        <h2>📈 Métricas Generales</h2>
        {metricas_generales_html}

        <h2>🔥 Top {len(leads_prioritarios)} Leads Prioritarios</h2>
        <table>
        <thead>
            <tr>
                <th>Nombre</th>
                <th>Teléfono</th>
                <th>Score</th>
                <th>Estado</th>
                <th>Temperatura</th>
                <th>Modelo Interés</th>
                <th>Días sin Interacción</th>
                <th>Memoria</th>
            </tr>
        </thead>
        <tbody>
            {leads_table_html if leads_prioritarios else "<tr><td colspan='8'>No hay leads prioritarios para mostrar.</td></tr>"}
        </tbody>
        </table>
        <br>
        <p><a href="/">🏠 Inicio</a> | <a href="/dashboard">🔄 Actualizar Dashboard</a></p>
        </body>
        </html>
        """

    except Exception as e:
        print(f"❌ Error generando dashboard: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error generando el dashboard: {html.escape(str(e))}"

# ========= NUEVO ENDPOINT PARA GESTIÓN DE CITAS (DE app_with_calendar.py) =========
@app.route("/citas")
def dashboard_citas():
    """Dashboard específico para gestión de citas"""
    if not CALENDAR_AVAILABLE:
        return "❌ Sistema de calendario no disponible. Activa CALENDAR_AVAILABLE y configura el servicio."

    # Intentar usar la instancia del manager si existe y tiene calendar_service
    current_calendar_service = None
    if lead_manager and hasattr(lead_manager, 'calendar_service') and lead_manager.calendar_service:
        current_calendar_service = lead_manager.calendar_service
    else: # Fallback a una nueva instancia si no está en el manager (menos ideal)
        try:
            current_calendar_service = CalendarService()
        except Exception as e:
             return f"❌ Error inicializando CalendarService para el dashboard de citas: {html.escape(str(e))}"


    try:
        fecha_hoy_dt = datetime.now()
        fecha_hoy_str = fecha_hoy_dt.strftime("%Y-%m-%d")
        fecha_fin_semana_str = (fecha_hoy_dt + timedelta(days=7)).strftime("%Y-%m-%d")

        # Obtener citas agendadas (simulación o desde Cal.com si está implementado en CalendarService)
        # Esto es una simulación. CalendarService debería tener un método para obtener citas.
        # citas_agendadas = current_calendar_service.obtener_citas_agendadas(fecha_hoy_str, fecha_fin_semana_str)
        
        # Simulación de citas si el método no existe en CalendarService
        # En una implementación real, esto vendría de `current_calendar_service.obtener_citas_agendadas()`
        citas_simuladas = []
        if hasattr(current_calendar_service, 'obtener_eventos_cal_com'):
            eventos_cal = current_calendar_service.obtener_eventos_cal_com(
                start_time=fecha_hoy_dt.isoformat() + "Z",
                end_time=(fecha_hoy_dt + timedelta(days=7)).isoformat() + "Z" # Próximos 7 días
            )
            if eventos_cal.get('exito') and eventos_cal.get('eventos'):
                 for evento in eventos_cal['eventos']:
                    # Adaptar la estructura del evento de Cal.com a lo que espera el HTML
                    attendee_name = "No especificado"
                    attendee_email = "No especificado"
                    if evento.get('attendees'):
                        # Buscar al asistente que no sea el organizador (host)
                        host_email_cal = os.getenv('CAL_HOST_EMAIL', '').lower() # Email del dueño del calendario
                        for att in evento['attendees']:
                            if att.get('email', '').lower() != host_email_cal:
                                attendee_name = att.get('name', attendee_name)
                                attendee_email = att.get('email', attendee_email)
                                break # Tomar el primer no-organizador
                    
                    # Extraer teléfono del email si sigue el patrón "telefono@whatsapp.lead"
                    telefono_cita = "N/A"
                    if "@whatsapp.lead" in attendee_email:
                        telefono_cita = attendee_email.split("@")[0]

                    citas_simuladas.append({
                        "id": evento.get('id'),
                        "nombre": attendee_name,
                        "hora_inicio": datetime.fromisoformat(evento['startTime'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M'),
                        "hora_fin": datetime.fromisoformat(evento['endTime'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M'),
                        "titulo": evento.get('title', 'Cita Programada'),
                        "telefono": telefono_cita,
                        "estado": evento.get('status', 'CONFIRMED').upper() # ej: CONFIRMED, CANCELLED
                    })
            elif not eventos_cal.get('exito'):
                 print(f"⚠️ No se pudieron obtener eventos de Cal.com: {eventos_cal.get('error', 'Error desconocido')}")

        citas_hoy_count = sum(1 for c in citas_simuladas if c['hora_inicio'].startswith(fecha_hoy_str))
        # Próximas 24h (más complejo de simular sin lógica de tiempo real, simplificamos a "próximos eventos")
        citas_proximas_24h_count = len(citas_simuladas) # Total en los próximos 7 días para esta simulación


        citas_html_parts = []
        if citas_simuladas:
            citas_simuladas.sort(key=lambda c: c['hora_inicio']) # Ordenar por fecha/hora
            for cita in citas_simuladas:
                es_hoy = cita['hora_inicio'].startswith(fecha_hoy_str)
                clase_cita = "cita-hoy" if es_hoy else "cita-proxima"
                citas_html_parts.append(f"""
                <div class="cita {clase_cita}">
                    <h4>📅 {html.escape(cita['hora_inicio'])} - {html.escape(cita['titulo'])}</h4>
                    <p><strong>Cliente:</strong> {html.escape(cita['nombre'])} (Tel: {html.escape(cita['telefono'])})</p>
                    <p><strong>Duración:</strong> Hasta {html.escape(cita['hora_fin'])}</p>
                    <p><strong>Estado Cal.com:</strong> <span class="estado-{html.escape(cita['estado'].lower())}">{html.escape(cita['estado'])}</span></p>
                </div>
                """)
        else:
            citas_html_parts.append("<p>No hay citas programadas en los próximos 7 días según Cal.com o la simulación.</p>")
        
        citas_html = "".join(citas_html_parts)


        return f"""
        <html>
        <head>
            <title>Dashboard de Citas - Nissan</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; line-height: 1.6; }}
                .container {{ max-width: 1000px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .cita {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .cita-hoy {{ background: #e8f5e8; border-left: 5px solid #4CAF50; }}
                .cita-proxima {{ background: #fff3e0; border-left: 5px solid #FFC107; }}
                .stats-container {{ display: flex; justify-content: space-around; flex-wrap: wrap; }}
                .stats {{ margin: 10px; padding: 20px; background: #e3f2fd; border-radius: 8px; text-align: center; min-width: 150px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);}}
                .stats h3 {{ margin-top: 0; color: #1976d2; }}
                .stats p {{ font-size: 28px; font-weight: bold; margin-bottom: 0; color: #0d47a1;}}
                .estado-confirmed {{ color: green; font-weight: bold; }}
                .estado-cancelled {{ color: red; }}
                .estado-pending {{ color: orange; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
        <div class="container">
            <h1>📅 Dashboard de Citas Nissan (Cal.com)</h1>
            <p><strong>Fecha Actual:</strong> {fecha_hoy_dt.strftime('%d/%m/%Y %H:%M')}</p>
            <p><em>Mostrando citas obtenidas de Cal.com para los próximos 7 días.</em></p>

            <div class="card">
                <h2>📊 Estadísticas Rápidas</h2>
                <div class="stats-container">
                    <div class="stats">
                        <h3>Citas Hoy ({fecha_hoy_str})</h3>
                        <p>{citas_hoy_count}</p>
                    </div>
                    <div class="stats">
                        <h3>Total Próx. 7 Días</h3>
                        <p>{citas_proximas_24h_count}</p>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>🗓️ Próximas Citas Agendadas</h2>
                {citas_html}
            </div>

            <div class="card">
                <h2>📱 Acciones Rápidas</h2>
                <p><a href="/test_calendar">🧪 Probar integración con Cal.com</a></p>
                <p><a href="/disponibilidad">📅 Ver disponibilidad para nuevas citas</a></p>
                <p><a href="/">🏠 Volver al dashboard principal</a></p>
            </div>
        </div>
        </body>
        </html>
        """

    except Exception as e:
        print(f"❌ Error en dashboard_citas: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error generando el dashboard de citas: {html.escape(str(e))}"

@app.route("/test_calendar")
def test_calendar():
    """Endpoint para probar el sistema de calendario (integración Cal.com)"""
    if not CALENDAR_AVAILABLE:
        return "❌ Sistema de calendario no disponible. CALENDAR_AVAILABLE es False."

    # Usar la instancia del servicio de calendario del lead_manager si es posible
    current_calendar_service = None
    if lead_manager and hasattr(lead_manager, 'calendar_service') and lead_manager.calendar_service:
        current_calendar_service = lead_manager.calendar_service
    else:
        try:
            current_calendar_service = CalendarService() # Fallback a nueva instancia
        except Exception as e:
            return f"❌ Error inicializando CalendarService para el test: {html.escape(str(e))}"


    results_html = ""

    try:
        # 1. Test de Variables de Entorno para Cal.com
        env_vars_status = {
            'CAL_API_KEY': '✅ Configurada' if os.getenv('CAL_API_KEY') else '❌ FALTANTE (Necesaria para crear citas)',
            'CAL_BASE_URL': os.getenv('CAL_BASE_URL', 'Usando default: https://api.cal.com/v1'),
            'CAL_EVENT_TYPE_ID': '✅ Configurada' if os.getenv('CAL_EVENT_TYPE_ID') else '❌ FALTANTE (Necesario para filtrar disponibilidad y crear citas)',
            'CAL_USER_ID': '✅ Configurada' if os.getenv('CAL_USER_ID') else '⚠️ Opcional (puede ser necesario para algunos setups)',
            'CAL_HOST_EMAIL': '✅ Configurada' if os.getenv('CAL_HOST_EMAIL') else '⚠️ Opcional (usado para identificar al organizador en eventos)'
        }
        results_html += "<div class='test-section'><h3>1. Variables de Entorno Cal.com</h3><ul>"
        for var, status in env_vars_status.items():
            results_html += f"<li><strong>{html.escape(var)}:</strong> {html.escape(status)}</li>"
        results_html += "</ul></div>"


        # 2. Test de Obtener Disponibilidad de Cal.com (Función base de CalendarService)
        fecha_inicio_dt = datetime.now()
        fecha_fin_dt = fecha_inicio_dt + timedelta(days=2) # Próximos 2 días para un test rápido
        
        # Usar el método de la instancia de CalendarService
        disponibilidad_raw = current_calendar_service.obtener_disponibilidad_cal_com(
            start_time = fecha_inicio_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z", # formato ISO UTC
            end_time = fecha_fin_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        )
        
        results_html += f"<div class='test-section {'success' if disponibilidad_raw.get('exito') else 'error'}'>"
        results_html += f"<h3>2. Test de Disponibilidad Directa de Cal.com (Raw)</h3>"
        results_html += f"<p><strong>Estado:</strong> {'✅ Exitoso' if disponibilidad_raw.get('exito') else '❌ Fallido'}</p>"
        if disponibilidad_raw.get('slots'):
            results_html += f"<p><strong>Slots crudos encontrados:</strong> {len(disponibilidad_raw['slots'])}</p>"
            results_html += f"<p><strong>Primeros 3 slots (ejemplo):</strong></p><pre>{html.escape(str(disponibilidad_raw['slots'][:3]))}</pre>"
        else:
            results_html += f"<p><strong>Respuesta/Error:</strong></p><pre>{html.escape(str(disponibilidad_raw))}</pre>"
        results_html += "</div>"


        # 3. Test de Obtener Slots Legibles (Función procesada en CalendarService)
        slots_humanos = current_calendar_service.obtener_slots_disponibles_humanos(dias_a_futuro=2, max_slots=5)
        results_html += f"<div class='test-section {'success' if slots_humanos else ('warning' if not disponibilidad_raw.get('exito') else 'error')}'>"
        results_html += f"<h3>3. Test de Slots Legibles para el Usuario</h3>"
        if slots_humanos:
            results_html += f"<p><strong>Slots legibles generados:</strong> {len(slots_humanos)}</p><ul>"
            for slot in slots_humanos:
                results_html += f"<li>{html.escape(slot)}</li>"
            results_html += "</ul>"
        elif not disponibilidad_raw.get('exito'):
             results_html += "<p>No se pueden generar slots legibles porque la consulta a Cal.com falló.</p>"
        else:
            results_html += "<p>⚠️ No se encontraron slots disponibles en los próximos 2 días o hubo un problema procesándolos.</p>"
        results_html += "</div>"


        # 4. Test de `procesar_solicitud_cita` (simula lo que haría el bot)
        lead_test_data = {
            "nombre": "Cliente de Prueba Cal",
            "telefono": "+5216649998877",
            "email": "test.cal@example.com", # Necesario para Cal.com
            "metadata": {"modelo_interes": "Kicks Test"}
        }
        resultado_procesar_cita = procesar_solicitud_cita("Quiero agendar una cita para mañana", lead_test_data)
        results_html += f"<div class='test-section {'success' if resultado_procesar_cita.get('tipo') == 'opciones_cita' else 'error'}'>"
        results_html += f"<h3>4. Test de `procesar_solicitud_cita`</h3>"
        results_html += f"<p><strong>Tipo de resultado:</strong> {html.escape(str(resultado_procesar_cita.get('tipo')))}</p>"
        results_html += f"<p><strong>Mensaje generado para el usuario:</strong></p>"
        results_html += f"<div style='background: white; padding: 10px; border-radius: 3px; border: 1px solid #ccc;'>"
        results_html += f"{html.escape(resultado_procesar_cita.get('mensaje', 'Sin mensaje')).replace(chr(10), '<br>')}"
        results_html += f"</div>"
        if resultado_procesar_cita.get('slots_disponibles'):
            results_html += f"<p><strong>Slots en el resultado:</strong> {len(resultado_procesar_cita['slots_disponibles'])}</p>"
            # No mostrar todos los slots aquí, ya se vieron antes.
        results_html += "</div>"
        
        # 5. Test de `confirmar_cita_seleccionada` (simulación, no crea cita real aquí)
        # Para este test, necesitamos unos slots de ejemplo que `procesar_solicitud_cita` podría haber devuelto.
        # Usaremos los `slots_disponibles` de la prueba anterior si existen.
        if resultado_procesar_cita.get('tipo') == 'opciones_cita' and resultado_procesar_cita.get('slots_disponibles'):
            slots_para_confirmacion = resultado_procesar_cita['slots_disponibles']
            if slots_para_confirmacion:
                # Simular que el usuario elige la primera opción (índice '1')
                seleccion_usuario = "1"
                resultado_confirmacion = confirmar_cita_seleccionada(seleccion_usuario, lead_test_data, slots_para_confirmacion)
                
                results_html += f"<div class='test-section {'success' if resultado_confirmacion.get('tipo') == 'cita_confirmada' else 'error'}'>"
                results_html += f"<h3>5. Test de `confirmar_cita_seleccionada` (¡Crea una cita real si Cal.com está bien configurado!)</h3>"
                results_html += f"<p><em>Se intentó confirmar la opción '{seleccion_usuario}' de los slots anteriores.</em></p>"
                results_html += f"<p><strong>Tipo de resultado:</strong> {html.escape(str(resultado_confirmacion.get('tipo')))}</p>"
                results_html += f"<p><strong>Mensaje generado:</strong></p>"
                results_html += f"<div style='background: white; padding: 10px; border-radius: 3px; border: 1px solid #ccc;'>"
                results_html += f"{html.escape(resultado_confirmacion.get('mensaje', 'Sin mensaje')).replace(chr(10), '<br>')}"
                results_html += f"</div>"
                if resultado_confirmacion.get('booking_id'):
                     results_html += f"<p><strong>ID de Reserva (Cal.com):</strong> {html.escape(str(resultado_confirmacion['booking_id']))}</p>"
                     results_html += f"<p class='warning-text'><strong>⚠️ ATENCIÓN:</strong> Se ha creado una cita real en Cal.com con ID {html.escape(str(resultado_confirmacion['booking_id']))}. Por favor, cancélala manualmente si es solo una prueba.</p>"
                elif resultado_confirmacion.get('error'):
                     results_html += f"<p><strong>Error al crear cita:</strong> {html.escape(str(resultado_confirmacion.get('error')))}</p>"

                results_html += "</div>"
            else:
                results_html += "<div class='test-section warning'><p>No hay slots disponibles de la prueba anterior para simular la confirmación.</p></div>"
        else:
             results_html += "<div class='test-section warning'><p>El paso anterior de `procesar_solicitud_cita` no produjo opciones de cita, no se puede probar la confirmación.</p></div>"


        final_html = f"""
        <html>
        <head>
            <title>Test Sistema de Calendario (Cal.com)</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .test-section {{ background: #f0f0f0; padding: 15px; margin: 15px 0; border-radius: 8px; border-left: 5px solid #ccc; }}
                .test-section.success {{ border-left-color: #4CAF50; }}
                .test-section.error {{ border-left-color: #F44336; }}
                .test-section.warning {{ border-left-color: #FFC107; }}
                .warning-text {{ color: #F44336; font-weight: bold; }}
                pre {{ background: white; padding: 10px; border: 1px solid #eee; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; }}
                h1, h3 {{ color: #333; }}
            </style>
        </head>
        <body>
        <h1>🧪 Test del Sistema de Calendario (Integración Cal.com)</h1>
        <p>Este test verifica la comunicación con Cal.com y las funciones principales del `CalendarService`.</p>
        {results_html}
        <p><a href="/citas">📅 Ver dashboard de citas</a> | <a href="/">🏠 Volver al inicio</a></p>
        </body>
        </html>
        """
        return final_html

    except Exception as e:
        print(f"❌ Error crítico en test_calendar: {e}")
        import traceback
        traceback.print_exc()
        return f"""
        <html><head><title>Error Test Calendario</title></head><body>
        <h1>❌ Error Crítico en Test de Calendario</h1>
        <p><strong>Error:</strong> {html.escape(str(e))}</p>
        <pre>{html.escape(traceback.format_exc())}</pre>
        <p><a href="/">🏠 Volver al inicio</a></p>
        </body></html>
        """

@app.route("/disponibilidad")
def mostrar_disponibilidad():
    """Muestra disponibilidad semanal obtenida de Cal.com"""
    if not CALENDAR_AVAILABLE:
        return "❌ Sistema de calendario no disponible."

    # Usar la instancia del servicio de calendario del lead_manager si es posible
    current_calendar_service = None
    if lead_manager and hasattr(lead_manager, 'calendar_service') and lead_manager.calendar_service:
        current_calendar_service = lead_manager.calendar_service
    else:
        try:
            current_calendar_service = CalendarService() # Fallback a nueva instancia
        except Exception as e:
            return f"❌ Error inicializando CalendarService para mostrar disponibilidad: {html.escape(str(e))}"

    try:
        # Obtener slots para los próximos 7 días, hasta 50 slots.
        slots_disponibles = current_calendar_service.obtener_slots_disponibles_humanos(dias_a_futuro=7, max_slots=50)

        slots_html_parts = []
        if slots_disponibles:
            for slot in slots_disponibles:
                slots_html_parts.append(f'<div class="slot">🕒 {html.escape(slot)}</div>')
        else:
            slots_html_parts.append("<p>No se encontraron horarios disponibles en los próximos 7 días o hubo un problema al consultar Cal.com.</p>")
        
        slots_html = "".join(slots_html_parts)

        return f"""
        <html>
        <head>
            <title>Disponibilidad Semanal - Nissan (Cal.com)</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .container {{ max-width: 900px; margin: auto; }}
                .slot-container {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }}
                .slot {{ background: #e8f5e8; padding: 12px 18px; border-radius: 6px; border: 1px solid #c8e6c9; font-size: 0.95em; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
                h1 {{ color: #333; }}
                p {{ color: #555; }}
            </style>
        </head>
        <body>
        <div class="container">
            <h1>📅 Disponibilidad para Citas (Próximos 7 Días)</h1>
            <p>Estos son los horarios actualmente disponibles según la configuración de Cal.com.</p>
            <h3>Horarios Disponibles:</h3>
            <div class="slot-container">
                {slots_html}
            </div>
            <br>
            <p><em>Nota: La duración de cada cita está preconfigurada en Cal.com (usualmente 30 o 60 minutos).</em></p>
            <p><a href="/citas">📅 Volver al Dashboard de Citas</a> | <a href="/">🏠 Volver al Inicio</a></p>
        </div>
        </body>
        </html>
        """

    except Exception as e:
        print(f"❌ Error en mostrar_disponibilidad: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error mostrando disponibilidad: {html.escape(str(e))}"


@app.route("/advanced_dashboard")
def advanced_dashboard():
    """Dashboard avanzado con métricas de negocio y ROI"""
    if not ADVANCED_FEATURES:
        return "❌ Funcionalidades avanzadas no disponibles"

    try:
        # Suponiendo que AdvancedDashboard y generar_reporte_completo están definidos y funcionan
        # dashboard_instance = AdvancedDashboard() # Si es necesario instanciar
        reporte = generar_reporte_completo(periodo_dias=30) # Generar reporte para 30 días

        # Asegurarse de que las claves existen en el reporte
        conversion_metrics = reporte.get('conversion_metrics', {})
        tasas_conversion = conversion_metrics.get('tasas_conversion', {})
        roi_analysis = reporte.get('roi_analysis', {})

        html_response = f"""
        <html>
        <head>
            <title>Dashboard Avanzado Nissan</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; line-height: 1.6; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .card {{ background: white; padding: 25px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }}
                .metric {{ padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05);}}
                .metric h3 {{ margin-top: 0; font-size: 1.1em; color: #555; }}
                .metric p {{ margin-bottom: 0; font-size: 2em; font-weight: bold; color: #1976d2; }}
                .metric.success p {{ color: #2e7d32; }}
                .metric.warning p {{ color: #f57c00; }}
                .metric.neutral p {{ color: #1976d2; }}
                .metric.success {{ background: #e8f5e9; border-left: 5px solid #4CAF50; }}
                .metric.warning {{ background: #fff3e0; border-left: 5px solid #FFC107; }}
                .metric.neutral {{ background: #e3f2fd; border-left: 5px solid #2196F3; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
        <div class="container">
            <h1>📈 Dashboard Avanzado de Rendimiento Nissan</h1>
            <p><strong>Reporte para el período de:</strong> Últimos {reporte.get('periodo_dias', 'N/A')} días (Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')})</p>

            <div class="card">
                <h2>📊 Métricas Clave de Conversión</h2>
                <div class="metrics-grid">
                    <div class="metric neutral">
                        <h3>Total Leads Generados</h3>
                        <p>{conversion_metrics.get('total_leads', 0)}</p>
                    </div>
                    <div class="metric neutral">
                        <h3>Leads Calificados</h3>
                        <p>{conversion_metrics.get('leads_calificados', 0)}</p>
                    </div>
                    <div class="metric neutral">
                        <h3>Citas Agendadas</h3>
                        <p>{conversion_metrics.get('citas_agendadas', 0)}</p>
                    </div>
                    <div class="metric success">
                        <h3>Ventas Realizadas</h3>
                        <p>{conversion_metrics.get('ventas_realizadas', 0)}</p>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>📉 Tasas de Conversión</h2>
                <div class="metrics-grid">
                    <div class="metric neutral">
                        <h3>Lead a Calificado</h3>
                        <p>{tasas_conversion.get('lead_a_calificado', 0):.1f}%</p>
                    </div>
                    <div class="metric neutral">
                        <h3>Calificado a Cita</h3>
                        <p>{tasas_conversion.get('calificado_a_cita', 0):.1f}%</p>
                    </div>
                    <div class="metric success">
                        <h3>Cita a Venta (Cierre)</h3>
                        <p>{tasas_conversion.get('cita_a_venta', 0):.1f}%</p>
                    </div>
                    <div class="metric success">
                        <h3>Lead a Venta (Global)</h3>
                        <p>{tasas_conversion.get('lead_a_venta_global', 0):.1f}%</p>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>💰 Análisis de Retorno de Inversión (ROI)</h2>
                <div class="metrics-grid">
                    <div class="metric neutral">
                        <h3>Costo por Lead (CPL)</h3>
                        <p>${roi_analysis.get('costo_por_lead', 0):,.2f}</p>
                    </div>
                    <div class="metric neutral">
                        <h3>Valor Promedio de Venta</h3>
                        <p>${roi_analysis.get('valor_promedio_venta', 0):,.2f}</p>
                    </div>
                    <div class="metric success">
                        <h3>ROI Actual</h3>
                        <p>{roi_analysis.get('roi_actual_porcentaje', 0):.1f}%</p>
                    </div>
                     <div class="metric warning">
                        <h3>ROI Potencial (con mejoras)</h3>
                        <p>{roi_analysis.get('roi_potencial_porcentaje', 0):.1f}%</p>
                    </div>
                </div>
                <p style="margin-top: 15px;"><small><em>El ROI se calcula basado en la inversión en generación de leads y los ingresos por ventas.</em></small></p>
            </div>

            <p><a href="/">🏠 Volver al inicio</a></p>
        </div>
        </body>
        </html>
        """
        return html_response

    except Exception as e:
        print(f"❌ Error generando dashboard avanzado: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error generando el dashboard avanzado: {html.escape(str(e))}"

@app.route("/test_sentiment")
def test_sentiment():
    """Endpoint para probar el análisis de sentimientos"""
    if not ADVANCED_FEATURES: # Asegúrate que ADVANCED_FEATURES se define basado en la importación exitosa
        return "❌ Análisis de sentimientos no disponible (ADVANCED_FEATURES es False)."

    try:
        # Asegurarse que SentimentAnalyzer está disponible e importado
        analyzer = SentimentAnalyzer()

        mensajes_test = [
            "Hola, me interesa mucho el Sentra pero el precio me parece un poco elevado. ¿Hay alguna promoción?",
            "¡Excelente servicio! Me encanta el diseño del nuevo Kicks, es justo lo que buscaba.",
            "No estoy seguro si mis comprobantes de ingresos son suficientes para el financiamiento.",
            "Necesito el auto lo más pronto posible, es urgente para mi trabajo. ¿Qué tan rápido es el proceso?",
            "Gracias por toda la información detallada, lo voy a pensar y te aviso cualquier cosa.",
            "Estoy muy molesto, llevo esperando una respuesta media hora.",
            "Quizás el Versa sea una buena opción para mí, ¿tienen el color azul?"
        ]

        resultados_html_parts = []
        for i, mensaje in enumerate(mensajes_test):
            analisis = analyzer.analizar_sentimiento_basico(mensaje) # Usar el método de la instancia
            estrategia = analyzer.sugerir_estrategia_respuesta(analisis) # Usar el método de la instancia

            sentimientos_str = ', '.join(analisis.get('sentimientos', [])) if analisis.get('sentimientos') else 'General/Neutro'
            
            resultados_html_parts.append(f"""
            <div class="test-item">
                <h3>Test {i+1}</h3>
                <p><strong>Mensaje:</strong> "{html.escape(mensaje)}"</p>
                <p><strong>Sentimientos detectados:</strong> <span class="sentiment-tag">{html.escape(sentimientos_str)}</span></p>
                <p><strong>Tipo de mensaje:</strong> {html.escape(analisis.get('tipo_mensaje', 'N/A'))}</p>
                <p><strong>Score de sentimiento (Compuesto):</strong> {analisis.get('score_sentimiento_compuesto', 0.0):.2f}</p>
                <hr>
                <p><strong>Sugerencia de Estrategia:</strong></p>
                <ul>
                    <li><strong>Tono sugerido:</strong> {html.escape(estrategia.get('tono', 'N/A'))}</li>
                    <li><strong>Enfoque principal:</strong> {html.escape(estrategia.get('enfoque', 'N/A'))}</li>
                    <li><strong>Acción recomendada:</strong> {html.escape(estrategia.get('accion_sugerida', 'N/A'))}</li>
                </ul>
            </div>
            """)
        
        resultados_html = "".join(resultados_html_parts)

        return f"""
        <html>
        <head>
            <title>Test Análisis de Sentimientos</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .container {{ max-width: 800px; margin: auto; }}
                .test-item {{ background: #f9f9f9; padding: 20px; margin-bottom: 20px; border-radius: 8px; border-left: 5px solid #2196F3; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}}
                .sentiment-tag {{ background: #e3f2fd; color: #1976d2; padding: 3px 8px; border-radius: 4px; font-size: 0.9em; }}
                h1, h3 {{ color: #333; }}
                hr {{ border: 0; border-top: 1px solid #eee; margin: 15px 0; }}
                ul {{ padding-left: 20px; }}
            </style>
        </head>
        <body>
        <div class="container">
            <h1>🧠 Test de Análisis de Sentimientos y Estrategia de Respuesta</h1>
            <p>Este test evalúa cómo el `SentimentAnalyzer` procesa diferentes mensajes y sugiere estrategias.</p>
            {resultados_html}
            <p><a href="/">🏠 Volver al inicio</a></p>
        </div>
        </body>
        </html>
        """

    except NameError as ne: # Específicamente si SentimentAnalyzer no está definido
        print(f"⚠️ Error en test_sentiment: {ne}. ¿Está SentimentAnalyzer importado y ADVANCED_FEATURES es True?")
        return f"❌ Error: El servicio de análisis de sentimientos no parece estar cargado. Verifica la importación y la variable ADVANCED_FEATURES. Detalle: {html.escape(str(ne))}"
    except Exception as e:
        print(f"❌ Error probando análisis de sentimientos: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error probando análisis de sentimientos: {html.escape(str(e))}"


if __name__ == "__main__":
    print("🚀 Iniciando aplicación Flask...")
    print(f"📊 Tracking disponible: {TRACKING_AVAILABLE}")
    print(f"🤖 Seguimiento automático disponible: {SEGUIMIENTO_AVAILABLE}")
    print(f"🧠 RAG (Base de Conocimiento) disponible: {RAG_AVAILABLE}")
    print(f"📅 Servicio de Calendario disponible: {CALENDAR_AVAILABLE}")
    print(f"✨ Funcionalidades Avanzadas disponibles: {ADVANCED_FEATURES}")

    print("\n🧠 MEMORIA DE CONVERSACIÓN MEJORADA: ✅ ACTIVADA")
    print("   • Análisis inteligente del historial.")
    print("   • Contexto enriquecido con información del lead.")
    print("   • Detección de modelos y montos mencionados.")

    if CALENDAR_AVAILABLE:
        print("\n📅 SISTEMA DE AGENDADO DE CITAS (Cal.com): ✅ ACTIVADO")
        print("   • Permite agendar citas vía WhatsApp.")
        print(f"   • CAL_EVENT_TYPE_ID: {os.getenv('CAL_EVENT_TYPE_ID', 'NO CONFIGURADO')}")


    # Inicializar seguimiento automático si está disponible
    if SEGUIMIENTO_AVAILABLE and seguimiento_auto:
        try:
            seguimiento_auto.iniciar_seguimiento() # Asumiendo que este método existe y es seguro llamarlo aquí
            print("🚦 Sistema de seguimiento automático iniciado y corriendo en segundo plano.")
        except Exception as e:
            print(f"⚠️ Error iniciando el sistema de seguimiento automático: {e}")
    elif SEGUIMIENTO_AVAILABLE and not seguimiento_auto:
             print(f"⚠️ SEGUIMIENTO_AVAILABLE es True, pero la instancia 'seguimiento_auto' no está definida.")


    # Mostrar métricas iniciales si el tracking está disponible
    if TRACKING_AVAILABLE and lead_tracker:
        try:
            metricas = lead_tracker.obtener_dashboard_metricas()
            print(f"\n📈 Leads actuales en sistema: {metricas.get('total_leads', 0)}")
            por_temperatura = metricas.get('por_temperatura', {})
            print(f"   🔥 Calientes: {por_temperatura.get(TemperaturaMercado.CALIENTE.value, 0)}")
            print(f"   ☀️ Tibios: {por_temperatura.get(TemperaturaMercado.TIBIO.value, 0)}")
            print(f"   ❄️ Fríos: {por_temperatura.get(TemperaturaMercado.FRIO.value, 0)}")
            por_estado = metricas.get('por_estado', {})
            print(f"   🗓️ Citas Agendadas: {por_estado.get(EstadoLead.CITA_AGENDADA.value, 0)}")

        except Exception as e:
            print(f"⚠️ Error obteniendo métricas iniciales del lead_tracker: {e}")
    elif TRACKING_AVAILABLE and not lead_tracker:
        print(f"⚠️ TRACKING_AVAILABLE es True, pero la instancia 'lead_tracker' no está definida.")


    # Definir el puerto y host
    host = "0.0.0.0"
    port = int(os.getenv("PORT", 5001)) # Usar variable de entorno PORT si existe, sino default 5001
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t") # Activar debug si FLASK_DEBUG=True

    print(f"\n🌐 Servidor Flask listo para iniciar en http://{host}:{port}")
    print(f"   🐛 Modo Debug: {'Activado' if debug_mode else 'Desactivado'}")
    print("\n🔗 Enlaces rápidos:")
    print(f"   🏠 Home: http://localhost:{port}/")
    print(f"   📊 Dashboard Leads: http://localhost:{port}/dashboard")
    if CALENDAR_AVAILABLE:
        print(f"   📅 Dashboard Citas: http://localhost:{port}/citas")
        print(f"   🧪 Test Calendario: http://localhost:{port}/test_calendar")
        print(f"   🗓️ Ver Disponibilidad: http://localhost:{port}/disponibilidad")
    if ADVANCED_FEATURES:
        print(f"   📈 Dashboard Avanzado: http://localhost:{port}/advanced_dashboard")
        print(f"   🧐 Test Sentimientos: http://localhost:{port}/test_sentiment")
    print(f"   🧪 Test General Servicios: http://localhost:{port}/test")
    print(f"   🧠 Test Memoria Mejorada: http://localhost:{port}/test_memoria_mejorada")

    app.run(host=host, port=port, debug=debug_mode)