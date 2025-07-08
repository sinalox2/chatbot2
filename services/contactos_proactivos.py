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
            # Usar la función SQL creada
            response = supabase.rpc('obtener_contactos_pendientes', {'limite': limite}).execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"❌ Error obteniendo contactos pendientes: {e}")
            return []
    
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
            if 'sentra' in contexto.lower():
                return f"¡Hola {nombre}! 😁 ¿Qué tal? Oye, ¿seguiste pensando en el Sentra? Tenemos nuevas promos que te pueden convenir..."
            elif 'versa' in contexto.lower():
                return f"¡Ey {nombre}! ¿Cómo vas? 😁 ¿Ya te decidiste por el Versa o aún tienes dudas? Platícame..."
            elif 'buró' in contexto.lower() or 'buro' in contexto.lower():
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
        """Envía mensaje proactivo por WhatsApp"""
        try:
            token = os.getenv("WHATSAPP_TOKEN")
            phone_number_id = os.getenv("PHONE_NUMBER_ID")
            
            if not token or not phone_number_id:
                print("❌ Faltan variables de WhatsApp para envío proactivo")
                return False
                
            url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
            
            payload = {
                "messaging_product": "whatsapp",
                "to": telefono,
                "type": "text",
                "text": {"body": mensaje}
            }
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.ok:
                print(f"✅ Mensaje proactivo enviado a {telefono}")
                return True
            else:
                print(f"❌ Error enviando mensaje proactivo: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error en envío proactivo: {e}")
            return False
    
    def enviar_plantilla_whatsapp(self, telefono: str, template_name: str, contacto: Dict) -> bool:
        """Envía plantilla de WhatsApp Business"""
        try:
            token = os.getenv("WHATSAPP_TOKEN")
            phone_number_id = os.getenv("PHONE_NUMBER_ID")
            
            if not token or not phone_number_id:
                print("❌ Faltan variables de WhatsApp para envío de plantilla")
                return False
                
            url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
            
            payload = {
                "messaging_product": "whatsapp",
                "to": telefono,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "es"}
                }
            }
            
            # Agregar parámetros si la plantilla los requiere
            if template_name == "saludo_lead":
                # Plantilla de saludo puede incluir nombre del cliente
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": contacto.get('nombre', '')}
                        ]
                    }
                ]
            elif template_name == "recordatorio_cita":
                # Plantilla de recordatorio puede incluir fecha/hora
                payload["template"]["components"] = [
                    {
                        "type": "body", 
                        "parameters": [
                            {"type": "text", "text": contacto.get('nombre', '')},
                            {"type": "text", "text": "próximamente"}  # Aquí iría fecha real
                        ]
                    }
                ]
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.ok:
                print(f"✅ Plantilla '{template_name}' enviada a {telefono}")
                return True
            else:
                print(f"❌ Error enviando plantilla: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error en envío de plantilla: {e}")
            return False
    
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
                        template_whatsapp = observaciones.split('Template:')[1].strip().split('|')[0].strip()
                        print(f"📱 Template encontrado en observaciones: {template_whatsapp}")
                
                # Usar plantilla si está disponible, sino generar mensaje personalizado
                if template_whatsapp:
                    print(f"📱 Enviando plantilla '{template_whatsapp}' a {contacto['nombre']} ({telefono})")
                    
                    # Enviar usando plantilla
                    if self.enviar_plantilla_whatsapp(telefono, template_whatsapp, contacto):
                        # Marcar como enviado
                        self.marcar_contacto_enviado(contacto['id'])
                        
                        # Registrar en historial de conversaciones
                        if supabase:
                            supabase.table('historial_conversaciones').insert({
                                'telefono': telefono,
                                'mensaje': f"[CONTACTO PROACTIVO] Contexto: {contacto['contexto'][:100]}...",
                                'respuesta': f"Plantilla enviada: {template_whatsapp}",
                                'timestamp': datetime.now().isoformat()
                            }).execute()
                    else:
                        print(f"❌ Error enviando plantilla a {telefono}")
                        self.marcar_contacto_error(contacto['id'], "Error enviando plantilla")
                else:
                    # Fallback a mensaje personalizado (para compatibilidad)
                    mensaje = self.generar_mensaje_personalizado(contacto)
                    
                    print(f"📱 Enviando mensaje personalizado a {contacto['nombre']} ({telefono}): {mensaje[:50]}...")
                    
                    # Enviar mensaje
                    if self.enviar_mensaje_whatsapp(telefono, mensaje):
                        # Marcar como enviado
                        self.marcar_contacto_enviado(contacto['id'])
                        
                        # Registrar en historial de conversaciones
                        if supabase:
                            supabase.table('historial_conversaciones').insert({
                                'telefono': telefono,
                                'mensaje': f"[CONTACTO PROACTIVO] Contexto: {contacto['contexto'][:100]}...",
                                'respuesta': mensaje,
                                'timestamp': datetime.now().isoformat()
                            }).execute()
                    else:
                    # Marcar como error
                        supabase.table('contactos_proactivos').update({
                        'estado': 'error',
                        'updated_at': datetime.now().isoformat()
                    }).eq('id', contacto['id']).execute()
                
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
                'observaciones': observaciones
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