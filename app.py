# app.py - Versión final completa con memoria mejorada
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
        if TRACKING_AVAILABLE and lead_tracker:
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
        
        for entrada in historial[-6:]:
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
            """
        
        # Generar respuesta
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
            temperature=0.8  # Más creatividad para evitar repeticiones
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
        elif hasattr(lead_info, 'nombre'):
            nombre = lead_info.nombre
        
        messages = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Cliente: {nombre}\n\nInformación útil:\n{contexto}\n\nPregunta del cliente:\n{mensaje}"}
        ]
        
        completion = client.chat.completions.create(
            model="gpt-4o",
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

# INICIO: Clase ConversationalLeadManager (reemplazo completo)
class ConversationalLeadManager(LeadManager):
    """
    Manager conversacional avanzado para leads, integrando análisis de mensajes,
    extracción de información, lógica de flujo conversacional y soporte para memoria.
    """
    def __init__(self, lead_tracker, seguimiento_auto=None):
        self.lead_tracker = lead_tracker
        self.seguimiento_auto = seguimiento_auto

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

        return lead, siguiente_paso

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
                        if 100 <= monto <= 999:
                            monto *= 1000
                        if 5000 <= monto <= 500000:
                            info_extraida['monto_enganche'] = monto
                            print(f"💰 Enganche detectado: ${monto:,.0f}")
                            break
                    except Exception:
                        pass

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
        Determina el siguiente paso en el flujo de ventas según el estado y la información del lead.
        """
        mensaje_lower = mensaje.lower()
        info = lead.info_prospecto
        print(f"📊 Estado Lead: {lead.estado.value}")
        print(f"📊 Info Prospecto: uso={info.uso_vehiculo}, ingresos={info.comprobacion_ingresos}, enganche={info.monto_enganche}, credito={info.historial_credito}")

        # Flujo avanzado según estado
        if lead.estado.value not in ['contacto_inicial', 'calificando']:
            if any(palabra in mensaje_lower for palabra in ['precio', 'cotización', 'modelo', 'plan', 'financiamiento', 'duda', 'consulta', 'versión']):
                return {
                    'accion': 'responder_duda_modelo',
                    'mensaje': f"¡Hola {lead.nombre}! 😁 Claro, dime qué modelo o plan te interesa y te paso toda la info."
                }
            else:
                return {
                    'accion': 'conversacion_ligera',
                    'mensaje': f"¡Hola {lead.nombre}! 😄 ¿Cómo vas con la decisión? ¿Tienes alguna duda sobre algún auto o plan?"
                }

        # Primer contacto
        if lead.estado == EstadoLead.CONTACTO_INICIAL:
            if any(word in mensaje_lower for word in ['hola', 'info', 'informacion', 'precio', 'cotizar']):
                return {
                    'accion': 'solicitar_uso_vehiculo',
                    'nuevo_estado': EstadoLead.CALIFICANDO,
                    'mensaje': f"¡Qué onda {lead.nombre}! 😁 ¿El auto lo necesitas para chambear o para uso personal?"
                }

        # Proceso de calificación
        elif lead.estado == EstadoLead.CALIFICANDO:
            if not info.uso_vehiculo:
                if any(word in mensaje_lower for word in ['particular', 'personal', 'familia']):
                    return {
                        'accion': 'solicitar_comprobacion_ingresos',
                        'mensaje': f"Va que va {lead.nombre}... ¿trabajas en empresa o tienes tu negocio?"
                    }
                elif any(word in mensaje_lower for word in ['trabajo', 'uber', 'didi', 'taxi', 'negocio']):
                    return {
                        'accion': 'solicitar_comprobacion_ingresos',
                        'mensaje': f"Órale, para la chamba entonces... ¿recibes nómina o cómo le haces con los ingresos?"
                    }
                else:
                    return {
                        'accion': 'solicitar_uso_vehiculo',
                        'mensaje': f"¿Para qué ocuparías el carro principalmente, {lead.nombre}? 😁"
                    }
            elif not info.comprobacion_ingresos:
                if any(word in mensaje_lower for word in ['nomina', 'nómina', 'formal', 'empresa', 'recibo']):
                    return {
                        'accion': 'solicitar_enganche',
                        'mensaje': f"Perfecto {lead.nombre}, qué bueno que tienes comprobantes... ¿cuánto tienes pensado de entrada? 😁"
                    }
                elif any(word in mensaje_lower for word in ['informal', 'negocio', 'propio', 'independiente']):
                    return {
                        'accion': 'solicitar_enganche',
                        'mensaje': f"Ah ya veo, negocio propio... ¿con cuánto le podrías entrar de enganche?"
                    }
                else:
                    return {
                        'accion': 'solicitar_comprobacion_ingresos',
                        'mensaje': f"¿Cómo está tu situación con los comprobantes de ingresos, {lead.nombre}?"
                    }
            elif not info.monto_enganche:
                numeros = re.findall(r'\d+', mensaje)
                if numeros:
                    return {
                        'accion': 'solicitar_buro',
                        'mensaje': f"¡Órale, está bien! 😁 ¿Y cómo andas de buró de crédito?"
                    }
                else:
                    return {
                        'accion': 'solicitar_enganche',
                        'mensaje': f"¿Más o menos cuánto tienes guardado para el enganche?"
                    }
            elif not info.historial_credito:
                if any(word in mensaje_lower for word in ['bueno', 'bien', 'excelente', 'limpio']):
                    return {
                        'accion': 'finalizar_calificacion',
                        'nuevo_estado': EstadoLead.CALIFICADO,
                        'mensaje': f"¡Perfecto {lead.nombre}! 😁 Con esa info ya te puedo conseguir las mejores opciones... ¿te marco al 6644918078 para platicarte?"
                    }
                elif any(word in mensaje_lower for word in ['malo', 'mal', 'problemas', 'buro', 'buró']):
                    return {
                        'accion': 'finalizar_calificacion',
                        'nuevo_estado': EstadoLead.CALIFICADO,
                        'mensaje': f"No te preocupes {lead.nombre}, para eso está el plan Sí Fácil 😁 ¿Te llamo para explicarte cómo funciona?"
                    }
                elif any(word in mensaje_lower for word in ['regular', 'mas o menos', 'normal']):
                    return {
                        'accion': 'finalizar_calificacion',
                        'nuevo_estado': EstadoLead.CALIFICADO,
                        'mensaje': f"Va, tenemos opciones para tu situación {lead.nombre} 😁 ¿Cuándo puedo llamarte para ver cuál te conviene más?"
                    }
                else:
                    return {
                        'accion': 'solicitar_buro',
                        'mensaje': f"¿Todo bien con tu historial o hay algún detalle que deba saber?"
                    }
            else:
                return {
                    'accion': 'finalizar_calificacion',
                    'nuevo_estado': EstadoLead.CALIFICADO,
                    'mensaje': f"¡Ya quedó {lead.nombre}! 😁 Tengo varias opciones para ti... ¿te marco ahorita o prefieres que te mande la info por aquí?"
                }

        elif lead.estado == EstadoLead.CALIFICADO:
            if any(word in mensaje_lower for word in ['si', 'sí', 'claro', 'dale', 'órale', 'va', 'llamame', 'llama', 'márcame', 'marca']):
                return {
                    'accion': 'agendar_llamada',
                    'nuevo_estado': EstadoLead.INTERESADO_ALTO,
                    'mensaje': f"¡Órale! Te marco en unos minutos {lead.nombre} 😁 Mientras, ¿ya tienes en mente algún modelo en especial?"
                }
            elif any(word in mensaje_lower for word in ['precio', 'costo', 'cuanto', 'cuánto', 'cotizar', 'info', 'información']):
                return {
                    'accion': 'solicitar_cotizacion',
                    'nuevo_estado': EstadoLead.INTERESADO_ALTO,
                    'mensaje': f"Claro que sí {lead.nombre}! 😁 ¿Qué modelo te late? ¿Versa, Sentra, Kicks...?"
                }
            elif any(word in mensaje_lower for word in ['no', 'luego', 'después', 'despues', 'ahorita no']):
                return {
                    'accion': 'mantener_interes',
                    'mensaje': f"No hay bronca {lead.nombre}, aquí andamos cuando gustes 😁 ¿Te mando la info de las promos actuales por si acaso?"
                }

        elif lead.estado == EstadoLead.INTERESADO_ALTO:
            if any(word in mensaje_lower for word in ['cita', 'visita', 'agencia', 'ver', 'cuando', 'cuándo']):
                return {
                    'accion': 'agendar_cita',
                    'nuevo_estado': EstadoLead.CITA_AGENDADA,
                    'mensaje': f"¡Va! ¿Qué día te acomoda venir {lead.nombre}? Tengo disponible mañana y pasado... 😁"
                }
            elif any(modelo in mensaje_lower for modelo in ['versa', 'sentra', 'march', 'kicks', 'frontier', 'x-trail']):
                return {
                    'accion': 'cotizar_modelo',
                    'mensaje': f"¡Buena elección! El {lead.info_prospecto.modelo_interes} está padrísimo 😁 Te mando los números..."
                }

        return {
            'accion': 'continuar_conversacion',
            'mensaje': None
        }

    def programar_seguimiento_automatico(self, lead):
        """
        Programa seguimiento automático basado en el estado del lead.
        """
        if not self.seguimiento_auto:
            return
        if lead.temperatura == TemperaturaMercado.CALIENTE:
            dias = 1
        elif lead.temperatura == TemperaturaMercado.TIBIO:
            dias = 2
        else:
            dias = 3
        try:
            self.seguimiento_auto.programar_seguimiento_especifico(
                lead.telefono,
                f'auto_{lead.estado.value}',
                dias,
                prioridad=3 if lead.temperatura == TemperaturaMercado.CALIENTE else 2
            )
        except Exception as e:
            print(f"❌ Error programando seguimiento automático: {e}")
