# app.py - Versión final con memoria completa del bot
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

# Inicializar servicios
if TRACKING_AVAILABLE:
    lead_tracker = LeadTrackingService()
else:
    lead_tracker = None

if SEGUIMIENTO_AVAILABLE:
    seguimiento_auto = SeguimientoAutomaticoService()
else:
    seguimiento_auto = None

def recuperar_contexto(pregunta):
    """Recupera contexto de la base de conocimiento si está disponible"""
    if RAG_AVAILABLE:
        try:
            resultados = vector_db.similarity_search(pregunta, k=2)
            return "\n\n".join([doc.page_content for doc in resultados])
        except Exception as e:
            print(f"Error en RAG: {e}")
    
    # Contexto básico si no hay RAG
    return """
    SICREA ofrece financiamiento automotriz con:
    - Plan Sí Fácil: Para personas con mal buró o sin comprobación de ingresos
    - Plan Cronos: Financiamiento tradicional
    - Enganches desde $15,000 pesos
    - Mensualidades competitivas
    """

def obtener_historial_conversacion_completo(telefono):
    """Obtiene historial tanto de la tabla antigua como de las nuevas interacciones"""
    historial_completo = []
    
    try:
        # 1. Obtener de la tabla antigua historial_conversaciones
        if supabase:
            response_antiguo = supabase.table('historial_conversaciones').select('mensaje, respuesta, timestamp').eq('telefono', telefono).order('timestamp', desc=False).execute()
            
            for entrada in response_antiguo.data:
                # Agregar mensaje del cliente
                historial_completo.append({
                    "role": "user", 
                    "content": entrada["mensaje"],
                    "timestamp": entrada.get("timestamp", "")
                })
                # Agregar respuesta del bot
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
                    # Extraer mensaje del cliente de la descripción
                    descripcion = interaccion['descripcion']
                    if descripcion.startswith('Cliente: '):
                        mensaje = descripcion.replace('Cliente: ', '')
                        historial_completo.append({
                            "role": "user", 
                            "content": mensaje,
                            "timestamp": interaccion['fecha']
                        })
                elif interaccion['tipo'] == 'respuesta_bot':
                    # Extraer respuesta del bot
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
        return historial_completo[-20:]  # Últimas 10 conversaciones (20 mensajes)
        
    except Exception as e:
        print(f"❌ Error obteniendo historial: {e}")
        return []

def construir_contexto_conversacion(telefono, mensaje_actual):
    """Construye el contexto completo de la conversación para OpenAI"""
    try:
        # Obtener historial completo
        historial = obtener_historial_conversacion_completo(telefono)
        
        # Construir mensajes para OpenAI
        messages = []
        
        # Agregar prompt del sistema
        prompt_path = "prompt_sistema_nissan.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_sistema = f.read().strip()
        else:
            prompt_sistema = """
            Eres César Arias, asesor de ventas Nissan. Responde de forma amigable y profesional.
            Mantén respuestas cortas (máximo 2 líneas). Usa emoji 😁.
            Tu objetivo es calificar leads y agendar citas. Teléfono: 6644918078.
            """
        
        messages.append({"role": "system", "content": prompt_sistema})
        
        # Agregar historial de conversación
        for entrada in historial:
            if entrada['role'] in ['user', 'assistant']:
                messages.append({
                    "role": entrada['role'],
                    "content": entrada['content']
                })
        
        # Agregar mensaje actual
        messages.append({
            "role": "user",
            "content": mensaje_actual
        })
        
        return messages
        
    except Exception as e:
        print(f"❌ Error construyendo contexto: {e}")
        return [
            {"role": "system", "content": "Eres César Arias, asesor de ventas Nissan."},
            {"role": "user", "content": mensaje_actual}
        ]

