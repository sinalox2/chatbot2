# services/notification_system.py
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class NotificationSystem:
    """
    Sistema de notificaciones push para alertas en tiempo real
    Soporta Slack, Discord, Teams, Email y Webhooks
    """
    
    def __init__(self):
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        self.teams_webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
        self.email_config = {
            'smtp_server': os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            'smtp_port': int(os.getenv("SMTP_PORT", "587")),
            'email_user': os.getenv("EMAIL_USER"),
            'email_password': os.getenv("EMAIL_PASSWORD"),
            'email_to': os.getenv("NOTIFICATION_EMAIL")
        }
    
    def send_slack_notification(self, mensaje: str, urgencia: str = "info", datos_adicionales: Dict = None) -> bool:
        """
        Envía notificación a Slack
        """
        if not self.slack_webhook_url:
            print("⚠️ Slack webhook no configurado")
            return False
        
        try:
            # Determinar color según urgencia
            colores = {
                "critical": "#FF0000",  # Rojo
                "warning": "#FFA500",   # Naranja
                "info": "#36a64f",      # Verde
                "success": "#36a64f"    # Verde
            }
            
            color = colores.get(urgencia, "#36a64f")
            
            # Construir payload
            payload = {
                "text": f"🚗 Nissan Bot - {urgencia.upper()}",
                "attachments": [
                    {
                        "color": color,
                        "fields": [
                            {
                                "title": "Mensaje",
                                "value": mensaje,
                                "short": False
                            },
                            {
                                "title": "Timestamp",
                                "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            # Agregar datos adicionales si los hay
            if datos_adicionales:
                for key, value in datos_adicionales.items():
                    payload["attachments"][0]["fields"].append({
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": True
                    })
            
            response = requests.post(
                self.slack_webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ Error enviando notificación Slack: {e}")
            return False
    
    def send_discord_notification(self, mensaje: str, urgencia: str = "info") -> bool:
        """
        Envía notificación a Discord
        """
        if not self.discord_webhook_url:
            print("⚠️ Discord webhook no configurado")
            return False
        
        try:
            # Emojis según urgencia
            emojis = {
                "critical": "🚨",
                "warning": "⚠️",
                "info": "ℹ️",
                "success": "✅"
            }
            
            emoji = emojis.get(urgencia, "ℹ️")
            
            payload = {
                "content": f"{emoji} **Nissan Bot - {urgencia.upper()}**\n{mensaje}",
                "username": "Nissan Bot Notifications"
            }
            
            response = requests.post(
                self.discord_webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            return response.status_code == 204
            
        except Exception as e:
            print(f"❌ Error enviando notificación Discord: {e}")
            return False
    
    def send_email_notification(self, asunto: str, mensaje: str) -> bool:
        """
        Envía notificación por email
        """
        if not all([self.email_config['email_user'], self.email_config['email_password'], self.email_config['email_to']]):
            print("⚠️ Configuración de email incompleta")
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.email_config['email_user']
            msg['To'] = self.email_config['email_to']
            msg['Subject'] = f"🚗 Nissan Bot - {asunto}"
            
            # Agregar timestamp al mensaje
            mensaje_completo = f"{mensaje}\n\n---\nEnviado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            msg.attach(MIMEText(mensaje_completo, 'plain'))
            
            # Enviar email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['email_user'], self.email_config['email_password'])
            text = msg.as_string()
            server.sendmail(self.email_config['email_user'], self.email_config['email_to'], text)
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"❌ Error enviando email: {e}")
            return False
    
    def notificar_lead_caliente(self, lead_info: Dict) -> bool:
        """
        Notifica cuando un lead se vuelve caliente
        """
        mensaje = f"""
🔥 LEAD CALIENTE DETECTADO

👤 Cliente: {lead_info.get('nombre', 'Desconocido')}
📞 Teléfono: {lead_info.get('telefono', 'N/A')}
📊 Score: {lead_info.get('score', 0)}/100
🎯 Estado: {lead_info.get('estado', 'N/A')}
⏰ Último contacto: {lead_info.get('ultima_interaccion', 'N/A')}

¡Contactar ASAP!
        """.strip()
        
        datos_adicionales = {
            "telefono": lead_info.get('telefono'),
            "score": f"{lead_info.get('score', 0)}/100",
            "estado": lead_info.get('estado')
        }
        
        # Enviar a todos los canales configurados
        resultados = []
        resultados.append(self.send_slack_notification(mensaje, "warning", datos_adicionales))
        resultados.append(self.send_discord_notification(mensaje, "warning"))
        
        return any(resultados)
    
    def notificar_lead_sin_respuesta(self, lead_info: Dict, horas_sin_respuesta: int) -> bool:
        """
        Notifica cuando un lead lleva mucho tiempo sin respuesta
        """
        mensaje = f"""
⏰ LEAD SIN RESPUESTA

👤 Cliente: {lead_info.get('nombre', 'Desconocido')}
📞 Teléfono: {lead_info.get('telefono', 'N/A')}
🕐 Sin respuesta: {horas_sin_respuesta} horas
🎯 Estado: {lead_info.get('estado', 'N/A')}
📊 Score: {lead_info.get('score', 0)}/100

Revisar seguimiento.
        """.strip()
        
        urgencia = "critical" if horas_sin_respuesta > 24 else "warning"
        
        datos_adicionales = {
            "telefono": lead_info.get('telefono'),
            "horas_sin_respuesta": horas_sin_respuesta,
            "score": f"{lead_info.get('score', 0)}/100"
        }
        
        resultados = []
        resultados.append(self.send_slack_notification(mensaje, urgencia, datos_adicionales))
        resultados.append(self.send_discord_notification(mensaje, urgencia))
        
        return any(resultados)
    
    def notificar_meta_diaria(self, leads_hoy: int, meta_diaria: int = 10) -> bool:
        """
        Notifica el progreso de la meta diaria
        """
        porcentaje = (leads_hoy / meta_diaria * 100) if meta_diaria > 0 else 0
        
        if porcentaje >= 100:
            mensaje = f"🎉 ¡META DIARIA ALCANZADA! {leads_hoy}/{meta_diaria} leads ({porcentaje:.1f}%)"
            urgencia = "success"
        elif porcentaje >= 80:
            mensaje = f"🔥 Casi llegamos! {leads_hoy}/{meta_diaria} leads ({porcentaje:.1f}%)"
            urgencia = "info"
        elif porcentaje >= 50:
            mensaje = f"📈 Buen progreso: {leads_hoy}/{meta_diaria} leads ({porcentaje:.1f}%)"
            urgencia = "info"
        else:
            mensaje = f"⚡ Necesitamos más leads: {leads_hoy}/{meta_diaria} ({porcentaje:.1f}%)"
            urgencia = "warning"
        
        datos_adicionales = {
            "leads_generados": leads_hoy,
            "meta_diaria": meta_diaria,
            "porcentaje_completado": f"{porcentaje:.1f}%"
        }
        
        return self.send_slack_notification(mensaje, urgencia, datos_adicionales)
    
    def notificar_error_sistema(self, error_msg: str, componente: str) -> bool:
        """
        Notifica errores críticos del sistema
        """
        mensaje = f"""
🚨 ERROR SISTEMA

🔧 Componente: {componente}
❌ Error: {error_msg}
⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Revisar logs del sistema.
        """.strip()
        
        datos_adicionales = {
            "componente": componente,
            "error": error_msg
        }
        
        resultados = []
        resultados.append(self.send_slack_notification(mensaje, "critical", datos_adicionales))
        resultados.append(self.send_discord_notification(mensaje, "critical"))
        resultados.append(self.send_email_notification("Error Sistema", mensaje))
        
        return any(resultados)
    
    def test_notifications(self) -> Dict[str, bool]:
        """
        Prueba todas las notificaciones configuradas
        """
        mensaje_test = f"🧪 Test de notificaciones - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        resultados = {
            'slack': False,
            'discord': False,
            'email': False
        }
        
        if self.slack_webhook_url:
            resultados['slack'] = self.send_slack_notification(mensaje_test, "info", {"test": True})
        
        if self.discord_webhook_url:
            resultados['discord'] = self.send_discord_notification(mensaje_test, "info")
        
        if all(self.email_config.values()):
            resultados['email'] = self.send_email_notification("Test", mensaje_test)
        
        return resultados

class NotificationScheduler:
    """
    Programador de notificaciones automáticas
    """
    
    def __init__(self, notification_system: NotificationSystem):
        self.notification_system = notification_system
        self.scheduled_checks = []
    
    def programar_verificacion_leads_frios(self, intervalo_horas: int = 4):
        """
        Programa verificación automática de leads que necesitan seguimiento
        """
        # Esta función se conectaría con el sistema de seguimiento automático
        # para identificar leads que necesitan atención
        pass
    
    def programar_reporte_diario(self, hora: str = "18:00"):
        """
        Programa reporte diario de métricas
        """
        # Implementar con scheduler como celery o APScheduler
        pass

# Funciones helper para uso fácil
def notificar_evento(tipo_evento: str, datos: Dict) -> bool:
    """
    Función helper para notificar eventos desde cualquier parte del código
    """
    notificador = NotificationSystem()
    
    if tipo_evento == "lead_caliente":
        return notificador.notificar_lead_caliente(datos)
    elif tipo_evento == "lead_sin_respuesta":
        return notificador.notificar_lead_sin_respuesta(datos, datos.get('horas', 24))
    elif tipo_evento == "error_sistema":
        return notificador.notificar_error_sistema(datos.get('error'), datos.get('componente'))
    elif tipo_evento == "meta_diaria":
        return notificador.notificar_meta_diaria(datos.get('leads_hoy'), datos.get('meta', 10))
    
    return False