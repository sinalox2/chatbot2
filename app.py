# app.py - Versión final completa con memoria mejorada

# Sistema robusto para evitar respuestas duplicadas
import time
from collections import defaultdict

# Cambiar de set simple a dict con timestamps
mensajes_procesados = defaultdict(float)

try:
    from services.contactos_proactivos import contactos_proactivos_service
    CONTACTOS_PROACTIVOS_AVAILABLE = True
    print("✅ Servicio de contactos proactivos importado correctamente")
except ImportError as e:
    print(f"⚠️ Error importando contactos proactivos: {e}")
    CONTACTOS_PROACTIVOS_AVAILABLE = False

def detectar_cliente_para_seguimiento_proactivo(telefono, nombre, contexto_conversacion):
    """
    Función para detectar automáticamente clientes que necesitan seguimiento proactivo
    Se puede llamar desde el flujo principal cuando un cliente se enfría
    """
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return False
    
    try:
        # Detectar si es un lead que se enfrió
        if any(palabra in contexto_conversacion.lower() for palabra in 
               ['lo voy a pensar', 'después', 'más tarde', 'ahorita no', 'luego te digo']):
            
            # Programar seguimiento en 24 horas
            exito = contactos_proactivos_service.programar_mensaje_diferido(
                telefono=telefono,
                nombre=nombre,
                contexto=f"Cliente que mostró interés pero decidió pensarlo. Contexto: {contexto_conversacion[:200]}",
                horas_delay=24,
                tipo_campana='seguimiento'
            )
            
            if exito:
                print(f"📅 Seguimiento proactivo programado para {nombre} ({telefono})")
                return True
        
        # Detectar si es un lead con objeción de precio
        elif any(palabra in contexto_conversacion.lower() for palabra in 
                ['caro', 'precio alto', 'no puedo', 'muy caro']):
            
            # Programar seguimiento con nueva promoción en 3 días
            exito = contactos_proactivos_service.programar_mensaje_diferido(
                telefono=telefono,
                nombre=nombre,
                contexto=f"Cliente con objeción de precio. Contexto: {contexto_conversacion[:200]}",
                horas_delay=72,  # 3 días
                tipo_campana='promocion'
            )
            
            if exito:
                print(f"🎯 Seguimiento promocional programado para {nombre} ({telefono})")
                return True
                
        return False
        
    except Exception as e:
        print(f"❌ Error detectando seguimiento proactivo: {e}")
        return False

def limpiar_mensajes_antiguos():
    """Limpia mensajes procesados más antiguos de 1 hora"""
    limite = time.time() - 3600  # 1 hora
    keys_to_remove = [k for k, v in mensajes_procesados.items() if v < limite]
    for key in keys_to_remove:
        del mensajes_procesados[key]
    if keys_to_remove:
        print(f"🧹 Limpiados {len(keys_to_remove)} mensajes antiguos")

def generar_id_unico(data, telefono):
    """Genera ID único considerando múltiples fuentes"""
    mensaje_id = data.get("id") or data.get("message", {}).get("id", "")
    contenido = data.get("content", "").strip()
    timestamp = data.get("timestamp", int(time.time()))
    
    # Combinar fuentes para ID único
    return f"{telefono}_{mensaje_id}_{hash(contenido)}_{timestamp}"

def validar_origen_mensaje(data):
    """Valida si el mensaje viene de usuario real o es loop"""
    # Verificar si es mensaje entrante de usuario
    sender_type = data.get("sender", {}).get("type", "")
    message_type = data.get("message_type", "")
    
    # No procesar mensajes del bot o agente
    if sender_type in ["agent_bot", "agent"] or message_type == "outgoing":
        print(f"🚫 Mensaje ignorado - origen: {sender_type}, tipo: {message_type}")
        return False
    
    return True

def determinar_canal_respuesta(data):
    """Determina si responder por Chatwoot o WhatsApp directamente"""
    # Si viene de Chatwoot, responder solo por Chatwoot
    if data.get("conversation", {}).get("id"):
        return "chatwoot"
    # Si viene directamente de WhatsApp, responder solo por WhatsApp
    else:
        return "whatsapp"

from flask import Flask, request, Response, jsonify
import importlib
def handle_message_with_rag(message):
    """
    Lógica para consultar RAG si aplica: 
    Si el mensaje termina en '?' y tiene al menos 4 palabras, intenta responder con RAG.
    """
    if message.strip().endswith('?') and len(message.strip().split()) >= 4:
        try:
            # Importación dinámica para evitar error si rag.buscador no existe
            consulta_rag_vectorial = None
            try:
                from rag.buscador import consulta_rag_vectorial
            except ImportError:
                # Intentar import dinámico
                rag_mod = importlib.import_module("rag.buscador")
                consulta_rag_vectorial = getattr(rag_mod, "consulta_rag_vectorial", None)
            if not consulta_rag_vectorial:
                return None
            # --- BLOQUE DE LOG PARA SUPABASE RAG ---
            # Si la función consulta_rag_vectorial internamente llama a buscar_similitud_supabase, interceptar aquí
            # Si no, se asume que buscar_similitud_supabase está en rag.buscador y puede ser llamada aquí
            # Suponemos que la función consulta_rag_vectorial usa buscar_similitud_supabase(query)
            # Entonces para loguear, primero intentamos llamar buscar_similitud_supabase directamente, si existe:
            try:
                from rag.buscador import buscar_similitud_supabase
                documentos = buscar_similitud_supabase(message)
                print(f"🔍 Resultados del RAG desde Supabase para '{message}':")
                for doc in documentos:
                    print(f"📄 Contenido: {doc.page_content[:200]}...\n")
            except Exception as e:
                # Si no se puede importar o falla, ignorar el log y continuar normalmente
                pass
            respuesta_rag = consulta_rag_vectorial(message)
            if respuesta_rag:
                print("🤖 RAG activado")
                return respuesta_rag
        except Exception as e:
            print(f"❌ Error consultando RAG: {e}")
    return None
import html
# from twilio.twiml.messaging_response import MessagingResponse  # No longer needed
import os
from dotenv import load_dotenv
import openai
import requests
from datetime import datetime, timedelta

# --- PARSER FECHA ISO ROBUSTO ---
def parse_fecha_iso(fecha_str):
    """Parse fecha ISO manejando diferentes formatos y timezones"""
    if not fecha_str:
        return datetime.min
    
    try:
        # Limpiar string de comillas extras
        fecha_limpia = str(fecha_str).strip().strip('"').strip("'")
        
        # Intentar parse directo
        fecha = datetime.fromisoformat(fecha_limpia)
        
        # Si tiene timezone, convertir a naive (UTC)
        if fecha.tzinfo is not None:
            fecha = fecha.replace(tzinfo=None)
        
        return fecha
        
    except ValueError:
        try:
            # Intentar truncar microsegundos y timezone
            if '.' in fecha_limpia:
                fecha_sin_micro = fecha_limpia.split('.')[0]
            else:
                fecha_sin_micro = fecha_limpia
                
            # Remover timezone info si existe
            if '+' in fecha_sin_micro:
                fecha_sin_micro = fecha_sin_micro.split('+')[0]
            elif fecha_sin_micro.endswith('Z'):
                fecha_sin_micro = fecha_sin_micro[:-1]
                
            return datetime.fromisoformat(fecha_sin_micro)
            
        except Exception as e:
            print(f"⚠️ Error parseando fecha '{fecha_str}': {e}")
            return datetime.min
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

# Función para enviar respuestas a WhatsApp Cloud API
def enviar_respuesta_whatsapp(numero, mensaje):
    try:
        token = os.getenv("WHATSAPP_TOKEN")
        phone_number_id = os.getenv("PHONE_NUMBER_ID")
        
        if not token or not phone_number_id:
            print("❌ Faltan variables de entorno para WhatsApp (WHATSAPP_TOKEN, PHONE_NUMBER_ID)")
            return False
            
        url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": mensaje}
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.ok:
            print(f"✅ Mensaje enviado a WhatsApp ({numero}): {response.status_code}")
            return True
        else:
            print(f"❌ Error enviando a WhatsApp: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout enviando mensaje a WhatsApp ({numero})")
        return False
    except Exception as e:
        print(f"❌ Error enviando mensaje a WhatsApp: {e}")
        return False


# Función utilitaria para enviar plantillas de WhatsApp Cloud API
def enviar_template_whatsapp(numero, template_name, parametros):
    """
    Envía un mensaje de plantilla (template) por WhatsApp Cloud API.

    :param numero: Número del cliente en formato internacional, ej. +5216612345678
    :param template_name: Nombre de la plantilla aprobada en WhatsApp
    :param parametros: Lista de strings con los parámetros dinámicos de la plantilla
    """
    try:
        token = os.getenv("WHATSAPP_TOKEN")
        phone_number_id = os.getenv("PHONE_NUMBER_ID")
        
        if not token or not phone_number_id:
            print("❌ Faltan variables de entorno para WhatsApp (WHATSAPP_TOKEN, PHONE_NUMBER_ID)")
            return False

        url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"

        components = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in parametros]
            }
        ]

        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "template",
            "template": {
                "name": template_name,
                "language": { "code": "es_MX" },
                "components": components
            }
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.ok:
            print(f"✅ Plantilla '{template_name}' enviada a WhatsApp ({numero})")
            return True
        else:
            print(f"❌ Error enviando plantilla: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout enviando plantilla a WhatsApp ({numero})")
        return False
    except Exception as e:
        print(f"❌ Error enviando plantilla a WhatsApp: {e}")
        return False



# Variables de entorno para Chatwoot
CHATWOOT_URL = os.getenv("CHATWOOT_BASE_URL", "https://crm.progreweb.com")
CHATWOOT_TOKEN = os.getenv("CHATWOOT_BOT_TOKEN")
CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID")

# Función para enviar mensajes a Chatwoot usando account_id y endpoint correcto
def enviar_respuesta_chatwoot(conversation_id, mensaje):
    if not CHATWOOT_URL or not CHATWOOT_TOKEN or not CHATWOOT_ACCOUNT_ID:
        print("❌ Faltan variables de entorno de Chatwoot.")
        return False

    try:
        url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages"

        headers = {
            "Content-Type": "application/json",
            "api_access_token": CHATWOOT_TOKEN,
        }

        payload = {
            "content": mensaje,
            "message_type": "outgoing",
        }

        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code == 200:
            print(f"✅ Mensaje enviado a Chatwoot (convo_id={conversation_id}): {response.status_code}")
            return True
        else:
            print(f"❌ Error enviando mensaje a Chatwoot: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout enviando mensaje a Chatwoot (convo_id={conversation_id})")
        return False
    except Exception as e:
        print(f"❌ Error enviando mensaje a Chatwoot: {e}")
        return False

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