def generar_respuesta_con_memoria(mensaje, telefono, lead_info):
    """Genera respuesta usando OpenAI con memoria completa de la conversación"""
    try:
        # Construir contexto con historial completo
        messages = construir_contexto_conversacion(telefono, mensaje)
        
        # Obtener contexto de RAG
        contexto_rag = recuperar_contexto(mensaje)
        
        # Agregar información del lead actual al contexto
        nombre = lead_info.get('nombre', 'amigo')
        info_lead = f"\nINFORMACIÓN DEL LEAD ACTUAL:\n- Nombre: {nombre}"
        
        if hasattr(lead_info, 'info_prospecto'):
            # Es un objeto Lead completo
            if lead_info.info_prospecto.uso_vehiculo:
                info_lead += f"\n- Uso vehículo: {lead_info.info_prospecto.uso_vehiculo}"
            if lead_info.info_prospecto.comprobacion_ingresos:
                info_lead += f"\n- Comprobación ingresos: {lead_info.info_prospecto.comprobacion_ingresos}"
            if lead_info.info_prospecto.monto_enganche:
                info_lead += f"\n- Monto enganche: ${lead_info.info_prospecto.monto_enganche:,.0f}"
            if lead_info.info_prospecto.historial_credito:
                info_lead += f"\n- Historial crédito: {lead_info.info_prospecto.historial_credito}"
            if lead_info.info_prospecto.modelo_interes:
                info_lead += f"\n- Modelo interés: {lead_info.info_prospecto.modelo_interes}"
            
            info_lead += f"\n- Estado: {lead_info.estado.value}"
            info_lead += f"\n- Score: {lead_info.score_calificacion:.1f}"
            
        elif isinstance(lead_info, dict) and 'info' in lead_info:
            # Es un lead básico
            for key, value in lead_info['info'].items():
                info_lead += f"\n- {key}: {value}"
        
        # Agregar contexto de RAG e información del lead al primer mensaje del sistema
        messages[0]['content'] += f"\n\nINFORMACIÓN ÚTIL:\n{contexto_rag}\n{info_lead}"
        
        # Generar respuesta
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        
        respuesta = completion.choices[0].message.content.strip()
        
        # Guardar en historial_conversaciones (tabla antigua) para mantener compatibilidad
        if supabase:
            try:
                supabase.table('historial_conversaciones').insert({
                    'telefono': telefono,
                    'mensaje': mensaje,
                    'respuesta': respuesta,
                    'timestamp': datetime.now().isoformat()
                }).execute()
                print(f"✅ Guardado en historial_conversaciones: {telefono}")
            except Exception as e:
                print(f"⚠️ Error guardando en historial_conversaciones: {e}")
        
        return respuesta
        
    except Exception as e:
        print(f"❌ Error generando respuesta con memoria: {e}")
        return f"Hola {lead_info.get('nombre', 'amigo')}! 😁 Disculpa, ¿puedes repetir tu pregunta? Te ayudo con gusto."

def generar_respuesta_openai(mensaje, lead_info, telefono=None):
    """Genera respuesta usando OpenAI - versión con memoria mejorada"""
    
    # Si tenemos el teléfono, usar la función con memoria completa
    if telefono:
        return generar_respuesta_con_memoria(mensaje, telefono, lead_info)
    
    # Fallback a la función original si no hay teléfono
    try:
        prompt_path = "prompt_sistema_nissan.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_sistema = f.read().strip()
        else:
            prompt_sistema = """
            Eres César Arias, asesor de ventas Nissan. Responde de forma amigable y profesional.
            Mantén respuestas cortas (máximo 2 líneas). Usa emoji 😁.
            Tu objetivo es calificar leads y agendar citas. Teléfono: 6644918078.
            """
        
        contexto = recuperar_contexto(mensaje)
        nombre = lead_info.get('nombre', 'amigo')
        
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
        return f"Hola {lead_info.get('nombre', 'amigo')}! 😁 Disculpa, ¿puedes repetir tu pregunta? Te ayudo con gusto."

