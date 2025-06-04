# models/lead_tracking.py
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import json

class EstadoLead(Enum):
    CONTACTO_INICIAL = "contacto_inicial"
    CALIFICANDO = "calificando"
    CALIFICADO = "calificado"
    INTERESADO_ALTO = "interesado_alto"
    COTIZADO = "cotizado"
    SEGUIMIENTO_ACTIVO = "seguimiento_activo"
    CITA_AGENDADA = "cita_agendada"
    EN_AGENCIA = "en_agencia"
    PRUEBA_MANEJO = "prueba_manejo"
    NEGOCIANDO = "negociando"
    VENDIDO = "vendido"
    PERDIDO_PRECIO = "perdido_precio"
    PERDIDO_CREDITO = "perdido_credito"
    PERDIDO_INTERES = "perdido_interes"
    DESCALIFICADO = "descalificado"

class TipoInteraccion(Enum):
    MENSAJE_ENTRANTE = "mensaje_entrante"
    RESPUESTA_BOT = "respuesta_bot"
    LLAMADA_SALIENTE = "llamada_saliente"
    LLAMADA_ENTRANTE = "llamada_entrante"
    WHATSAPP_SALIENTE = "whatsapp_saliente"
    EMAIL_ENVIADO = "email_enviado"
    CITA_AGENDADA = "cita_agendada"
    CITA_COMPLETADA = "cita_completada"
    CITA_PERDIDA = "cita_perdida"
    COTIZACION_ENVIADA = "cotizacion_enviada"
    DOCUMENTO_ENVIADO = "documento_enviado"
    SEGUIMIENTO_PROGRAMADO = "seguimiento_programado"
    CAMBIO_ESTADO = "cambio_estado"

class CanalOrigen(Enum):
    FACEBOOK_ADS = "facebook_ads"
    INSTAGRAM_ADS = "instagram_ads"
    GOOGLE_ADS = "google_ads"
    WHATSAPP_DIRECTO = "whatsapp_directo"
    REFERENCIA = "referencia"
    PAGINA_WEB = "pagina_web"
    LLAMADA_DIRECTA = "llamada_directa"

class TemperaturaMercado(Enum):
    CALIENTE = "caliente"
    TIBIO = "tibio"
    FRIO = "frio"

