# services/contactos_proactivos.py
import os
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from supabase_client import supabase
import threading
import schedule

class ContactosProactivosService:
    """Servicio para manejar contactos proactivos del bot"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        
    def obtener_contactos_pendientes(self, limite: int = 10) -> List[Dict]:
        """Obtiene contactos pendientes para envío"""
        try:
            # Usar query directo que incluye template_whatsapp 
            print(f"📊 Obteniendo contactos pendientes con query directo...")
            response = supabase.table('contactos_proactivos')\
                .select('id, telefono, nombre, contexto, tipo_campana, mensaje_personalizado, observaciones, created_at, template_whatsapp')\
                .eq('estado', 'pendiente')\
                .lte('fecha_programada', datetime.now().isoformat())\
                .order('created_at', desc=False)\
                .limit(limite)\
                .execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"❌ Error obteniendo contactos pendientes: {e}")
            return []
    
    def _generar_parametros_template(self, template_name: str, contacto: Dict) -> Dict:
        """Genera parámetros específicos para cada template"""
        nombre = contacto.get('nombre', 'Cliente')
        
        if template_name == "saludo_lead":
            return {'nombre': nombre}
            
        elif template_name == "recordatorio_cita":
            return {
                'nombre': nombre,
                'fecha': contacto.get('fecha_cita', '10 de julio'),
                'hora': contacto.get('hora_cita', '4:00 PM'),
                'direccion': contacto.get('direccion', 'Av. Revolución 123, Nissan Tijuana')
            }
            
        else:
            # Fallback genérico
            return {'nombre': nombre}
    
    def generar_mensaje_personalizado(self, contacto: Dict) -> str:
        """Genera mensaje personalizado basado en el contexto del contacto"""
        nombre = contacto.get('nombre', 'amigo')
        contexto = contacto.get('contexto', '')
        tipo_campana = contacto.get('tipo_campana', 'seguimiento')
        mensaje_custom = contacto.get('mensaje_personalizado')
        
        # Si hay mensaje personalizado, usarlo
        if mensaje_custom:
            return mensaje_custom.replace('{nombre}', nombre)
        
        # Generar mensaje según tipo de campaña y contexto
        if tipo_campana == 'seguimiento':
            contexto_lower = (contexto or '').lower()
            if contexto_lower and 'sentra' in contexto_lower:
                return f"¡Hola {nombre}! 😁 ¿Qué tal? Oye, ¿seguiste pensando en el Sentra? Tenemos nuevas promos que te pueden convenir..."
            elif contexto_lower and 'versa' in contexto_lower:
                return f"¡Ey {nombre}! ¿Cómo vas? 😁 ¿Ya te decidiste por el Versa o aún tienes dudas? Platícame..."
            elif contexto_lower and ('buró' in contexto_lower or 'buro' in contexto_lower):
                return f"Hola {nombre} 😁 Recordé que platicamos del plan Sí Fácil... ¿ya tuviste oportunidad de pensarlo?"
            else:
                return f"¡Hola {nombre}! 😁 ¿Qué tal todo? Quería saber si seguías interesado en algún Nissan..."
                
        elif tipo_campana == 'promocion':
            return f"¡Hola {nombre}! 😁 César de Nissan aquí... tenemos promociones increíbles este mes, ¿te interesa conocerlas?"
            
        elif tipo_campana == 'reactivacion':
            return f"¡{nombre}! ¿Cómo está todo? 😁 ¿Ya es hora de cambiar el auto? Tengo opciones muy buenas para ti..."
            
        else:
            return f"¡Hola {nombre}! 😁 César de Nissan por aquí, ¿cómo vas? ¿Seguís buscando auto?"
    
    def enviar_mensaje_whatsapp(self, telefono: str, mensaje: str) -> bool:
        """Envía mensaje proactivo por WhatsApp usando el servicio centralizado"""
        try:
            # Usar el servicio centralizado de WhatsApp con auto-reload de token
            from services.whatsapp_service import whatsapp_service
            
            resultado = whatsapp_service.enviar_mensaje(telefono, mensaje)
            
            if resultado.get('success'):
                print(f"✅ Mensaje proactivo enviado a {telefono}")
                if resultado.get('token_renovado'):
                    print("🔄 Token fue renovado automáticamente durante el envío")
                return True
            else:
                error_msg = resultado.get('error', 'Error desconocido')
                print(f"❌ Error enviando mensaje proactivo: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ Error en envío proactivo: {e}")
            return False
    
    def enviar_plantilla_whatsapp(self, telefono: str, template_name: str, contacto: Dict) -> bool:
        """Envía plantilla de WhatsApp Business usando el servicio centralizado"""
        try:
            # Usar el servicio centralizado de WhatsApp
            from services.whatsapp_service import whatsapp_service
            
            # Preparar parámetros según el template
            parameters = self._generar_parametros_template(template_name, contacto)
            
            # Enviar template usando el servicio centralizado
            resultado = whatsapp_service.enviar_mensaje_template(
                telefono=telefono,
                template_name=template_name,
                parameters=parameters
            )
            
            if resultado.get('success'):
                print(f"✅ Plantilla '{template_name}' enviada a {telefono}")
                return True
            else:
                error_msg = resultado.get('error', 'Error desconocido')
                print(f"❌ Error enviando plantilla: {error_msg}")
                
                # FALLBACK: Si falla la plantilla, enviar mensaje personalizado
                print(f"📱 FALLBACK: Plantilla '{template_name}' no existe, enviando mensaje personalizado")
                mensaje_fallback = self.generar_mensaje_para_plantilla(template_name, contacto)
                return self.enviar_mensaje_whatsapp(telefono, mensaje_fallback)
                
        except Exception as e:
            print(f"❌ Error enviando plantilla: {e}")
            # FALLBACK: En caso de error, enviar mensaje personalizado
            mensaje_fallback = self.generar_mensaje_para_plantilla(template_name, contacto)
            return self.enviar_mensaje_whatsapp(telefono, mensaje_fallback)
    
    def generar_mensaje_para_plantilla(self, template_name: str, contacto: Dict) -> str:
        """Genera mensaje específico simulando el contenido de una plantilla"""
        nombre = contacto.get('nombre', 'amigo')
        
        if template_name == "saludo_lead":
            return f"¡Hola {nombre}! 😊 Soy César de Nissan. Me da mucho gusto saludarte. ¿En qué modelo de Nissan estás interesado? Tengo excelentes promociones para ti."
            
        elif template_name == "recordatorio_cita":
            return f"¡Hola {nombre}! 📅 Te recuerdo que tienes una cita pendiente con nosotros en Nissan. ¿Podrías confirmarme si sigues interesado? ¡Tengo muy buenas noticias para ti!"
            
        else:
            # Fallback genérico
            return f"¡Hola {nombre}! 😊 Soy César de Nissan. ¿Cómo puedo ayudarte con tu próximo vehículo?"

    def marcar_contacto_enviado(self, contact_id: int, estado: str = 'enviado'):
        """Marca un contacto como enviado en la base de datos"""
        try:
            supabase.rpc('marcar_contacto_enviado', {'contact_id': contact_id}).execute()
            print(f"✅ Contacto {contact_id} marcado como {estado}")
        except Exception as e:
            print(f"❌ Error marcando contacto como enviado: {e}")
    
    def marcar_contacto_error(self, contact_id: int, error_msg: str):
        """Marca un contacto como error en la base de datos"""
        try:
            supabase.table('contactos_proactivos').update({
                'estado': 'error',
                'observaciones': error_msg,
                'updated_at': datetime.now().isoformat()
            }).eq('id', contact_id).execute()
            print(f"✅ Contacto {contact_id} marcado como error: {error_msg}")
        except Exception as e:
            print(f"❌ Error marcando contacto como error: {e}")
    
    def procesar_contactos_pendientes(self):
        """Procesa todos los contactos pendientes"""
        contactos = self.obtener_contactos_pendientes(limite=5)  # Procesar de a 5
        
        if not contactos:
            print("✅ No hay contactos pendientes")
            return
        
        print(f"📤 Procesando {len(contactos)} contactos pendientes...")
        
        for contacto in contactos:
            try:
                telefono = contacto['telefono']
                template_whatsapp = contacto.get('template_whatsapp')
                
                # Si no hay template_whatsapp en el contacto, buscar en observaciones
                if not template_whatsapp and contacto.get('observaciones'):
                    observaciones = contacto.get('observaciones', '')
                    if 'Template:' in observaciones:
                        # Extraer después de 'Template:' hasta el final o hasta el siguiente separador
                        template_part = observaciones.split('Template:')[1].strip()
                        # Si hay más contenido después, tomar solo la plantilla
                        if '|' in template_part:
                            template_whatsapp = template_part.split('|')[0].strip()
                        else:
                            template_whatsapp = template_part.strip()
                        print(f"📱 Template encontrado en observaciones: {template_whatsapp}")
                
                # Validar que el template no esté vacío
                if template_whatsapp and template_whatsapp.strip() == '':
                    template_whatsapp = None
                
                # Verificar si es primer contacto o contacto existente
                observaciones = contacto.get('observaciones', '') or ''
                es_primer_contacto = observaciones and 'Primer contacto' in observaciones
                es_contacto_existente = observaciones and 'Contacto existente' in observaciones
                
                # Lógica de envío según tipo de contacto
                if es_primer_contacto and template_whatsapp:
                    # --- INICIO: NUEVA INTEGRACIÓN CON CHATWOOT ---
                    try:
                        from chatwoot_api import buscar_contacto, crear_contacto, crear_conversacion, crear_mensaje_privado
                        
                        print(f"🤖 Iniciando flujo de Chatwoot para {telefono}...")
                        
                        # 1. Buscar o crear contacto en Chatwoot
                        chatwoot_contact = buscar_contacto(telefono)
                        if not chatwoot_contact:
                            print(f"📞 Contacto no encontrado en Chatwoot, creando uno nuevo...")
                            chatwoot_contact = crear_contacto(contacto.get('nombre', 'Contacto Proactivo'), telefono)
                        
                        if not chatwoot_contact or not chatwoot_contact.get('id'):
                            raise Exception("No se pudo crear o encontrar el contacto en Chatwoot.")

                        contact_id = chatwoot_contact.get('id')
                        print(f"✅ Contacto ID en Chatwoot: {contact_id}")

                        # 2. Crear conversación en Chatwoot
                        conversacion = crear_conversacion(contact_id)
                        conversation_id = conversacion.get('id')
                        if not conversation_id:
                            raise Exception("No se pudo crear la conversación en Chatwoot.")
                        
                        print(f"💬 Conversación ID en Chatwoot: {conversation_id}")

                        # 3. Enviar plantilla de WhatsApp (lógica existente)
                        print(f"📱 PRIMER CONTACTO - Enviando plantilla '{template_whatsapp}' a {contacto['nombre']} ({telefono})")
                        if self.enviar_plantilla_whatsapp(telefono, template_whatsapp, contacto):
                            self.marcar_contacto_enviado(contacto['id'])
                            
                            # 4. (Mejora) Agregar nota privada a la conversación de Chatwoot
                            nota_privada = f"[Lead Proactivo] Contactado en frío con plantilla '{template_whatsapp}'.\nContexto: {contacto.get('contexto', 'Sin contexto')}"
                            crear_mensaje_privado(conversation_id, nota_privada)
                            print(f"📝 Nota privada agregada a la conversación {conversation_id}")
                            
                            # Guardar en historial local (opcional, redundante si se usa Chatwoot)
                            if supabase:
                                supabase.table('historial_conversaciones').insert({
                                    'telefono': telefono,
                                    'mensaje': f"[PRIMER CONTACTO CHATWOOT] Contexto: {(contacto.get('contexto') or '')[:100]}...",
                                    'respuesta': f"Plantilla enviada: {template_whatsapp}",
                                    'timestamp': datetime.now().isoformat()
                                }).execute()
                        else:
                            self.marcar_contacto_error(contacto['id'], "Error enviando plantilla de WhatsApp")

                    except Exception as e:
                        error_msg = f"Error en el flujo de Chatwoot: {e}"
                        print(f"❌ {error_msg}")
                        self.marcar_contacto_error(contacto['id'], error_msg)
                    # --- FIN: NUEVA INTEGRACIÓN CON CHATWOOT ---
                        
                elif es_contacto_existente:
                    # CONTACTO EXISTENTE: Usar mensaje personalizado
                    mensaje = self.generar_mensaje_personalizado(contacto)
                    print(f"📱 CONTACTO EXISTENTE - Enviando mensaje personalizado a {contacto['nombre']} ({telefono}): {mensaje[:50]}...")
                    
                    if self.enviar_mensaje_whatsapp(telefono, mensaje):
                        self.marcar_contacto_enviado(contacto['id'])
                        if supabase:
                            contexto_text = (contacto.get('contexto') or '')[:100]
                            supabase.table('historial_conversaciones').insert({
                                'telefono': telefono,
                                'mensaje': f"[CONTACTO EXISTENTE] Contexto: {contexto_text}...",
                                'respuesta': mensaje,
                                'timestamp': datetime.now().isoformat()
                            }).execute()
                    else:
                        print(f"❌ Error enviando mensaje personalizado a {telefono}")
                        self.marcar_contacto_error(contacto['id'], "Error enviando mensaje personalizado")
                        
                elif template_whatsapp:
                    # FALLBACK: Si hay plantilla pero no está marcado, usar plantilla
                    print(f"📱 FALLBACK - Enviando plantilla '{template_whatsapp}' a {contacto['nombre']} ({telefono})")
                    
                    if self.enviar_plantilla_whatsapp(telefono, template_whatsapp, contacto):
                        self.marcar_contacto_enviado(contacto['id'])
                        if supabase:
                            contexto_text = (contacto.get('contexto') or '')[:100]
                            supabase.table('historial_conversaciones').insert({
                                'telefono': telefono,
                                'mensaje': f"[CONTACTO PROACTIVO] Contexto: {contexto_text}...",
                                'respuesta': f"Plantilla enviada: {template_whatsapp}",
                                'timestamp': datetime.now().isoformat()
                            }).execute()
                    else:
                        print(f"❌ Error enviando plantilla a {telefono}")
                        self.marcar_contacto_error(contacto['id'], "Error enviando plantilla")
                else:
                    # ÚLTIMO FALLBACK: Mensaje personalizado para compatibilidad
                    mensaje = self.generar_mensaje_personalizado(contacto)
                    print(f"📱 ÚLTIMO FALLBACK - Enviando mensaje personalizado a {contacto['nombre']} ({telefono}): {mensaje[:50]}...")
                    
                    if self.enviar_mensaje_whatsapp(telefono, mensaje):
                        self.marcar_contacto_enviado(contacto['id'])
                        if supabase:
                            contexto_text = (contacto.get('contexto') or '')[:100]
                            supabase.table('historial_conversaciones').insert({
                                'telefono': telefono,
                                'mensaje': f"[CONTACTO PROACTIVO] Contexto: {contexto_text}...",
                                'respuesta': mensaje,
                                'timestamp': datetime.now().isoformat()
                            }).execute()
                    else:
                        print(f"❌ Error enviando mensaje personalizado a {telefono}")
                        self.marcar_contacto_error(contacto['id'], "Error enviando mensaje personalizado")
                
                # Esperar entre envíos para no saturar
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Error procesando contacto {contacto.get('id')}: {e}")
    
    def agregar_contacto_proactivo(self, telefono: str, nombre: str, contexto: str, 
                                  tipo_campana: str = 'seguimiento', 
                                  prioridad: int = 2,
                                  fecha_programada: Optional[datetime] = None,
                                  mensaje_personalizado: Optional[str] = None,
                                  observaciones: Optional[str] = None,
                                  template_whatsapp: Optional[str] = None) -> bool:
        """Agrega un nuevo contacto para envío proactivo"""
        try:
            data = {
                'telefono': telefono,
                'nombre': nombre,
                'contexto': contexto,
                'tipo_campana': tipo_campana,
                'prioridad': prioridad,
                'fecha_programada': (fecha_programada or datetime.now()).isoformat(),
                'mensaje_personalizado': mensaje_personalizado,
                'observaciones': observaciones,
                'estado': 'pendiente'  # Establecer estado inicial
            }
            
            # Agregar template_whatsapp solo si se proporciona y la columna existe
            if template_whatsapp:
                # Verificar si la columna existe haciendo una consulta de prueba
                try:
                    test_response = supabase.table('contactos_proactivos').select('template_whatsapp').limit(1).execute()
                    data['template_whatsapp'] = template_whatsapp
                    print(f"✅ Columna template_whatsapp disponible, agregando: {template_whatsapp}")
                except Exception as e:
                    print(f"⚠️ Columna template_whatsapp no disponible, usando mensaje personalizado: {e}")
                    # Guardar la plantilla en observaciones como fallback
                    if observaciones:
                        data['observaciones'] = f"{observaciones} | Template: {template_whatsapp}"
                    else:
                        data['observaciones'] = f"Template: {template_whatsapp}"
            
            response = supabase.table('contactos_proactivos').insert(data).execute()
            
            if response.data:
                print(f"✅ Contacto proactivo agregado: {nombre} ({telefono})")
                return True
            else:
                print(f"❌ Error agregando contacto proactivo")
                return False
                
        except Exception as e:
            print(f"❌ Error agregando contacto proactivo: {e}")
            return False
    
    def programar_mensaje_diferido(self, telefono: str, nombre: str, contexto: str,
                                  horas_delay: int = 24, tipo_campana: str = 'seguimiento',
                                  template_whatsapp: str = 'saludo_lead'):
        """Programa un mensaje para envío diferido"""
        fecha_programada = datetime.now() + timedelta(hours=horas_delay)
        
        return self.agregar_contacto_proactivo(
            telefono=telefono,
            nombre=nombre,
            contexto=contexto,
            tipo_campana=tipo_campana,
            fecha_programada=fecha_programada,
            observaciones=f"Programado para {horas_delay} horas después",
            template_whatsapp=template_whatsapp
        )
    
    def programar_mensajes_constantes(self, telefono: str, nombre: str, contexto: str,
                                     max_mensajes: int = 5, intervalo_horas: int = 20):
        """Programa mensajes constantes cada 20 horas para mantener la ventana de 24 horas"""
        print(f"📅 Programando {max_mensajes} mensajes cada {intervalo_horas} horas para {nombre}")
        
        for i in range(max_mensajes):
            horas_delay = intervalo_horas * (i + 1)  # 20, 40, 60, 80, 100 horas
            
            # Alternar entre plantillas
            template = 'saludo_lead' if i % 2 == 0 else 'recordatorio_cita'
            
            # Crear contexto específico para cada mensaje
            contexto_mensaje = f"{contexto} - Mensaje {i+1}/{max_mensajes} del seguimiento automático"
            
            exito = self.agregar_contacto_proactivo(
                telefono=telefono,
                nombre=nombre,
                contexto=contexto_mensaje,
                tipo_campana='seguimiento_automatico',
                fecha_programada=datetime.now() + timedelta(hours=horas_delay),
                observaciones=f"Seguimiento automático {i+1}/{max_mensajes} - {horas_delay}h",
                template_whatsapp=template
            )
            
            if exito:
                print(f"✅ Mensaje {i+1} programado para {horas_delay} horas ({template})")
            else:
                print(f"❌ Error programando mensaje {i+1}")
                
        return True
    
    def obtener_estadisticas(self) -> Dict:
        """Obtiene estadísticas del sistema de contactos proactivos"""
        try:
            # Total por estado
            response = supabase.table('contactos_proactivos').select('estado').execute()
            contactos = response.data if response.data else []
            
            estadisticas = {
                'total': len(contactos),
                'pendientes': len([c for c in contactos if c['estado'] == 'pendiente']),
                'enviados': len([c for c in contactos if c['estado'] == 'enviado']),
                'respondidos': len([c for c in contactos if c['estado'] == 'respondido']),
                'errores': len([c for c in contactos if c['estado'] == 'error'])
            }
            
            # Contactos por tipo de campaña
            tipos = {}
            for contacto in contactos:
                tipo = contacto.get('tipo_campana', 'sin_tipo')
                tipos[tipo] = tipos.get(tipo, 0) + 1
            
            estadisticas['por_tipo'] = tipos
            
            return estadisticas
            
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
            return {}
    
    def iniciar_servicio_automatico(self):
        """Inicia el servicio automático de procesamiento"""
        if self.running:
            print("⚠️ El servicio ya está ejecutándose")
            return
        
        # Programar ejecución cada 30 minutos
        schedule.every(30).minutes.do(self.procesar_contactos_pendientes)
        
        # También ejecutar cada día a las 9:00 AM
        schedule.every().day.at("09:00").do(self.procesar_contactos_pendientes)
        
        # Y cada día a las 2:00 PM
        schedule.every().day.at("14:00").do(self.procesar_contactos_pendientes)
        
        def run_scheduler():
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Revisar cada minuto
        
        self.running = True
        self.thread = threading.Thread(target=run_scheduler, daemon=True)
        self.thread.start()
        
        print("🤖 Servicio de contactos proactivos iniciado")
        print("⏰ Programado: cada 30 min, 9:00 AM y 2:00 PM")
    
    def detener_servicio(self):
        """Detiene el servicio automático"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        schedule.clear()
        print("🛑 Servicio de contactos proactivos detenido")

# Instancia global del servicio
contactos_proactivos_service = ContactosProactivosService()