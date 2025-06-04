# services/advanced_dashboard.py
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os
import sys

# Agregar el directorio padre al path para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from supabase_client import supabase
    from models.lead_tracking import EstadoLead, TemperaturaMercado
except ImportError as e:
    print(f"⚠️ Error importando dependencias: {e}")
    supabase = None

class AdvancedDashboard:
    """
    Dashboard avanzado con métricas de negocio, ROI y análisis predictivo
    """
    
    def __init__(self):
        self.tabla_leads = 'leads_tracking_pro'
        self.tabla_interacciones = 'interacciones_leads'
        
    def obtener_metricas_conversion(self, dias: int = 30) -> Dict:
        """
        Calcula métricas de conversión y funnel de ventas
        """
        if not supabase:
            return {'error': 'Supabase no disponible'}
        
        try:
            fecha_limite = (datetime.now() - timedelta(days=dias)).isoformat()
            
            # Obtener todos los leads del período
            response = supabase.table(self.tabla_leads).select('*').gte('fecha_creacion', fecha_limite).execute()
            leads = response.data
            
            if not leads:
                return {'total_leads': 0, 'mensaje': 'No hay datos en el período especificado'}
            
            # Análisis del funnel
            funnel = {
                'contacto_inicial': 0,
                'calificando': 0,
                'calificado': 0,
                'interesado_alto': 0,
                'cita_agendada': 0,
                'vendido': 0,
                'perdidos': 0
            }
            
            temperaturas = {'caliente': 0, 'tibio': 0, 'frio': 0}
            scores = []
            canales = {}
            
            for lead in leads:
                estado = lead.get('estado', '')
                temperatura = lead.get('temperatura', '')
                score = float(lead.get('score_calificacion', 0))
                canal = lead.get('canal_origen', 'desconocido')
                
                # Conteo por estado
                if estado in funnel:
                    funnel[estado] += 1
                elif estado in ['perdido_precio', 'perdido_credito', 'perdido_interes', 'descalificado']:
                    funnel['perdidos'] += 1
                
                # Conteo por temperatura
                if temperatura in temperaturas:
                    temperaturas[temperatura] += 1
                
                scores.append(score)
                canales[canal] = canales.get(canal, 0) + 1
            
            # Calcular tasas de conversión
            total_leads = len(leads)
            tasa_calificacion = (funnel['calificado'] / total_leads * 100) if total_leads > 0 else 0
            tasa_interes_alto = (funnel['interesado_alto'] / total_leads * 100) if total_leads > 0 else 0
            tasa_cita = (funnel['cita_agendada'] / total_leads * 100) if total_leads > 0 else 0
            tasa_cierre = (funnel['vendido'] / total_leads * 100) if total_leads > 0 else 0
            
            score_promedio = sum(scores) / len(scores) if scores else 0
            
            return {
                'periodo_dias': dias,
                'total_leads': total_leads,
                'funnel_conversion': funnel,
                'tasas_conversion': {
                    'calificacion': round(tasa_calificacion, 2),
                    'interes_alto': round(tasa_interes_alto, 2),
                    'cita_agendada': round(tasa_cita, 2),
                    'cierre': round(tasa_cierre, 2)
                },
                'distribucion_temperatura': temperaturas,
                'score_promedio': round(score_promedio, 2),
                'canales_origen': canales,
                'fecha_reporte': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error calculando métricas de conversión: {e}")
            return {'error': str(e)}
    
    def obtener_metricas_tiempo_respuesta(self, dias: int = 7) -> Dict:
        """
        Analiza tiempos de respuesta y patrones de comunicación
        """
        if not supabase:
            return {'error': 'Supabase no disponible'}
        
        try:
            fecha_limite = (datetime.now() - timedelta(days=dias)).isoformat()
            
            # Obtener interacciones recientes
            response = supabase.table(self.tabla_interacciones).select('*').gte('fecha', fecha_limite).order('fecha').execute()
            interacciones = response.data
            
            if not interacciones:
                return {'mensaje': 'No hay interacciones en el período'}
            
            # Agrupar por teléfono para calcular tiempos
            conversaciones = {}
            for interaccion in interacciones:
                telefono = interaccion['telefono']
                if telefono not in conversaciones:
                    conversaciones[telefono] = []
                conversaciones[telefono].append(interaccion)
            
            tiempos_respuesta = []
            patrones_horarios = {}
            
            for telefono, mensajes in conversaciones.items():
                mensajes.sort(key=lambda x: x['fecha'])
                
                for i in range(len(mensajes) - 1):
                    msg_actual = mensajes[i]
                    msg_siguiente = mensajes[i + 1]
                    
                    # Si el mensaje actual es del cliente y el siguiente del bot
                    if (msg_actual.get('tipo') == 'mensaje_entrante' and 
                        msg_siguiente.get('tipo') == 'respuesta_bot'):
                        
                        try:
                            tiempo_actual = datetime.fromisoformat(msg_actual['fecha'].replace('Z', '+00:00'))
                            tiempo_respuesta = datetime.fromisoformat(msg_siguiente['fecha'].replace('Z', '+00:00'))
                            
                            diferencia = (tiempo_respuesta - tiempo_actual).total_seconds() / 60  # en minutos
                            if diferencia > 0 and diferencia < 1440:  # menos de 24 horas
                                tiempos_respuesta.append(diferencia)
                                
                                # Patrón horario
                                hora = tiempo_actual.hour
                                patrones_horarios[hora] = patrones_horarios.get(hora, 0) + 1
                                
                        except Exception:
                            continue
            
            # Calcular estadísticas
            if tiempos_respuesta:
                tiempo_promedio = sum(tiempos_respuesta) / len(tiempos_respuesta)
                tiempo_mediano = sorted(tiempos_respuesta)[len(tiempos_respuesta) // 2]
                tiempo_max = max(tiempos_respuesta)
                tiempo_min = min(tiempos_respuesta)
            else:
                tiempo_promedio = tiempo_mediano = tiempo_max = tiempo_min = 0
            
            return {
                'periodo_dias': dias,
                'total_interacciones': len(interacciones),
                'conversaciones_analizadas': len(conversaciones),
                'tiempos_respuesta': {
                    'promedio_minutos': round(tiempo_promedio, 2),
                    'mediano_minutos': round(tiempo_mediano, 2),
                    'maximo_minutos': round(tiempo_max, 2),
                    'minimo_minutos': round(tiempo_min, 2)
                },
                'patrones_horarios': patrones_horarios,
                'total_respuestas_analizadas': len(tiempos_respuesta)
            }
            
        except Exception as e:
            print(f"❌ Error calculando métricas de tiempo: {e}")
            return {'error': str(e)}
    
    def obtener_analisis_roi(self, dias: int = 30) -> Dict:
        """
        Calcula ROI estimado y valor del pipeline
        """
        try:
            # Valores estimados promedio (configurables)
            PRECIO_PROMEDIO_AUTO = 350000  # Pesos mexicanos
            COMISION_PROMEDIO = 0.05  # 5%
            COSTO_LEAD = 50  # Costo promedio por lead
            
            metricas = self.obtener_metricas_conversion(dias)
            
            if 'error' in metricas:
                return metricas
            
            total_leads = metricas.get('total_leads', 0)
            vendidos = metricas.get('funnel_conversion', {}).get('vendido', 0)
            citas_agendadas = metricas.get('funnel_conversion', {}).get('cita_agendada', 0)
            interesados_alto = metricas.get('funnel_conversion', {}).get('interesado_alto', 0)
            
            # Cálculos de ROI
            inversion_total = total_leads * COSTO_LEAD
            ingresos_reales = vendidos * PRECIO_PROMEDIO_AUTO * COMISION_PROMEDIO
            
            # Pipeline value (valor potencial)
            pipeline_citas = citas_agendadas * PRECIO_PROMEDIO_AUTO * COMISION_PROMEDIO * 0.3  # 30% close rate
            pipeline_interesados = interesados_alto * PRECIO_PROMEDIO_AUTO * COMISION_PROMEDIO * 0.15  # 15% close rate
            
            roi_actual = ((ingresos_reales - inversion_total) / inversion_total * 100) if inversion_total > 0 else 0
            roi_potencial = ((ingresos_reales + pipeline_citas + pipeline_interesados - inversion_total) / inversion_total * 100) if inversion_total > 0 else 0
            
            return {
                'periodo_dias': dias,
                'inversion_total': inversion_total,
                'ingresos_reales': round(ingresos_reales, 2),
                'valor_pipeline': round(pipeline_citas + pipeline_interesados, 2),
                'roi_actual_porcentaje': round(roi_actual, 2),
                'roi_potencial_porcentaje': round(roi_potencial, 2),
                'costo_por_lead': COSTO_LEAD,
                'costo_por_venta': round(inversion_total / vendidos, 2) if vendidos > 0 else 0,
                'leads_necesarios_break_even': round(inversion_total / (PRECIO_PROMEDIO_AUTO * COMISION_PROMEDIO)) if PRECIO_PROMEDIO_AUTO > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error calculando ROI: {e}")
            return {'error': str(e)}
    
    def obtener_analisis_predictivo(self) -> Dict:
        """
        Análisis predictivo basado en patrones históricos
        """
        try:
            # Obtener datos de los últimos 60 días para análisis de tendencias
            metricas_60d = self.obtener_metricas_conversion(60)
            metricas_30d = self.obtener_metricas_conversion(30)
            metricas_7d = self.obtener_metricas_conversion(7)
            
            if any('error' in m for m in [metricas_60d, metricas_30d, metricas_7d]):
                return {'error': 'No se pudieron obtener datos para análisis predictivo'}
            
            # Calcular tendencias
            tendencia_leads = self._calcular_tendencia(
                metricas_60d.get('total_leads', 0),
                metricas_30d.get('total_leads', 0),
                metricas_7d.get('total_leads', 0)
            )
            
            tendencia_conversion = self._calcular_tendencia(
                metricas_60d.get('tasas_conversion', {}).get('cierre', 0),
                metricas_30d.get('tasas_conversion', {}).get('cierre', 0),
                metricas_7d.get('tasas_conversion', {}).get('cierre', 0)
            )
            
            # Predicciones para próximos 30 días
            leads_predichos = round(metricas_7d.get('total_leads', 0) * 4.3)  # 7 días * 4.3 ≈ 30 días
            ventas_predichas = round(leads_predichos * (metricas_30d.get('tasas_conversion', {}).get('cierre', 0) / 100))
            
            return {
                'tendencias': {
                    'leads': tendencia_leads,
                    'conversion': tendencia_conversion
                },
                'predicciones_30_dias': {
                    'leads_esperados': leads_predichos,
                    'ventas_esperadas': ventas_predichas,
                    'confianza': 'media'  # Basado en cantidad de datos históricos
                },
                'recomendaciones': self._generar_recomendaciones(metricas_30d),
                'fecha_analisis': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error en análisis predictivo: {e}")
            return {'error': str(e)}
    
    def _calcular_tendencia(self, valor_60d: float, valor_30d: float, valor_7d: float) -> str:
        """Calcula si la tendencia es creciente, decreciente o estable"""
        if valor_7d > valor_30d * 1.1:
            return 'creciente'
        elif valor_7d < valor_30d * 0.9:
            return 'decreciente'
        else:
            return 'estable'
    
    def _generar_recomendaciones(self, metricas: Dict) -> List[str]:
        """Genera recomendaciones basadas en las métricas"""
        recomendaciones = []
        
        tasa_cierre = metricas.get('tasas_conversion', {}).get('cierre', 0)
        tasa_cita = metricas.get('tasas_conversion', {}).get('cita_agendada', 0)
        
        if tasa_cierre < 5:
            recomendaciones.append("Mejorar proceso de cierre - tasa de conversión baja")
        
        if tasa_cita < 15:
            recomendaciones.append("Incrementar agendado de citas - muchos leads se pierden antes de la cita")
        
        temperaturas = metricas.get('distribucion_temperatura', {})
        if temperaturas.get('frio', 0) > temperaturas.get('caliente', 0) * 2:
            recomendaciones.append("Mejorar calificación de leads - muchos leads fríos")
        
        return recomendaciones

def generar_reporte_completo(dias: int = 30) -> Dict:
    """
    Genera un reporte completo con todas las métricas avanzadas
    """
    dashboard = AdvancedDashboard()
    
    return {
        'conversion_metrics': dashboard.obtener_metricas_conversion(dias),
        'response_time_metrics': dashboard.obtener_metricas_tiempo_respuesta(7),
        'roi_analysis': dashboard.obtener_analisis_roi(dias),
        'predictive_analysis': dashboard.obtener_analisis_predictivo(),
        'generated_at': datetime.now().isoformat()
    }