class LeadManager:
    """Manager completo para leads con seguimiento"""
    
    def __init__(self, lead_tracker):
        self.lead_tracker = lead_tracker
    
    def procesar_mensaje_lead(self, telefono, mensaje, nombre_perfil):
        """Procesa un mensaje y actualiza el lead correspondientemente"""
        
        # Obtener o crear lead
        lead = self.lead_tracker.obtener_lead(telefono)
        if not lead:
            lead = self.lead_tracker.crear_lead(telefono, nombre_perfil, "whatsapp")
            print(f"✅ Nuevo lead creado: {telefono}")
        
        # Registrar mensaje entrante
        interaccion = Interaccion(
            telefono=telefono,
            tipo=TipoInteraccion.MENSAJE_ENTRANTE,
            descripcion=f"Cliente: {mensaje}",
            fecha=datetime.now(),
            usuario='cliente'
        )
        self.lead_tracker.registrar_interaccion(interaccion)
        
        # Analizar mensaje y extraer información
        info_extraida = self.extraer_informacion_mensaje(mensaje, lead)
        
        # Actualizar información del lead si se extrajo algo
        if info_extraida:
            for campo, valor in info_extraida.items():
                self.lead_tracker.actualizar_info_prospecto(telefono, campo, valor)
                print(f"📝 Actualizado {campo}: {valor}")
        
        # Determinar siguiente paso en el flujo
        siguiente_paso = self.determinar_siguiente_paso(lead, mensaje)
        
        # Actualizar estado si es necesario
        if siguiente_paso.get('nuevo_estado'):
            self.lead_tracker.cambiar_estado(
                telefono, 
                siguiente_paso['nuevo_estado'], 
                siguiente_paso.get('notas', '')
            )
        
        return lead, siguiente_paso
    
    def extraer_informacion_mensaje(self, mensaje, lead):
        """Extrae información específica del mensaje"""
        info_extraida = {}
        mensaje_lower = mensaje.lower()
        
        # Extraer uso del vehículo
        if not lead.info_prospecto.uso_vehiculo:
            if any(word in mensaje_lower for word in ['particular', 'personal', 'familia', 'casa']):
                info_extraida['uso_vehiculo'] = 'particular'
            elif any(word in mensaje_lower for word in ['trabajo', 'uber', 'didi', 'taxi', 'negocio', 'comercial']):
                info_extraida['uso_vehiculo'] = 'trabajo'
        
        # Extraer comprobación de ingresos
        if not lead.info_prospecto.comprobacion_ingresos:
            if any(word in mensaje_lower for word in ['nomina', 'formal', 'empresa', 'empleado', 'recibo']):
                info_extraida['comprobacion_ingresos'] = 'formal'
            elif any(word in mensaje_lower for word in ['informal', 'negocio', 'independiente', 'sin recibos']):
                info_extraida['comprobacion_ingresos'] = 'informal'
            elif any(word in mensaje_lower for word in ['no tengo', 'sin ingresos', 'no compruebo']):
                info_extraida['comprobacion_ingresos'] = 'ninguna'
        
        # Extraer monto de enganche
        if not lead.info_prospecto.monto_enganche:
            numeros = re.findall(r'\d+(?:,\d{3})*', mensaje)
            if numeros:
                try:
                    monto = float(numeros[0].replace(',', ''))
                    if monto > 5000:  # Solo si parece un monto real
                        if monto < 1000:  # Probablemente en miles
                            monto *= 1000
                        info_extraida['monto_enganche'] = monto
                except:
                    pass
        
        # Extraer historial crediticio
        if not lead.info_prospecto.historial_credito:
            if any(word in mensaje_lower for word in ['bueno', 'bien', 'excelente', 'sin problemas']):
                info_extraida['historial_credito'] = 'bueno'
            elif any(word in mensaje_lower for word in ['regular', 'mas o menos', 'normal', 'algunos problemas']):
                info_extraida['historial_credito'] = 'regular'
            elif any(word in mensaje_lower for word in ['malo', 'mal', 'problemas', 'buro', 'deudas']):
                info_extraida['historial_credito'] = 'malo'
        
        # Extraer modelo de interés
        modelos_nissan = ['sentra', 'versa', 'march', 'frontier', 'kicks', 'x-trail', 'pathfinder', 'altima']
        for modelo in modelos_nissan:
            if modelo in mensaje_lower:
                info_extraida['modelo_interes'] = modelo.title()
                break
        
        # Extraer urgencia de compra
        if any(word in mensaje_lower for word in ['ya', 'pronto', 'inmediato', 'rapido', 'urgente']):
            info_extraida['urgencia_compra'] = 'inmediata'
        elif any(word in mensaje_lower for word in ['mes', 'meses', '3 meses']):
            info_extraida['urgencia_compra'] = '3meses'
        elif any(word in mensaje_lower for word in ['año', 'tiempo', 'pensando']):
            info_extraida['urgencia_compra'] = 'año'
        
        return info_extraida
    
    def determinar_siguiente_paso(self, lead, mensaje):
        """Determina el siguiente paso en el flujo de ventas"""
        mensaje_lower = mensaje.lower()
        info = lead.info_prospecto
        
        # Si es primer contacto
        if lead.estado == EstadoLead.CONTACTO_INICIAL:
            if any(word in mensaje_lower for word in ['hola', 'info', 'informacion', 'precio', 'cotizar']):
                return {
                    'accion': 'solicitar_uso_vehiculo',
                    'nuevo_estado': EstadoLead.CALIFICANDO,
                    'mensaje': f"¡Hola {lead.nombre}! 😁 ¿El auto lo buscas para uso particular o para trabajo?"
                }
        
        # Si está en proceso de calificación
        elif lead.estado == EstadoLead.CALIFICANDO:
            if not info.uso_vehiculo:
                return {
                    'accion': 'solicitar_comprobacion_ingresos',
                    'mensaje': f"Perfecto {lead.nombre}. ¿De qué forma compruebas tus ingresos? ¿Formal o informal?"
                }
            elif not info.comprobacion_ingresos:
                return {
                    'accion': 'solicitar_enganche',
                    'mensaje': f"Entiendo. ¿Cuentas con alguna cantidad disponible para enganche inicial?"
                }
            elif not info.monto_enganche:
                return {
                    'accion': 'solicitar_buro',
                    'mensaje': f"Perfecto. ¿Cómo consideras tu historial de buró de crédito?"
                }
            elif not info.historial_credito:
                return {
                    'accion': 'finalizar_calificacion',
                    'nuevo_estado': EstadoLead.CALIFICADO,
                    'mensaje': f"¡Excelente {lead.nombre}! 😁 Con esa información puedo ayudarte mejor. ¿Te gustaría que te llame al 6644918078 para explicarte las mejores opciones?"
                }
        
        # Si ya está calificado
        elif lead.estado == EstadoLead.CALIFICADO:
            if any(word in mensaje_lower for word in ['si', 'claro', 'esta bien', 'llamame', 'llama']):
                return {
                    'accion': 'agendar_llamada',
                    'nuevo_estado': EstadoLead.INTERESADO_ALTO,
                    'mensaje': f"¡Perfecto {lead.nombre}! 😁 Te contacto hoy mismo. Mientras tanto, ¿te gustaría hacer una precalificación rápida enviando tus documentos por WhatsApp?"
                }
            elif any(word in mensaje_lower for word in ['precio', 'costo', 'cuanto', 'cotizar']):
                return {
                    'accion': 'solicitar_cotizacion',
                    'nuevo_estado': EstadoLead.INTERESADO_ALTO,
                    'mensaje': f"Claro {lead.nombre}! 😁 Para darte el mejor precio necesito saber qué modelo específico te interesa. ¿Sentra, Versa, March, o cuál?"
                }
        
        # Si está interesado alto
        elif lead.estado == EstadoLead.INTERESADO_ALTO:
            if any(word in mensaje_lower for word in ['cita', 'visita', 'agencia', 'ver']):
                return {
                    'accion': 'agendar_cita',
                    'nuevo_estado': EstadoLead.CITA_AGENDADA,
                    'mensaje': f"¡Excelente {lead.nombre}! 😁 ¿Qué día te viene mejor? ¿Mañana o pasado?"
                }
        
        # Default - continuar conversación
        return {
            'accion': 'continuar_conversacion',
            'mensaje': None  # Usar OpenAI para generar respuesta
        }
    
    def programar_seguimiento_automatico(self, lead):
        """Programa seguimiento automático basado en el estado del lead"""
        if not seguimiento_auto:
            return
            
        if lead.temperatura == TemperaturaMercado.CALIENTE:
            dias = 1
        elif lead.temperatura == TemperaturaMercado.TIBIO:
            dias = 2
        else:
            dias = 3
        
        try:
            seguimiento_auto.programar_seguimiento_especifico(
                lead.telefono,
                f'auto_{lead.estado.value}',
                dias,
                prioridad=3 if lead.temperatura == TemperaturaMercado.CALIENTE else 2
            )
        except Exception as e:
            print(f"❌ Error programando seguimiento automático: {e}")

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
        
        if 'monto_enganche' not in lead['info']:
            numeros = re.findall(r'\d+', mensaje)
            if numeros:
                try:
                    monto = float(numeros[0])
                    if monto > 5000:
                        if monto < 1000:
                            monto *= 1000
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
        elif 'historial_credito' not in info:
            return {
                'mensaje': f"¡Excelente {nombre}! 😁 Con esa información puedo ayudarte mejor. ¿Te gustaría que te llame al 6644918078 para explicarte las mejores opciones?"
            }
        
        if any(word in mensaje_lower for word in ['si', 'claro', 'llamame']):
            return {
                'mensaje': f"¡Perfecto {nombre}! 😁 Te contacto hoy mismo. Mientras tanto, ¿te gustaría hacer una precalificación rápida enviando tus documentos por WhatsApp?"
            }
        
        return {'mensaje': None}