class PrioridadLead(Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"

@dataclass
class ProspectoInfo:
    uso_vehiculo: Optional[str] = None
    comprobacion_ingresos: Optional[str] = None
    monto_enganche: Optional[float] = None
    historial_credito: Optional[str] = None
    ingresos_mensuales: Optional[float] = None
    ciudad: Optional[str] = None
    ocupacion: Optional[str] = None
    edad_aproximada: Optional[int] = None
    tiene_auto_actual: Optional[bool] = None
    modelo_interes: Optional[str] = None
    presupuesto_maximo: Optional[float] = None
    urgencia_compra: Optional[str] = None
    
    def to_dict(self):
        return {
            'uso_vehiculo': self.uso_vehiculo,
            'comprobacion_ingresos': self.comprobacion_ingresos,
            'monto_enganche': self.monto_enganche,
            'historial_credito': self.historial_credito,
            'ingresos_mensuales': self.ingresos_mensuales,
            'ciudad': self.ciudad,
            'ocupacion': self.ocupacion,
            'edad_aproximada': self.edad_aproximada,
            'tiene_auto_actual': self.tiene_auto_actual,
            'modelo_interes': self.modelo_interes,
            'presupuesto_maximo': self.presupuesto_maximo,
            'urgencia_compra': self.urgencia_compra
        }

@dataclass
class Lead:
    telefono: str
    nombre: str
    estado: EstadoLead
    temperatura: TemperaturaMercado
    canal_origen: CanalOrigen
    fecha_creacion: datetime
    ultima_interaccion: datetime
    
    info_prospecto: ProspectoInfo = field(default_factory=ProspectoInfo)
    
    total_mensajes_recibidos: int = 0
    total_mensajes_enviados: int = 0
    total_llamadas: int = 0
    total_citas_agendadas: int = 0
    total_citas_completadas: int = 0
    
    proximo_seguimiento: Optional[datetime] = None
    asesor_asignado: Optional[str] = None
    notas_importantes: str = ""
    
    score_calificacion: float = 0.0
    probabilidad_cierre: float = 0.0
    valor_estimado_venta: float = 0.0
    
    email: Optional[str] = None
    ciudad: Optional[str] = None
    fecha_nacimiento: Optional[datetime] = None
    
    def calcular_score(self) -> float:
        score = 0.0
        
        if self.telefono: score += 5
        if self.email: score += 5
        
        if self.info_prospecto.comprobacion_ingresos == "formal":
            score += 20
        elif self.info_prospecto.comprobacion_ingresos == "informal":
            score += 10
            
        if self.info_prospecto.monto_enganche:
            if self.info_prospecto.monto_enganche >= 50000:
                score += 20
            elif self.info_prospecto.monto_enganche >= 30000:
                score += 15
            elif self.info_prospecto.monto_enganche >= 15000:
                score += 10
            else:
                score += 5
                
        if self.info_prospecto.historial_credito == "bueno":
            score += 20
        elif self.info_prospecto.historial_credito == "regular":
            score += 10
        elif self.info_prospecto.historial_credito == "malo":
            score += 5
            
        if self.total_mensajes_recibidos >= 5:
            score += 10
        elif self.total_mensajes_recibidos >= 2:
            score += 5
            
        if self.total_citas_agendadas > 0:
            score += 10
            
        if self.info_prospecto.urgencia_compra == "inmediata":
            score += 10
        elif self.info_prospecto.urgencia_compra == "3meses":
            score += 7
        elif self.info_prospecto.urgencia_compra == "6meses":
            score += 5
            
        self.score_calificacion = min(score, 100.0)
        return self.score_calificacion
    
    def calcular_probabilidad_cierre(self) -> float:
        base_score = self.calcular_score()
        
        multiplicadores = {
            EstadoLead.CONTACTO_INICIAL: 0.1,
            EstadoLead.CALIFICANDO: 0.2,
            EstadoLead.CALIFICADO: 0.3,
            EstadoLead.INTERESADO_ALTO: 0.5,
            EstadoLead.COTIZADO: 0.6,
            EstadoLead.SEGUIMIENTO_ACTIVO: 0.7,
            EstadoLead.CITA_AGENDADA: 0.8,
            EstadoLead.EN_AGENCIA: 0.85,
            EstadoLead.PRUEBA_MANEJO: 0.9,
            EstadoLead.NEGOCIANDO: 0.95,
            EstadoLead.VENDIDO: 1.0,
            EstadoLead.PERDIDO_PRECIO: 0.0,
            EstadoLead.PERDIDO_CREDITO: 0.0,
            EstadoLead.PERDIDO_INTERES: 0.0,
            EstadoLead.DESCALIFICADO: 0.0
        }
        
        multiplicador = multiplicadores.get(self.estado, 0.1)
        self.probabilidad_cierre = base_score * multiplicador
        return self.probabilidad_cierre
    
    def determinar_temperatura(self):
        if (self.total_mensajes_recibidos >= 3 and 
            self.info_prospecto.urgencia_compra == "inmediata" and
            self.score_calificacion >= 70):
            self.temperatura = TemperaturaMercado.CALIENTE
        elif (self.total_mensajes_recibidos >= 2 and 
              self.score_calificacion >= 40):
            self.temperatura = TemperaturaMercado.TIBIO
        else:
            self.temperatura = TemperaturaMercado.FRIO
    
    def dias_sin_interaccion(self) -> int:
        ahora = datetime.now()
        if self.ultima_interaccion:
            # Asegurar que ambas fechas sean naive o aware
            if self.ultima_interaccion.tzinfo is not None:
                # Si ultima_interaccion es aware, hacer ahora aware también
                import pytz
                ahora = ahora.replace(tzinfo=pytz.UTC)
            return (ahora - self.ultima_interaccion).days
        return 0
    
    def to_dict(self):
        return {
            'telefono': self.telefono,
            'nombre': self.nombre,
            'estado': self.estado.value,
            'temperatura': self.temperatura.value,
            'canal_origen': self.canal_origen.value,
            'fecha_creacion': self.fecha_creacion.isoformat(),
            'ultima_interaccion': self.ultima_interaccion.isoformat(),
            'info_prospecto': json.dumps(self.info_prospecto.to_dict()),
            'total_mensajes_recibidos': self.total_mensajes_recibidos,
            'total_mensajes_enviados': self.total_mensajes_enviados,
            'total_llamadas': self.total_llamadas,
            'total_citas_agendadas': self.total_citas_agendadas,
            'total_citas_completadas': self.total_citas_completadas,
            'proximo_seguimiento': self.proximo_seguimiento.isoformat() if self.proximo_seguimiento else None,
            'asesor_asignado': self.asesor_asignado,
            'notas_importantes': self.notas_importantes,
            'score_calificacion': self.score_calificacion,
            'probabilidad_cierre': self.probabilidad_cierre,
            'valor_estimado_venta': self.valor_estimado_venta,
            'email': self.email,
            'ciudad': self.ciudad,
            'fecha_nacimiento': self.fecha_nacimiento.isoformat() if self.fecha_nacimiento else None
        }

@dataclass
class Interaccion:
    telefono: str
    tipo: TipoInteraccion
    descripcion: str
    fecha: datetime
    usuario: str
    duracion_segundos: Optional[int] = None
    resultado: Optional[str] = None
    datos_adicionales: Optional[Dict[str, Any]] = None
    
    def to_dict(self):
        return {
            'telefono': self.telefono,
            'tipo': self.tipo.value,
            'descripcion': self.descripcion,
            'fecha': self.fecha.isoformat(),
            'usuario': self.usuario,
            'duracion_segundos': self.duracion_segundos,
            'resultado': self.resultado,
            'datos_adicionales': json.dumps(self.datos_adicionales) if self.datos_adicionales else None
        }