# FIN: Clase ConversationalLeadManager

class SimpleLeadManager:
    """Manager simplificado para cuando no está disponible el tracking completo"""
    
    def __init__(self):
        self.leads_basicos = {}
    
    def procesar_mensaje_lead(self, telefono, mensaje, nombre_perfil):
        if telefono not in self.leads_basicos:
            self.leads_basicos[telefono] = {
                'nombre': nombre_perfil,
                'telefono': telefono,
                'mensajes': [],
                'info': {},
                'fecha_creacion': datetime.now()
            }
        
        lead_basico = self.leads_basicos[telefono]
        lead_basico['mensajes'].append({
            'mensaje': mensaje,
            'fecha': datetime.now(),
            'tipo': 'entrante'
        })
        
        info_extraida = self.extraer_informacion_basica(mensaje, lead_basico)
        if info_extraida:
            lead_basico['info'].update(info_extraida)
        
        siguiente_paso = self.determinar_siguiente_paso_basico(lead_basico, mensaje)
        
        return lead_basico, siguiente_paso
    
    def extraer_informacion_basica(self, mensaje, lead):
        info = {}
        mensaje_lower = mensaje.lower()

        if 'uso_vehiculo' not in lead['info']:
            if any(word in mensaje_lower for word in ['particular', 'personal', 'familia']):
                info['uso_vehiculo'] = 'particular'
            elif any(word in mensaje_lower for word in ['trabajo', 'uber', 'didi', 'taxi']):
                info['uso_vehiculo'] = 'trabajo'

        if 'comprobacion_ingresos' not in lead['info']:
            if any(word in mensaje_lower for word in ['nomina', 'formal', 'empresa']):
                info['comprobacion_ingresos'] = 'formal'
            elif any(word in mensaje_lower for word in ['informal', 'negocio', 'independiente']):
                info['comprobacion_ingresos'] = 'informal'

        # NUEVO: Captura cualquier monto de enganche y permite avanzar el flujo.
        if 'monto_enganche' not in lead['info']:
            numeros = re.findall(r'\d+', mensaje.replace(',', '').replace('.', ''))
            if numeros:
                try:
                    monto = float(numeros[0])
                    if monto < 1000:
                        monto *= 1000
                    if monto > 0:
                        info['monto_enganche'] = monto
                except:
                    pass

        if 'historial_credito' not in lead['info']:
            if any(word in mensaje_lower for word in ['bueno', 'bien', 'excelente']):
                info['historial_credito'] = 'bueno'
            elif any(word in mensaje_lower for word in ['regular', 'mas o menos']):
                info['historial_credito'] = 'regular'
            elif any(word in mensaje_lower for word in ['malo', 'mal', 'problemas']):
                info['historial_credito'] = 'malo'

        return info
    
    def determinar_siguiente_paso_basico(self, lead, mensaje):
        mensaje_lower = mensaje.lower()
        info = lead['info']
        nombre = lead['nombre']

        if len(lead['mensajes']) == 1:
            return {
                'mensaje': f"¡Hola {nombre}! 😁 ¿El auto lo buscas para uso particular o para trabajo?"
            }

        if 'uso_vehiculo' not in info:
            return {
                'mensaje': f"Perfecto {nombre}. ¿De qué forma compruebas tus ingresos? ¿Formal o informal?"
            }
        elif 'comprobacion_ingresos' not in info:
            return {
                'mensaje': f"Entiendo. ¿Cuentas con alguna cantidad disponible para enganche inicial?"
            }
        elif 'monto_enganche' not in info:
            return {
                'mensaje': f"Perfecto. ¿Cómo consideras tu historial de buró de crédito?"
            }
        elif 'monto_enganche' in info and info['monto_enganche'] < 15000:
            return {
                'mensaje': "El enganche mínimo recomendado es $15,000. ¿Te gustaría intentar con ese monto o necesitas otra opción?"
            }
        elif 'historial_credito' not in info:
            return {
                'mensaje': f"¡Excelente {nombre}! 😁 Con esa información puedo ayudarte mejor. ¿Te gustaría que te llame al 6644918078 para explicarte las mejores opciones?"
            }

        if any(word in mensaje_lower for word in ['si', 'claro', 'llamame']):
            return {
                'mensaje': f"¡Perfecto {nombre}! 😁 Te contacto hoy mismo. Mientras tanto, ¿te gustaría hacer una precalificación rápida enviando tus documentos por WhatsApp?"
            }

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
    print("🎯 Usando sistema completo de tracking")
    lead_manager = ConversationalLeadManager(lead_tracker, seguimiento_auto)
