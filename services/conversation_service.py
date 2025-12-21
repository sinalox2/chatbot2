# services/conversation_service.py
import os
import openai
from datetime import datetime
from typing import Dict, List, Optional
import sys
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from rag.buscador_supabase import recuperar_contexto
    from supabase_client import supabase
    from services.lead_tracking_service import LeadTrackingService
    from models.lead_tracking import EstadoLead, TemperaturaMercado
    from config import get_config
    from utils.logger import Logger
    RAG_AVAILABLE = True
except ImportError as e:
    RAG_AVAILABLE = False
    from utils.logger import Logger
    def recuperar_contexto(query, k=3):
        return "Sistema RAG no disponible."

class ConversationService:
    """Servicio para manejar conversaciones con IA usando OpenAI y RAG"""
    
    def __init__(self):
        self.client = None
        self.system_prompt = self._load_system_prompt()
        self.lead_service = LeadTrackingService() if 'LeadTrackingService' in globals() else None
        self.config = get_config()() if 'get_config' in globals() else None
        self._setup_openai()
        
    def _setup_openai(self):
        """Configura el cliente de OpenAI"""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            openai.api_key = api_key
            self.client = openai
        else:
            Logger.warning("OpenAI API key not found", "OPENAI")
    
    def _load_system_prompt(self) -> str:
        """Carga el prompt del sistema desde el archivo .md"""
        try:
            prompt_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompt_sistema_nissan.md')
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Si es un archivo markdown, extraer solo el contenido del prompt
                if 'return """' in content:
                    start = content.find('return """') + len('return """')
                    end = content.rfind('"""')
                    return content[start:end].strip()
                # Si es markdown puro, usar todo el contenido
                return content.strip()
        except Exception as e:
            Logger.error(f"Error cargando prompt desde archivo: {e}", "PROMPT")
            return "Eres César Arias, asesor de ventas de Nissan Tijuana. Responde de manera amigable y profesional."
    
    def get_conversation_history(self, telefono: str, limit: int = 6) -> List[Dict]:
        """
        Obtiene el historial de conversación de un cliente
        OPTIMIZADO: Limitado a últimos 6 mensajes (3 turnos completos) para mejor contexto
        """
        try:
            if not supabase:
                return []
            
            # Aumentado a 6 mensajes para mejor contexto conversacional
            limit = min(limit, 6)
            
            response = supabase.table('historial_conversaciones')\
                .select('*')\
                .eq('telefono', telefono)\
                .order('timestamp', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data or []
        except Exception as e:
            return []
    
    def save_conversation(self, telefono: str, mensaje_usuario: str, respuesta_bot: str):
        """Guarda la conversación en la base de datos"""
        try:
            if not supabase:
                return False
            
            supabase.table('historial_conversaciones').insert({
                'telefono': telefono,
                'mensaje': mensaje_usuario,
                'respuesta': respuesta_bot,
                'timestamp': datetime.now().isoformat()
            }).execute()
            
            return True
        except Exception as e:
            return False
    
    def get_or_create_lead(self, telefono: str, nombre: Optional[str] = None) -> Optional[Dict]:
        """Obtiene o crea un lead en el sistema de tracking"""
        try:
            if not self.lead_service:
                return None
            
            # First try to find existing lead
            lead = self.lead_service.obtener_lead(telefono)
            
            if not lead and nombre:
                # Create new lead if name is provided
                lead_data = {
                    'telefono': telefono,
                    'nombre': nombre,
                    'canal_origen': 'whatsapp',
                    'estado': EstadoLead.NUEVO.value,
                    'temperatura': TemperaturaMercado.FRIO.value,
                    'fecha_creacion': datetime.now(),
                    'ultimo_contacto': datetime.now()
                }
                
                lead_id = self.lead_service.crear_lead(lead_data)
                if lead_id:
                    lead = self.lead_service.obtener_lead(lead_id)
            
            return lead
        except Exception as e:
            return None
    
    def detect_image_request(self, mensaje: str) -> Dict:
        """Detecta si solicitan imágenes y de qué modelo"""
        mensaje_lower = mensaje.lower()
        
        # Palabras clave para solicitudes de imágenes
        image_keywords = [
            'foto', 'fotos', 'imagen', 'imagenes', 'picture', 'pic', 'pics',
            'se ve', 'como es', 'mostrar', 'muestra', 'enseña', 'ver',
            'aspecto', 'apariencia', 'colores', 'como se ve', 'que tal se ve'
        ]
        
        wants_image = any(keyword in mensaje_lower for keyword in image_keywords)
        
        if wants_image:
            # Detectar modelo específico
            modelos_config = {
                'sentra': ['sentra'],
                'versa': ['versa'], 
                'march': ['march'],
                'kicks': ['kicks', 'kick'],
                'v-drive': ['v-drive', 'v drive', 'vdrive'],
                'x-trail': ['x-trail', 'x trail', 'xtrail'],
                'pathfinder': ['pathfinder', 'path finder'],
                'frontier': ['frontier'],
                'np300': ['np300', 'np 300'],
                'magnite': ['magnite']
            }
            
            for modelo, variantes in modelos_config.items():
                for variante in variantes:
                    if variante in mensaje_lower:
                        # Determinar tipo de imagen solicitada
                        image_type = 'exterior'  # por defecto
                        if 'interior' in mensaje_lower or 'adentro' in mensaje_lower:
                            image_type = 'interior'
                        elif 'color' in mensaje_lower or 'colores' in mensaje_lower:
                            image_type = 'colores'
                        elif 'lateral' in mensaje_lower or 'lado' in mensaje_lower:
                            image_type = 'lateral'
                        
                        return {
                            'wants_image': True,
                            'modelo': modelo,
                            'image_type': image_type,
                            'image_path': f'images/{modelo}/{modelo}-{image_type}.jpg'
                        }
            
            # Si quiere imagen pero no especifica modelo
            return {
                'wants_image': True,
                'modelo': None,
                'needs_clarification': True
            }
        
        return {'wants_image': False}
    
    def analyze_message_intent(self, mensaje: str) -> Dict:
        """Analiza la intención del mensaje del usuario"""
        mensaje_lower = mensaje.lower()
        
        intent_info = {
            'intent': 'general',
            'entities': {},
            'urgency': 'normal',
            'conversation_step': 'initial'
        }
        
        # Detect greeting
        if any(word in mensaje_lower for word in ['hola', 'buenos', 'buenas', 'saludos', 'qué tal']):
            intent_info['intent'] = 'greeting'
        
        # Detect interest in specific car models
        modelos = ['sentra', 'versa', 'march', 'kicks', 'x-trail', 'pathfinder', 'frontier', 'np300']
        for modelo in modelos:
            if modelo in mensaje_lower:
                intent_info['entities']['modelo_interes'] = modelo
                intent_info['intent'] = 'product_inquiry'
        
        # Detect financing interest
        if any(word in mensaje_lower for word in ['crédito', 'financiamiento', 'enganche', 'mensualidad', 'pago']):
            intent_info['intent'] = 'financing_inquiry'
        
        # Detect price inquiry
        if any(word in mensaje_lower for word in ['precio', 'costo', 'vale', 'cuesta', 'cuánto']):
            intent_info['intent'] = 'price_inquiry'
        
        # Detect appointment request
        if any(word in mensaje_lower for word in ['cita', 'visita', 'ir', 'ver', 'agendar', 'cuando']):
            intent_info['intent'] = 'appointment_request'
        
        # Detect urgency
        if any(word in mensaje_lower for word in ['urgente', 'rápido', 'pronto', 'ya', 'hoy']):
            intent_info['urgency'] = 'high'
        
        # Detect financing conversation steps
        if intent_info['intent'] == 'financing_inquiry':
            intent_info.update(self._analyze_financing_step(mensaje_lower))
        
        return intent_info
    
    def _analyze_financing_step(self, mensaje_lower: str) -> Dict:
        """Analiza en qué paso de la conversación de financiamiento estamos"""
        step_info = {'conversation_step': 'initial'}
        
        # Detectar respuestas a preguntas de calificación
        if any(word in mensaje_lower for word in ['personal', 'particular', 'familia', 'uso personal']):
            step_info['conversation_step'] = 'uso_personal'
            step_info['uso_vehiculo'] = 'personal'
        
        elif any(word in mensaje_lower for word in ['trabajo', 'uber', 'comercial', 'negocio', 'taxi', 'app']):
            step_info['conversation_step'] = 'uso_comercial' 
            step_info['uso_vehiculo'] = 'comercial'
        
        elif any(word in mensaje_lower for word in ['transporte', 'urvan', 'publico', 'pasajeros']):
            step_info['conversation_step'] = 'uso_urvan'
            step_info['uso_vehiculo'] = 'urvan'
        
        # Detectar información sobre enganche
        if any(word in mensaje_lower for word in ['sin enganche', 'no tengo', 'no cuento', 'poco dinero']):
            step_info['tiene_enganche'] = False
            
        elif any(word in mensaje_lower for word in ['si tengo', 'si cuento', 'tengo', 'disponible']):
            step_info['tiene_enganche'] = True
            
        # Detectar solicitud de cita
        if any(word in mensaje_lower for word in ['cita', 'visita', 'ir', 'agencia', 'oficina']):
            step_info['conversation_step'] = 'solicita_cita'
        
        return step_info
    
    def get_temperature_for_intent(self, intent_info: Dict, urgency: str = 'normal') -> float:
        """Selecciona la temperatura óptima según el contexto de la conversación"""
        try:
            if not self.config:
                return 0.4  # Default fallback
            
            intent = intent_info.get('intent', 'general')
            
            # Temperaturas específicas por tipo de intención
            if intent == 'price_inquiry':
                # Consultas de precios requieren máxima precisión
                return self.config.TEMPERATURE_PRECISE  # 0.2
            
            elif intent == 'financing_inquiry':
                # Consultas de financiamiento: precisas pero conversacionales
                return self.config.TEMPERATURE_FINANCING  # 0.3
            
            elif intent == 'greeting':
                # Saludos pueden ser más naturales y variados
                return self.config.TEMPERATURE_GREETING  # 0.6
                
            elif intent in ['appointment_request', 'product_inquiry']:
                # Consultas de productos y citas: balanceado pero preciso
                return self.config.TEMPERATURE_DEFAULT  # 0.4
                
            elif urgency == 'high':
                # Situaciones urgentes requieren respuestas más directas
                return self.config.TEMPERATURE_PRECISE  # 0.2
                
            else:
                # Conversación general
                return self.config.TEMPERATURE_DEFAULT  # 0.4
                
        except Exception as e:
            Logger.warning(f"Error obteniendo temperatura: {e}", "CONFIG")
            return 0.4  # Safe default
    
    def generate_response(self, telefono: str, mensaje_usuario: str, nombre_usuario: Optional[str] = None) -> str:
        """Genera una respuesta usando OpenAI y el contexto RAG"""
        try:
            if not self.client:
                return "Disculpa, tengo problemas técnicos. ¿Puedes intentar más tarde? 😅"
            
            # Get conversation history (limitado a 3 turnos = 6 mensajes)
            historial = self.get_conversation_history(telefono, limit=6)
            
            # Get or create lead
            lead = self.get_or_create_lead(telefono, nombre_usuario)
            
            # Analyze message intent
            intent_info = self.analyze_message_intent(mensaje_usuario)
            
            # Detect image requests
            image_request = self.detect_image_request(mensaje_usuario)
            
            # Get relevant context from RAG if available (limitado a 2 chunks)
            contexto_rag = ""
            usa_rag = False
            if RAG_AVAILABLE:
                try:
                    contexto_rag = recuperar_contexto(mensaje_usuario, k=2)  # Máximo 2 chunks
                    if contexto_rag and "No se encontró" not in contexto_rag:
                        usa_rag = True
                except Exception as e:
                    usa_rag = False
            
            # Build context for the AI
            system_context = self._build_system_context(lead, intent_info, contexto_rag, image_request)
            context_messages = [
                {"role": "system", "content": system_context}
            ]
            
            # Add conversation history (máximo 3 turnos = 6 mensajes)
            historial_procesado = 0
            for item in reversed(historial):
                if historial_procesado >= 6:  # Máximo 6 mensajes (3 turnos)
                    break
                context_messages.append({"role": "user", "content": item.get('mensaje', '')})
                context_messages.append({"role": "assistant", "content": item.get('respuesta', '')})
                historial_procesado += 2
            
            # Add current message
            context_messages.append({"role": "user", "content": mensaje_usuario})
            
            # Get optimal temperature for this conversation context
            temperature = self.get_temperature_for_intent(intent_info, intent_info.get('urgency', 'normal'))
            
            # Generate response with OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=context_messages,
                max_tokens=180,  # Aumentado a 180 para permitir referencias contextuales
                temperature=temperature,  # Temperatura dinámica según contexto
                presence_penalty=0.2,  # Aumentado para evitar repetición
                frequency_penalty=0.2  # Aumentado para mayor variedad
            )
            
            respuesta = response.choices[0].message.content.strip()
            
            # Log token usage and conversation info using the new Logger
            Logger.incoming(telefono, mensaje_usuario)
            Logger.rag_info(usa_rag, contexto_rag)
            
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            Logger.ai_response(respuesta, tokens=tokens_used, temp=temperature)
            
            # Prepare response with potential image
            response_data = {
                'text': respuesta,
                'type': 'text_only'
            }
            
            # Add image info if requested and available
            if image_request and image_request.get('wants_image') and image_request.get('modelo'):
                image_path = image_request.get('image_path')
                # Check if image file exists
                full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), image_path)
                if os.path.exists(full_path):
                    response_data.update({
                        'type': 'text_with_image',
                        'image_path': image_path,
                        'modelo': image_request['modelo'],
                        'image_type': image_request.get('image_type', 'exterior')
                    })
            
            # Save conversation
            self.save_conversation(telefono, mensaje_usuario, respuesta)
            
            # Update lead if it exists
            if lead and self.lead_service:
                # Get telefono from lead object
                telefono_lead = getattr(lead, 'telefono', None) if hasattr(lead, '__dict__') else lead.get('telefono')
                if telefono_lead:
                    self._update_lead_from_conversation(telefono_lead, mensaje_usuario, intent_info)
            
            return response_data
            
        except Exception as e:
            Logger.error(f"Error {telefono}: {str(e)[:200]}", "SERVICE")
            return {
                'text': "Disculpa, tuve un problemita técnico 😅 ¿Me puedes repetir tu mensaje?",
                'type': 'text_only'
            }
    
    def _build_system_context(self, lead: Optional[Dict], intent_info: Dict, contexto_rag: str, image_request: Dict = None) -> str:
        """Construye el contexto del sistema para OpenAI"""
        context = self.system_prompt + "\n\n"
        
        # Add lead information if available
        if lead:
            # Handle both dict and Lead object formats
            if hasattr(lead, '__dict__'):
                # Lead object
                context += f"INFORMACIÓN DEL CLIENTE:\n"
                context += f"- Nombre: {getattr(lead, 'nombre', 'No proporcionado')}\n"
                context += f"- Estado: {getattr(lead, 'estado', 'nuevo')}\n"
                context += f"- Temperatura: {getattr(lead, 'temperatura', 'frio')}\n"
                context += f"- Último contacto: {getattr(lead, 'ultimo_contacto', 'Primer contacto')}\n"
                if hasattr(lead, 'modelo_interes') and lead.modelo_interes:
                    context += f"- Interés en: {lead.modelo_interes}\n"
            else:
                # Dict format
                context += f"INFORMACIÓN DEL CLIENTE:\n"
                context += f"- Nombre: {lead.get('nombre', 'No proporcionado')}\n"
                context += f"- Estado: {lead.get('estado', 'nuevo')}\n"
                context += f"- Temperatura: {lead.get('temperatura', 'frio')}\n"
                context += f"- Último contacto: {lead.get('ultimo_contacto', 'Primer contacto')}\n"
                if lead.get('modelo_interes'):
                    context += f"- Interés en: {lead.get('modelo_interes')}\n"
            context += "\n"
        
        # Add intent information
        if intent_info['intent'] != 'general':
            context += f"CONTEXTO DE LA CONVERSACIÓN:\n"
            context += f"- Intención detectada: {intent_info['intent']}\n"
            context += f"- Urgencia: {intent_info['urgency']}\n"
            
            # Add financing-specific context
            if intent_info['intent'] == 'financing_inquiry':
                context += f"- Paso de conversación: {intent_info.get('conversation_step', 'initial')}\n"
                if intent_info.get('uso_vehiculo'):
                    context += f"- Uso del vehículo: {intent_info['uso_vehiculo']}\n"
                if 'tiene_enganche' in intent_info:
                    enganche_status = "Sí tiene enganche" if intent_info['tiene_enganche'] else "No tiene enganche"
                    context += f"- Enganche disponible: {enganche_status}\n"
                    
                # Add specific instructions based on conversation step
                if intent_info.get('conversation_step') == 'initial':
                    context += f"- ACCIÓN: Hacer preguntas calificadoras (uso y enganche)\n"
                elif intent_info.get('uso_vehiculo') and 'tiene_enganche' in intent_info:
                    context += f"- ACCIÓN: Recomendar plan específico y ofrecer cita\n"
                elif intent_info.get('conversation_step') == 'solicita_cita':
                    context += f"- ACCIÓN: Agendar cita en agencia\n"
            
            if intent_info['entities']:
                context += f"- Entidades: {intent_info['entities']}\n"
            context += "\n"
        
        # Add RAG context if available
        if contexto_rag:
            context += f"INFORMACIÓN RELEVANTE DE LA BASE DE CONOCIMIENTO:\n{contexto_rag}\n\n"
        
        # Add image request context if applicable
        if image_request and image_request.get('wants_image'):
            context += f"SOLICITUD DE IMAGEN DETECTADA:\n"
            if image_request.get('modelo'):
                context += f"- Modelo solicitado: {image_request['modelo']}\n"
                context += f"- Tipo de imagen: {image_request.get('image_type', 'exterior')}\n"
                context += f"- Confirma que enviarás la imagen después del mensaje de texto\n"
            elif image_request.get('needs_clarification'):
                context += f"- Cliente quiere imagen pero no especificó modelo\n"
                context += f"- Pregunta qué modelo específico le interesa\n"
            context += "\n"
        
        context += "INSTRUCCIONES CRÍTICAS:\n"
        context += "- Respuesta: 1-3 líneas máximo\n"
        context += "- MEMORIA: Revisa SIEMPRE el historial conversacional para mantener coherencia\n"
        context += "- CONTINUIDAD: Conecta tu respuesta con mensajes anteriores del cliente\n"
        context += "- REFERENCIAS: Si ya discutiste algo, refiérete específicamente (ej: 'Como te mencioné del Sentra...')\n"
        context += "- SOLO usa información del contexto RAG para datos técnicos\n"
        context += "- Si no sabes algo: 'déjame verificar esa información'\n"
        context += "- Usa emojis moderadamente\n"
        
        return context
    
    def _update_lead_from_conversation(self, telefono: str, mensaje: str, intent_info: Dict):
        """Actualiza el lead basado en la conversación"""
        try:
            if not self.lead_service:
                return
            
            # Get the current lead
            lead = self.lead_service.obtener_lead(telefono)
            if not lead:
                return
            
            # Update last interaction time
            lead.ultima_interaccion = datetime.now()
            
            # Update model interest if detected
            if 'modelo_interes' in intent_info['entities']:
                if hasattr(lead, 'info_prospecto') and lead.info_prospecto:
                    lead.info_prospecto.modelo_interes = intent_info['entities']['modelo_interes']
            
            # Update temperature based on intent
            if intent_info['intent'] in ['appointment_request', 'financing_inquiry']:
                lead.temperatura = TemperaturaMercado.CALIENTE
            elif intent_info['intent'] in ['product_inquiry', 'price_inquiry']:
                lead.temperatura = TemperaturaMercado.TIBIO
            
            # Save the updated lead
            self.lead_service.guardar_lead(lead)
            
        except Exception as e:
            pass

# Global instance
conversation_service = ConversationService()