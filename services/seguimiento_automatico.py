# services/seguimiento_automatico.py
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import List
import os
import sys

# Agregar el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from services.lead_tracking_service import LeadTrackingService
    from models.lead_tracking import EstadoLead, TipoInteraccion, Interaccion, TemperaturaMercado
    from supabase_client import supabase
except ImportError as e:
    print(f"⚠️ Error importando en seguimiento_automatico: {e}")
    supabase = None

# Configuración de WhatsApp Business API
import requests
from services.whatsapp_service import whatsapp_service

class SeguimientoAutomaticoService:
    
    def __init__(self):
        self.lead_tracker = LeadTrackingService()
        self.running = False
        self.whatsapp_enabled = whatsapp_service.enabled
    
    def iniciar_seguimiento(self):
        """Inicia el sistema de seguimiento automático"""
        if self.running:
            print("⚠️ Sistema de seguimiento ya está corriendo")
            return
        
        # Configurar tareas programadas
        schedule.every(30).minutes.do(self.procesar_seguimientos_pendientes)
        schedule.every(2).hours.do(self.identificar_leads_sin_respuesta)
        schedule.every().day.at("09:00").do(self.seguimiento_diario_leads_calientes)
        schedule.every().day.at("18:00").do(self.reporte_diario_equipo)
        
        # Ejecutar en hilo separado para no bloquear Flask
        def run_scheduler():
            self.running = True
            print("🤖 Scheduler de seguimiento iniciado")
            while self.running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Revisar cada minuto
                except Exception as e:
                    print(f"❌ Error en scheduler: {e}")
                    time.sleep(300)  # Esperar 5 minutos si hay error
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("🤖 Sistema de seguimiento automático iniciado")
    
    def detener_seguimiento(self):
        """Detiene el sistema de seguimiento"""
        self.running = False
        schedule.clear()
        print("🛑 Sistema de seguimiento detenido")
    
    def procesar_seguimientos_pendientes(self):
        """Procesa seguimientos que ya llegó su hora"""
        print("📅 Procesando seguimientos pendientes...")
        
        if not supabase:
            print("❌ Supabase no disponible para seguimientos")
            return
        
        try:
            ahora = datetime.now()
            
            # Obtener seguimientos pendientes de la tabla
            response = supabase.table('seguimientos_programados').select('*').eq('estado', 'pendiente').lte('fecha_programada', ahora.isoformat()).execute()
            
            seguimientos_procesados = 0
            
            for seguimiento in response.data:
                try:
                    # Obtener información del lead
                    lead = self.lead_tracker.obtener_lead(seguimiento['telefono'])
                    if not lead:
                        print(f"⚠️ Lead no encontrado: {seguimiento['telefono']}")
                        continue
                    
                    # Generar mensaje personalizado
                    mensaje = self.generar_mensaje_seguimiento(lead, seguimiento)
                    
                    # Enviar según el canal
                    if seguimiento['canal'] == 'whatsapp':
                        if self.enviar_whatsapp(lead.telefono, mensaje):
                            resultado = 'enviado'
                        else:
                            resultado = 'fallido'
                    else:
                        # Simular otros canales
                        print(f"📞 Simulando {seguimiento['canal']} a {lead.telefono}: {mensaje}")
                        resultado = 'simulado'
                    
                    # Marcar como procesado
                    supabase.table('seguimientos_programados').update({
                        'estado': resultado,
                        'executed_at': datetime.now().isoformat()
                    }).eq('id', seguimiento['id']).execute()
                    
                    # Registrar interacción
                    interaccion = Interaccion(
                        telefono=lead.telefono,
                        tipo=TipoInteraccion.WHATSAPP_SALIENTE,
                        descripcion=f"Seguimiento automático: {seguimiento['tipo_seguimiento']}",
                        fecha=datetime.now(),
                        usuario='sistema_automatico',
                        resultado=resultado,
                        datos_adicionales={'seguimiento_id': seguimiento['id'], 'mensaje': mensaje}
                    )
                    self.lead_tracker.registrar_interaccion(interaccion)
                    
                    # Programar próximo seguimiento
                    self.programar_proximo_seguimiento(lead)
                    
                    seguimientos_procesados += 1
                    
                except Exception as e:
                    print(f"❌ Error procesando seguimiento {seguimiento.get('id', 'unknown')}: {e}")
            
            if seguimientos_procesados > 0:
                print(f"✅ Procesados {seguimientos_procesados} seguimientos")
            
        except Exception as e:
            print(f"❌ Error en procesar_seguimientos_pendientes: {e}")
    
    def identificar_leads_sin_respuesta(self):
        """Identifica leads que no han respondido y programa seguimientos"""
        print("🔍 Identificando leads sin respuesta...")
        
        if not supabase:
            return
        
        try:
            # Leads sin respuesta en 24 horas
            hace_24h = datetime.now() - timedelta(hours=24)
            
            response = supabase.table('leads_tracking_pro').select('*').lt('ultima_interaccion', hace_24h.isoformat()).execute()
            
            leads_programados = 0
            
            for lead_data in response.data:
                lead = self.lead_tracker.obtener_lead(lead_data['telefono'])
                if not lead:
                    continue
                
                # Solo leads activos
                if lead.estado in [EstadoLead.VENDIDO, EstadoLead.PERDIDO_INTERES, EstadoLead.DESCALIFICADO]:
                    continue
                
                # Verificar si ya tiene seguimiento programado
                seguimiento_existente = supabase.table('seguimientos_programados').select('id').eq('telefono', lead.telefono).eq('estado', 'pendiente').execute()
                
                if not seguimiento_existente.data:
                    # Programar seguimiento según temperatura
                    if lead.temperatura == TemperaturaMercado.CALIENTE:
                        dias_siguiente = 1
                        prioridad = 3
                    elif lead.temperatura == TemperaturaMercado.TIBIO:
                        dias_siguiente = 2
                        prioridad = 2
                    else:
                        dias_siguiente = 3
                        prioridad = 1
                    
                    self.programar_seguimiento_especifico(
                        lead.telefono,
                        'sin_respuesta',
                        dias_siguiente,
                        prioridad=prioridad
                    )
                    leads_programados += 1
            
            if leads_programados > 0:
                print(f"📅 Programados {leads_programados} seguimientos por falta de respuesta")
                
        except Exception as e:
            print(f"❌ Error identificando leads sin respuesta: {e}")
    
    def seguimiento_diario_leads_calientes(self):
        """Seguimiento diario para leads calientes"""
        print("🔥 Procesando seguimiento diario de leads calientes...")
        
        if not supabase:
            return
        
        try:
            # Obtener leads calientes sin interacción reciente
            response = supabase.table('leads_tracking_pro').select('*').eq('temperatura', 'caliente').execute()
            
            leads_procesados = 0
            
            for lead_data in response.data:
                lead = self.lead_tracker.obtener_lead(lead_data['telefono'])
                if not lead:
                    continue
                
                dias_sin_interaccion = lead.dias_sin_interaccion()
                
                # Si tiene más de 1 día sin interacción, programar seguimiento prioritario
                if dias_sin_interaccion >= 1:
                    self.programar_seguimiento_especifico(
                        lead.telefono,
                        'daily_hot_lead',
                        0,  # Inmediato
                        prioridad=3
                    )
                    leads_procesados += 1
            
            if leads_procesados > 0:
                print(f"🔥 Programados {leads_procesados} seguimientos de leads calientes")
                
        except Exception as e:
            print(f"❌ Error en seguimiento diario leads calientes: {e}")
    
    def generar_mensaje_seguimiento(self, lead, seguimiento_data):
        """Genera mensaje personalizado para seguimiento"""
        try:
            # Obtener plantilla de la base de datos
            if supabase:
                template_response = supabase.table('plantillas_seguimiento').select('mensaje_template').eq('tipo_seguimiento', seguimiento_data['tipo_seguimiento']).execute()
                
                if template_response.data:
                    template = template_response.data[0]['mensaje_template']
                else:
                    template = seguimiento_data.get('mensaje_template', self.get_default_template(seguimiento_data['tipo_seguimiento']))
            else:
                template = self.get_default_template(seguimiento_data['tipo_seguimiento'])
            
            # Validar template antes de usar
            if not template:
                template = "Hola {nombre}, ¿cómo vas con la decisión del {modelo}? Soy César 😊"
            
            # Reemplazar variables con validación
            try:
                mensaje = template.format(
                    nombre=lead.nombre or 'amigo',
                    modelo=lead.info_prospecto.modelo_interes or 'auto Nissan',
                    dias=lead.dias_sin_interaccion(),
                    telefono_asesor='6644918078'
                )
            except (AttributeError, KeyError) as e:
                print(f"❌ Error formateando template: {e}")
                mensaje = f"Hola {lead.nombre or 'amigo'}, ¿cómo puedo ayudarte con tu auto Nissan? Soy César 😊"
            
            return mensaje
            
        except Exception as e:
            print(f"❌ Error generando mensaje: {e}")
            return f"Hola {lead.nombre}! 😁 ¿Cómo estás? ¿Sigues interesado en nuestros autos Nissan?"
    
    def get_default_template(self, tipo_seguimiento):
        """Plantillas por defecto si no hay en base de datos"""
        templates = {
            'primer_contacto': 'Hola {nombre}! 😁 Vi que preguntaste sobre autos Nissan. ¿Aún te interesa conocer nuestras opciones?',
            'post_calificacion': 'Hola {nombre}! 😁 ¿Cómo vas con la decisión del {modelo}? ¿Te gustaría que te llame para platicar más detalles?',
            'post_cotizacion': 'Hola {nombre}! 😁 ¿Tuviste oportunidad de revisar la cotización? ¿Tienes alguna duda?',
            'sin_respuesta': 'Hola {nombre}! 😁 ¿Recibiste mi mensaje anterior? ¿Hay algo en lo que pueda ayudarte?',
            'daily_hot_lead': 'Hola {nombre}! 😁 Como vi que estás muy interesado, ¿quieres que te reserve el {modelo}? Las promociones están por terminar.',
            'reactivacion': 'Hola {nombre}! 😁 Tenemos nuevas promociones en Nissan. ¿Te interesa conocerlas?'
        }
        return templates.get(tipo_seguimiento, 'Hola {nombre}! 😁 ¿Cómo estás? ¿Sigues interesado en nuestros autos?')
    
    def enviar_whatsapp(self, telefono, mensaje):
        """Envía mensaje de WhatsApp usando el servicio centralizado"""
        resultado = whatsapp_service.enviar_mensaje(telefono, mensaje)
        return resultado.get('success', False)
    
    def programar_seguimiento_especifico(self, telefono, tipo, dias, prioridad=1, canal='whatsapp'):
        """Programa un seguimiento específico"""
        if not supabase:
            print(f"📅 SIMULADO - Seguimiento {tipo} para {telefono} en {dias} días")
            return
        
        try:
            fecha_programada = datetime.now() + timedelta(days=dias)
            
            seguimiento = {
                'telefono': telefono,
                'tipo_seguimiento': tipo,
                'fecha_programada': fecha_programada.isoformat(),
                'canal': canal,
                'prioridad': prioridad,
                'estado': 'pendiente'
            }
            
            supabase.table('seguimientos_programados').insert(seguimiento).execute()
            print(f"📅 Seguimiento {tipo} programado para {telefono} en {dias} días")
            
        except Exception as e:
            print(f"❌ Error programando seguimiento: {e}")
    
    def programar_proximo_seguimiento(self, lead):
        """Programa el próximo seguimiento basado en el estado del lead"""
        try:
            # Lógica para próximo seguimiento según estado y temperatura
            if lead.estado == EstadoLead.CONTACTO_INICIAL:
                dias = 1
                tipo = 'primer_seguimiento'
            elif lead.estado == EstadoLead.CALIFICADO:
                dias = 2 if lead.temperatura == TemperaturaMercado.CALIENTE else 3
                tipo = 'post_calificacion'
            elif lead.estado == EstadoLead.COTIZADO:
                dias = 1 if lead.temperatura == TemperaturaMercado.CALIENTE else 2
                tipo = 'post_cotizacion'
            else:
                dias = 3
                tipo = 'seguimiento_general'
            
            # Solo programar si no hay seguimientos pendientes
            if supabase:
                existing = supabase.table('seguimientos_programados').select('id').eq('telefono', lead.telefono).eq('estado', 'pendiente').execute()
                if not existing.data:
                    self.programar_seguimiento_especifico(
                        lead.telefono,
                        tipo,
                        dias,
                        prioridad=3 if lead.temperatura == TemperaturaMercado.CALIENTE else 2
                    )
            
        except Exception as e:
            print(f"❌ Error programando próximo seguimiento: {e}")
    
    def reporte_diario_equipo(self):
        """Genera reporte diario para el equipo de ventas"""
        print("📊 Generando reporte diario...")
        
        try:
            metricas = self.lead_tracker.obtener_dashboard_metricas()
            
            # Obtener leads que necesitan atención inmediata
            leads_prioritarios = self.lead_tracker.obtener_leads_por_prioridad(10)
            
            reporte = f"""
📊 REPORTE DIARIO NISSAN - {datetime.now().strftime('%d/%m/%Y')}

🔥 LEADS CALIENTES: {metricas.get('por_temperatura', {}).get('caliente', 0)}
📈 TOTAL LEADS: {metricas.get('total_leads', 0)}
📞 SEGUIMIENTOS PENDIENTES: {self.contar_seguimientos_pendientes()}

TOP 5 LEADS PRIORITARIOS:
"""
            
            for i, lead in enumerate(leads_prioritarios[:5], 1):
                reporte += f"{i}. {lead.nombre} - Score: {lead.score_calificacion:.1f} - Tel: {lead.telefono}\n"
            
            print(reporte)
            
            # Aquí podrías enviar el reporte por WhatsApp/email al equipo
            
        except Exception as e:
            print(f"❌ Error generando reporte diario: {e}")
    
    def contar_seguimientos_pendientes(self):
        """Cuenta seguimientos pendientes"""
        if not supabase:
            return 0
        
        try:
            response = supabase.table('seguimientos_programados').select('id', count='exact').eq('estado', 'pendiente').execute()
            return response.count if response.count else 0
        except:
            return 0
    
    # Métodos para control manual
    def ejecutar_seguimientos_ahora(self):
        """Ejecuta seguimientos pendientes inmediatamente (para testing)"""
        print("🚀 Ejecutando seguimientos manualmente...")
        self.procesar_seguimientos_pendientes()
    
    def mostrar_estado(self):
        """Muestra el estado actual del sistema"""
        return {
            'running': self.running,
            'whatsapp_enabled': self.whatsapp_enabled,
            'seguimientos_pendientes': self.contar_seguimientos_pendientes(),
            'proximo_reporte': '18:00'
        }