else:
    print("🔧 Usando sistema básico simplificado")
    lead_manager = SimpleLeadManager()

app = Flask(__name__)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    try:
        incoming_msg = request.values.get("Body", "").strip()
        telefono = request.values.get("From", "").replace("whatsapp:", "")
        nombre_perfil = request.values.get("ProfileName", "desconocido")
        
        print(f"📱 Mensaje de {telefono}: {incoming_msg}")
        
        if not incoming_msg:
            return Response("", mimetype="application/xml")
        
        # Usar el nuevo manager conversacional
        if TRACKING_AVAILABLE and lead_tracker:
            # Crear instancia del manager conversacional
            conversational_manager = ConversationalLeadManager(lead_tracker)
            
            # Procesar mensaje
            lead, siguiente_paso = conversational_manager.procesar_mensaje_lead(telefono, incoming_msg, nombre_perfil)
            
            # SIEMPRE usar IA para generar respuesta natural
            respuesta_final = generar_respuesta_con_contexto_inteligente(
                incoming_msg, 
                telefono, 
                lead, 
                siguiente_paso
            )
            
            # Registrar respuesta
            interaccion_bot = Interaccion(
                telefono=telefono,
                tipo=TipoInteraccion.RESPUESTA_BOT,
                descripcion=f"Bot: {respuesta_final}",
                fecha=datetime.now(),
                usuario='bot'
            )
            lead_tracker.registrar_interaccion(interaccion_bot)
            
        else:
            # Sistema básico también mejorado
            lead_basico, siguiente_paso = lead_manager.procesar_mensaje_lead(telefono, incoming_msg, nombre_perfil)
            respuesta_final = generar_respuesta_openai(incoming_msg, lead_basico, telefono)
        
        # Enviar respuesta
        resp = MessagingResponse()
        msg = resp.message()
        msg.body(html.escape(respuesta_final))
        
        print(f"🤖 Respuesta: {respuesta_final}")
        print(f"🧠 Conversación natural activada")
        return Response(str(resp), mimetype="application/xml")
        
    except Exception as e:
        print(f"❌ Error en whatsapp_reply: {e}")
        import traceback
        traceback.print_exc()
        
        resp = MessagingResponse()
        msg = resp.message()
        msg.body("¡Uy! 😁 Algo falló... ¿Me das un segundo? Ya te contesto.")
        return Response(str(resp), mimetype="application/xml")

