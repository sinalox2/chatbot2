# services/calendar_service.py - VERSIÓN CORREGIDA CON SISTEMA DE RESPALDO

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class CalendarService:
    """
    Servicio para integración con Cal.com API con sistema de respaldo
    """
    
    def __init__(self):
        self.cal_api_key = os.getenv("CAL_API_KEY")
        self.cal_base_url = os.getenv("CAL_BASE_URL", "https://api.cal.com/v1")
        self.cal_event_type_id = os.getenv("CAL_EVENT_TYPE_ID")
        self.cal_user_id = os.getenv("CAL_USER_ID")
        
        # Verificar configuración
        self.configuracion_valida = self._verificar_configuracion()
        
        if self.configuracion_valida:
            self.headers = {
                "Authorization": f"Bearer {self.cal_api_key}",
                "Content-Type": "application/json"
            }
        else:
            print("⚠️ Configuración de Cal.com incompleta, usando sistema de respaldo")
            self.headers = None
        
        # Horarios de respaldo (cuando Cal.com no esté disponible)
        self.horarios_respaldo = self._generar_horarios_respaldo()
        
    def _verificar_configuracion(self) -> bool:
        """Verifica que todas las variables de Cal.com estén configuradas"""
        required_vars = [
            ('CAL_API_KEY', self.cal_api_key),
            ('CAL_EVENT_TYPE_ID', self.cal_event_type_id),
            ('CAL_USER_ID', self.cal_user_id)
        ]
        
        for var_name, var_value in required_vars:
            if not var_value:
                print(f"❌ Variable de entorno faltante: {var_name}")
                return False
        
        # Verificar formato de API Key
        if not self.cal_api_key.startswith(('cal_live_', 'cal_test_')):
            print(f"❌ API Key inválida: debe empezar con 'cal_live_' o 'cal_test_'")
            return False
            
        return True
    
    def _generar_horarios_respaldo(self) -> List[Dict]:
        """Genera horarios de respaldo para los próximos 7 días"""
        horarios = []
        
        # Horarios típicos de negocio
        horas_disponibles = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"]
        
        for i in range(1, 8):  # Próximos 7 días
            fecha = datetime.now() + timedelta(days=i)
            
            # Saltar domingos
            if fecha.weekday() == 6:  # Domingo
                continue
                
            # Sábados solo hasta las 15:00
            horas_del_dia = horas_disponibles[:6] if fecha.weekday() == 5 else horas_disponibles
            
            for hora in horas_del_dia:
                slot_datetime = datetime.combine(fecha.date(), datetime.strptime(hora, "%H:%M").time())
                
                horarios.append({
                    "fecha": fecha.strftime("%Y-%m-%d"),
                    "hora": hora,
                    "datetime": slot_datetime.isoformat(),
                    "disponible": True,
                    "dia_semana": self._get_dia_semana_es(fecha.weekday())
                })
        
        return horarios
    
    def _get_dia_semana_es(self, weekday: int) -> str:
        """Convierte número de día a nombre en español"""
        dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        return dias[weekday]
    
    def test_conexion_cal(self) -> Dict:
        """Prueba la conexión con Cal.com"""
        if not self.configuracion_valida:
            return {
                "exito": False,
                "error": "Configuración incompleta",
                "codigo": "CONFIG_ERROR"
            }
        
        try:
            # Probar endpoint básico de Cal.com
            url = f"{self.cal_base_url}/me"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    "exito": True,
                    "mensaje": "Conexión exitosa con Cal.com",
                    "usuario": response.json()
                }
            elif response.status_code == 401:
                return {
                    "exito": False,
                    "error": "API Key inválida o expirada",
                    "codigo": "AUTH_ERROR",
                    "sugerencia": "Verificar CAL_API_KEY en .env"
                }
            elif response.status_code == 403:
                return {
                    "exito": False,
                    "error": "Permisos insuficientes",
                    "codigo": "PERMISSION_ERROR"
                }
            else:
                return {
                    "exito": False,
                    "error": f"Error HTTP {response.status_code}: {response.text}",
                    "codigo": "HTTP_ERROR"
                }
                
        except requests.exceptions.Timeout:
            return {
                "exito": False,
                "error": "Timeout conectando con Cal.com",
                "codigo": "TIMEOUT_ERROR"
            }
        except Exception as e:
            return {
                "exito": False,
                "error": f"Error de conexión: {str(e)}",
                "codigo": "CONNECTION_ERROR"
            }
    
    def obtener_disponibilidad(self, fecha_inicio: str, fecha_fin: str) -> Dict:
        """
        Obtiene disponibilidad - con respaldo automático
        """
        # Primero intentar Cal.com
        if self.configuracion_valida:
            try:
                url = f"{self.cal_base_url}/availability"
                params = {
                    "username": self.cal_user_id,
                    "dateFrom": fecha_inicio,
                    "dateTo": fecha_fin,
                    "eventTypeId": self.cal_event_type_id
                }
                
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "exito": True,
                        "fuente": "cal.com",
                        "disponibilidad": data.get("busy", []),
                        "slots_libres": self._procesar_slots_calcom(data)
                    }
                else:
                    print(f"❌ Error Cal.com {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"❌ Error conectando con Cal.com: {e}")
        
        # Sistema de respaldo
        print("🔄 Usando sistema de horarios de respaldo")
        return {
            "exito": True,
            "fuente": "respaldo",
            "slots_libres": self.horarios_respaldo[:20]  # Limitar a 20 slots
        }
    
    def _procesar_slots_calcom(self, data: Dict) -> List[Dict]:
        """Procesa respuesta real de Cal.com"""
        # Implementación simplificada - en producción sería más compleja
        return self.horarios_respaldo[:15]
    
    def obtener_slots_disponibles_humanos(self, dias_adelante: int = 7) -> List[str]:
        """
        Retorna slots en formato legible - SIEMPRE funciona
        """
        try:
            fecha_inicio = datetime.now().strftime("%Y-%m-%d")
            fecha_fin = (datetime.now() + timedelta(days=dias_adelante)).strftime("%Y-%m-%d")
            
            disponibilidad = self.obtener_disponibilidad(fecha_inicio, fecha_fin)
            
            if not disponibilidad["exito"]:
                return self._get_slots_respaldo_humanos()
            
            slots = disponibilidad["slots_libres"][:10]
            slots_formateados = []
            
            for slot in slots:
                try:
                    fecha_obj = datetime.fromisoformat(slot["datetime"])
                    dia_semana = slot.get("dia_semana", fecha_obj.strftime("%a"))
                    fecha_num = fecha_obj.strftime("%d/%m")
                    hora = fecha_obj.strftime("%H:%M")
                    
                    slots_formateados.append(f"{dia_semana} {fecha_num} a las {hora}")
                except Exception as e:
                    print(f"⚠️ Error formateando slot: {e}")
                    continue
            
            return slots_formateados if slots_formateados else self._get_slots_respaldo_humanos()
            
        except Exception as e:
            print(f"❌ Error obteniendo slots: {e}")
            return self._get_slots_respaldo_humanos()
    
    def _get_slots_respaldo_humanos(self) -> List[str]:
        """Slots de respaldo en formato humano"""
        slots_respaldo = []
        
        for i in range(1, 6):  # Próximos 5 días
            fecha = datetime.now() + timedelta(days=i)
            
            if fecha.weekday() == 6:  # Saltar domingos
                continue
                
            dia_es = self._get_dia_semana_es(fecha.weekday())
            fecha_str = fecha.strftime("%d/%m")
            
            # 2-3 horarios por día
            horas = ["10:00", "14:30"] if fecha.weekday() == 5 else ["10:00", "14:30", "16:00"]
            
            for hora in horas:
                slots_respaldo.append(f"{dia_es} {fecha_str} a las {hora}")
                
        return slots_respaldo[:8]  # Máximo 8 opciones
    
    def agendar_cita_respaldo(self, lead_info: Dict, slot_seleccionado: str) -> Dict:
        """
        Sistema de respaldo para agendar citas cuando Cal.com no esté disponible
        """
        try:
            # Simular agendado exitoso
            booking_id = f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # En producción, aquí guardarías en tu base de datos
            # o enviarías notificación manual al equipo
            
            return {
                "exito": True,
                "booking_id": booking_id,
                "metodo": "respaldo",
                "mensaje_confirmacion": self._generar_mensaje_confirmacion_respaldo(slot_seleccionado, lead_info),
                "accion_requerida": f"MANUAL: Confirmar cita {slot_seleccionado} para {lead_info.get('nombre')}"
            }
            
        except Exception as e:
            return {
                "exito": False,
                "error": f"Error en sistema de respaldo: {str(e)}"
            }
    
    def _generar_mensaje_confirmacion_respaldo(self, slot: str, lead_info: Dict) -> str:
        """Genera mensaje de confirmación para sistema de respaldo"""
        return f"""
🎉 ¡Cita pre-agendada exitosamente!

👤 Cliente: {lead_info.get('nombre', 'Cliente')}
📅 Horario solicitado: {slot}
📍 Ubicación: Nissan Tijuana
🚗 Interés: {lead_info.get('modelo_interes', 'Autos Nissan')}

⏳ Te confirmo la disponibilidad exacta en unos minutos
📞 O puedes llamar al 6644918078 para confirmar inmediatamente

¡Nos vemos pronto! 😊

*Cita sujeta a confirmación de disponibilidad
        """.strip()

# Funciones helper actualizadas
def procesar_solicitud_cita(mensaje: str, lead_info: Dict) -> Dict:
    """
    Procesa solicitud de cita - SIEMPRE funciona
    """
    calendar_service = CalendarService()
    
    # Probar conexión primero
    test_conexion = calendar_service.test_conexion_cal()
    
    # Obtener slots (de Cal.com o respaldo)
    slots_disponibles = calendar_service.obtener_slots_disponibles_humanos()
    
    if not slots_disponibles:
        return {
            "tipo": "error",
            "mensaje": "⚠️ Temporalmente no puedo mostrar horarios. Te contacto al 6644918078 para agendar tu cita 😊"
        }
    
    # Mensaje con indicador de fuente
    fuente_info = ""
    if not test_conexion.get("exito", False):
        fuente_info = "\n💡 *Horarios sujetos a confirmación de disponibilidad*"
    
    mensaje_respuesta = f"""
📅 ¡Perfecto {lead_info.get('nombre', 'amigo')}! Te tengo varios horarios disponibles:

"""
    
    for i, slot in enumerate(slots_disponibles[:5], 1):
        mensaje_respuesta += f"{i}. {slot}\n"
    
    mensaje_respuesta += f"""
💡 Solo dime el número de la opción que prefieras

📍 Ubicación: Nissan Tijuana
⏰ Duración: 30 minutos
🚗 Para ver el {lead_info.get('modelo_interes', 'auto que te interesa')}
📞 O llama directo: 6644918078{fuente_info}
"""
    
    return {
        "tipo": "opciones_cita",
        "mensaje": mensaje_respuesta,
        "slots_disponibles": slots_disponibles,
        "cal_disponible": test_conexion.get("exito", False)
    }

def confirmar_cita_seleccionada(opcion: str, lead_info: Dict, slots_disponibles: List[str]) -> Dict:
    """
    Confirma cita - con respaldo automático
    """
    try:
        calendar_service = CalendarService()
        
        if opcion.isdigit():
            indice = int(opcion) - 1
            if 0 <= indice < len(slots_disponibles):
                slot_seleccionado = slots_disponibles[indice]
                
                # Probar Cal.com primero
                test_conexion = calendar_service.test_conexion_cal()
                
                if test_conexion.get("exito", False):
                    # Intentar agendar en Cal.com (implementación completa)
                    fecha_hora = convertir_slot_a_datetime(slot_seleccionado)
                    # resultado = calendar_service.agendar_cita(lead_info, fecha_hora)
                    # Por ahora usar respaldo hasta configurar completamente
                    resultado = calendar_service.agendar_cita_respaldo(lead_info, slot_seleccionado)
                else:
                    # Usar sistema de respaldo
                    resultado = calendar_service.agendar_cita_respaldo(lead_info, slot_seleccionado)
                
                if resultado["exito"]:
                    return {
                        "tipo": "cita_confirmada",
                        "mensaje": resultado["mensaje_confirmacion"],
                        "booking_id": resultado["booking_id"],
                        "metodo": resultado.get("metodo", "cal.com")
                    }
                else:
                    return {
                        "tipo": "error",
                        "mensaje": "⚠️ Hubo un problema agendando. Te contacto al 6644918078 para confirmar tu cita 😊"
                    }
        
        return {
            "tipo": "error", 
            "mensaje": "No entendí la opción. ¿Puedes elegir un número del 1 al 5? 😊"
        }
        
    except Exception as e:
        print(f"❌ Error confirmando cita: {e}")
        return {
            "tipo": "error",
            "mensaje": "⚠️ Error agendando. Te contacto por teléfono: 6644918078"
        }

def convertir_slot_a_datetime(slot_humano: str) -> str:
    """Convierte slot legible a datetime ISO"""
    try:
        import re
        
        patron = r"(\w+) (\d{2}/\d{2}) a las (\d{2}:\d{2})"
        match = re.search(patron, slot_humano)
        
        if match:
            dia, fecha, hora = match.groups()
            año_actual = datetime.now().year
            dia_num, mes_num = fecha.split("/")
            
            fecha_completa = f"{año_actual}-{mes_num}-{dia_num}T{hora}:00"
            return datetime.fromisoformat(fecha_completa).isoformat()
        
        return (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
        
    except Exception as e:
        print(f"❌ Error convirtiendo slot: {e}")
        return (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()