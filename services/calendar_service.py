# services/calendar_service.py
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class CalendarService:
    """
    Servicio para integración con Cal.com API
    Permite agendar, consultar y gestionar citas automáticamente
    """
    
    def __init__(self):
        self.cal_api_key = os.getenv("CAL_API_KEY")
        self.cal_base_url = os.getenv("CAL_BASE_URL", "https://api.cal.com/v1")
        self.cal_event_type_id = os.getenv("CAL_EVENT_TYPE_ID")  # ID del tipo de evento (consulta autos)
        self.cal_user_id = os.getenv("CAL_USER_ID")  # Tu user ID en Cal.com
        
        self.headers = {
            "Authorization": f"Bearer {self.cal_api_key}",
            "Content-Type": "application/json"
        }
        
        # Configuraciones de negocio
        self.horarios_disponibles = {
            "lunes": {"inicio": "09:00", "fin": "18:00"},
            "martes": {"inicio": "09:00", "fin": "18:00"},
            "miercoles": {"inicio": "09:00", "fin": "18:00"},
            "jueves": {"inicio": "09:00", "fin": "18:00"},
            "viernes": {"inicio": "09:00", "fin": "18:00"},
            "sabado": {"inicio": "09:00", "fin": "15:00"},
            "domingo": {"cerrado": True}
        }
        
        self.duracion_cita_minutos = 30
        
    def obtener_disponibilidad(self, fecha_inicio: str, fecha_fin: str) -> Dict:
        """
        Obtiene disponibilidad en un rango de fechas
        """
        try:
            url = f"{self.cal_base_url}/availability"
            params = {
                "username": self.cal_user_id,
                "dateFrom": fecha_inicio,
                "dateTo": fecha_fin,
                "eventTypeId": self.cal_event_type_id
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "exito": True,
                    "disponibilidad": data.get("busy", []),
                    "slots_libres": self._procesar_slots_libres(data)
                }
            else:
                print(f"❌ Error obteniendo disponibilidad: {response.status_code}")
                return {"exito": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Error en obtener_disponibilidad: {e}")
            return {"exito": False, "error": str(e)}
    
    def _procesar_slots_libres(self, data: Dict) -> List[Dict]:
        """
        Procesa la respuesta de Cal.com para extraer slots disponibles
        """
        try:
            slots_libres = []
            
            # Obtener próximos 7 días
            for i in range(7):
                fecha = datetime.now() + timedelta(days=i+1)
                fecha_str = fecha.strftime("%Y-%m-%d")
                
                # Verificar si es día laborable
                dia_semana = fecha.strftime("%A").lower()
                if dia_semana == "sunday":
                    dia_semana = "domingo"
                elif dia_semana == "monday":
                    dia_semana = "lunes"
                elif dia_semana == "tuesday":
                    dia_semana = "martes"
                elif dia_semana == "wednesday":
                    dia_semana = "miercoles"
                elif dia_semana == "thursday":
                    dia_semana = "jueves"
                elif dia_semana == "friday":
                    dia_semana = "viernes"
                elif dia_semana == "saturday":
                    dia_semana = "sabado"
                
                config_dia = self.horarios_disponibles.get(dia_semana, {})
                
                if config_dia.get("cerrado", False):
                    continue
                
                # Generar slots de 30 minutos
                hora_inicio = datetime.strptime(config_dia["inicio"], "%H:%M").time()
                hora_fin = datetime.strptime(config_dia["fin"], "%H:%M").time()
                
                slot_actual = datetime.combine(fecha.date(), hora_inicio)
                slot_fin = datetime.combine(fecha.date(), hora_fin)
                
                while slot_actual + timedelta(minutes=self.duracion_cita_minutos) <= slot_fin:
                    slots_libres.append({
                        "fecha": fecha_str,
                        "hora": slot_actual.strftime("%H:%M"),
                        "datetime": slot_actual.isoformat(),
                        "disponible": self._verificar_slot_disponible(slot_actual, data)
                    })
                    slot_actual += timedelta(minutes=self.duracion_cita_minutos)
            
            return [slot for slot in slots_libres if slot["disponible"]]
            
        except Exception as e:
            print(f"❌ Error procesando slots: {e}")
            return []
    
    def _verificar_slot_disponible(self, slot_datetime: datetime, cal_data: Dict) -> bool:
        """
        Verifica si un slot específico está disponible
        """
        # Aquí verificarías contra las citas ya agendadas en cal_data
        # Implementación simplificada - en producción revisar contra busy slots
        return True
    
    def agendar_cita(self, lead_info: Dict, fecha_hora: str, notas: str = "") -> Dict:
        """
        Agenda una cita en Cal.com
        """
        try:
            url = f"{self.cal_base_url}/bookings"
            
            # Datos de la cita
            booking_data = {
                "eventTypeId": int(self.cal_event_type_id),
                "start": fecha_hora,
                "responses": {
                    "name": lead_info.get("nombre", "Cliente"),
                    "email": lead_info.get("email", "cliente@temp.com"),
                    "phone": lead_info.get("telefono", ""),
                    "notes": f"Cliente interesado en {lead_info.get('modelo_interes', 'autos Nissan')}. {notas}"
                },
                "timeZone": "America/Mexico_City",
                "language": "es",
                "metadata": {
                    "lead_score": str(lead_info.get("score", 0)),
                    "canal_origen": lead_info.get("canal_origen", "whatsapp"),
                    "temperatura": lead_info.get("temperatura", "tibio")
                }
            }
            
            response = requests.post(url, headers=self.headers, json=booking_data)
            
            if response.status_code == 201:
                booking = response.json()
                return {
                    "exito": True,
                    "booking_id": booking.get("id"),
                    "booking_uid": booking.get("uid"),
                    "fecha_hora": fecha_hora,
                    "link_reschedule": booking.get("rescheduleLink"),
                    "link_cancel": booking.get("cancelLink"),
                    "mensaje_confirmacion": self._generar_mensaje_confirmacion(booking, lead_info)
                }
            else:
                print(f"❌ Error agendando cita: {response.status_code} - {response.text}")
                return {"exito": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Error en agendar_cita: {e}")
            return {"exito": False, "error": str(e)}
    
    def _generar_mensaje_confirmacion(self, booking: Dict, lead_info: Dict) -> str:
        """
        Genera mensaje de confirmación personalizado
        """
        fecha_obj = datetime.fromisoformat(booking.get("startTime", "").replace("Z", "+00:00"))
        fecha_legible = fecha_obj.strftime("%A %d de %B a las %H:%M")
        
        # Traducir día de la semana
        dias = {
            "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
            "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"
        }
        
        meses = {
            "January": "enero", "February": "febrero", "March": "marzo", "April": "abril",
            "May": "mayo", "June": "junio", "July": "julio", "August": "agosto",
            "September": "septiembre", "October": "octubre", "November": "noviembre", "December": "diciembre"
        }
        
        for en, es in dias.items():
            fecha_legible = fecha_legible.replace(en, es)
        for en, es in meses.items():
            fecha_legible = fecha_legible.replace(en, es)
        
        mensaje = f"""
🎉 ¡Cita agendada exitosamente!

👤 Cliente: {lead_info.get('nombre', 'Cliente')}
📅 Fecha: {fecha_legible}
📍 Ubicación: Nissan Tijuana
🚗 Motivo: Consulta sobre {lead_info.get('modelo_interes', 'autos Nissan')}

📱 Recibirás recordatorios por WhatsApp
📧 También te llegará confirmación por email

¿Necesitas reagendar? 👉 {booking.get('rescheduleLink', 'Contacta al 6644918078')}

¡Nos vemos pronto! 😊
        """.strip()
        
        return mensaje
    
    def obtener_citas_lead(self, telefono: str) -> List[Dict]:
        """
        Obtiene todas las citas de un lead específico
        """
        try:
            url = f"{self.cal_base_url}/bookings"
            params = {
                "filters[attendeeEmail]": f"{telefono.replace('+', '')}@temp.com"  # Email temporal basado en teléfono
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                bookings = response.json().get("bookings", [])
                return [
                    {
                        "id": booking.get("id"),
                        "fecha": booking.get("startTime"),
                        "estado": booking.get("status"),
                        "link_meet": booking.get("videoCallData", {}).get("url"),
                        "notas": booking.get("description", "")
                    }
                    for booking in bookings
                ]
            else:
                print(f"❌ Error obteniendo citas: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error en obtener_citas_lead: {e}")
            return []
    
    def cancelar_cita(self, booking_id: str, razon: str = "") -> Dict:
        """
        Cancela una cita específica
        """
        try:
            url = f"{self.cal_base_url}/bookings/{booking_id}/cancel"
            data = {
                "reason": razon or "Cancelado por el cliente",
                "allRemainingBookings": False
            }
            
            response = requests.delete(url, headers=self.headers, json=data)
            
            if response.status_code == 200:
                return {"exito": True, "mensaje": "Cita cancelada exitosamente"}
            else:
                return {"exito": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Error cancelando cita: {e}")
            return {"exito": False, "error": str(e)}
    
    def reagendar_cita(self, booking_id: str, nueva_fecha: str) -> Dict:
        """
        Reagenda una cita existente
        """
        try:
            url = f"{self.cal_base_url}/bookings/{booking_id}/reschedule"
            data = {
                "start": nueva_fecha,
                "reschedulingReason": "Reagendado por el cliente"
            }
            
            response = requests.post(url, headers=self.headers, json=data)
            
            if response.status_code == 200:
                return {"exito": True, "nueva_fecha": nueva_fecha}
            else:
                return {"exito": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Error reagendando cita: {e}")
            return {"exito": False, "error": str(e)}
    
    def obtener_slots_disponibles_humanos(self, dias_adelante: int = 7) -> List[str]:
        """
        Retorna slots disponibles en formato legible para mostrar al cliente
        """
        try:
            fecha_inicio = datetime.now().strftime("%Y-%m-%d")
            fecha_fin = (datetime.now() + timedelta(days=dias_adelante)).strftime("%Y-%m-%d")
            
            disponibilidad = self.obtener_disponibilidad(fecha_inicio, fecha_fin)
            
            if not disponibilidad["exito"]:
                return ["No hay disponibilidad en este momento"]
            
            slots = disponibilidad["slots_libres"][:10]  # Mostrar máximo 10 opciones
            
            slots_formateados = []
            for slot in slots:
                fecha_obj = datetime.fromisoformat(slot["datetime"])
                dia_semana = fecha_obj.strftime("%A")
                fecha_num = fecha_obj.strftime("%d/%m")
                hora = fecha_obj.strftime("%H:%M")
                
                # Traducir días
                dias_es = {
                    "Monday": "Lun", "Tuesday": "Mar", "Wednesday": "Mié",
                    "Thursday": "Jue", "Friday": "Vie", "Saturday": "Sáb"
                }
                
                dia_es = dias_es.get(dia_semana, dia_semana)
                slots_formateados.append(f"{dia_es} {fecha_num} a las {hora}")
            
            return slots_formateados
            
        except Exception as e:
            print(f"❌ Error obteniendo slots legibles: {e}")
            return ["Error obteniendo disponibilidad"]

# Funciones helper para integración con el bot
def procesar_solicitud_cita(mensaje: str, lead_info: Dict) -> Dict:
    """
    Procesa solicitud de cita del cliente y sugiere horarios
    """
    calendar_service = CalendarService()
    
    # Detectar preferencias de fecha/hora en el mensaje
    preferencias = extraer_preferencias_fecha(mensaje)
    
    # Obtener slots disponibles
    slots_disponibles = calendar_service.obtener_slots_disponibles_humanos()
    
    if not slots_disponibles or slots_disponibles[0].startswith("Error"):
        return {
            "tipo": "error",
            "mensaje": "⚠️ Temporalmente no puedo acceder al calendario. Te contacto por teléfono para agendar: 6644918078"
        }
    
    # Generar respuesta con opciones
    mensaje_respuesta = f"""
📅 ¡Perfecto {lead_info.get('nombre', 'amigo')}! Te tengo varios horarios disponibles:

"""
    
    for i, slot in enumerate(slots_disponibles[:5], 1):
        mensaje_respuesta += f"{i}. {slot}\n"
    
    mensaje_respuesta += f"""
💡 Solo dime el número de la opción que prefieras o escribe "otro horario" si necesitas algo diferente.

📍 La cita será en: Nissan Tijuana
⏰ Duración: 30 minutos
🚗 Para ver el {lead_info.get('modelo_interes', 'auto que te interesa')}
"""
    
    return {
        "tipo": "opciones_cita",
        "mensaje": mensaje_respuesta,
        "slots_disponibles": slots_disponibles
    }

def confirmar_cita_seleccionada(opcion: str, lead_info: Dict, slots_disponibles: List[str]) -> Dict:
    """
    Confirma y agenda la cita seleccionada por el cliente
    """
    try:
        calendar_service = CalendarService()
        
        # Parsear la opción seleccionada
        if opcion.isdigit():
            indice = int(opcion) - 1
            if 0 <= indice < len(slots_disponibles):
                slot_seleccionado = slots_disponibles[indice]
                
                # Convertir slot a datetime ISO
                fecha_hora = convertir_slot_a_datetime(slot_seleccionado)
                
                # Agendar en Cal.com
                resultado = calendar_service.agendar_cita(
                    lead_info, 
                    fecha_hora, 
                    f"Cliente interesado en {lead_info.get('modelo_interes', 'autos Nissan')}"
                )
                
                if resultado["exito"]:
                    return {
                        "tipo": "cita_confirmada",
                        "mensaje": resultado["mensaje_confirmacion"],
                        "booking_id": resultado["booking_id"]
                    }
                else:
                    return {
                        "tipo": "error",
                        "mensaje": "⚠️ Hubo un problema agendando la cita. Te contacto directamente al 6644918078"
                    }
        
        return {
            "tipo": "error", 
            "mensaje": "No entendí la opción. ¿Puedes elegir un número del 1 al 5?"
        }
        
    except Exception as e:
        print(f"❌ Error confirmando cita: {e}")
        return {
            "tipo": "error",
            "mensaje": "⚠️ Error agendando. Te contacto por teléfono: 6644918078"
        }

def extraer_preferencias_fecha(mensaje: str) -> Dict:
    """
    Extrae preferencias de fecha y hora del mensaje del cliente
    """
    mensaje_lower = mensaje.lower()
    
    preferencias = {
        "dia_preferido": None,
        "hora_preferida": None,
        "urgencia": "normal"
    }
    
    # Detectar días
    if any(word in mensaje_lower for word in ["mañana", "tomorrow"]):
        preferencias["dia_preferido"] = "mañana"
    elif any(word in mensaje_lower for word in ["hoy", "today"]):
        preferencias["urgencia"] = "urgente"
    
    # Detectar horarios
    if any(word in mensaje_lower for word in ["mañana", "morning", "temprano"]):
        preferencias["hora_preferida"] = "mañana"
    elif any(word in mensaje_lower for word in ["tarde", "afternoon"]):
        preferencias["hora_preferida"] = "tarde"
    
    return preferencias

def convertir_slot_a_datetime(slot_humano: str) -> str:
    """
    Convierte un slot legible como "Lun 15/01 a las 10:00" a datetime ISO
    """
    try:
        import re
        
        # Extraer fecha y hora
        patron = r"(\w+) (\d{2}/\d{2}) a las (\d{2}:\d{2})"
        match = re.search(patron, slot_humano)
        
        if match:
            dia, fecha, hora = match.groups()
            
            # Construir datetime
            año_actual = datetime.now().year
            mes, dia = fecha.split("/")
            dia_num = fecha.split("/")[0]
            mes_num = fecha.split("/")[1]
            
            fecha_completa = f"{año_actual}-{mes_num}-{dia_num}T{hora}:00"
            return datetime.fromisoformat(fecha_completa).isoformat()
        
        # Fallback: usar la próxima hora disponible
        return (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
        
    except Exception as e:
        print(f"❌ Error convirtiendo slot: {e}")
        return (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()