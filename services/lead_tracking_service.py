# services/lead_tracking_service.py
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json
import os
import sys
import re

# Agregar el directorio padre al path para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.lead_tracking import (
    Lead, Interaccion, EstadoLead, TipoInteraccion, 
    TemperaturaMercado, CanalOrigen, ProspectoInfo
)

try:
    from supabase_client import supabase
except ImportError:
    print("⚠️ No se pudo importar supabase_client. Asegúrate de que el archivo existe.")
    supabase = None

def _parse_datetime_safe(date_string: str) -> datetime:
    """
    Parsea fechas de Supabase de manera segura, manejando microsegundos variables
    """
    if not date_string:
        return datetime.now()
    
    try:
        # Limpiar el string de fecha
        clean_date = date_string.replace('Z', '+00:00')
        
        # Corregir microsegundos si tienen formato incorrecto
        # Buscar patrón de microsegundos: .12345 o .123456
        microsecond_pattern = r'\.(\d{1,6})\+'
        match = re.search(microsecond_pattern, clean_date)
        
        if match:
            microseconds = match.group(1)
            # Asegurar que tenga exactamente 6 dígitos
            microseconds = microseconds.ljust(6, '0')[:6]
            # Reemplazar en la fecha
            clean_date = re.sub(microsecond_pattern, f'.{microseconds}+', clean_date)
        
        return datetime.fromisoformat(clean_date)
        
    except ValueError as e:
        print(f"⚠️ Error parseando fecha '{date_string}': {e}")
        # Fallback: intentar sin microsegundos
        try:
            # Remover microsegundos completamente
            no_micro = re.sub(r'\.\d+\+', '+', date_string.replace('Z', '+00:00'))
            return datetime.fromisoformat(no_micro)
        except:
            print(f"⚠️ Usando fecha actual como fallback")
            return datetime.now()