@app.route("/")
def home():
    """Página de inicio con información de memoria mejorada"""
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
    
    # Estado de memoria mejorada
    servicios.append("✅ Memoria de conversación MEJORADA activada")
    
    # Obtener métricas si están disponibles
    metricas_html = ""
    if TRACKING_AVAILABLE and lead_tracker:
        try:
            metricas = lead_tracker.obtener_dashboard_metricas()
            metricas_html = f"""
            <h2>📊 Métricas Actuales</h2>
            <ul>
                <li><strong>Total leads:</strong> {metricas.get('total_leads', 0)}</li>
                <li><strong>Leads calientes:</strong> {metricas.get('por_temperatura', {}).get('caliente', 0)}</li>
                <li><strong>Leads tibios:</strong> {metricas.get('por_temperatura', {}).get('tibio', 0)}</li>
                <li><strong>Leads fríos:</strong> {metricas.get('por_temperatura', {}).get('frio', 0)}</li>
            </ul>
            """
        except:
            metricas_html = "<p>⚠️ Error obteniendo métricas</p>"
    
    return f"""
    <html>
    <head>
        <title>Nissan WhatsApp Bot - Memoria Mejorada</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .status {{ color: green; font-weight: bold; }}
            .service-ok {{ color: green; }}
            .service-warning {{ color: orange; }}
            .metrics {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .memory-status {{ background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 5px solid #4caf50; }}
            .feature {{ background: #e3f2fd; padding: 10px; border-radius: 5px; margin: 5px 0; }}
        </style>
    </head>
    <body>
        <h1>🚗 Bot WhatsApp Nissan</h1>
        <p class="status"><strong>Estado:</strong> {status}</p>
        
        <div class="memory-status">
            <strong>🧠 MEMORIA MEJORADA ACTIVADA:</strong>
            <ul>
                <li>✅ Recuerda conversaciones completas (20 mensajes)</li>
                <li>✅ Analiza historial de modelos y montos mencionados</li>
                <li>✅ Detecta citas y cotizaciones previas</li>
                <li>✅ Contexto enriquecido con información del lead</li>
                <li>✅ Temperatura ajustada según estado del lead</li>
            </ul>
        </div>
        
        <h2>🔧 Servicios:</h2>
        <ul>
        {"".join([f"<li class='service-ok' if '✅' in servicio else 'service-warning'>{servicio}</li>" for servicio in servicios])}
        </ul>
        
        <div class="feature">
            <strong>🚀 Nuevas características de memoria:</strong><br>
            • Análisis inteligente del historial<br>
            • Contexto personalizado por lead<br>
            • Respuestas más precisas y contextuales
        </div>
        
        <div class="metrics">
        {metricas_html}
        </div>
        
        <h2>🔗 Enlaces Útiles:</h2>
        <ul>
            <li><a href="/test">🧪 Probar servicios</a></li>
            <li><a href="/dashboard">📊 Dashboard de leads</a></li>
            <li><a href="/seguimientos">📅 Estado de seguimientos</a></li>
            <li><a href="/ejecutar_seguimientos">🚀 Ejecutar seguimientos ahora</a></li>
            <li><a href="/test_memoria">🧠 Probar memoria del bot</a></li>
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
        
        return f"""
        <html>
        <head>
            <title>Test Memoria Mejorada</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .section {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .highlight {{ background: #e8f5e8; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
        <h1>🧠 Test de Memoria MEJORADA del Bot</h1>
        
        <h2>📞 Teléfono de prueba: {test_telefono}</h2>
        <p><strong>Mensajes en historial:</strong> {len(historial)}</p>
        
        <div class="section">
            <h3>📋 Información Relevante Extraída:</h3>
            <p><strong>Modelos mencionados:</strong> {', '.join(info_relevante['modelos_mencionados']) if info_relevante['modelos_mencionados'] else 'Ninguno'}</p>
            <p><strong>Montos mencionados:</strong> {', '.join(info_relevante['montos_enganche'][:5]) if info_relevante['montos_enganche'] else 'Ninguno'}</p>
            <p><strong>Citas previas:</strong> {'✅ Sí' if info_relevante['citas_previas'] else '❌ No'}</p>
            <p><strong>Cotizaciones previas:</strong> {'✅ Sí' if info_relevante['cotizaciones_previas'] else '❌ No'}</p>
        </div>
        
        <div class="section">
            <h3>🤖 Información del Lead:</h3>
            {f"<p><strong>Nombre:</strong> {lead_info['nombre']}</p>" if lead_info and 'nombre' in lead_info else "<p>Sin información de lead</p>"}
            {f"<p><strong>Estado:</strong> {lead_info['estado']}</p>" if lead_info and 'estado' in lead_info else ""}
            {f"<p><strong>Temperatura:</strong> {lead_info['temperatura']}</p>" if lead_info and 'temperatura' in lead_info else ""}
            {f"<p><strong>Score:</strong> {lead_info['score']:.1f}</p>" if lead_info and 'score' in lead_info else ""}
        </div>
        
        <div class="section">
            <h3>💬 Contexto Construido:</h3>
            <p><strong>Total mensajes en contexto:</strong> {len(messages)}</p>
            <p><strong>Prompt del sistema incluye:</strong> {len(messages[0]['content']) if messages else 0} caracteres</p>
        </div>
        
        <div class="highlight">
            <h3>🗨️ Últimas 5 conversaciones:</h3>
        """
        + "".join([
            f"<p><strong>{'👤 Cliente' if msg['role'] == 'user' else '🤖 Bot'}:</strong> {msg['content'][:100]}...</p>"
            for msg in historial[-5:]  # Últimos 5 mensajes
        ]) + """
        </div>
        
        <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"❌ Error probando memoria mejorada: {e}"

@app.route("/test_memoria")
def test_memoria():
    """Endpoint para probar la memoria básica del bot"""
    test_telefono = "+5216641234567"  # Teléfono de prueba
    
    try:
        historial = obtener_historial_conversacion_completo(test_telefono)
        
        return f"""
        <html>
        <head><title>Test Memoria Básica</title></head>
        <body>
        <h1>🧠 Test de Memoria Básica del Bot</h1>
        
        <h2>📞 Teléfono de prueba: {test_telefono}</h2>
        <p><strong>Mensajes en historial:</strong> {len(historial)}</p>
        
        <h3>🗨️ Últimas conversaciones:</h3>
        <div style="background: #f0f0f0; padding: 15px; border-radius: 5px;">
        """
        + "".join([
            f"<p><strong>{'👤 Cliente' if msg['role'] == 'user' else '🤖 Bot'}:</strong> {msg['content']}</p>"
            for msg in historial[-10:]  # Últimos 10 mensajes
        ]) + """
        </div>
        
        <p><a href="/test_memoria_mejorada">🧠 Ver memoria MEJORADA</a></p>
        <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"❌ Error probando memoria: {e}"

@app.route("/test")
def test():
    """Endpoint para probar todos los servicios incluyendo memoria mejorada"""
    resultado = {"timestamp": datetime.now().isoformat()}
    
    # Probar OpenAI
    try:
        test_completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Di 'funciona'"}],
            max_tokens=5
        )
        resultado["openai"] = "✅ Funcionando"
    except Exception as e:
        resultado["openai"] = f"❌ Error: {str(e)}"
    
    # Probar tracking
    if TRACKING_AVAILABLE:
        try:
            metricas = lead_tracker.obtener_dashboard_metricas()
            resultado["tracking"] = f"✅ Funcionando - {metricas.get('total_leads', 0)} leads"
        except Exception as e:
            resultado["tracking"] = f"❌ Error: {str(e)}"
    else:
        resultado["tracking"] = "⚠️ No disponible"
    
    # Probar seguimiento automático
    if SEGUIMIENTO_AVAILABLE:
        try:
            estado = seguimiento_auto.mostrar_estado()
            resultado["seguimiento"] = f"✅ Funcionando - {estado['seguimientos_pendientes']} pendientes"
        except Exception as e:
            resultado["seguimiento"] = f"❌ Error: {str(e)}"
    else:
        resultado["seguimiento"] = "⚠️ No disponible"
    
    # Probar RAG
    if RAG_AVAILABLE:
        try:
            contexto = recuperar_contexto("test")
            resultado["rag"] = f"✅ Funcionando - {len(contexto)} chars"
        except Exception as e:
            resultado["rag"] = f"❌ Error: {str(e)}"
    else:
        resultado["rag"] = "⚠️ No disponible"
    
    # Probar memoria mejorada
    try:
        test_telefono = "+5216641234567"
        historial = obtener_historial_conversacion_completo(test_telefono)
        info_relevante = extraer_info_relevante_historial(historial)
        resultado["memoria_mejorada"] = f"✅ Funcionando - {len(historial)} mensajes, {len(info_relevante['modelos_mencionados'])} modelos detectados"
    except Exception as e:
        resultado["memoria_mejorada"] = f"❌ Error: {str(e)}"
    
    return jsonify(resultado)

@app.route("/dashboard")
def dashboard():
    """Dashboard con información de memoria mejorada"""
    if not TRACKING_AVAILABLE:
        return "❌ Sistema de tracking no disponible"
    
    try:
        metricas = lead_tracker.obtener_dashboard_metricas()
        leads_prioritarios = lead_tracker.obtener_leads_por_prioridad(15)
        
        html_response = f"""
        <html>
        <head>
            <title>Dashboard Nissan - Memoria Mejorada</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .caliente {{ background-color: #ffebee; }}
                .tibio {{ background-color: #fff3e0; }}
                .frio {{ background-color: #e8f5e8; }}
                .memory-info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 5px solid #2196f3; }}
            </style>
        </head>
        <body>
        <h1>📊 Dashboard Nissan - {datetime.now().strftime('%d/%m/%Y %H:%M')}</h1>
        
        <div class="memory-info">
            <strong>🧠 MEMORIA MEJORADA ACTIVADA:</strong><br>
            • Análisis inteligente del historial de cada lead<br>
            • Contexto enriquecido con información específica<br>
            • Detección automática de modelos y montos mencionados<br>
            • Respuestas personalizadas según temperatura del lead
        </div>
        
        <h2>📈 Métricas Generales</h2>
        <p><strong>Total Leads:</strong> {metricas.get('total_leads', 0)}</p>
        <p><strong>Leads Calientes:</strong> {metricas.get('por_temperatura', {}).get('caliente', 0)}</p>
        <p><strong>Leads Tibios:</strong> {metricas.get('por_temperatura', {}).get('tibio', 0)}</p>
        <p><strong>Leads Fríos:</strong> {metricas.get('por_temperatura', {}).get('frio', 0)}</p>
        
        <h2>🔥 Top Leads Prioritarios</h2>
        <table>
        <tr>
            <th>Nombre</th>
            <th>Teléfono</th>
            <th>Score</th>
            <th>Estado</th>
            <th>Temperatura</th>
            <th>Modelo</th>
            <th>Días sin interacción</th>
            <th>Memoria</th>
        </tr>
        """
        
        for lead in leads_prioritarios:
            clase_temp = lead.temperatura.value
            modelo = lead.info_prospecto.modelo_interes or "Sin definir"
            dias_sin = lead.dias_sin_interaccion()
            
            # Verificar si tiene historial y analizarlo
            historial = obtener_historial_conversacion_completo(lead.telefono)
            if historial:
                info_relevante = extraer_info_relevante_historial(historial)
                memoria_status = f"✅ {len(historial)} msgs"
            else:
                memoria_status = "❌ Sin memoria"
            
            html_response += f"""
            <tr class="{clase_temp}">
                <td>{lead.nombre}</td>
                <td>{lead.telefono}</td>
                <td>{lead.score_calificacion:.1f}</td>
                <td>{lead.estado.value}</td>
                <td>{lead.temperatura.value}</td>
                <td>{modelo}</td>
                <td>{dias_sin}</td>
                <td>{memoria_status}</td>
            </tr>
            """
        
        html_response += """
        </table>
        <br>
        <p><a href="/">🏠 Inicio</a> | <a href="/dashboard">🔄 Actualizar</a></p>
        </body>
        </html>
        """
        
        return html_response
        
    except Exception as e:
        return f"❌ Error: {e}"

@app.route("/advanced_dashboard")
def advanced_dashboard():
    """Dashboard avanzado con métricas de negocio y ROI"""
    if not ADVANCED_FEATURES:
        return "❌ Funcionalidades avanzadas no disponibles"
    
    try:
        dashboard = AdvancedDashboard()
        reporte = generar_reporte_completo(30)
        
        html_response = f"""
        <html>
        <head>
            <title>Dashboard Avanzado Nissan</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric {{ display: inline-block; margin: 10px; padding: 15px; background: #e3f2fd; border-radius: 5px; min-width: 150px; text-align: center; }}
                .metric h3 {{ margin: 0; color: #1976d2; }}
                .metric p {{ margin: 5px 0; font-size: 24px; font-weight: bold; }}
                .success {{ background: #e8f5e8; color: #2e7d32; }}
                .warning {{ background: #fff3e0; color: #f57c00; }}
            </style>
        </head>
        <body>
        <div class="container">
            <h1>📈 Dashboard Avanzado Nissan</h1>
            <p><strong>Reporte generado:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            
            <div class="card">
                <h2>📊 Métricas de Conversión (30 días)</h2>
                <div class="metric success">
                    <h3>Total Leads</h3>
                    <p>{reporte['conversion_metrics'].get('total_leads', 0)}</p>
                </div>
                <div class="metric">
                    <h3>Tasa Cierre</h3>
                    <p>{reporte['conversion_metrics'].get('tasas_conversion', {}).get('cierre', 0)}%</p>
                </div>
            </div>
            
            <div class="card">
                <h2>💰 Análisis ROI</h2>
                <div class="metric success">
                    <h3>ROI Actual</h3>
                    <p>{reporte['roi_analysis'].get('roi_actual_porcentaje', 0)}%</p>
                </div>
                <div class="metric warning">
                    <h3>ROI Potencial</h3>
                    <p>{reporte['roi_analysis'].get('roi_potencial_porcentaje', 0)}%</p>
                </div>
            </div>
            
            <p><a href="/">🏠 Volver al inicio</a></p>
        </div>
        </body>
        </html>
        """
        
        return html_response
        
    except Exception as e:
        return f"❌ Error generando dashboard avanzado: {e}"

@app.route("/test_sentiment")
def test_sentiment():
    """Endpoint para probar el análisis de sentimientos"""
    if not ADVANCED_FEATURES:
        return "❌ Análisis de sentimientos no disponible"
    
    try:
        analyzer = SentimentAnalyzer()
        
        # Mensajes de prueba
        mensajes_test = [
            "Hola, me interesa el Sentra pero está muy caro",
            "¡Excelente! Me encanta el diseño del Kicks",
            "No sé si pueda comprobar mis ingresos",
            "Necesito el auto ya, es urgente para trabajar",
            "Gracias por la información, lo voy a pensar"
        ]
        
        resultados = []
        for mensaje in mensajes_test:
            analisis = analyzer.analizar_sentimiento_basico(mensaje)
            estrategia = analyzer.sugerir_estrategia_respuesta(analisis)
            resultados.append({
                'mensaje': mensaje,
                'sentimientos': analisis.get('sentimientos', []),
                'tipo': analisis.get('tipo_mensaje', 'general'),
                'tono_sugerido': estrategia.get('tono', 'amigable'),
                'enfoque': estrategia.get('enfoque', 'informativo')
            })
        
        html_response = f"""
        <html>
        <head><title>Test Análisis de Sentimientos</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .test {{ background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .sentiment {{ background: #e3f2fd; padding: 5px; margin: 5px; border-radius: 3px; display: inline-block; }}
        </style>
        </head>
        <body>
        <h1>🧠 Test de Análisis de Sentimientos</h1>
        """
        
        for resultado in resultados:
            html_response += f"""
            <div class="test">
                <p><strong>Mensaje:</strong> "{resultado['mensaje']}"</p>
                <p><strong>Sentimientos detectados:</strong> 
                {' '.join([f'<span class="sentiment">{s}</span>' for s in resultado['sentimientos']]) if resultado['sentimientos'] else 'Ninguno específico'}
                </p>
                <p><strong>Tipo:</strong> {resultado['tipo']}</p>
                <p><strong>Tono sugerido:</strong> {resultado['tono_sugerido']}</p>
                <p><strong>Enfoque:</strong> {resultado['enfoque']}</p>
            </div>
            """
        
        html_response += """
        <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
        </html>
        """
        
        return html_response
        
    except Exception as e:
        return f"❌ Error probando análisis de sentimientos: {e}"

if __name__ == "__main__":
    print("🚀 Iniciando aplicación Flask...")
    print(f"📊 Tracking disponible: {TRACKING_AVAILABLE}")
    print(f"🤖 Seguimiento automático disponible: {SEGUIMIENTO_AVAILABLE}")
    print(f"🧠 RAG disponible: {RAG_AVAILABLE}")
    print(f"🧠 MEMORIA DE CONVERSACIÓN MEJORADA: ✅ ACTIVADA")
    print("   • Análisis inteligente del historial")
    print("   • Contexto enriquecido con información del lead")
    print("   • Detección de modelos y montos mencionados")
    print("   • Temperatura ajustada según estado")
    
    # Inicializar seguimiento automático
    if SEGUIMIENTO_AVAILABLE:
        try:
            seguimiento_auto.iniciar_seguimiento()
            print("🤖 Sistema de seguimiento automático iniciado")
        except Exception as e:
            print(f"⚠️ Error iniciando seguimiento automático: {e}")
    
    # Mostrar métricas iniciales
    if TRACKING_AVAILABLE:
        try:
            metricas = lead_tracker.obtener_dashboard_metricas()
            print(f"📈 Leads en sistema: {metricas.get('total_leads', 0)}")
            print(f"🔥 Leads calientes: {metricas.get('por_temperatura', {}).get('caliente', 0)}")
        except Exception as e:
            print(f"⚠️ Error obteniendo métricas iniciales: {e}")
    
    print("🌐 Servidor iniciado en http://localhost:5001")
    print("🔗 Dashboard: http://localhost:5001/dashboard")
    print("📅 Seguimientos: http://localhost:5001/seguimientos")
    print("🧪 Test: http://localhost:5001/test")
    print("🧠 Test memoria: http://localhost:5001/test_memoria")
    print("🧠 Test memoria MEJORADA: http://localhost:5001/test_memoria_mejorada")
    
    app.run(host="0.0.0.0", port=5001, debug=True)