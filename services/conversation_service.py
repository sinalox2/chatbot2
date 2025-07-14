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
    RAG_AVAILABLE = True
    print("✅ RAG Supabase system loaded successfully")
except ImportError as e:
    print(f"⚠️ RAG Supabase system not available: {e}")
    RAG_AVAILABLE = False
    def recuperar_contexto(query, k=3):
        return "Sistema RAG no disponible."

class ConversationService:
    """Servicio para manejar conversaciones con IA usando OpenAI y RAG"""
    
    def __init__(self):
        self.client = None
        self.system_prompt = self._load_system_prompt()
        self.lead_service = LeadTrackingService() if 'LeadTrackingService' in globals() else None
        self._setup_openai()
        
    def _setup_openai(self):
        """Configura el cliente de OpenAI"""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            openai.api_key = api_key
            self.client = openai
            print("✅ OpenAI client configured")
        else:
            print("⚠️ OpenAI API key not found in environment variables")
    
    def _load_system_prompt(self) -> str:
        """Carga el prompt del sistema desde el archivo"""
        try:
            prompt_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompt_sistema_nissan.txt')
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract just the prompt text, remove the function definition
                if 'return """' in content:
                    start = content.find('return """') + len('return """')
                    end = content.rfind('"""')
                    return content[start:end].strip()
                return content
        except Exception as e:
            print(f"⚠️ Error loading system prompt: {e}")
            return "Eres César Arias, asesor de ventas de Nissan Tijuana. Responde de manera amigable y profesional."
    
    def get_conversation_history(self, telefono: str, limit: int = 10) -> List[Dict]:
        """Obtiene el historial de conversación de un cliente"""
        try:
            if not supabase:
                return []
            
            response = supabase.table('historial_conversaciones')\
                .select('*')\
                .eq('telefono', telefono)\
                .order('timestamp', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data or []
        except Exception as e:
            print(f"❌ Error getting conversation history: {e}")
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
            print(f"❌ Error saving conversation: {e}")
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
            print(f"❌ Error managing lead: {e}")
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
            'urgency': 'normal'
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
        
        return intent_info
    
    def generate_response(self, telefono: str, mensaje_usuario: str, nombre_usuario: Optional[str] = None) -> str:
        """Genera una respuesta usando OpenAI y el contexto RAG"""
        try:
            if not self.client:
                return "Disculpa, tengo problemas técnicos. ¿Puedes intentar más tarde? 😅"
            
            # Get conversation history
            historial = self.get_conversation_history(telefono, limit=5)
            
            # Get or create lead
            lead = self.get_or_create_lead(telefono, nombre_usuario)
            
            # Analyze message intent
            intent_info = self.analyze_message_intent(mensaje_usuario)
            
            # Detect image requests
            image_request = self.detect_image_request(mensaje_usuario)
            
            # Get relevant context from RAG if available
            contexto_rag = ""
            if RAG_AVAILABLE:
                try:
                    contexto_rag = recuperar_contexto(mensaje_usuario, k=5)
                    print(f"🔍 RAG Context found: {len(contexto_rag)} characters")
                    if "V‑Drive" in contexto_rag or "v-drive" in contexto_rag.lower():
                        print("✅ V-Drive info found in RAG context")
                except Exception as e:
                    print(f"⚠️ Error getting RAG context: {e}")
            
            # Build context for the AI
            system_context = self._build_system_context(lead, intent_info, contexto_rag, image_request)
            context_messages = [
                {"role": "system", "content": system_context}
            ]
            
            # Add conversation history
            for item in reversed(historial[:3]):  # Last 3 messages
                context_messages.append({"role": "user", "content": item.get('mensaje', '')})
                context_messages.append({"role": "assistant", "content": item.get('respuesta', '')})
            
            # Add current message
            context_messages.append({"role": "user", "content": mensaje_usuario})
            
            # Generate response with OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=context_messages,
                max_tokens=150,  # Keep responses short and conversational
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            respuesta = response.choices[0].message.content.strip()
            
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
                    print(f"✅ Imagen encontrada: {image_path}")
                else:
                    print(f"⚠️ Imagen no encontrada: {full_path}")
            
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
            print(f"❌ Error generating response: {e}")
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
        context += "- Responde como César Arias de manera natural y conversacional\n"
        context += "- Máximo 2 líneas de respuesta\n"
        context += "- SOLO usa información de la INFORMACIÓN RELEVANTE DE LA BASE DE CONOCIMIENTO mostrada arriba\n"
        context += "- NUNCA inventes precios, fechas o especificaciones\n"
        context += "- Si la información no está en el contexto, di 'déjame verificar esa información'\n"
        context += "- Estamos en JULIO 2025, usa los precios actuales\n"
        context += "- Usa emojis apropiados pero no abuses\n"
        
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
            print(f"❌ Error updating lead: {e}")

# Global instance
conversation_service = ConversationService()