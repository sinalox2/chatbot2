# services/sentiment_analyzer.py
import re
from typing import Dict, Tuple
from datetime import datetime
import openai
import os
from dotenv import load_dotenv

load_dotenv()

class SentimentAnalyzer:
    """
    Sistema avanzado de análisis de sentimientos para optimizar respuestas del bot
    """
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Patrones emocionales básicos para análisis rápido
        self.patrones_emocionales = {
            'frustracion': [
                'molesto', 'enojado', 'fastidio', 'cansado', 'harto', 'ya no',
                'terrible', 'malo', 'pesimo', 'pésimo', 'horrible', 'odio'
            ],
            'entusiasmo': [
                'genial', 'excelente', 'perfecto', 'increible', 'increíble', 'wow',
                'súper', 'padrísimo', 'chévere', 'buenísimo', 'me encanta'
            ],
            'urgencia': [
                'urgente', 'rápido', 'ya', 'ahorita', 'inmediato', 'pronto',
                'necesito ya', 'cuanto antes', 'hoy mismo'
            ],
            'dudas': [
                'no sé', 'no estoy seguro', 'tal vez', 'quizás', 'duda',
                'pensando', 'viendo opciones', 'comparando'
            ],
            'precio_sensible': [
                'caro', 'costoso', 'mucho dinero', 'no tengo', 'económico',
                'barato', 'descuento', 'oferta', 'financiamiento'
            ]
        }
    
    def analizar_sentimiento_basico(self, mensaje: str) -> Dict[str, any]:
        """
        Análisis rápido basado en patrones predefinidos
        """
        mensaje_lower = mensaje.lower()
        sentimientos_detectados = []
        
        for sentimiento, patrones in self.patrones_emocionales.items():
            for patron in patrones:
                if patron in mensaje_lower:
                    sentimientos_detectados.append(sentimiento)
                    break
        
        # Análisis de longitud y puntuación
        longitud = len(mensaje)
        signos_exclamacion = mensaje.count('!')
        signos_pregunta = mensaje.count('?')
        mayusculas_ratio = sum(1 for c in mensaje if c.isupper()) / len(mensaje) if mensaje else 0
        
        return {
            'sentimientos': sentimientos_detectados,
            'longitud_mensaje': longitud,
            'exclamaciones': signos_exclamacion,
            'preguntas': signos_pregunta,
            'mayusculas_ratio': mayusculas_ratio,
            'tipo_mensaje': self._clasificar_tipo_mensaje(mensaje_lower)
        }
    
    def analizar_sentimiento_avanzado(self, mensaje: str, historial: list = None) -> Dict[str, any]:
        """
        Análisis avanzado usando OpenAI para mayor precisión
        """
        try:
            # Construir prompt con contexto
            prompt = f"""
            Analiza el sentimiento y intención del siguiente mensaje de un cliente potencial de autos:
            
            Mensaje: "{mensaje}"
            
            Proporciona un análisis en formato JSON con:
            1. sentimiento_principal: (positivo/neutral/negativo)
            2. emociones_detectadas: [lista de emociones]
            3. nivel_interes: (alto/medio/bajo)
            4. urgencia_compra: (inmediata/3meses/6meses/exploratoria)
            5. precio_sensibilidad: (alta/media/baja)
            6. recomendacion_respuesta: (entusiasta/calmada/informativa/empática)
            7. probabilidad_cierre: (0-100)
            
            Responde solo con JSON válido.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            import json
            resultado_ai = json.loads(response.choices[0].message.content)
            
            # Combinar con análisis básico
            resultado_basico = self.analizar_sentimiento_basico(mensaje)
            
            return {
                **resultado_ai,
                'analisis_basico': resultado_basico,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error en análisis avanzado: {e}")
            # Fallback al análisis básico
            return self.analizar_sentimiento_basico(mensaje)
    
    def _clasificar_tipo_mensaje(self, mensaje: str) -> str:
        """Clasifica el tipo de mensaje"""
        if any(word in mensaje for word in ['precio', 'costo', 'cuanto', 'cuánto']):
            return 'consulta_precio'
        elif any(word in mensaje for word in ['cuando', 'cuándo', 'cita', 'visita']):
            return 'solicitud_cita'
        elif any(word in mensaje for word in ['info', 'información', 'detalles']):
            return 'solicitud_info'
        elif any(word in mensaje for word in ['hola', 'buenas', 'saludo']):
            return 'saludo'
        elif any(word in mensaje for word in ['gracias', 'ok', 'entiendo']):
            return 'confirmacion'
        else:
            return 'conversacion_general'
    
    def sugerir_estrategia_respuesta(self, analisis: Dict) -> Dict[str, str]:
        """
        Sugiere estrategia de respuesta basada en el análisis de sentimiento
        """
        estrategia = {
            'tono': 'amigable',
            'velocidad': 'normal',
            'enfoque': 'informativo',
            'emojis': True,
            'urgencia': False
        }
        
        # Ajustar según sentimientos detectados
        if 'frustracion' in analisis.get('sentimientos', []):
            estrategia.update({
                'tono': 'empático',
                'enfoque': 'solución_problemas',
                'emojis': False
            })
        
        if 'entusiasmo' in analisis.get('sentimientos', []):
            estrategia.update({
                'tono': 'entusiasta',
                'emojis': True,
                'enfoque': 'aprovechamiento_momentum'
            })
        
        if 'urgencia' in analisis.get('sentimientos', []):
            estrategia.update({
                'velocidad': 'rápida',
                'urgencia': True,
                'enfoque': 'acción_inmediata'
            })
        
        if 'precio_sensible' in analisis.get('sentimientos', []):
            estrategia.update({
                'enfoque': 'valor_beneficios',
                'mencionar_financiamiento': True
            })
        
        return estrategia
    
    def obtener_metricas_sentimiento(self, telefono: str, dias: int = 7) -> Dict:
        """
        Obtiene métricas de sentimiento para un lead específico
        """
        # Esta función se conectaría con la base de datos para obtener
        # el historial de sentimientos del cliente
        return {
            'tendencia_sentimiento': 'mejorando',
            'nivel_interes_promedio': 75,
            'momentos_criticos': [],
            'recomendaciones': ['Enviar información de financiamiento']
        }

# Función helper para uso fácil en app.py
def analizar_mensaje_cliente(mensaje: str, usar_ai: bool = True) -> Dict:
    """
    Función helper para análisis rápido de sentimientos
    """
    analyzer = SentimentAnalyzer()
    if usar_ai:
        return analyzer.analizar_sentimiento_avanzado(mensaje)
    else:
        return analyzer.analizar_sentimiento_basico(mensaje)