# Inicializar manager apropiado
if TRACKING_AVAILABLE and lead_tracker:
    print("🎯 Usando sistema completo de tracking")
    lead_manager = LeadManager(lead_tracker)
else:
    print("🔧 Usando sistema básico simplificado")
    lead_manager = SimpleLeadManager()

app = Flask(__name__)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    try:
        # Obtener datos del mensaje
        incoming_msg = request.values.get("Body", "").strip()
        telefono = request.values.get("From", "").replace("whatsapp:", "")
        nombre_perfil = request.values.get("ProfileName", "desconocido")
        
        print(f"📱 Mensaje de {telefono}: {incoming_msg}")
        
        if not incoming_msg:
            return Response("", mimetype="application/xml")
        
        # Procesar según sistema disponible
        if TRACKING_AVAILABLE and lead_tracker:
            # Usar sistema completo
            lead, siguiente_paso = lead_manager.procesar_mensaje_lead(telefono, incoming_msg, nombre_perfil)
            
            # Generar respuesta CON MEMORIA
            if siguiente_paso.get('mensaje'):
                respuesta_final = siguiente_paso['mensaje']
            else:
                # AQUÍ ES LA CLAVE: Pasar el teléfono para usar memoria
                respuesta_final = generar_respuesta_openai(incoming_msg, lead, telefono)
            
            # Registrar respuesta del bot
            interaccion_bot = Interaccion(
                telefono=telefono,
                tipo=TipoInteraccion.RESPUESTA_BOT,
                descripcion=f"Bot: {respuesta_final}",
                fecha=datetime.now(),
                usuario='bot'
            )
            lead_tracker.registrar_interaccion(interaccion_bot)
            
            # Programar seguimiento automático si es necesario
            if siguiente_paso.get('nuevo_estado'):
                lead_manager.programar_seguimiento_automatico(lead)
            
        else:
            # Usar sistema básico CON MEMORIA
            lead_basico, siguiente_paso = lead_manager.procesar_mensaje_lead(telefono, incoming_msg, nombre_perfil)
            
            if siguiente_paso.get('mensaje'):
                respuesta_final = siguiente_paso['mensaje']
            else:
                # TAMBIÉN aquí pasar teléfono para memoria
                respuesta_final = generar_respuesta_openai(incoming_msg, lead_basico, telefono)
        
        # Enviar respuesta
        resp = MessagingResponse()
        msg = resp.message()
        msg.body(html.escape(respuesta_final))
        
        print(f"🤖 Respuesta enviada: {respuesta_final}")
        print(f"🧠 Memoria activada para: {telefono}")
        return Response(str(resp), mimetype="application/xml")
        
    except Exception as e:
        print(f"❌ Error en whatsapp_reply: {e}")
        import traceback
        traceback.print_exc()
        
        # Respuesta de emergencia
        resp = MessagingResponse()
        msg = resp.message()
        msg.body("Lo siento, tuvimos un problema técnico. Un asesor te contactará pronto. 😁")
        return Response(str(resp), mimetype="application/xml")