def obtener_historial_conversacion_completo(telefono, limite_mensajes=50):
    """Obtiene historial completo EXTENDIDO con información enriquecida del lead"""
    historial_completo = []
    
    import time
    try:
        # 1. Obtener de la tabla antigua historial_conversaciones
        if supabase:
            for _ in range(3):
                try:
                    response_antiguo = supabase.table('historial_conversaciones').select('mensaje, respuesta, timestamp').eq('telefono', telefono).order('timestamp', desc=False).execute()
                    break
                except OSError as e:
                    if "temporarily unavailable" in str(e):
                        time.sleep(0.5)
                    else:
                        raise e
            else:
                response_antiguo = supabase.table('historial_conversaciones').select('mensaje, respuesta, timestamp').eq('telefono', telefono).order('timestamp', desc=False).execute()
            
            print(f"📚 Encontrados {len(response_antiguo.data)} registros en historial_conversaciones")
            
            for entrada in response_antiguo.data:
                historial_completo.append({
                    "role": "user", 
                    "content": entrada["mensaje"],
                    "timestamp": entrada.get("timestamp", ""),
                    "source": "historial_conversaciones"
                })
                historial_completo.append({
                    "role": "assistant", 
                    "content": entrada["respuesta"],
                    "timestamp": entrada.get("timestamp", ""),
                    "source": "historial_conversaciones"
                })
                
        # 2. Obtener de la nueva tabla interacciones_leads (más recientes)
        if supabase and TRACKING_AVAILABLE:
            for _ in range(3):
                try:
                    response_nuevo = supabase.table('interacciones_leads').select('tipo, descripcion, fecha').eq('telefono', telefono).order('fecha', desc=False).execute()
                    break
                except OSError as e:
                    if "temporarily unavailable" in str(e):
                        time.sleep(0.5)
                    else:
                        raise e
            else:
                response_nuevo = supabase.table('interacciones_leads').select('tipo, descripcion, fecha').eq('telefono', telefono).order('fecha', desc=False).execute()
            
            print(f"📚 Encontrados {len(response_nuevo.data)} registros en interacciones_leads")
            
            for interaccion in response_nuevo.data:
                if interaccion['tipo'] == 'mensaje_entrante':
                    descripcion = interaccion['descripcion']
                    if descripcion.startswith('Cliente: '):
                        mensaje = descripcion.replace('Cliente: ', '')
                        historial_completo.append({
                            "role": "user", 
                            "content": mensaje,
                            "timestamp": interaccion['fecha'],
                            "source": "interacciones_leads"
                        })
                elif interaccion['tipo'] == 'respuesta_bot':
                    descripcion = interaccion['descripcion']
                    if descripcion.startswith('Bot: '):
                        respuesta = descripcion.replace('Bot: ', '')
                        historial_completo.append({
                            "role": "assistant", 
                            "content": respuesta,
                            "timestamp": interaccion['fecha'],
                            "source": "interacciones_leads"
                        })
                        
        # 3. Ordenar por timestamp y retornar más mensajes (configurable)
        def fecha_key_robusta(x):
            """Función robusta para ordenar por fecha"""
            timestamp = x.get('timestamp', '')
            if not timestamp:
                return datetime.min
                
            # Usar la función mejorada de parse
            return parse_fecha_iso(timestamp)
                    
        try:
            historial_completo.sort(key=fecha_key_robusta)
        except Exception as e:
            print(f"⚠️ Error ordenando historial, usando orden original: {e}")
            # Si falla el ordenamiento, continuar sin ordenar
        
        # Retornar últimos mensajes según límite configurable
        print(f"🧠 Total mensajes encontrados: {len(historial_completo)}, retornando últimos {min(limite_mensajes, len(historial_completo))}")
        
        return historial_completo[-limite_mensajes:]
        
    except Exception as e:
        print(f"❌ Error obteniendo historial: {e}")
        import traceback
        traceback.print_exc()
        return []

def generar_resumen_inteligente_historial(historial, max_mensajes=30):
    """Genera un resumen inteligente cuando el historial es muy largo"""
    if len(historial) <= max_mensajes:
        return historial
    
    # Tomar los primeros 5 mensajes (inicio de conversación)
    inicio = historial[:5]
    
    # Tomar los últimos 20 mensajes (más recientes)
    recientes = historial[-20:]
    
    # Buscar mensajes clave en el medio (menciones de modelos, precios, citas)
    mensajes_clave = []
    for msg in historial[5:-20]:
        contenido = msg['content'].lower()
        es_clave = any([
            'sentra' in contenido, 'versa' in contenido, 'kicks' in contenido,
            'precio' in contenido, 'cotiz' in contenido, 'cita' in contenido,
            '$' in contenido, 'enganche' in contenido, 'financ' in contenido,
            'agendar' in contenido, 'llamar' in contenido
        ])
        if es_clave:
            mensajes_clave.append(msg)
    
    # Limitar mensajes clave a máximo 5
    mensajes_clave = mensajes_clave[:5]
    
    # Combinar inicio + clave + recientes
    historial_resumido = inicio + mensajes_clave + recientes
    
    # Eliminar duplicados manteniendo orden
    seen = set()
    historial_final = []
    for msg in historial_resumido:
        key = f"{msg['role']}_{msg['content'][:50]}"
        if key not in seen:
            seen.add(key)
            historial_final.append(msg)
    
    print(f"🧠 Historial resumido: {len(historial)} → {len(historial_final)} mensajes")
    return historial_final