class LeadTrackingService:
    
    def __init__(self):
        self.tabla_leads = 'leads_tracking_pro'
        self.tabla_interacciones = 'interacciones_leads'
        
        if not supabase:
            print("❌ Supabase no está disponible. Verificar configuración.")
    
    def crear_lead(self, telefono: str, nombre: str, canal_origen: str) -> Lead:
        """Crea un nuevo lead con tracking completo"""
        try:
            canal = CanalOrigen.WHATSAPP_DIRECTO  # Default
            if canal_origen in [e.value for e in CanalOrigen]:
                canal = CanalOrigen(canal_origen)
        except:
            canal = CanalOrigen.WHATSAPP_DIRECTO
            
        lead = Lead(
            telefono=telefono,
            nombre=nombre,
            estado=EstadoLead.CONTACTO_INICIAL,
            temperatura=TemperaturaMercado.FRIO,
            canal_origen=canal,
            fecha_creacion=datetime.now(),
            ultima_interaccion=datetime.now()
        )
        
        self.guardar_lead(lead)
        
        # Registrar interacción inicial
        interaccion = Interaccion(
            telefono=telefono,
            tipo=TipoInteraccion.MENSAJE_ENTRANTE,
            descripcion="Primer contacto del lead",
            fecha=datetime.now(),
            usuario='cliente'
        )
        self.registrar_interaccion(interaccion)
        
        return lead
    
    def obtener_lead(self, telefono: str) -> Optional[Lead]:
        """Obtiene un lead completo por teléfono"""
        if not supabase:
            return None
            
        try:
            response = supabase.table(self.tabla_leads).select('*').eq('telefono', telefono).execute()
            if response.data:
                data = response.data[0]
                
                # Construir objeto ProspectoInfo
                info_data = {}
                if data.get('info_prospecto'):
                    if isinstance(data['info_prospecto'], str):
                        info_data = json.loads(data['info_prospecto'])
                    else:
                        info_data = data['info_prospecto']
                
                info_prospecto = ProspectoInfo(**info_data)
                
                # Construir objeto Lead
                lead = Lead(
                    telefono=data['telefono'],
                    nombre=data['nombre'],
                    estado=EstadoLead(data['estado']),
                    temperatura=TemperaturaMercado(data['temperatura']),
                    canal_origen=CanalOrigen(data['canal_origen']),
                    fecha_creacion=datetime.fromisoformat(data['fecha_creacion'].replace('Z', '+00:00')),
                    ultima_interaccion=datetime.fromisoformat(data['ultima_interaccion'].replace('Z', '+00:00')),
                    info_prospecto=info_prospecto,
                    total_mensajes_recibidos=data.get('total_mensajes_recibidos', 0),
                    total_mensajes_enviados=data.get('total_mensajes_enviados', 0),
                    total_llamadas=data.get('total_llamadas', 0),
                    total_citas_agendadas=data.get('total_citas_agendadas', 0),
                    total_citas_completadas=data.get('total_citas_completadas', 0),
                    proximo_seguimiento=datetime.fromisoformat(data['proximo_seguimiento'].replace('Z', '+00:00')) if data.get('proximo_seguimiento') else None,
                    asesor_asignado=data.get('asesor_asignado'),
                    notas_importantes=data.get('notas_importantes', ''),
                    score_calificacion=float(data.get('score_calificacion', 0.0)),
                    probabilidad_cierre=float(data.get('probabilidad_cierre', 0.0)),
                    valor_estimado_venta=float(data.get('valor_estimado_venta', 0.0)),
                    email=data.get('email'),
                    ciudad=data.get('ciudad'),
                    fecha_nacimiento=datetime.fromisoformat(data['fecha_nacimiento']) if data.get('fecha_nacimiento') else None
                )
                
                return lead
            return None
        except Exception as e:
            print(f"❌ Error obteniendo lead: {e}")
            return None
    
    def guardar_lead(self, lead: Lead):
        """Guarda o actualiza un lead completo"""
        if not supabase:
            print("❌ Supabase no disponible para guardar lead")
            return
            
        try:
            # Actualizar scores antes de guardar
            lead.calcular_score()
            lead.calcular_probabilidad_cierre()
            lead.determinar_temperatura()
            
            data = {
                'telefono': lead.telefono,
                'nombre': lead.nombre,
                'estado': lead.estado.value,
                'temperatura': lead.temperatura.value,
                'canal_origen': lead.canal_origen.value,
                'fecha_creacion': lead.fecha_creacion.isoformat(),
                'ultima_interaccion': lead.ultima_interaccion.isoformat(),
                'info_prospecto': json.dumps(lead.info_prospecto.to_dict()),
                'total_mensajes_recibidos': lead.total_mensajes_recibidos,
                'total_mensajes_enviados': lead.total_mensajes_enviados,
                'total_llamadas': lead.total_llamadas,
                'total_citas_agendadas': lead.total_citas_agendadas,
                'total_citas_completadas': lead.total_citas_completadas,
                'proximo_seguimiento': lead.proximo_seguimiento.isoformat() if lead.proximo_seguimiento else None,
                'asesor_asignado': lead.asesor_asignado,
                'notas_importantes': lead.notas_importantes,
                'score_calificacion': lead.score_calificacion,
                'probabilidad_cierre': lead.probabilidad_cierre,
                'valor_estimado_venta': lead.valor_estimado_venta,
                'email': lead.email,
                'ciudad': lead.ciudad,
                'fecha_nacimiento': lead.fecha_nacimiento.isoformat() if lead.fecha_nacimiento else None
            }
            
            # Verificar si existe
            existing = supabase.table(self.tabla_leads).select('telefono').eq('telefono', lead.telefono).execute()
            
            if existing.data:
                supabase.table(self.tabla_leads).update(data).eq('telefono', lead.telefono).execute()
                print(f"✅ Lead actualizado: {lead.telefono} - Score: {lead.score_calificacion}")
            else:
                supabase.table(self.tabla_leads).insert(data).execute()
                print(f"✅ Lead creado: {lead.telefono} - Score: {lead.score_calificacion}")
                
        except Exception as e:
            print(f"❌ Error guardando lead: {e}")
    
    def registrar_interaccion(self, interaccion: Interaccion):
        """Registra una interacción y actualiza métricas del lead"""
        if not supabase:
            print("❌ Supabase no disponible para registrar interacción")
            return
            
        try:
            # Guardar interacción
            data = interaccion.to_dict()
            supabase.table(self.tabla_interacciones).insert(data).execute()
            
            # Actualizar métricas del lead
            lead = self.obtener_lead(interaccion.telefono)
            if lead:
                lead.ultima_interaccion = interaccion.fecha
                
                if interaccion.tipo == TipoInteraccion.MENSAJE_ENTRANTE:
                    lead.total_mensajes_recibidos += 1
                elif interaccion.tipo in [TipoInteraccion.RESPUESTA_BOT, TipoInteraccion.WHATSAPP_SALIENTE]:
                    lead.total_mensajes_enviados += 1
                elif interaccion.tipo in [TipoInteraccion.LLAMADA_SALIENTE, TipoInteraccion.LLAMADA_ENTRANTE]:
                    lead.total_llamadas += 1
                elif interaccion.tipo == TipoInteraccion.CITA_AGENDADA:
                    lead.total_citas_agendadas += 1
                elif interaccion.tipo == TipoInteraccion.CITA_COMPLETADA:
                    lead.total_citas_completadas += 1
                
                self.guardar_lead(lead)
                
        except Exception as e:
            print(f"❌ Error registrando interacción: {e}")
    
    def actualizar_info_prospecto(self, telefono: str, campo: str, valor: any):
        """Actualiza información específica del prospecto"""
        lead = self.obtener_lead(telefono)
        if lead:
            setattr(lead.info_prospecto, campo, valor)
            self.guardar_lead(lead)
            
            # Registrar cambio
            interaccion = Interaccion(
                telefono=telefono,
                tipo=TipoInteraccion.CAMBIO_ESTADO,
                descripcion=f"Actualizado {campo}: {valor}",
                fecha=datetime.now(),
                usuario='bot',
                datos_adicionales={'campo': campo, 'valor': str(valor)}
            )
            self.registrar_interaccion(interaccion)
    
    def cambiar_estado(self, telefono: str, nuevo_estado: EstadoLead, notas: str = ""):
        """Cambia el estado de un lead"""
        lead = self.obtener_lead(telefono)
        if lead:
            estado_anterior = lead.estado
            lead.estado = nuevo_estado
            
            if notas:
                lead.notas_importantes += f"\n{datetime.now().strftime('%Y-%m-%d %H:%M')}: {notas}"
            
            self.guardar_lead(lead)
            
            # Registrar cambio de estado
            interaccion = Interaccion(
                telefono=telefono,
                tipo=TipoInteraccion.CAMBIO_ESTADO,
                descripcion=f"Estado cambió de {estado_anterior.value} a {nuevo_estado.value}",
                fecha=datetime.now(),
                usuario='sistema',
                datos_adicionales={
                    'estado_anterior': estado_anterior.value,
                    'estado_nuevo': nuevo_estado.value,
                    'notas': notas
                }
            )
            self.registrar_interaccion(interaccion)
    
    def programar_seguimiento(self, telefono: str, dias: int, tipo_seguimiento: str = "general"):
        """Programa un seguimiento futuro"""
        lead = self.obtener_lead(telefono)
        if lead:
            lead.proximo_seguimiento = datetime.now() + timedelta(days=dias)
            self.guardar_lead(lead)
            
            interaccion = Interaccion(
                telefono=telefono,
                tipo=TipoInteraccion.SEGUIMIENTO_PROGRAMADO,
                descripcion=f"Seguimiento programado para {dias} días ({tipo_seguimiento})",
                fecha=datetime.now(),
                usuario='sistema',
                datos_adicionales={'dias': dias, 'tipo': tipo_seguimiento}
            )
            self.registrar_interaccion(interaccion)
    
    def obtener_dashboard_metricas(self) -> Dict:
        """Obtiene métricas para dashboard de ventas"""
        if not supabase:
            return {'error': 'Supabase no disponible'}
            
        try:
            # Total de leads
            total_response = supabase.table(self.tabla_leads).select('telefono', count='exact').execute()
            total_leads = total_response.count if total_response.count else 0
            
            # Leads por estado
            estados_response = supabase.table(self.tabla_leads).select('estado').execute()
            estados = {}
            for lead in estados_response.data:
                estado = lead['estado']
                estados[estado] = estados.get(estado, 0) + 1
            
            # Leads por temperatura
            temp_response = supabase.table(self.tabla_leads).select('temperatura').execute()
            temperaturas = {}
            for lead in temp_response.data:
                temp = lead['temperatura']
                temperaturas[temp] = temperaturas.get(temp, 0) + 1
            
            return {
                'total_leads': total_leads,
                'por_estado': estados,
                'por_temperatura': temperaturas,
                'fecha_reporte': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error obteniendo métricas: {e}")
            return {'error': str(e)}
    
    def obtener_leads_por_prioridad(self, limite: int = 20) -> List[Lead]:
        """Obtiene leads ordenados por prioridad"""
        if not supabase:
            return []
            
        try:
            response = supabase.table(self.tabla_leads).select('*').order('score_calificacion', desc=True).limit(limite).execute()
            
            leads = []
            for data in response.data:
                lead = self.obtener_lead(data['telefono'])
                if lead and lead.estado not in [EstadoLead.VENDIDO, EstadoLead.PERDIDO_INTERES, EstadoLead.DESCALIFICADO]:
                    leads.append(lead)
            
            return leads
            
        except Exception as e:
            print(f"❌ Error obteniendo leads por prioridad: {e}")
            return []