@app.route("/")
def home():
    """Página de inicio mejorada"""
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
    
    # NUEVO: Estado de memoria
    servicios.append("✅ Memoria de conversación activada")
    
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
        <title>Nissan WhatsApp Bot</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .status {{ color: green; font-weight: bold; }}
            .service-ok {{ color: green; }}
            .service-warning {{ color: orange; }}
            .metrics {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .memory-status {{ background: #e8f5e8; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h1>🚗 Bot WhatsApp Nissan</h1>
        <p class="status"><strong>Estado:</strong> {status}</p>
        
        <div class="memory-status">
            <strong>🧠 MEMORIA ACTIVADA:</strong> El bot ahora recuerda conversaciones completas
        </div>
        
        <h2>🔧 Servicios:</h2>
        <ul>
        {"".join([f"<li class='service-ok' if '✅' in servicio else 'service-warning'>{servicio}</li>" for servicio in servicios])}
        </ul>
        
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
        </ul>
        
        <p><small>⏰ Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
    </body>
    </html>
    """

@app.route("/test_memoria")
def test_memoria():
    """Endpoint para probar la memoria del bot"""
    test_telefono = "+5216641234567"  # Teléfono de prueba
    
    try:
        historial = obtener_historial_conversacion_completo(test_telefono)
        
        return f"""
        <html>
        <head><title>Test Memoria Bot</title></head>
        <body>
        <h1>🧠 Test de Memoria del Bot</h1>
        
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
        
        <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"❌ Error probando memoria: {e}"

@app.route("/dashboard")
def dashboard():
    """Dashboard simple de leads con información de memoria"""
    if not TRACKING_AVAILABLE:
        return "❌ Sistema de tracking no disponible"
    
    try:
        metricas = lead_tracker.obtener_dashboard_metricas()
        leads_prioritarios = lead_tracker.obtener_leads_por_prioridad(15)
        
        html_response = f"""
        <html>
        <head>
            <title>Dashboard Nissan</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .caliente {{ background-color: #ffebee; }}
                .tibio {{ background-color: #fff3e0; }}
                .frio {{ background-color: #e8f5e8; }}
                .memory-info {{ background: #e3f2fd; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
        <h1>📊 Dashboard Nissan - {datetime.now().strftime('%d/%m/%Y %H:%M')}</h1>
        
        <div class="memory-info">
            <strong>🧠 MEMORIA ACTIVADA:</strong> El bot recuerda hasta 20 mensajes por conversación
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
            
            # Verificar si tiene historial
            historial = obtener_historial_conversacion_completo(lead.telefono)
            memoria_status = f"✅ {len(historial)} msgs" if historial else "❌ Sin memoria"
            
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
        <p><a href="/">🏠 Inicio</a> | <a href="/dashboard">🔄 Actualizar</a> | <a href="/seguimientos">📅 Seguimientos</a></p>
        </body>
        </html>
        """
        
        return html_response
        
    except Exception as e:
        return f"❌ Error: {e}"

# Resto de endpoints iguales...
@app.route("/seguimientos")
def estado_seguimientos():
    """Muestra el estado del sistema de seguimientos"""
    if not SEGUIMIENTO_AVAILABLE:
        return "❌ Sistema de seguimiento no disponible"
    
    try:
        estado = seguimiento_auto.mostrar_estado()
        
        return f"""
        <html>
        <head><title>Estado de Seguimientos</title></head>
        <body>
        <h1>📅 Estado del Sistema de Seguimientos</h1>
        
        <h2>🔧 Estado del Sistema</h2>
        <p><strong>Funcionando:</strong> {"✅ Sí" if estado['running'] else "❌ No"}</p>
        <p><strong>Twilio habilitado:</strong> {"✅ Sí" if estado['twilio_enabled'] else "❌ No"}</p>
        <p><strong>Seguimientos pendientes:</strong> {estado['seguimientos_pendientes']}</p>
        <p><strong>Próximo reporte:</strong> {estado['proximo_reporte']}</p>
        
        <h2>🚀 Acciones</h2>
        <p><a href="/ejecutar_seguimientos">▶️ Ejecutar seguimientos ahora</a></p>
        <p><a href="/dashboard">📊 Ver dashboard</a></p>
        <p><a href="/">🏠 Inicio</a></p>
        
        <p><small>⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"❌ Error: {e}"

@app.route("/ejecutar_seguimientos")
def ejecutar_seguimientos():
    """Ejecuta seguimientos pendientes manualmente"""
    if not SEGUIMIENTO_AVAILABLE:
        return "❌ Sistema de seguimiento no disponible"
    
    try:
        seguimiento_auto.ejecutar_seguimientos_ahora()
        return """
        <html>
        <head><title>Seguimientos Ejecutados</title></head>
        <body>
        <h1>✅ Seguimientos Ejecutados</h1>
        <p>Los seguimientos pendientes han sido procesados.</p>
        <p><a href="/seguimientos">📅 Ver estado de seguimientos</a></p>
        <p><a href="/dashboard">📊 Ver dashboard</a></p>
        <p><a href="/">🏠 Inicio</a></p>
        </body>
        </html>
        """
    except Exception as e:
        return f"❌ Error ejecutando seguimientos: {e}"

@app.route("/test")
def test():
    """Endpoint para probar todos los servicios incluyendo memoria"""
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
    
    # Probar memoria
    try:
        test_telefono = "+5216641234567"
        historial = obtener_historial_conversacion_completo(test_telefono)
        resultado["memoria"] = f"✅ Funcionando - {len(historial)} mensajes de prueba"
    except Exception as e:
        resultado["memoria"] = f"❌ Error: {str(e)}"
    
    return jsonify(resultado)

if __name__ == "__main__":
    print("🚀 Iniciando aplicación Flask...")
    print(f"📊 Tracking disponible: {TRACKING_AVAILABLE}")
    print(f"🤖 Seguimiento automático disponible: {SEGUIMIENTO_AVAILABLE}")
    print(f"🧠 RAG disponible: {RAG_AVAILABLE}")
    print(f"🧠 MEMORIA DE CONVERSACIÓN: ✅ ACTIVADA")
    
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
    
    app.run(host="0.0.0.0", port=5001, debug=True)