def extraer_info_relevante_historial(historial):
    """Extrae información clave del historial para contexto resumido MEJORADO"""
    info_relevante = {
        'modelos_mencionados': set(),
        'montos_enganche': [],
        'citas_previas': False,
        'cotizaciones_previas': False,
        'ultimo_tema': None,
        'sentimientos_positivos': 0,
        'sentimientos_negativos': 0,
        'interes_urgencia': False
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
            
        # NUEVO: Detectar sentimientos y urgencia
        if any(palabra in contenido for palabra in ['excelente', 'perfecto', 'genial', 'me gusta', 'me encanta']):
            info_relevante['sentimientos_positivos'] += 1
        if any(palabra in contenido for palabra in ['caro', 'no me gusta', 'problema', 'mal', 'difícil']):
            info_relevante['sentimientos_negativos'] += 1
        if any(palabra in contenido for palabra in ['urgente', 'ya', 'pronto', 'inmediato', 'necesito ya']):
            info_relevante['interes_urgencia'] = True
    
    if historial:
        info_relevante['ultimo_tema'] = historial[-1]['content'][:100]  # Aumentado a 100 chars
    
    return info_relevante

def construir_contexto_conversacion_mejorado(telefono, mensaje_actual):
    """Construye contexto enriquecido MEJORADO con información del lead y resumen inteligente del historial"""
    try:
        # Obtener historial completo (ahora con hasta 50 mensajes)
        historial_completo = obtener_historial_conversacion_completo(telefono, limite_mensajes=50)
        
        # Aplicar resumen inteligente si es muy largo
        historial = generar_resumen_inteligente_historial(historial_completo, max_mensajes=30)
        
        # Extraer información relevante del historial completo
        info_historial = extraer_info_relevante_historial(historial_completo)
        
        # NUEVO: Detectar si es cliente conocido (tiene historial previo)
        es_cliente_conocido = len(historial_completo) > 0
        print(f"🔍 Cliente {telefono}: {'CONOCIDO' if es_cliente_conocido else 'NUEVO'} ({len(historial_completo)} mensajes)")
        
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
        
        # MEJORADO: Contexto más rico del historial
        if es_cliente_conocido:
            # Cliente conocido - agregar contexto de continuidad
            contexto_historial = f"\n\n💬 CLIENTE CONOCIDO - CONTINUAR CONVERSACIÓN:\n"
            contexto_historial += f"- Ya hemos hablado antes ({len(historial_completo)} mensajes previos)\n"
            contexto_historial += f"- NO saludar como si fuera primera vez\n"
            contexto_historial += f"- Retomar conversación de manera natural\n"
            contexto_historial += f"- Recordar información previa compartida\n"
            
        if (info_historial['modelos_mencionados'] or info_historial['citas_previas'] or 
            info_historial['sentimientos_positivos'] > 0 or info_historial['interes_urgencia']):
            
            if not es_cliente_conocido:
                contexto_historial = f"\n\n💬 HISTORIAL RELEVANTE EXTENDIDO:\n"
            
            if info_historial['modelos_mencionados']:
                contexto_historial += f"- Modelos discutidos: {', '.join(info_historial['modelos_mencionados'])}\n"
            
            if info_historial['citas_previas']:
                contexto_historial += f"- Ha mostrado interés en agendar cita\n"
            
            if info_historial['cotizaciones_previas']:
                contexto_historial += f"- Ha solicitado cotizaciones\n"
            
            if info_historial['montos_enganche']:
                contexto_historial += f"- Montos mencionados: {', '.join(info_historial['montos_enganche'][:3])}\n"
                
            # NUEVO: Información de sentimientos y urgencia
            if info_historial['sentimientos_positivos'] > 0:
                contexto_historial += f"- Sentimientos positivos detectados: {info_historial['sentimientos_positivos']} veces\n"
            
            if info_historial['sentimientos_negativos'] > 0:
                contexto_historial += f"- Preocupaciones detectadas: {info_historial['sentimientos_negativos']} veces\n"
                
            if info_historial['interes_urgencia']:
                contexto_historial += f"- URGENCIA: Cliente necesita solución pronto\n"
                
            if info_historial['ultimo_tema']:
                contexto_historial += f"- Último tema: {info_historial['ultimo_tema']}\n"
            
            contexto_historial += f"- Total mensajes en memoria: {len(historial_completo)}\n"
            
            prompt_sistema += contexto_historial
        
        messages.append({"role": "system", "content": prompt_sistema})
        
        # MEJORADO: Usar más mensajes del historial para mejor contexto
        # Usar últimos 15 mensajes (en lugar de 6) para mejor memoria
        historial_para_contexto = historial[-15:] if len(historial) > 15 else historial
        
        print(f"🧠 Usando {len(historial_para_contexto)} mensajes del historial para contexto")
        
        for entrada in historial_para_contexto:
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
            import time
            for _ in range(3):
                try:
                    supabase.table('historial_conversaciones').insert({
                        'telefono': telefono,
                        'mensaje': mensaje,
                        'respuesta': respuesta,
                        'timestamp': datetime.now().isoformat()
                    }).execute()
                    break
                except OSError as e:
                    if "temporarily unavailable" in str(e):
                        time.sleep(0.5)
                    else:
                        print(f"⚠️ Error guardando historial: {e}")
                        break
            else:
                print(f"⚠️ Error guardando historial después de reintentos.")
        
        return respuesta
        
    except Exception as e:
        print(f"❌ Error generando respuesta inteligente: {e}")
        return "¡Ups! 😁 Se me fue la onda... ¿Me repites qué necesitas?"

def generar_respuesta_openai(mensaje, lead_info, telefono=None):
    """Genera respuesta usando OpenAI - SIEMPRE con memoria mejorada"""
    
    if telefono:
        print(f"🧠 Usando memoria mejorada para: {telefono}")
        return generar_respuesta_con_contexto_inteligente(mensaje, telefono, lead_info, None)
    
    # NUEVO: Si no hay teléfono pero hay lead_info básico, extraer teléfono
    if isinstance(lead_info, dict) and 'telefono' in lead_info:
        telefono_extraido = lead_info['telefono']
        print(f"🔍 Teléfono extraído del lead básico: {telefono_extraido}")
        return generar_respuesta_con_contexto_inteligente(mensaje, telefono_extraido, lead_info, None)
    
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
        return f"Disculpa, tuve un problema técnico. ¿Puedes repetir tu mensaje?"

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

        # Primer contacto - MEJORADO para detectar clientes conocidos
        if lead.estado == EstadoLead.CONTACTO_INICIAL:
            # Verificar si ya tiene historial previo
            historial_existente = obtener_historial_conversacion_completo(lead.telefono, limite_mensajes=5)
            tiene_historial = len(historial_existente) > 0
            
            if any(word in mensaje_lower for word in ['hola', 'info', 'informacion', 'precio', 'cotizar']):
                if tiene_historial:
                    # Cliente conocido - respuesta de retomar conversación
                    return {
                        'accion': 'retomar_conversacion',
                        'nuevo_estado': EstadoLead.CALIFICANDO,
                        'mensaje': f"Hola {lead.nombre}, ¿cómo está todo? Retomando nuestra conversación sobre los vehículos Nissan, ¿en qué más puedo apoyarlo?"
                    }
                else:
                    # Cliente nuevo - saludo formal
                    return {
                        'accion': 'solicitar_uso_vehiculo',
                        'nuevo_estado': EstadoLead.CALIFICANDO,
                        'mensaje': f"Buenos días {lead.nombre}, soy César Arias, asesor de ventas de Nissan. ¿Para qué uso principal destinará la unidad? ¿Personal, trabajo o comercial?"
                    }

        # Proceso de calificación
        elif lead.estado == EstadoLead.CALIFICANDO:
            if not info.uso_vehiculo:
                if any(word in mensaje_lower for word in ['particular', 'personal', 'familia']):
                    return {
                        'accion': 'solicitar_comprobacion_ingresos',
                        'mensaje': f"Perfecto {lead.nombre}. ¿De qué forma comprueba sus ingresos? ¿Nómina, honorarios o negocio propio?"
                    }
                elif any(word in mensaje_lower for word in ['trabajo', 'uber', 'didi', 'taxi', 'negocio']):
                    return {
                        'accion': 'solicitar_comprobacion_ingresos',
                        'mensaje': f"Entiendo {lead.nombre}. ¿Requiere el vehículo para generar ingresos? ¿Trabaja de manera formal o maneja ingresos informales?"
                    }
                else:
                    return {
                        'accion': 'solicitar_uso_vehiculo',
                        'mensaje': f"¿Para qué uso principal destinará la unidad, {lead.nombre}? ¿Personal, trabajo o comercial?"
                    }
            elif not info.comprobacion_ingresos:
                if any(word in mensaje_lower for word in ['nomina', 'nómina', 'formal', 'empresa', 'recibo']):
                    return {
                        'accion': 'solicitar_enganche',
                        'mensaje': f"Excelente {lead.nombre}, eso facilita el proceso. ¿Cuenta con enganche para la compra? ¿De qué monto dispone?"
                    }
                elif any(word in mensaje_lower for word in ['informal', 'negocio', 'propio', 'independiente']):
                    return {
                        'accion': 'solicitar_enganche',
                        'mensaje': f"Entiendo {lead.nombre}. Tenemos planes especiales para casos sin comprobar ingresos. ¿Ha contemplado cuánto podría aportar como enganche inicial?"
                    }
                else:
                    return {
                        'accion': 'solicitar_comprobacion_ingresos',
                        'mensaje': f"¿De qué forma comprueba sus ingresos actualmente, {lead.nombre}? ¿Nómina, honorarios o negocio propio?"
                    }
            elif not info.monto_enganche:
                numeros = re.findall(r'\d+', mensaje)
                if numeros:
                    return {
                        'accion': 'solicitar_buro',
                        'mensaje': f"Perfecto {lead.nombre}. ¿Cómo se encuentra actualmente en buró de crédito? ¿Ha tenido algún inconveniente con créditos anteriores?"
                    }
                else:
                    return {
                        'accion': 'solicitar_enganche',
                        'mensaje': f"Nuestros planes van desde $15,000 de enganche, ¿se encuentra en ese rango, {lead.nombre}?"
                    }
            elif not info.historial_credito:
                if any(word in mensaje_lower for word in ['bueno', 'bien', 'excelente', 'limpio']):
                    return {
                        'accion': 'finalizar_calificacion',
                        'nuevo_estado': EstadoLead.CALIFICADO,
                        'mensaje': f"Excelente {lead.nombre}. Con su perfil crediticio tenemos las mejores opciones de financiamiento. ¿Le interesaría agendar una cita para revisar los planes disponibles?"
                    }
                elif any(word in mensaje_lower for word in ['malo', 'mal', 'problemas', 'buro', 'buró']):
                    return {
                        'accion': 'finalizar_calificacion',
                        'nuevo_estado': EstadoLead.CALIFICADO,
                        'mensaje': f"Entiendo {lead.nombre}. Tenemos el plan Sí Fácil especialmente diseñado para estos casos. ¿Prefiere que lo contacte telefónicamente para explicarle detalladamente este programa?"
                    }
                elif any(word in mensaje_lower for word in ['regular', 'mas o menos', 'normal']):
                    return {
                        'accion': 'finalizar_calificacion',
                        'nuevo_estado': EstadoLead.CALIFICADO,
                        'mensaje': f"Perfecto {lead.nombre}, tenemos diversas opciones que se adaptan a su situación. ¿Cuándo sería conveniente contactarlo para explicarle los planes disponibles?"
                    }
                else:
                    return {
                        'accion': 'solicitar_buro',
                        'mensaje': f"¿Considera que su historial crediticio está en buenas condiciones, {lead.nombre}?"
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
        # MEJORADO: Verificar si ya existe historial en Supabase
        historial_existente = obtener_historial_conversacion_completo(telefono, limite_mensajes=10)
        tiene_historial_previo = len(historial_existente) > 0
        
        if telefono not in self.leads_basicos:
            self.leads_basicos[telefono] = {
                'nombre': nombre_perfil,
                'telefono': telefono,
                'mensajes': [],
                'info': {},
                'fecha_creacion': datetime.now(),
                'tiene_historial_previo': tiene_historial_previo  # NUEVO
            }
        
        lead_basico = self.leads_basicos[telefono]
        lead_basico['mensajes'].append({
            'mensaje': mensaje,
            'fecha': datetime.now(),
            'tipo': 'entrante'
        })
        
        # Actualizar información de historial
        lead_basico['tiene_historial_previo'] = tiene_historial_previo
        
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
        
        # MEJORADO: Detectar si es cliente conocido
        es_primer_mensaje_sesion = len(lead['mensajes']) == 1
        tiene_historial_previo = lead.get('tiene_historial_previo', False)
        
        print(f"🔍 {nombre}: primer_mensaje={es_primer_mensaje_sesion}, historial_previo={tiene_historial_previo}")

        if es_primer_mensaje_sesion and not tiene_historial_previo:
            # Cliente completamente nuevo
            return {
                'mensaje': f"Buenos días {nombre}, soy César Arias, asesor de ventas de Nissan. ¿Para qué uso principal destinará la unidad? ¿Personal, trabajo o comercial?"
            }
        elif es_primer_mensaje_sesion and tiene_historial_previo:
            # Cliente conocido - retomar conversación
            return {
                'mensaje': f"Hola {nombre}, ¿cómo está todo? Retomando nuestra conversación sobre los vehículos Nissan, ¿en qué más puedo apoyarlo?"
            }

        if 'uso_vehiculo' not in info:
            return {
                'mensaje': f"Perfecto {nombre}. ¿De qué forma comprueba sus ingresos? ¿Nómina, honorarios o negocio propio?"
            }
        elif 'comprobacion_ingresos' not in info:
            return {
                'mensaje': f"Entiendo. ¿Cuenta con enganche para la compra? ¿De qué monto dispone?"
            }
        elif 'monto_enganche' not in info:
            return {
                'mensaje': f"¿Cómo se encuentra actualmente en buró de crédito, {nombre}?"
            }
        elif 'monto_enganche' in info and info['monto_enganche'] < 15000:
            return {
                'mensaje': f"Entiendo {nombre}. Nuestros planes van desde $15,000 de enganche. ¿Se encuentra en ese rango o prefiere conocer otras opciones de financiamiento?"
            }
        elif 'historial_credito' not in info:
            return {
                'mensaje': f"Excelente {nombre}. Con esta información puedo ofrecerle las mejores opciones. ¿Le interesaría agendar una cita para revisar los planes disponibles o prefiere que lo contacte telefónicamente?"
            }

        if any(word in mensaje_lower for word in ['si', 'claro', 'llamame', 'telefono', 'llamar']):
            return {
                'mensaje': f"Perfecto {nombre}. Lo contactaré al 6644918078 para explicarle detalladamente las opciones que mejor se adapten a su perfil. ¿Cuál sería el mejor horario para contactarlo?"
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
        data = request.get_json()
        print("🔔 Webhook recibido:", data)

        # Obtener el tipo de evento
        event_type = data.get("event", "message_created")
        
        # =====================================================
        # MANEJAR DIFERENTES TIPOS DE EVENTOS
        # =====================================================
        
        if event_type == "conversation_created":
            # Nueva conversación iniciada
            return manejar_conversacion_creada(data)
            
        elif event_type == "conversation_status_changed":
            # Estado de conversación cambió (resuelto, cerrado, etc.)
            return manejar_cambio_estado_conversacion(data)
            
        elif event_type == "message_created":
            # Mensaje normal - lógica existente
            return manejar_mensaje_creado(data)
            
        else:
            print(f"⚠️ Evento no manejado: {event_type}")
            return jsonify({"status": "ok", "event": event_type})

    except Exception as e:
        print(f"❌ Error en webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def manejar_conversacion_creada(data):
    """Maneja cuando se crea una nueva conversación"""
    try:
        conversation = data.get("conversation", {})
        contact = conversation.get("contact_inbox", {})
        telefono = contact.get("source_id", "")
        nombre = data.get("sender", {}).get("name", "Nuevo Lead")
        
        if telefono and CONTACTOS_PROACTIVOS_AVAILABLE:
            # Programar seguimiento automático para nuevo lead
            contexto = f"Nuevo lead detectado automáticamente. Conversación iniciada desde {conversation.get('channel', 'WhatsApp')}."
            
            contactos_proactivos_service.programar_mensaje_diferido(
                telefono=telefono,
                nombre=nombre,
                contexto=contexto,
                horas_delay=48,  # Seguimiento en 2 días si no hay respuesta
                tipo_campana='seguimiento'
            )
            
            print(f"🆕 Nuevo lead detectado y seguimiento programado: {nombre} ({telefono})")
        
        return jsonify({"status": "ok", "action": "new_lead_detected"})
        
    except Exception as e:
        print(f"❌ Error manejando conversación creada: {e}")
        return jsonify({"error": str(e)}), 500

def manejar_cambio_estado_conversacion(data):
    """Maneja cuando cambia el estado de una conversación"""
    try:
        conversation = data.get("conversation", {})
        nuevo_estado = conversation.get("status", "")
        contact = conversation.get("contact_inbox", {})
        telefono = contact.get("source_id", "")
        nombre = data.get("sender", {}).get("name", "Cliente")
        
        if telefono and nuevo_estado in ["resolved", "snoozed"] and CONTACTOS_PROACTIVOS_AVAILABLE:
            # Conversación cerrada o pospuesta - programar reactivación
            
            if nuevo_estado == "resolved":
                # Conversación resuelta - seguimiento de satisfacción en 7 días
                contexto = f"Conversación resuelta. Seguimiento de satisfacción y posibles necesidades adicionales."
                delay_hours = 168  # 7 días
                tipo = 'reactivacion'
                
            elif nuevo_estado == "snoozed":
                # Conversación pospuesta - seguimiento más pronto
                contexto = f"Conversación pospuesta. Cliente puede necesitar seguimiento."
                delay_hours = 48  # 2 días
                tipo = 'seguimiento'
            
            contactos_proactivos_service.programar_mensaje_diferido(
                telefono=telefono,
                nombre=nombre,
                contexto=contexto,
                horas_delay=delay_hours,
                tipo_campana=tipo
            )
            
            print(f"🔄 Conversación {nuevo_estado} - seguimiento programado: {nombre} ({telefono})")
        
        return jsonify({"status": "ok", "action": "status_change_handled"})
        
    except Exception as e:
        print(f"❌ Error manejando cambio de estado: {e}")
        return jsonify({"error": str(e)}), 500

def manejar_mensaje_creado(data):
    """Maneja mensajes creados - lógica original"""
    try:
        # Limpiar mensajes antiguos periódicamente
        limpiar_mensajes_antiguos()

        # Validar si el mensaje viene de usuario real
        if not validar_origen_mensaje(data):
            return jsonify({"status": "Mensaje ignorado - origen bot"}), 200

        # Extraer información del mensaje
        incoming_msg = data.get("content", "").strip()
        telefono = data.get("conversation", {}).get("contact_inbox", {}).get("source_id", "")
        nombre_perfil = data.get("sender", {}).get("name", "desconocido")

        if not incoming_msg or not telefono:
            return jsonify({"status": "ok"})

        # Sistema robusto de deduplicación
        id_unico = generar_id_unico(data, telefono)
        tiempo_actual = time.time()
        
        if id_unico in mensajes_procesados:
            tiempo_previo = mensajes_procesados[id_unico]
            if tiempo_actual - tiempo_previo < 300:  # 5 minutos
                print(f"🔁 Mensaje {id_unico} ya fue procesado hace {tiempo_actual - tiempo_previo:.1f}s")
                return jsonify({"status": "Mensaje duplicado"}), 200
        
        mensajes_procesados[id_unico] = tiempo_actual

        print(f"📱 Procesando mensaje único de {telefono}: {incoming_msg}")

        # --- BLOQUE RAG: Siempre intentar responder con RAG primero ---
        respuesta_final = handle_message_with_rag(incoming_msg)
        if not respuesta_final:
            if TRACKING_AVAILABLE and lead_tracker:
                conversational_manager = ConversationalLeadManager(lead_tracker)
                lead, siguiente_paso = conversational_manager.procesar_mensaje_lead(telefono, incoming_msg, nombre_perfil)
                respuesta_final = generar_respuesta_con_contexto_inteligente(incoming_msg, telefono, lead, siguiente_paso)
                interaccion_bot = Interaccion(
                    telefono=telefono,
                    tipo=TipoInteraccion.RESPUESTA_BOT,
                    descripcion=f"Bot: {respuesta_final}",
                    fecha=datetime.now(),
                    usuario='bot'
                )
                lead_tracker.registrar_interaccion(interaccion_bot)
            else:
                lead_basico, siguiente_paso = lead_manager.procesar_mensaje_lead(telefono, incoming_msg, nombre_perfil)
                respuesta_final = generar_respuesta_openai(incoming_msg, lead_basico, telefono)

        print(f"🤖 Respuesta generada: {respuesta_final}")

        # INTEGRACIÓN AUTOMÁTICA DE SEGUIMIENTO PROACTIVO
        integrar_seguimiento_proactivo_automatico(telefono, nombre_perfil, incoming_msg, respuesta_final)

        # Determinar canal de respuesta para evitar bucles
        canal_respuesta = determinar_canal_respuesta(data)
        print(f"📡 Canal de respuesta: {canal_respuesta}")

        if canal_respuesta == "chatwoot":
            # Enviar solo a Chatwoot
            conversation_id = (
                data.get("conversation", {}).get("id")
                or data.get("meta", {}).get("conversation_id")
            )
            if conversation_id:
                enviar_respuesta_chatwoot(conversation_id, respuesta_final)
                print(f"📩 Respuesta enviada a Chatwoot (convo_id={conversation_id})")
            else:
                print("⚠️ No se encontró conversation_id para Chatwoot")
        else:
            # Enviar solo a WhatsApp Cloud API
            enviar_respuesta_whatsapp(telefono, respuesta_final)
            print(f"📤 Respuesta enviada a WhatsApp ({telefono})")

        return jsonify({"status": "ok", "canal": canal_respuesta, "id_unico": id_unico})

    except Exception as e:
        print(f"❌ Error procesando mensaje: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def integrar_seguimiento_proactivo_automatico(telefono, nombre_perfil, incoming_msg, respuesta_final):
    """
    Integra automáticamente el sistema de seguimiento proactivo
    basado en las respuestas del cliente
    """
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return
    
    try:
        mensaje_lower = incoming_msg.lower()
        
        # Detectar respuestas que indican que el cliente necesita seguimiento
        patterns_seguimiento = {
            'pensando': {
                'keywords': ['lo voy a pensar', 'pensarlo', 'después', 'más tarde', 'ahorita no', 'luego'],
                'delay_hours': 24,
                'tipo': 'seguimiento',
                'contexto_extra': 'Cliente que decidió pensarlo'
            },
            'precio_alto': {
                'keywords': ['caro', 'precio alto', 'muy caro', 'no puedo pagar', 'está salado'],
                'delay_hours': 72,  # 3 días
                'tipo': 'promocion',
                'contexto_extra': 'Objeción de precio detectada'
            },
            'sin_enganche': {
                'keywords': ['no tengo enganche', 'sin dinero', 'no tengo ahorros', 'no tengo para enganche'],
                'delay_hours': 168,  # 1 semana
                'tipo': 'seguimiento',
                'contexto_extra': 'Cliente sin enganche disponible'
            },
            'buro_malo': {
                'keywords': ['mal buró', 'buro malo', 'problemas crediticios', 'estoy en buró'],
                'delay_hours': 48,
                'tipo': 'seguimiento',
                'contexto_extra': 'Cliente con historial crediticio complicado - Plan Sí Fácil'
            },
            'comparando': {
                'keywords': ['voy a comparar', 'checar otras opciones', 'ver en otros lados', 'comparar precios'],
                'delay_hours': 48,
                'tipo': 'seguimiento',
                'contexto_extra': 'Cliente comparando opciones en competencia'
            },
            'sin_tiempo': {
                'keywords': ['no tengo tiempo', 'muy ocupado', 'después hablamos', 'estoy trabajando'],
                'delay_hours': 12,  # Seguimiento más pronto
                'tipo': 'seguimiento',
                'contexto_extra': 'Cliente ocupado, requiere seguimiento en mejor momento'
            },
            'necesita_pensar': {
                'keywords': ['necesito pensarlo', 'consultarlo', 'hablar con mi esposo', 'hablar con mi esposa'],
                'delay_hours': 48,
                'tipo': 'seguimiento',
                'contexto_extra': 'Cliente necesita consultar decisión'
            }
        }
        
        for categoria, config in patterns_seguimiento.items():
            if any(keyword in mensaje_lower for keyword in config['keywords']):
                
                # Crear contexto detallado
                contexto = f"{config['contexto_extra']}. "
                contexto += f"Último mensaje: '{incoming_msg}'. "
                contexto += f"Respuesta del bot: '{respuesta_final[:100]}...'"
                
                # Programar seguimiento automático
                exito = contactos_proactivos_service.programar_mensaje_diferido(
                    telefono=telefono,
                    nombre=nombre_perfil,
                    contexto=contexto,
                    horas_delay=config['delay_hours'],
                    tipo_campana=config['tipo']
                )
                
                if exito:
                    print(f"🎯 Seguimiento automático programado: {categoria} para {nombre_perfil} en {config['delay_hours']} horas")
                    
                    # Notificar al sistema (opcional)
                    if ADVANCED_FEATURES:
                        try:
                            from services.notification_system import notificar_evento
                            notificar_evento(
                                'seguimiento_programado',
                                f"Seguimiento automático programado para {nombre_perfil}",
                                {'categoria': categoria, 'delay_hours': config['delay_hours']}
                            )
                        except:
                            pass
                
                break  # Solo uno por mensaje
                
    except Exception as e:
        print(f"❌ Error integrando seguimiento proactivo: {e}")

# =====================================================
# FUNCIONES AUXILIARES PARA EVENTOS ESPECÍFICOS
# =====================================================

def detectar_lead_abandonado_automatico(telefono, conversation_data):
    """
    Detecta automáticamente leads que abandonaron la conversación
    basado en el comportamiento en la conversación
    """
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return False
    
    try:
        # Obtener información del lead si existe
        lead_info = None
        if TRACKING_AVAILABLE and lead_tracker:
            lead = lead_tracker.obtener_lead(telefono)
            if lead:
                lead_info = {
                    'nombre': lead.nombre,
                    'estado': lead.estado.value,
                    'modelo_interes': lead.info_prospecto.modelo_interes,
                    'temperatura': lead.temperatura.value
                }
        
        if not lead_info:
            return False
        
        # Solo para leads calientes o tibios que abandonan
        if lead_info['temperatura'] in ['caliente', 'tibio']:
            contexto = f"Lead {lead_info['temperatura']} abandonó conversación. "
            contexto += f"Estado actual: {lead_info['estado']}. "
            if lead_info['modelo_interes']:
                contexto += f"Interés en: {lead_info['modelo_interes']}. "
            contexto += "Requiere seguimiento urgente para no perder venta."
            
            # Programar seguimiento urgente
            delay_hours = 4 if lead_info['temperatura'] == 'caliente' else 12
            
            exito = contactos_proactivos_service.programar_mensaje_diferido(
                telefono=telefono,
                nombre=lead_info['nombre'],
                contexto=contexto,
                horas_delay=delay_hours,
                tipo_campana='seguimiento'
            )
            
            if exito:
                print(f"🚨 Lead {lead_info['temperatura']} abandonado - seguimiento urgente programado: {lead_info['nombre']}")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error detectando lead abandonado: {e}")
        return False

def programar_seguimiento_por_resolucion(telefono, nombre, tipo_resolucion):
    """
    Programa seguimiento específico según cómo se resolvió la conversación
    """
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return False
    
    try:
        # Diferentes estrategias según tipo de resolución
        if tipo_resolucion == "venta_cerrada":
            # Cliente compró - seguimiento de satisfacción
            contexto = "Venta cerrada exitosamente. Seguimiento de satisfacción y servicios post-venta."
            delay_hours = 168  # 1 semana
            tipo_campana = 'reactivacion'
            
        elif tipo_resolucion == "informacion_proporcionada":
            # Solo se dio información - seguimiento de decisión
            contexto = "Información proporcionada al cliente. Seguimiento para conocer decisión."
            delay_hours = 48  # 2 días
            tipo_campana = 'seguimiento'
            
        elif tipo_resolucion == "cotizacion_enviada":
            # Se envió cotización - seguimiento crítico
            contexto = "Cotización enviada al cliente. Seguimiento crítico para cierre de venta."
            delay_hours = 24  # 1 día
            tipo_campana = 'seguimiento'
            
        else:
            # Resolución general
            contexto = "Conversación resuelta. Seguimiento de cortesía y posibles necesidades adicionales."
            delay_hours = 72  # 3 días
            tipo_campana = 'reactivacion'
        
        return contactos_proactivos_service.programar_mensaje_diferido(
            telefono=telefono,
            nombre=nombre,
            contexto=contexto,
            horas_delay=delay_hours,
            tipo_campana=tipo_campana
        )
        
    except Exception as e:
        print(f"❌ Error programando seguimiento por resolución: {e}")
        return False

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
            <li><a href="/test_duplicacion">🔒 Probar sistema anti-duplicación</a></li>
            <li><a href="/test_prompt">🎯 Probar prompt profesional NUEVO</a></li>
            <li><a href="/test_memoria_corregida">🔧 Probar correcciones de memoria</a></li>
        </ul>
        
        <p><small>⏰ Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
    </body>
    </html>
    """

@app.route("/test_memoria_mejorada")
def test_memoria_mejorada():
    """Endpoint para probar la memoria SÚPER MEJORADA del bot"""
    test_telefono = "+5216641234567"  # Teléfono de prueba
    
    try:
        # Probar nueva funcionalidad de memoria extendida
        historial_completo = obtener_historial_conversacion_completo(test_telefono, limite_mensajes=50)
        historial_resumido = generar_resumen_inteligente_historial(historial_completo, max_mensajes=30)
        info_relevante = extraer_info_relevante_historial(historial_completo)
        
        # Simular construcción de contexto
        messages, lead_info = construir_contexto_conversacion_mejorado(test_telefono, "Test de memoria SÚPER mejorada")
        
        return f"""
        <html>
        <head>
            <title>Test Memoria SÚPER Mejorada</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .section {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .highlight {{ background: #e8f5e8; padding: 10px; border-radius: 5px; }}
                .new-feature {{ background: #e3f2fd; padding: 10px; border-radius: 5px; border-left: 5px solid #2196f3; }}
                .stats {{ background: #fff3e0; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
        <h1>🧠 Test de Memoria SÚPER MEJORADA del Bot</h1>
        
        <div class="new-feature">
            <h2>🚀 NUEVAS CARACTERÍSTICAS ACTIVADAS:</h2>
            <ul>
                <li>✅ Historial extendido hasta 50 mensajes (antes 20)</li>
                <li>✅ Resumen inteligente para conversaciones largas</li>
                <li>✅ Detección de sentimientos y urgencia</li>
                <li>✅ Contexto de 15 mensajes (antes 6)</li>
                <li>✅ Análisis de múltiples fuentes de datos</li>
            </ul>
        </div>
        
        <div class="stats">
            <h2>📊 Estadísticas de Memoria</h2>
            <p><strong>📞 Teléfono de prueba:</strong> {test_telefono}</p>
            <p><strong>📚 Mensajes totales encontrados:</strong> {len(historial_completo)}</p>
            <p><strong>🧠 Mensajes en resumen inteligente:</strong> {len(historial_resumido)}</p>
            <p><strong>💬 Mensajes usados en contexto:</strong> {len(messages) - 2} (sistema + actual)</p>
        </div>
        
        <div class="section">
            <h3>📋 Información Relevante EXTENDIDA:</h3>
            <p><strong>Modelos mencionados:</strong> {', '.join(info_relevante['modelos_mencionados']) if info_relevante['modelos_mencionados'] else 'Ninguno'}</p>
            <p><strong>Montos mencionados:</strong> {', '.join(info_relevante['montos_enganche'][:5]) if info_relevante['montos_enganche'] else 'Ninguno'}</p>
            <p><strong>Citas previas:</strong> {'✅ Sí' if info_relevante['citas_previas'] else '❌ No'}</p>
            <p><strong>Cotizaciones previas:</strong> {'✅ Sí' if info_relevante['cotizaciones_previas'] else '❌ No'}</p>
            <p><strong>🟢 Sentimientos positivos:</strong> {info_relevante['sentimientos_positivos']} veces</p>
            <p><strong>🔴 Sentimientos negativos:</strong> {info_relevante['sentimientos_negativos']} veces</p>
            <p><strong>⚡ Urgencia detectada:</strong> {'✅ Sí' if info_relevante['interes_urgencia'] else '❌ No'}</p>
            <p><strong>💭 Último tema:</strong> {info_relevante['ultimo_tema'] if info_relevante['ultimo_tema'] else 'N/A'}</p>
        </div>
        
        <div class="section">
            <h3>🤖 Información del Lead:</h3>
            {f"<p><strong>Nombre:</strong> {lead_info['nombre']}</p>" if lead_info and 'nombre' in lead_info else "<p>Sin información de lead disponible</p>"}
            {f"<p><strong>Estado:</strong> {lead_info['estado']}</p>" if lead_info and 'estado' in lead_info else ""}
            {f"<p><strong>Temperatura:</strong> {lead_info['temperatura']}</p>" if lead_info and 'temperatura' in lead_info else ""}
            {f"<p><strong>Score:</strong> {lead_info['score']:.1f}</p>" if lead_info and 'score' in lead_info else ""}
        </div>
        
        <div class="section">
            <h3>💬 Análisis del Contexto:</h3>
            <p><strong>Total mensajes en contexto:</strong> {len(messages)}</p>
            <p><strong>Tamaño del prompt del sistema:</strong> {len(messages[0]['content']) if messages else 0} caracteres</p>
            <p><strong>Fuentes de datos:</strong> historial_conversaciones + interacciones_leads</p>
        </div>
        
        <div class="highlight">
            <h3>🗨️ Muestra del historial (últimos 5):</h3>
        """
        + "".join([
            f"<p><strong>{'👤 Cliente' if msg['role'] == 'user' else '🤖 Bot'}:</strong> {msg['content'][:150]}...</p>"
            for msg in historial_completo[-5:]  # Últimos 5 mensajes
        ]) + f"""
        </div>
        
        <div class="new-feature">
            <h3>🔍 Comparativa de Memoria:</h3>
            <p><strong>Antes:</strong> 20 mensajes máximo, 6 en contexto</p>
            <p><strong>Ahora:</strong> {len(historial_completo)} mensajes encontrados, {len(historial_resumido)} en resumen, {len(messages)-2} en contexto</p>
            <p><strong>Mejora:</strong> {((len(historial_completo)/20) * 100):.0f}% más memoria</p>
        </div>
        
        <p><a href="/">🏠 Volver al inicio</a> | <a href="/test_memoria">📊 Comparar con memoria básica</a></p>
        </body>
        </html>
        """
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error probando memoria súper mejorada: {e}"

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

@app.route("/test_duplicacion")
def test_duplicacion():
    """Endpoint para probar el sistema anti-duplicación"""
    try:
        # Simular datos de webhook
        test_data = {
            "id": "test_msg_123",
            "content": "Hola, esto es una prueba",
            "sender": {"type": "contact", "name": "Usuario Test"},
            "conversation": {"id": "conv_123", "contact_inbox": {"source_id": "+5216641234567"}},
            "message_type": "incoming",
            "timestamp": int(time.time())
        }
        
        telefono = test_data["conversation"]["contact_inbox"]["source_id"]
        
        # Generar ID único
        id_unico_1 = generar_id_unico(test_data, telefono)
        time.sleep(1)  # Esperar un segundo
        id_unico_2 = generar_id_unico(test_data, telefono)
        
        # Validar origen
        origen_valido = validar_origen_mensaje(test_data)
        
        # Determinar canal
        canal = determinar_canal_respuesta(test_data)
        
        # Probar mensaje de bot (debe ser rechazado)
        test_bot_data = test_data.copy()
        test_bot_data["sender"]["type"] = "agent_bot"
        origen_bot = validar_origen_mensaje(test_bot_data)
        
        return f"""
        <html>
        <head><title>Test Anti-Duplicación</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .test {{ background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .success {{ background: #e8f5e8; color: #2e7d32; }}
            .error {{ background: #ffebee; color: #c62828; }}
        </style>
        </head>
        <body>
        <h1>🔒 Test Sistema Anti-Duplicación</h1>
        
        <div class="test">
            <h3>📋 Datos de prueba:</h3>
            <p><strong>Teléfono:</strong> {telefono}</p>
            <p><strong>Mensaje:</strong> {test_data['content']}</p>
            <p><strong>ID original:</strong> {test_data['id']}</p>
        </div>
        
        <div class="test {'success' if id_unico_1 != id_unico_2 else 'error'}">
            <h3>🆔 Generación de ID único:</h3>
            <p><strong>ID único 1:</strong> {id_unico_1}</p>
            <p><strong>ID único 2:</strong> {id_unico_2}</p>
            <p><strong>Son diferentes:</strong> {'✅ Sí (correcto)' if id_unico_1 != id_unico_2 else '❌ No (malo)'}</p>
        </div>
        
        <div class="test {'success' if origen_valido else 'error'}">
            <h3>👤 Validación de origen (usuario real):</h3>
            <p><strong>Origen válido:</strong> {'✅ Sí' if origen_valido else '❌ No'}</p>
            <p><strong>Tipo sender:</strong> {test_data['sender']['type']}</p>
        </div>
        
        <div class="test {'success' if not origen_bot else 'error'}">
            <h3>🤖 Validación de origen (bot):</h3>
            <p><strong>Bot rechazado:</strong> {'✅ Sí' if not origen_bot else '❌ No'}</p>
            <p><strong>Tipo sender:</strong> {test_bot_data['sender']['type']}</p>
        </div>
        
        <div class="test">
            <h3>📡 Determinación de canal:</h3>
            <p><strong>Canal detectado:</strong> {canal}</p>
            <p><strong>Tiene conversation_id:</strong> {'✅ Sí' if test_data.get('conversation', {}).get('id') else '❌ No'}</p>
        </div>
        
        <div class="test">
            <h3>📊 Estado actual del sistema:</h3>
            <p><strong>Mensajes en memoria:</strong> {len(mensajes_procesados)}</p>
            <p><strong>Último ID procesado:</strong> {list(mensajes_procesados.keys())[-1] if mensajes_procesados else 'Ninguno'}</p>
        </div>
        
        <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"❌ Error probando anti-duplicación: {e}"

@app.route("/test_prompt")
def test_prompt():
    """Endpoint para probar el nuevo prompt profesional"""
    try:
        # Obtener el prompt actual
        prompt_actual = obtener_prompt_sistema_mejorado()
        
        # Simular diferentes escenarios de conversación
        escenarios = [
            {
                "tipo": "Primer contacto",
                "mensaje": "Hola, me interesa información sobre los Nissan",
                "respuesta_esperada": "Buenos días, soy César Arias, asesor de ventas de Nissan..."
            },
            {
                "tipo": "Calificación de uso",
                "mensaje": "Es para uso personal",
                "respuesta_esperada": "¿De qué forma comprueba sus ingresos? ¿Nómina, honorarios o negocio propio?"
            },
            {
                "tipo": "Calificación financiera",
                "mensaje": "Tengo nómina formal",
                "respuesta_esperada": "¿Cuenta con enganche para la compra? ¿De qué monto dispone?"
            },
            {
                "tipo": "Enganche disponible",
                "mensaje": "Tengo $20,000",
                "respuesta_esperada": "¿Cómo se encuentra actualmente en buró de crédito?"
            },
            {
                "tipo": "Buen historial",
                "mensaje": "Mi historial está bien",
                "respuesta_esperada": "¿Le interesaría agendar una cita para revisar los planes disponibles?"
            }
        ]
        
        return f"""
        <html>
        <head>
            <title>Test Prompt Profesional</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .prompt-section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .scenario {{ background: #e3f2fd; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 5px solid #2196f3; }}
                .professional {{ background: #e8f5e8; padding: 10px; border-radius: 5px; }}
                .comparison {{ background: #fff3e0; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                pre {{ background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 12px; }}
            </style>
        </head>
        <body>
        <h1>🎯 Test del Nuevo Prompt Profesional</h1>
        
        <div class="professional">
            <h2>✅ TRANSFORMACIÓN COMPLETADA</h2>
            <p><strong>Antes:</strong> Casual, coloquial, emojis, "¿Qué onda?"</p>
            <p><strong>Ahora:</strong> Profesional, formal, consultivo, estructurado</p>
        </div>
        
        <div class="prompt-section">
            <h2>📋 Características del Nuevo Prompt</h2>
            <ul>
                <li>✅ <strong>Rol profesional:</strong> César Arias, asesor especializado con 5 años de experiencia</li>
                <li>✅ <strong>Personalidad consultiva:</strong> Formal pero cercano, experto en financiamiento</li>
                <li>✅ <strong>Proceso estructurado:</strong> 7 puntos de calificación estratégica</li>
                <li>✅ <strong>Preguntas específicas:</strong> Tipo de financiamiento, uso, enganche, buró, etc.</li>
                <li>✅ <strong>Lenguaje profesional:</strong> Sin jerga casual, directo y respetuoso</li>
                <li>✅ <strong>Cierre estratégico:</strong> Enfoque en agendar citas y llamadas</li>
            </ul>
        </div>
        
        <h2>🔄 Escenarios de Conversación Actualizados</h2>
        """
        
        for escenario in escenarios:
            return_html = f"""
            <div class="scenario">
                <h3>📞 {escenario['tipo']}</h3>
                <p><strong>Cliente dice:</strong> "{escenario['mensaje']}"</p>
                <p><strong>Respuesta profesional esperada:</strong> {escenario['respuesta_esperada']}</p>
            </div>
            """
        
        return_html += f"""
        
        <div class="comparison">
            <h2>🔄 Comparativa Antes vs Ahora</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #f5f5f5;">
                    <th style="padding: 10px; border: 1px solid #ddd;">Aspecto</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Antes (Casual)</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Ahora (Profesional)</th>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Saludo</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">"¡Qué onda! 😁 César por aquí..."</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">"Buenos días, soy César Arias, asesor de ventas de Nissan"</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Preguntas</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">"¿El auto lo necesitas para chambear?"</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">"¿Para qué uso principal destinará la unidad?"</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Financiamiento</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">"¿Cuánto tienes guardado?"</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">"¿Cuenta con enganche? ¿De qué monto dispone?"</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Cierre</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">"¿Te marco ahorita?"</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">"¿Le interesaría agendar una cita para revisar opciones?"</td>
                </tr>
            </table>
        </div>
        
        <div class="prompt-section">
            <h2>📝 Nuevo Prompt Completo</h2>
            <pre>{prompt_actual[:1000]}...</pre>
            <p><small>Tamaño total: {len(prompt_actual)} caracteres</small></p>
        </div>
        
        <div class="professional">
            <h2>🎯 Puntos Clave de Calificación</h2>
            <ol>
                <li><strong>Tipo de financiamiento</strong> - Tradicional vs Sí Fácil</li>
                <li><strong>Uso del vehículo</strong> - Personal, trabajo, comercial</li>
                <li><strong>Situación de enganche</strong> - Monto disponible</li>
                <li><strong>Historial crediticio</strong> - Estado de buró</li>
                <li><strong>Comprobación de ingresos</strong> - Formal vs informal</li>
                <li><strong>Urgencia y tiempo</strong> - Cuándo necesita el vehículo</li>
                <li><strong>Cierre y agenda</strong> - Cita o llamada telefónica</li>
            </ol>
        </div>
        
        <p><a href="/">🏠 Volver al inicio</a> | <a href="/test_memoria_mejorada">🧠 Probar memoria</a></p>
        </body>
        </html>
        """
        
        return return_html
        
    except Exception as e:
        return f"❌ Error probando prompt profesional: {e}"

@app.route("/test_memoria_corregida")
def test_memoria_corregida():
    """Endpoint para probar las correcciones de memoria"""
    try:
        test_telefono = "+5216641234567"
        
        # Simular diferentes escenarios
        escenarios = [
            {
                "tipo": "Cliente nuevo (sin historial)",
                "telefono": "+5216640000001",
                "descripcion": "Primera vez que contacta"
            },
            {
                "tipo": "Cliente conocido (con historial)",
                "telefono": test_telefono,
                "descripcion": "Ya tiene conversaciones previas"
            }
        ]
        
        resultados = []
        
        for escenario in escenarios:
            tel = escenario["telefono"]
            
            # Verificar historial
            historial = obtener_historial_conversacion_completo(tel, limite_mensajes=10)
            tiene_historial = len(historial) > 0
            
            # Simular procesamiento de lead básico
            if not TRACKING_AVAILABLE:
                simple_manager = SimpleLeadManager()
                lead_basico, paso = simple_manager.procesar_mensaje_lead(tel, "Hola, me interesa información", "Cliente Test")
                
                resultado = {
                    "telefono": tel,
                    "tipo": escenario["tipo"],
                    "historial_encontrado": len(historial),
                    "tiene_historial_previo": lead_basico.get('tiene_historial_previo', False),
                    "respuesta_esperada": paso.get('mensaje', 'Sin respuesta'),
                    "es_saludo_inicial": "Buenos días" in paso.get('mensaje', '') and "soy César Arias" in paso.get('mensaje', '')
                }
            else:
                # Sistema completo
                resultado = {
                    "telefono": tel,
                    "tipo": escenario["tipo"],
                    "historial_encontrado": len(historial),
                    "sistema": "Tracking completo disponible"
                }
            
            resultados.append(resultado)
        
        return f"""
        <html>
        <head>
            <title>Test Memoria Corregida</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .fix {{ background: #e8f5e8; padding: 15px; border-radius: 5px; border-left: 5px solid #4caf50; margin: 10px 0; }}
                .test {{ background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .success {{ background: #e8f5e8; color: #2e7d32; padding: 10px; border-radius: 5px; }}
                .warning {{ background: #fff3e0; color: #f57c00; padding: 10px; border-radius: 5px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
        <h1>🔧 Test de Correcciones de Memoria</h1>
        
        <div class="fix">
            <h2>✅ PROBLEMAS CORREGIDOS</h2>
            <ul>
                <li>✅ <strong>Detección de clientes conocidos:</strong> Ahora verifica historial en Supabase</li>
                <li>✅ <strong>Contexto de continuidad:</strong> Diferencia entre cliente nuevo vs conocido</li>
                <li>✅ <strong>Prompt mejorado:</strong> Instruye específicamente sobre NO saludar repetidamente</li>
                <li>✅ <strong>SimpleLeadManager:</strong> Actualizado para detectar historial previo</li>
                <li>✅ <strong>ConversationalLeadManager:</strong> Lógica mejorada de retomar conversación</li>
            </ul>
        </div>
        
        <h2>🧪 Resultados de Prueba</h2>
        <table>
            <tr>
                <th>Tipo de Cliente</th>
                <th>Teléfono</th>
                <th>Mensajes en Historial</th>
                <th>Historial Detectado</th>
                <th>Comportamiento Esperado</th>
                <th>¿Saludo Inicial?</th>
            </tr>
        """
        
        for resultado in resultados:
            saludo_inicial = resultado.get('es_saludo_inicial', False)
            es_correcto = (resultado['historial_encontrado'] == 0 and saludo_inicial) or (resultado['historial_encontrado'] > 0 and not saludo_inicial)
            
            return_html += f"""
            <tr>
                <td>{resultado['tipo']}</td>
                <td>{resultado['telefono']}</td>
                <td>{resultado['historial_encontrado']}</td>
                <td>{'✅ Sí' if resultado.get('tiene_historial_previo', False) else '❌ No'}</td>
                <td>{'Retomar conversación' if resultado['historial_encontrado'] > 0 else 'Saludo inicial'}</td>
                <td>{'❌ Sí (MALO)' if saludo_inicial and resultado['historial_encontrado'] > 0 else '✅ Apropiado'}</td>
            </tr>
            """
        
        return_html += f"""
        </table>
        
        <h2>📋 Lógica Implementada</h2>
        <div class="test">
            <h3>Para Cliente NUEVO (sin historial):</h3>
            <p><strong>Respuesta:</strong> "Buenos días [nombre], soy César Arias, asesor de ventas de Nissan..."</p>
        </div>
        
        <div class="test">
            <h3>Para Cliente CONOCIDO (con historial):</h3>
            <p><strong>Respuesta:</strong> "Hola [nombre], ¿cómo está todo? Retomando nuestra conversación..."</p>
        </div>
        
        <div class="fix">
            <h2>🎯 Cambios Técnicos Realizados</h2>
            <ol>
                <li><strong>construir_contexto_conversacion_mejorado()</strong> - Detecta clientes conocidos</li>
                <li><strong>SimpleLeadManager.procesar_mensaje_lead()</strong> - Verifica historial en Supabase</li>
                <li><strong>ConversationalLeadManager.determinar_siguiente_paso()</strong> - Lógica de retomar conversación</li>
                <li><strong>Prompt del sistema</strong> - Instrucciones específicas sobre continuidad</li>
                <li><strong>generar_respuesta_openai()</strong> - Extrae teléfono para usar memoria mejorada</li>
            </ol>
        </div>
        
        <div class="warning">
            <h2>⚠️ Para Probar Completamente</h2>
            <p>1. Envía un mensaje desde un número nuevo → Debe saludar formalmente</p>
            <p>2. Envía otro mensaje desde el mismo número → NO debe saludar de nuevo</p>
            <p>3. Verifica que recuerda la conversación anterior</p>
        </div>
        
        <p><a href="/">🏠 Volver al inicio</a> | <a href="/test_memoria_mejorada">🧠 Test memoria completa</a></p>
        </body>
        </html>
        """
        
        return return_html
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error probando correcciones de memoria: {e}"
    
@app.route("/contactos_proactivos")
def dashboard_contactos_proactivos():
    """Dashboard para gestionar contactos proactivos"""
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return "❌ Servicio de contactos proactivos no disponible"
    
    try:
        # Obtener contactos pendientes
        contactos_pendientes = contactos_proactivos_service.obtener_contactos_pendientes(limite=20)
        
        # Obtener estadísticas
        estadisticas = contactos_proactivos_service.obtener_estadisticas()
        
        html_response = f"""
        <html>
        <head>
            <title>Contactos Proactivos - Nissan Bot</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stats {{ display: flex; flex-wrap: wrap; gap: 15px; }}
                .stat {{ background: #e3f2fd; padding: 15px; border-radius: 5px; text-align: center; min-width: 120px; }}
                .stat h3 {{ margin: 0; color: #1976d2; }}
                .stat p {{ margin: 5px 0; font-size: 24px; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .prioridad-alta {{ background-color: #ffebee; }}
                .prioridad-media {{ background-color: #fff3e0; }}
                .prioridad-baja {{ background-color: #e8f5e8; }}
                .form-section {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .form-group {{ margin: 10px 0; }}
                .form-group label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                .form-group input, .form-group select, .form-group textarea {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }}
                .btn {{ background: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }}
                .btn:hover {{ background: #1565c0; }}
                .btn-success {{ background: #4caf50; }}
                .btn-warning {{ background: #ff9800; }}
            </style>
        </head>
        <body>
        <div class="container">
            <h1>🤖 Contactos Proactivos - Sistema de Seguimiento</h1>
            
            <div class="card">
                <h2>📊 Estadísticas Generales</h2>
                <div class="stats">
                    <div class="stat">
                        <h3>Total</h3>
                        <p>{estadisticas.get('total', 0)}</p>
                    </div>
                    <div class="stat">
                        <h3>Pendientes</h3>
                        <p>{estadisticas.get('pendientes', 0)}</p>
                    </div>
                    <div class="stat">
                        <h3>Enviados</h3>
                        <p>{estadisticas.get('enviados', 0)}</p>
                    </div>
                    <div class="stat">
                        <h3>Respondidos</h3>
                        <p>{estadisticas.get('respondidos', 0)}</p>
                    </div>
                    <div class="stat">
                        <h3>Errores</h3>
                        <p>{estadisticas.get('errores', 0)}</p>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>📋 Contactos Pendientes ({len(contactos_pendientes)})</h2>
                <div style="margin: 10px 0;">
                    <a href="/enviar_contactos_ahora" class="btn btn-success">🚀 Enviar Todos Ahora</a>
                    <a href="/test_contacto_proactivo" class="btn btn-warning">🧪 Enviar Prueba</a>
                </div>
                
                <table>
                    <tr>
                        <th>Prioridad</th>
                        <th>Nombre</th>
                        <th>Teléfono</th>
                        <th>Tipo</th>
                        <th>Plantilla</th>
                        <th>Contexto</th>
                        <th>Programado</th>
                        <th>Observaciones</th>
                    </tr>
        """
        
        for contacto in contactos_pendientes:
            prioridad = contacto.get('prioridad', 2)
            clase_prioridad = f"prioridad-{'alta' if prioridad == 1 else 'media' if prioridad == 2 else 'baja'}"
            
            # Extraer plantilla de observaciones si no está disponible la columna
            template_display = contacto.get('template_whatsapp', '')
            if not template_display and contacto.get('observaciones'):
                observaciones = contacto.get('observaciones', '')
                if 'Template:' in observaciones:
                    template_display = observaciones.split('Template:')[1].strip().split('|')[0].strip()
            
            if not template_display:
                template_display = 'Sin plantilla'
            
            html_response += f"""
            <tr class="{clase_prioridad}">
                <td>{'🔴 Alta' if prioridad == 1 else '🟡 Media' if prioridad == 2 else '🟢 Baja'}</td>
                <td>{contacto.get('nombre', '')}</td>
                <td>{contacto.get('telefono', '')}</td>
                <td>{contacto.get('tipo_campana', '')}</td>
                <td>{template_display}</td>
                <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">
                    {contacto.get('contexto', '')[:100]}...
                </td>
                <td>Ahora</td>
                <td>{contacto.get('observaciones', '') or ''}</td>
            </tr>
            """
        
        html_response += f"""
                </table>
            </div>
            
            <div class="card">
                <h2>➕ Agregar Nuevo Contacto Proactivo</h2>
                <form action="/agregar_contacto_proactivo" method="post" class="form-section">
                    <div class="form-group">
                        <label for="telefono">Teléfono (con +52):</label>
                        <input type="text" id="telefono" name="telefono" placeholder="+5216641234567" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="nombre">Nombre:</label>
                        <input type="text" id="nombre" name="nombre" placeholder="Juan Pérez" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="tipo_campana">Tipo de Campaña:</label>
                        <select id="tipo_campana" name="tipo_campana">
                            <option value="seguimiento">Seguimiento</option>
                            <option value="promocion">Promoción</option>
                            <option value="reactivacion">Reactivación</option>
                            <option value="prospecto_nuevo">Prospecto Nuevo</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="template_whatsapp">Plantilla de WhatsApp (requerida para primer contacto):</label>
                        <select id="template_whatsapp" name="template_whatsapp" required>
                            <option value="">Seleccione una plantilla</option>
                            <option value="saludo_lead">Saludo Lead - Primer contacto general</option>
                            <option value="recordatorio_cita">Recordatorio de Cita - Para citas agendadas</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="prioridad">Prioridad:</label>
                        <select id="prioridad" name="prioridad">
                            <option value="1">🔴 Alta (envía inmediatamente)</option>
                            <option value="2" selected>🟡 Media (envía en próximo ciclo)</option>
                            <option value="3">🟢 Baja (envía cuando sea conveniente)</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="contexto">Contexto (para que el bot entienda la situación):</label>
                        <textarea id="contexto" name="contexto" rows="3" placeholder="Ej: Cliente interesado en Sentra hace 1 semana, mencionó enganche de $20,000, trabaja en maquiladora, no ha respondido después de cotización..." required></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="mensaje_personalizado">Mensaje Personalizado (opcional):</label>
                        <textarea id="mensaje_personalizado" name="mensaje_personalizado" rows="2" placeholder="Deja vacío para que el bot genere el mensaje automáticamente basado en el contexto"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="observaciones">Observaciones:</label>
                        <input type="text" id="observaciones" name="observaciones" placeholder="Ej: Lead de Facebook Ads, cliente referido, etc.">
                    </div>
                    
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="activar_seguimiento" name="activar_seguimiento" value="1">
                            Activar seguimiento automático cada 20 horas (5 mensajes máximo)
                        </label>
                    </div>
                    
                    <button type="submit" class="btn">➕ Agregar Contacto</button>
                </form>
            </div>
            
            <div class="card">
                <h2>📈 Distribución por Tipo de Campaña</h2>
                <ul>
        """
        
        for tipo, cantidad in estadisticas.get('por_tipo', {}).items():
            html_response += f"<li><strong>{tipo.title()}:</strong> {cantidad} contactos</li>"
        
        html_response += """
                </ul>
            </div>
            
            <p><a href="/">🏠 Volver al inicio</a> | <a href="/contactos_proactivos">🔄 Actualizar</a></p>
        </div>
        </body>
        </html>
        """
        
        return html_response
        
    except Exception as e:
        return f"❌ Error cargando dashboard: {e}"
    
@app.route("/agregar_contacto_proactivo", methods=["POST"])
def agregar_contacto_proactivo():
    """Endpoint para agregar nuevo contacto proactivo"""
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return "❌ Servicio no disponible"
    
    try:
        # Obtener datos del formulario
        telefono = request.form.get('telefono', '').strip()
        nombre = request.form.get('nombre', '').strip()
        contexto = request.form.get('contexto', '').strip()
        tipo_campana = request.form.get('tipo_campana', 'seguimiento')
        prioridad = int(request.form.get('prioridad', 2))
        mensaje_personalizado = request.form.get('mensaje_personalizado', '').strip() or None
        observaciones = request.form.get('observaciones', '').strip() or None
        
        # Validaciones básicas
        if not telefono or not nombre or not contexto:
            return "❌ Faltan datos requeridos (teléfono, nombre, contexto)"
        
        if not telefono.startswith('+52'):
            telefono = '+52' + telefono.lstrip('+')
        
        # Agregar contacto
        exito = contactos_proactivos_service.agregar_contacto_proactivo(
            telefono=telefono,
            nombre=nombre,
            contexto=contexto,
            tipo_campana=tipo_campana,
            prioridad=prioridad,
            mensaje_personalizado=mensaje_personalizado,
            observaciones=observaciones
        )
        
        if exito:
            return f"""
            <html>
            <head><title>Contacto Agregado</title></head>
            <body style="font-family: Arial; margin: 20px;">
                <h1>✅ Contacto Agregado Exitosamente</h1>
                <p><strong>Nombre:</strong> {nombre}</p>
                <p><strong>Teléfono:</strong> {telefono}</p>
                <p><strong>Tipo:</strong> {tipo_campana}</p>
                <p><strong>Prioridad:</strong> {'🔴 Alta' if prioridad == 1 else '🟡 Media' if prioridad == 2 else '🟢 Baja'}</p>
                <p><strong>Contexto:</strong> {contexto[:200]}...</p>
                
                <p>El contacto será procesado automáticamente según su prioridad.</p>
                
                <p><a href="/contactos_proactivos">🔙 Volver al dashboard</a></p>
            </body>
            </html>
            """
        else:
            return "❌ Error agregando contacto"
        
    except Exception as e:
        return f"❌ Error: {e}"
    
@app.route("/enviar_contactos_ahora")
def enviar_contactos_ahora():
    """Endpoint para enviar todos los contactos pendientes inmediatamente"""
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return "❌ Servicio no disponible"
    
    try:
        # Obtener contactos antes del envío
        contactos_antes = contactos_proactivos_service.obtener_contactos_pendientes(limite=50)
        
        # Procesar contactos
        contactos_proactivos_service.procesar_contactos_pendientes()
        
        # Obtener contactos después del envío
        contactos_despues = contactos_proactivos_service.obtener_contactos_pendientes(limite=50)
        
        enviados = len(contactos_antes) - len(contactos_despues)
        
        return f"""
        <html>
        <head><title>Envío Masivo Completado</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .success {{ background: #e8f5e8; padding: 15px; border-radius: 5px; color: #2e7d32; }}
            .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        </style>
        </head>
        <body>
            <h1>🚀 Envío Masivo Completado</h1>
            
            <div class="success">
                <h2>✅ Resultados del Envío</h2>
                <p><strong>Contactos procesados:</strong> {enviados}</p>
                <p><strong>Contactos pendientes restantes:</strong> {len(contactos_despues)}</p>
                <p><strong>Tiempo de procesamiento:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="info">
                <h3>📋 Contactos Enviados:</h3>
                <ul>
        """
        
        # Mostrar contactos que fueron enviados
        return_html = ""
        contactos_enviados = [c for c in contactos_antes if c not in contactos_despues]
        for contacto in contactos_enviados[:10]:  # Mostrar máximo 10
            return_html += f"<li>{contacto.get('nombre')} ({contacto.get('telefono')}) - {contacto.get('tipo_campana')}</li>"
        
        if len(contactos_enviados) > 10:
            return_html += f"<li>... y {len(contactos_enviados) - 10} más</li>"
        
        return_html += """
                </ul>
            </div>
            
            <p><a href="/contactos_proactivos">🔙 Volver al dashboard</a></p>
        </body>
        </html>
        """
        
        return return_html
        
    except Exception as e:
        return f"❌ Error procesando contactos: {e}"
    
@app.route("/test_contacto_proactivo")
def test_contacto_proactivo():
    """Endpoint para probar el sistema con un contacto de prueba"""
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return "❌ Servicio no disponible"
    
    try:
        # Crear contacto de prueba
        telefono_test = "+526871006601"  # Número de prueba
        nombre_test = "Usuario Test"
        contexto_test = "Cliente de prueba para validar el sistema de contactos proactivos. Interesado en Sentra."
        
        # Agregar contacto de prueba
        exito = contactos_proactivos_service.agregar_contacto_proactivo(
            telefono=telefono_test,
            nombre=nombre_test,
            contexto=contexto_test,
            tipo_campana='seguimiento',
            prioridad=1,  # Alta prioridad para envío inmediato
            observaciones="Contacto de prueba del sistema"
        )
        
        if not exito:
            return "❌ Error creando contacto de prueba"
        
        # Generar mensaje de prueba
        contacto_test = {
            'telefono': telefono_test,
            'nombre': nombre_test,
            'contexto': contexto_test,
            'tipo_campana': 'seguimiento',
            'mensaje_personalizado': None
        }
        
        mensaje_generado = contactos_proactivos_service.generar_mensaje_personalizado(contacto_test)
        
        return f"""
        <html>
        <head><title>Test Contacto Proactivo</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .test-section {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .message-preview {{ background: #e3f2fd; padding: 15px; border-radius: 5px; border-left: 5px solid #2196f3; }}
        </style>
        </head>
        <body>
            <h1>🧪 Test del Sistema de Contactos Proactivos</h1>
            
            <div class="test-section">
                <h2>📋 Datos del Contacto de Prueba</h2>
                <p><strong>Nombre:</strong> {nombre_test}</p>
                <p><strong>Teléfono:</strong> {telefono_test}</p>
                <p><strong>Contexto:</strong> {contexto_test}</p>
                <p><strong>Tipo:</strong> Seguimiento</p>
                <p><strong>Prioridad:</strong> 🔴 Alta</p>
            </div>
            
            <div class="message-preview">
                <h3>💬 Mensaje Generado Automáticamente:</h3>
                <p><em>"{mensaje_generado}"</em></p>
            </div>
            
            <div class="test-section">
                <h3>🎯 Próximos Pasos:</h3>
                <ol>
                    <li>El contacto se agregó a la cola de envío</li>
                    <li>Será procesado automáticamente en el próximo ciclo</li>
                    <li>Puedes enviarlo inmediatamente usando "Enviar Todos Ahora"</li>
                    <li>El mensaje se adaptará al contexto proporcionado</li>
                </ol>
            </div>
            
            <div style="margin: 20px 0;">
                <a href="/enviar_contactos_ahora" style="background: #4caf50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">🚀 Enviar Ahora</a>
                <a href="/contactos_proactivos" style="background: #2196f3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-left: 10px;">📋 Ver Dashboard</a>
            </div>
            
            <p><strong>Nota:</strong> El número {telefono_test} es solo para pruebas. Cambia por un número real para envío efectivo.</p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"❌ Error en test: {e}"
    
@app.route("/estadisticas_proactivos")
def estadisticas_proactivos():
    """Endpoint con estadísticas detalladas del sistema proactivo"""
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return "❌ Servicio no disponible"
    
    try:
        estadisticas = contactos_proactivos_service.obtener_estadisticas()
        
        # Obtener historial reciente
        response = supabase.table('contactos_proactivos').select('*').order('created_at', desc=True).limit(20).execute()
        historial_reciente = response.data if response.data else []
        
        return f"""
        <html>
        <head>
            <title>Estadísticas Contactos Proactivos</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1000px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric {{ display: inline-block; background: #e3f2fd; margin: 10px; padding: 15px; border-radius: 5px; text-align: center; min-width: 120px; }}
                .metric h4 {{ margin: 0; color: #1976d2; }}
                .metric p {{ margin: 5px 0; font-size: 20px; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .estado-pendiente {{ background-color: #fff3e0; }}
                .estado-enviado {{ background-color: #e8f5e8; }}
                .estado-respondido {{ background-color: #e3f2fd; }}
                .estado-error {{ background-color: #ffebee; }}
            </style>
        </head>
        <body>
        <div class="container">
            <h1>📊 Estadísticas Detalladas - Contactos Proactivos</h1>
            
            <div class="card">
                <h2>📈 Métricas Generales</h2>
                <div class="metric">
                    <h4>Total Contactos</h4>
                    <p>{estadisticas.get('total', 0)}</p>
                </div>
                <div class="metric">
                    <h4>Pendientes</h4>
                    <p>{estadisticas.get('pendientes', 0)}</p>
                </div>
                <div class="metric">
                    <h4>Enviados</h4>
                    <p>{estadisticas.get('enviados', 0)}</p>
                </div>
                <div class="metric">
                    <h4>Respondidos</h4>
                    <p>{estadisticas.get('respondidos', 0)}</p>
                </div>
                <div class="metric">
                    <h4>Errores</h4>
                    <p>{estadisticas.get('errores', 0)}</p>
                </div>
            </div>
            
            <div class="card">
                <h2>🎯 Distribución por Tipo de Campaña</h2>
                <table>
                    <tr><th>Tipo</th><th>Cantidad</th><th>Porcentaje</th></tr>
        """
        
        total = estadisticas.get('total', 1)  # Evitar división por cero
        for tipo, cantidad in estadisticas.get('por_tipo', {}).items():
            porcentaje = (cantidad / total) * 100 if total > 0 else 0
            return_html += f"""
            <tr>
                <td>{tipo.replace('_', ' ').title()}</td>
                <td>{cantidad}</td>
                <td>{porcentaje:.1f}%</td>
            </tr>
            """
        
        # Calcular tasa de respuesta
        enviados = estadisticas.get('enviados', 0)
        respondidos = estadisticas.get('respondidos', 0)
        tasa_respuesta = (respondidos / enviados * 100) if enviados > 0 else 0
        
        return_html += f"""
                </table>
            </div>
            
            <div class="card">
                <h2>📊 Métricas de Rendimiento</h2>
                <p><strong>Tasa de Respuesta:</strong> {tasa_respuesta:.1f}% ({respondidos}/{enviados})</p>
                <p><strong>Tasa de Error:</strong> {(estadisticas.get('errores', 0) / total * 100):.1f}% si hay contactos</p>
                <p><strong>Eficiencia de Envío:</strong> {((enviados + respondidos) / total * 100):.1f}% si hay contactos</p>
            </div>
            
            <div class="card">
                <h2>📝 Historial Reciente (últimos 20)</h2>
                <table>
                    <tr>
                        <th>Fecha</th>
                        <th>Nombre</th>
                        <th>Teléfono</th>
                        <th>Tipo</th>
                        <th>Estado</th>
                        <th>Prioridad</th>
                    </tr>
        """
        
        for contacto in historial_reciente:
            estado = contacto.get('estado', 'pendiente')
            prioridad = contacto.get('prioridad', 2)
            fecha = contacto.get('created_at', '')[:10] if contacto.get('created_at') else ''
            
            return_html += f"""
            <tr class="estado-{estado}">
                <td>{fecha}</td>
                <td>{contacto.get('nombre', '')}</td>
                <td>{contacto.get('telefono', '')}</td>
                <td>{contacto.get('tipo_campana', '').replace('_', ' ').title()}</td>
                <td>{estado.title()}</td>
                <td>{'🔴' if prioridad == 1 else '🟡' if prioridad == 2 else '🟢'}</td>
            </tr>
            """
        
        return_html += """
                </table>
            </div>
            
            <p><a href="/contactos_proactivos">🔙 Dashboard Principal</a> | <a href="/">🏠 Inicio</a></p>
        </div>
        </body>
        </html>
        """
        
        return return_html
        
    except Exception as e:
        return f"❌ Error obteniendo estadísticas: {e}"

if __name__ == "__main__":
    print("🚀 Iniciando aplicación Flask...")
    print(f"📊 Tracking disponible: {TRACKING_AVAILABLE}")
    print(f"🤖 Seguimiento automático disponible: {SEGUIMIENTO_AVAILABLE}")
    print(f"🧠 RAG disponible: {RAG_AVAILABLE}")
    print(f"🧠 MEMORIA DE CONVERSACIÓN SÚPER MEJORADA: ✅ ACTIVADA")
    print("   • Historial extendido hasta 50 mensajes (antes 20)")
    print("   • Resumen inteligente para conversaciones largas")
    print("   • Contexto de 15 mensajes (antes 6)")
    print("   • Detección de sentimientos y urgencia")
    print("   • Análisis de modelos, montos y citas")
    print("   • Múltiples fuentes de datos (2 tablas)")
    print("   • Contexto enriquecido con información del lead")
    print("")
    print("🔒 SISTEMA ANTI-DUPLICACIÓN: ✅ ACTIVADO")
    print("   • Deduplicación robusta con timestamps")
    print("   • Validación de origen de mensajes")
    print("   • Envío único por canal (Chatwoot/WhatsApp)")
    print("   • Limpieza automática de mensajes antiguos")
    print("   • Timeouts y manejo mejorado de errores")
    
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
# =====================================================
# FUNCIONES PARA ENVIAR PLANTILLAS NUEVAS DE WHATSAPP
# =====================================================

def enviar_saludo_lead(telefono, nombre_cliente):
    """
    Envía la plantilla 'saludo_lead' al número indicado con el nombre del cliente.
    """
    return enviar_template_whatsapp(
        numero=telefono,
        template_name="saludo_lead",
        parametros=[nombre_cliente]
    )

def enviar_recordatorio_cita(telefono, nombre_cliente, fecha, hora, direccion):
    """
    Envía la plantilla 'recordatorio_cita' al número indicado con los parámetros requeridos.
    """
    return enviar_template_whatsapp(
        numero=telefono,
        template_name="recordatorio_cita",
        parametros=[nombre_cliente, fecha, hora, direccion]
    )

def enviar_reasignacion_cita(telefono, nombre_cliente, nueva_fecha, nueva_hora):
    """
    Envía la plantilla 'reasignacion_cita' al número indicado con los parámetros requeridos.
    """
    return enviar_template_whatsapp(
        numero=telefono,
        template_name="reasignacion_cita",
        parametros=[nombre_cliente, nueva_fecha, nueva_hora]
    )