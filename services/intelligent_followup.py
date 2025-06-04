# services/intelligent_followup.py
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import os
import sys
import random

# Agregar el directorio padre al path para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from models.lead_tracking import Lead, EstadoLead, TemperaturaMercado
    from services.sentiment_analyzer import SentimentAnalyzer
    from services.notification_system import NotificationSystem
except ImportError as e:
    print(f"⚠️ Error importando dependencias: {e}")

class IntelligentFollowup:
    """
    Sistema de seguimiento automático inteligente que adapta estrategias
    según el comportamiento y características de cada lead
    """
    
    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.notification_system = NotificationSystem()
        
        # Patrones de seguimiento por tipo de lead
        self.estrategias_seguimiento = {
            'caliente_urgente': {
                'intervalo_horas': [2, 4, 8, 24],
                'canales': ['whatsapp', 'llamada'],
                'mensajes_max': 4,
                'tono': 'urgente_amigable'
            },
            'caliente_normal': {
                'intervalo_horas': [6, 12, 24, 48],
                'canales': ['whatsapp'],
                'mensajes_max': 3,
                'tono': 'entusiasta'
            },
            'tibio_interesado': {
                'intervalo_horas': [24, 48, 72, 168],  # 1, 2, 3 días, 1 semana
                'canales': ['whatsapp'],
                'mensajes_max': 3,
                'tono': 'informativo'
            },
            'tibio_dudoso': {
                'intervalo_horas': [48, 96, 168],  # 2, 4 días, 1 semana
                'canales': ['whatsapp'],
                'mensajes_max': 2,
                'tono': 'educativo'
            },
            'frio_exploratorio': {
                'intervalo_horas': [168, 336, 672],  # 1, 2, 4 semanas
                'canales': ['whatsapp'],
                'mensajes_max': 2,
                'tono': 'valor_agregado'
            }
        }
        
        # Templates de mensajes por contexto
        self.templates_mensajes = {
            'urgente_amigable': [
                "¡Hola {nombre}! 😊 Vi que andas buscando auto. ¿Ya decidiste cuál te gusta más?",
                "¡{nombre}! ¿Te ayudo a agendar una cita hoy? Tengo súper ofertas 🚗",
                "¡Oye {nombre}! No dejes pasar las promociones de este mes 🔥"
            ],
            'entusiasta': [
                "¡Hola {nombre}! 😁 ¿Cómo vas con la decisión del auto?",
                "¡{nombre}! Te tengo novedades de los modelos que te interesan ✨",
                "¡Qué tal {nombre}! ¿Te paso más info de financiamiento? 💰"
            ],
            'informativo': [
                "Hola {nombre}, espero estés bien 😊 ¿Tienes alguna duda sobre los autos?",
                "¡{nombre}! Por si te sirve, aquí tienes la info actualizada de modelos 📋",
                "Hola {nombre} ¿Te gustaría que te mande las promociones actuales? 📢"
            ],
            'educativo': [
                "Hola {nombre} 👋 Te comparto algunos tips para elegir el auto perfecto",
                "¡{nombre}! ¿Sabías que tenemos planes especiales sin buró? 💡",
                "Hola {nombre}, aquí tienes una guía rápida de financiamiento 📖"
            ],
            'valor_agregado': [
                "Hola {nombre} 😊 Te comparto las últimas novedades de Nissan",
                "¡{nombre}! Nuevo catálogo disponible, por si gustas verlo 📱",
                "Hola {nombre}, tips de mantenimiento que te pueden interesar 🔧"
            ]
        }
    
    def clasificar_lead_para_seguimiento(self, lead: Lead, historial_sentimientos: List[Dict] = None) -> str:
        """
        Clasifica un lead para determinar la estrategia de seguimiento óptima
        """
        try:
            # Factores de clasificación
            score = lead.score_calificacion
            temperatura = lead.temperatura
            estado = lead.estado
            dias_sin_interaccion = lead.dias_sin_interaccion()
            urgencia_compra = lead.info_prospecto.urgencia_compra
            
            # Análisis de sentimientos históricos
            sentimiento_promedio = self._analizar_sentimientos_historicos(historial_sentimientos)
            
            # Lógica de clasificación
            if temperatura == TemperaturaMercado.CALIENTE:
                if urgencia_compra == 'inmediata' or score > 80:
                    return 'caliente_urgente'
                else:
                    return 'caliente_normal'
            
            elif temperatura == TemperaturaMercado.TIBIO:
                if sentimiento_promedio.get('nivel_interes', 'medio') == 'alto':
                    return 'tibio_interesado'
                else:
                    return 'tibio_dudoso'
            
            else:  # FRIO
                return 'frio_exploratorio'
                
        except Exception as e:
            print(f"❌ Error clasificando lead: {e}")
            return 'tibio_normal'  # Fallback seguro
    
    def generar_plan_seguimiento(self, lead: Lead, clasificacion: str = None) -> Dict:
        """
        Genera un plan de seguimiento personalizado para un lead
        """
        if not clasificacion:
            clasificacion = self.clasificar_lead_para_seguimiento(lead)
        
        estrategia = self.estrategias_seguimiento.get(clasificacion, self.estrategias_seguimiento['tibio_interesado'])
        
        # Calcular horarios óptimos basados en historial de interacciones
        horarios_optimos = self._calcular_horarios_optimos(lead)
        
        # Generar secuencia de seguimientos
        seguimientos = []
        fecha_base = datetime.now()
        
        for i, intervalo_horas in enumerate(estrategia['intervalo_horas']):
            if i >= estrategia['mensajes_max']:
                break
            
            fecha_seguimiento = fecha_base + timedelta(hours=intervalo_horas)
            
            # Ajustar a horario óptimo más cercano
            fecha_ajustada = self._ajustar_a_horario_optimo(fecha_seguimiento, horarios_optimos)
            
            # Seleccionar canal
            canal = estrategia['canales'][i % len(estrategia['canales'])]
            
            # Generar mensaje personalizado
            mensaje = self._generar_mensaje_personalizado(lead, estrategia['tono'], i)
            
            seguimientos.append({
                'fecha_programada': fecha_ajustada.isoformat(),
                'canal': canal,
                'mensaje': mensaje,
                'prioridad': self._calcular_prioridad(lead, i),
                'tipo_seguimiento': clasificacion,
                'intento_numero': i + 1
            })
        
        return {
            'lead_telefono': lead.telefono,
            'lead_nombre': lead.nombre,
            'clasificacion': clasificacion,
            'seguimientos_programados': seguimientos,
            'estrategia_aplicada': estrategia,
            'fecha_creacion_plan': datetime.now().isoformat(),
            'horarios_optimos_detectados': horarios_optimos
        }
    
    def ejecutar_seguimiento_inteligente(self, plan_seguimiento: Dict) -> Dict:
        """
        Ejecuta un seguimiento específico del plan
        """
        try:
            # Verificar si es el momento adecuado
            ahora = datetime.now()
            seguimientos_pendientes = [
                s for s in plan_seguimiento['seguimientos_programados']
                if datetime.fromisoformat(s['fecha_programada']) <= ahora
            ]
            
            if not seguimientos_pendientes:
                return {'ejecutado': False, 'razon': 'No hay seguimientos pendientes'}
            
            # Ejecutar el siguiente seguimiento
            siguiente = seguimientos_pendientes[0]
            
            # Aquí se integraría con el sistema de envío de mensajes
            resultado = self._enviar_mensaje_seguimiento(siguiente)
            
            # Registrar la ejecución
            if resultado['exito']:
                # Notificar si es alta prioridad
                if siguiente['prioridad'] >= 8:
                    self.notification_system.notificar_lead_caliente({
                        'telefono': plan_seguimiento['lead_telefono'],
                        'nombre': plan_seguimiento['lead_nombre'],
                        'mensaje': 'Ejecutando seguimiento de alta prioridad'
                    })
            
            return {
                'ejecutado': True,
                'seguimiento_realizado': siguiente,
                'resultado_envio': resultado,
                'siguiente_seguimiento': self._obtener_siguiente_seguimiento(plan_seguimiento, siguiente)
            }
            
        except Exception as e:
            print(f"❌ Error ejecutando seguimiento: {e}")
            return {'ejecutado': False, 'error': str(e)}
    
    def optimizar_horarios_seguimiento(self, telefono: str, historial_interacciones: List[Dict]) -> List[int]:
        """
        Analiza el historial para encontrar los mejores horarios de contacto
        """
        # Analizar horarios de respuesta del cliente
        horarios_respuesta = []
        
        for interaccion in historial_interacciones:
            if interaccion.get('tipo') == 'mensaje_entrante':
                try:
                    fecha = datetime.fromisoformat(interaccion['fecha'].replace('Z', '+00:00'))
                    horarios_respuesta.append(fecha.hour)
                except:
                    continue
        
        if not horarios_respuesta:
            return [10, 14, 18]  # Horarios por defecto
        
        # Encontrar los horarios más frecuentes
        frecuencia_horarios = {}
        for hora in horarios_respuesta:
            frecuencia_horarios[hora] = frecuencia_horarios.get(hora, 0) + 1
        
        # Ordenar por frecuencia y tomar los top 3
        horarios_optimos = sorted(frecuencia_horarios.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return [hora for hora, freq in horarios_optimos]
    
    def _analizar_sentimientos_historicos(self, historial_sentimientos: List[Dict]) -> Dict:
        """Analiza tendencias de sentimiento histórico"""
        if not historial_sentimientos:
            return {'nivel_interes': 'medio', 'tendencia': 'neutral'}
        
        # Analizar últimos sentimientos
        niveles_interes = [s.get('nivel_interes', 'medio') for s in historial_sentimientos[-5:]]
        
        # Determinar tendencia
        if niveles_interes.count('alto') > niveles_interes.count('bajo'):
            return {'nivel_interes': 'alto', 'tendencia': 'positiva'}
        elif niveles_interes.count('bajo') > niveles_interes.count('alto'):
            return {'nivel_interes': 'bajo', 'tendencia': 'negativa'}
        else:
            return {'nivel_interes': 'medio', 'tendencia': 'neutral'}
    
    def _calcular_horarios_optimos(self, lead: Lead) -> List[int]:
        """Calcula horarios óptimos para contactar al lead"""
        # Por defecto, horarios de negocio
        horarios_default = [9, 12, 15, 18]
        
        # Aquí se conectaría con el historial de interacciones
        # para encontrar patrones de respuesta
        
        return horarios_default
    
    def _ajustar_a_horario_optimo(self, fecha: datetime, horarios_optimos: List[int]) -> datetime:
        """Ajusta una fecha al horario óptimo más cercano"""
        hora_actual = fecha.hour
        
        # Encontrar el horario óptimo más cercano
        horario_cercano = min(horarios_optimos, key=lambda x: abs(x - hora_actual))
        
        # Ajustar la fecha
        fecha_ajustada = fecha.replace(hour=horario_cercano, minute=0, second=0, microsecond=0)
        
        # Si el horario ya pasó hoy, mover al siguiente día
        if fecha_ajustada <= datetime.now():
            fecha_ajustada += timedelta(days=1)
        
        return fecha_ajustada
    
    def _generar_mensaje_personalizado(self, lead: Lead, tono: str, intento: int) -> str:
        """Genera un mensaje personalizado según el contexto"""
        templates = self.templates_mensajes.get(tono, self.templates_mensajes['informativo'])
        
        # Seleccionar template (rotar para evitar repetición)
        template = templates[intento % len(templates)]
        
        # Personalizar con información del lead
        mensaje = template.format(
            nombre=lead.nombre,
            modelo=lead.info_prospecto.modelo_interes or 'auto',
            enganche=f"${lead.info_prospecto.monto_enganche:,.0f}" if lead.info_prospecto.monto_enganche else "con facilidades"
        )
        
        return mensaje
    
    def _calcular_prioridad(self, lead: Lead, intento: int) -> int:
        """Calcula la prioridad del seguimiento (1-10)"""
        prioridad_base = 5
        
        # Ajustar por temperatura
        if lead.temperatura == TemperaturaMercado.CALIENTE:
            prioridad_base += 3
        elif lead.temperatura == TemperaturaMercado.TIBIO:
            prioridad_base += 1
        
        # Ajustar por score
        if lead.score_calificacion > 80:
            prioridad_base += 2
        elif lead.score_calificacion > 60:
            prioridad_base += 1
        
        # Reducir prioridad con cada intento
        prioridad_base -= intento
        
        return max(1, min(10, prioridad_base))
    
    def _enviar_mensaje_seguimiento(self, seguimiento: Dict) -> Dict:
        """Simula el envío de un mensaje de seguimiento"""
        # Aquí se integraría con Twilio o el sistema de mensajería
        return {
            'exito': True,
            'canal_usado': seguimiento['canal'],
            'mensaje_enviado': seguimiento['mensaje'],
            'timestamp': datetime.now().isoformat()
        }
    
    def _obtener_siguiente_seguimiento(self, plan: Dict, ejecutado: Dict) -> Optional[Dict]:
        """Obtiene el siguiente seguimiento programado"""
        seguimientos = plan['seguimientos_programados']
        
        try:
            indice_actual = seguimientos.index(ejecutado)
            if indice_actual < len(seguimientos) - 1:
                return seguimientos[indice_actual + 1]
        except ValueError:
            pass
        
        return None

def generar_plan_seguimiento_para_lead(lead: Lead) -> Dict:
    """
    Función helper para generar plan de seguimiento
    """
    followup_system = IntelligentFollowup()
    return followup_system.generar_plan_seguimiento(lead)