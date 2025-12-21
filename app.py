# app.py - Versión actualizada con nuevo dashboard moderno

# Sistema robusto para evitar respuestas duplicadas
import time
from collections import defaultdict

# Cambiar de set simple a dict con timestamps
mensajes_procesados = defaultdict(float)

# Imports principales
import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
from flask_cors import CORS
import re

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Agregar directorio dashboard al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'dashboard'))

# Import logger
from utils.logger import Logger

# Imports del proyecto
try:
    from supabase_client import supabase
    SUPABASE_AVAILABLE = True
    Logger.success("Supabase importado correctamente", "DB")
except ImportError as e:
    Logger.error(f"Error importando Supabase: {e}", "DB")
    SUPABASE_AVAILABLE = False
    supabase = None

try:
    from models.lead_tracking import Lead, EstadoLead, TipoInteraccion, Interaccion, TemperaturaMercado, CanalOrigen, ProspectoInfo
    LEAD_TRACKING_AVAILABLE = True
    Logger.success("Lead tracking importado correctamente", "LEADS")
except ImportError as e:
    Logger.error(f"Error importando lead tracking: {e}", "LEADS")
    LEAD_TRACKING_AVAILABLE = False

try:
    from services.lead_tracking_service import LeadTrackingService
    LEAD_SERVICE_AVAILABLE = True
    Logger.success("Lead service importado correctamente", "LEADS")
except ImportError as e:
    Logger.error(f"Error importando lead service: {e}", "LEADS")
    LEAD_SERVICE_AVAILABLE = False

try:
    from services.contactos_proactivos import contactos_proactivos_service
    CONTACTOS_PROACTIVOS_AVAILABLE = True
    print("✅ Servicio de contactos proactivos importado correctamente")
except ImportError as e:
    print(f"⚠️ Error importando contactos proactivos: {e}")
    CONTACTOS_PROACTIVOS_AVAILABLE = False

try:
    from services.whatsapp_service import whatsapp_service
    WHATSAPP_SERVICE_AVAILABLE = True
    print("⚠️ WhatsApp service importado - NOTA: Usando integración Chatwoot, servicio directo deshabilitado")
except ImportError as e:
    print(f"✅ WhatsApp service no importado (correcto para integración Chatwoot): {e}")
    WHATSAPP_SERVICE_AVAILABLE = False

try:
    from services.conversation_service import conversation_service
    CONVERSATION_SERVICE_AVAILABLE = True
    Logger.success("Conversation service importado correctamente", "CHAT")
except ImportError as e:
    Logger.warning(f"Error importando conversation service: {e}", "CHAT")
    CONVERSATION_SERVICE_AVAILABLE = False

# Import dashboard routes
try:
    from dashboard.routes.main_routes import main_bp
    from dashboard.routes.contacts_routes import contacts_bp
    DASHBOARD_AVAILABLE = True
    print("✅ Dashboard routes importado correctamente")
except ImportError as e:
    print(f"⚠️ Error importando dashboard routes: {e}")
    DASHBOARD_AVAILABLE = False

# Configuración de la aplicación
app = Flask(__name__, 
           template_folder='dashboard/templates',  # Usar templates del dashboard
           static_folder='dashboard/static')       # Usar static files del dashboard
CORS(app)

# Registrar blueprints del dashboard
if DASHBOARD_AVAILABLE:
    app.register_blueprint(main_bp)
    app.register_blueprint(contacts_bp)
    print("✅ Dashboard blueprints registrados")

# Inicializar servicios
if LEAD_SERVICE_AVAILABLE:
    lead_service = LeadTrackingService()
else:
    lead_service = None

# Funciones de utilidad del sistema original
def detectar_cliente_para_seguimiento_proactivo(telefono, nombre, contexto_conversacion):
    """
    Función para detectar automáticamente clientes que necesitan seguimiento proactivo
    Se puede llamar desde el flujo principal cuando un cliente se enfría
    """
    if not CONTACTOS_PROACTIVOS_AVAILABLE:
        return False
    
    try:
        # Detectar si es un lead que se enfrió
        if any(palabra in contexto_conversacion.lower() for palabra in 
               ['lo voy a pensar', 'después', 'más tarde', 'ahorita no', 'luego te digo']):
            
            # Programar seguimiento en 24 horas
            exito = contactos_proactivos_service.programar_mensaje_diferido(
                telefono=telefono,
                nombre=nombre,
                contexto=f"Cliente que mostró interés pero decidió pensarlo. Contexto: {contexto_conversacion[:200]}",
                horas_delay=24,
                tipo_campana='seguimiento'
            )
            
            if exito:
                print(f"📅 Seguimiento proactivo programado para {nombre} ({telefono})")
                return True
        
        # Detectar si es un lead con objeción de precio
        elif any(palabra in contexto_conversacion.lower() for palabra in 
                ['caro', 'precio alto', 'no puedo', 'muy caro']):
            
            # Programar seguimiento con nueva promoción en 3 días
            exito = contactos_proactivos_service.programar_mensaje_diferido(
                telefono=telefono,
                nombre=nombre,
                contexto=f"Cliente con objeción de precio. Contexto: {contexto_conversacion[:200]}",
                horas_delay=72,  # 3 días
                tipo_campana='promocion'
            )
            
            if exito:
                print(f"🎯 Seguimiento promocional programado para {nombre} ({telefono})")
                return True
                
        return False
        
    except Exception as e:
        print(f"❌ Error detectando seguimiento proactivo: {e}")
        return False

def limpiar_mensajes_antiguos():
    """Limpia mensajes procesados más antiguos de 1 hora"""
    limite = time.time() - 3600  # 1 hora
    keys_to_remove = [k for k, v in mensajes_procesados.items() if v < limite]
    for key in keys_to_remove:
        del mensajes_procesados[key]
    if keys_to_remove:
        print(f"🧹 Limpiados {len(keys_to_remove)} mensajes antiguos")

def generar_id_unico(data, telefono):
    """Genera ID único considerando múltiples fuentes"""
    mensaje_id = data.get("id") or data.get("message", {}).get("id", "")
    contenido = data.get("content", "").strip()
    timestamp = data.get("timestamp", int(time.time()))
    
    # Combinar fuentes para ID único
    return f"{telefono}_{mensaje_id}_{hash(contenido)}_{timestamp}"

def validar_origen_mensaje(data):
    """Valida si el mensaje viene de usuario real o es loop"""
    # Verificar si es mensaje entrante de usuario
    sender_type = data.get("sender", {}).get("type", "")
    message_type = data.get("message_type", "")
    
    # No procesar mensajes del bot o agente
    if sender_type in ["agent_bot", "agent"] or message_type == "outgoing":
        print(f"🚫 Mensaje ignorado - origen: {sender_type}, tipo: {message_type}")
        return False
    
    return True

# ============================================================================
# RUTAS PRINCIPALES DE LA APLICACIÓN
# ============================================================================

@app.route('/')
def index():
    """Redirigir a dashboard principal"""
    return redirect(url_for('main.dashboard'))

# ============================================================================
# API ENDPOINTS PARA EL DASHBOARD
# ============================================================================

@app.route('/api/contactos-proactivos', methods=['GET'])
def api_get_contactos_proactivos():
    """API endpoint para obtener contactos proactivos"""
    try:
        if not SUPABASE_AVAILABLE:
            print("❌ Supabase no disponible")
            return jsonify({'error': 'Supabase no disponible'}), 500
        
        # Obtener contactos con paginación
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))  # Aumentar límite para ver más contactos
        offset = (page - 1) * limit
        
        print(f"📊 Obteniendo contactos: página {page}, límite {limit}")
        
        # Intentar con diferentes nombres de columna para fecha
        try:
            # Primero intentar con created_at (estándar de Supabase)
            response = supabase.table('contactos_proactivos')\
                .select('*')\
                .order('created_at', desc=True)\
                .range(offset, offset + limit - 1)\
                .execute()
            print(f"✅ Usando ordenamiento por created_at")
        except Exception as e1:
            print(f"⚠️ Error con created_at: {e1}")
            try:
                # Intentar con updated_at
                response = supabase.table('contactos_proactivos')\
                    .select('*')\
                    .order('updated_at', desc=True)\
                    .range(offset, offset + limit - 1)\
                    .execute()
                print(f"✅ Usando ordenamiento por updated_at")
            except Exception as e2:
                print(f"⚠️ Error con updated_at: {e2}")
                try:
                    # Intentar con fecha_programada (que sabemos que existe)
                    response = supabase.table('contactos_proactivos')\
                        .select('*')\
                        .order('fecha_programada', desc=True)\
                        .range(offset, offset + limit - 1)\
                        .execute()
                    print(f"✅ Usando ordenamiento por fecha_programada")
                except Exception as e3:
                    print(f"⚠️ Error con fecha_programada: {e3}")
                    # Sin ordenamiento como último recurso
                    response = supabase.table('contactos_proactivos')\
                        .select('*')\
                        .range(offset, offset + limit - 1)\
                        .execute()
                    print(f"⚠️ Sin ordenamiento - obteniendo todos los registros")
        
        contacts = response.data or []
        print(f"✅ Contactos obtenidos: {len(contacts)} registros")
        
        # Log de primeros registros para debug
        if contacts:
            print(f"🔍 Primer contacto: {contacts[0].get('nombre', 'Sin nombre')} - {contacts[0].get('telefono', 'Sin teléfono')}")
        
        return jsonify({
            'success': True,
            'contacts': contacts,
            'page': page,
            'limit': limit,
            'total': len(contacts)
        })
    except Exception as e:
        print(f"❌ Error en api_get_contactos_proactivos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/contactos-proactivos', methods=['POST'])
def api_add_contacto_proactivo():
    """API endpoint para agregar nuevo contacto proactivo"""
    try:
        if not CONTACTOS_PROACTIVOS_AVAILABLE:
            print("❌ Servicio de contactos proactivos no disponible")
            return jsonify({'error': 'Servicio no disponible'}), 500
        
        data = request.get_json()
        print(f"📥 Datos recibidos para nuevo contacto: {data}")
        
        # Validar datos requeridos
        if not data.get('nombre') or not data.get('telefono'):
            print("❌ Faltan nombre o teléfono")
            return jsonify({'error': 'Nombre y teléfono son requeridos'}), 400
        
        # Manejar fecha programada de manera segura
        fecha_programada = None
        if data.get('fecha_programada'):
            try:
                fecha_programada = datetime.fromisoformat(data['fecha_programada'])
            except ValueError:
                print(f"⚠️ Fecha inválida: {data['fecha_programada']}, usando fecha actual")
                fecha_programada = datetime.now()
        
        print(f"💾 Agregando contacto: {data.get('nombre')} ({data.get('telefono')})")
        
        # Agregar contacto
        exito = contactos_proactivos_service.agregar_contacto_proactivo(
            telefono=data.get('telefono'),
            nombre=data.get('nombre'),
            contexto=data.get('contexto', ''),
            tipo_campana=data.get('tipo_campana', 'seguimiento'),
            prioridad=data.get('prioridad', 2),
            fecha_programada=fecha_programada,
            mensaje_personalizado=data.get('mensaje_personalizado'),
            observaciones=data.get('observaciones'),
            template_whatsapp=data.get('template_whatsapp')
        )
        
        if exito:
            print(f"✅ Contacto agregado exitosamente: {data.get('nombre')}")
            return jsonify({'success': True, 'message': 'Contacto agregado exitosamente'})
        else:
            print(f"❌ Error al agregar contacto: {data.get('nombre')}")
            return jsonify({'error': 'Error al agregar contacto en base de datos'}), 500
            
    except Exception as e:
        print(f"❌ Excepción en api_add_contacto_proactivo: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/contactos-proactivos/<int:contact_id>/send', methods=['POST'])
def api_send_contacto_proactivo(contact_id):
    """API endpoint para enviar contacto específico"""
    try:
        if not CONTACTOS_PROACTIVOS_AVAILABLE:
            return jsonify({'error': 'Servicio no disponible'}), 500
        
        # Obtener contacto específico
        if not SUPABASE_AVAILABLE:
            return jsonify({'error': 'Base de datos no disponible'}), 500
        
        response = supabase.table('contactos_proactivos')\
            .select('*')\
            .eq('id', contact_id)\
            .execute()
        
        if not response.data:
            return jsonify({'error': 'Contacto no encontrado'}), 404
        
        contacto = response.data[0]
        
        # Procesar envío
        template_whatsapp = contacto.get('template_whatsapp')
        if template_whatsapp:
            exito = contactos_proactivos_service.enviar_plantilla_whatsapp(
                contacto['telefono'], 
                template_whatsapp, 
                contacto
            )
        else:
            mensaje = contactos_proactivos_service.generar_mensaje_personalizado(contacto)
            exito = contactos_proactivos_service.enviar_mensaje_whatsapp(
                contacto['telefono'], 
                mensaje
            )
        
        if exito:
            contactos_proactivos_service.marcar_contacto_enviado(contact_id)
            return jsonify({'success': True, 'message': 'Contacto enviado exitosamente'})
        else:
            return jsonify({'error': 'Error al enviar contacto'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/contactos-proactivos/<int:contact_id>', methods=['DELETE'])
def api_delete_contacto_proactivo(contact_id):
    """API endpoint para eliminar contacto"""
    try:
        if not SUPABASE_AVAILABLE:
            return jsonify({'error': 'Base de datos no disponible'}), 500
        
        response = supabase.table('contactos_proactivos')\
            .delete()\
            .eq('id', contact_id)\
            .execute()
        
        return jsonify({'success': True, 'message': 'Contacto eliminado exitosamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/contactos-proactivos/stats')
def api_contactos_stats():
    """API endpoint para estadísticas de contactos"""
    try:
        if not CONTACTOS_PROACTIVOS_AVAILABLE:
            return jsonify({'error': 'Servicio no disponible'}), 500
        
        stats = contactos_proactivos_service.obtener_estadisticas()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/contactos-proactivos/debug')
def api_debug_contactos():
    """API endpoint para debug de tabla contactos_proactivos"""
    try:
        if not SUPABASE_AVAILABLE:
            return jsonify({'error': 'Supabase no disponible'}), 500
        
        # Obtener un registro para ver la estructura
        response = supabase.table('contactos_proactivos')\
            .select('*')\
            .limit(1)\
            .execute()
        
        sample_record = response.data[0] if response.data else {}
        columns = list(sample_record.keys()) if sample_record else []
        
        # Contar total de registros
        count_response = supabase.table('contactos_proactivos')\
            .select('*', count='exact')\
            .execute()
        
        return jsonify({
            'success': True,
            'columns': columns,
            'sample_record': sample_record,
            'total_records': count_response.count,
            'message': f'Tabla tiene {len(columns)} columnas y {count_response.count} registros'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/process-pending-contacts', methods=['POST'])
def api_process_pending_contacts():
    """API endpoint para procesar contactos pendientes"""
    try:
        if not CONTACTOS_PROACTIVOS_AVAILABLE:
            return jsonify({'error': 'Servicio no disponible'}), 500
        
        # Procesar contactos pendientes
        contactos_proactivos_service.procesar_contactos_pendientes()
        
        return jsonify({
            'success': True,
            'sent': 'procesado',  # TODO: Implementar conteo real
            'errors': 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# API ENDPOINTS PARA CARGA MASIVA
# ============================================================================

@app.route('/api/process-file', methods=['POST'])
def api_process_file():
    """API endpoint para procesar archivo de carga masiva"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No se proporcionó archivo'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Archivo vacío'}), 400
        
        # Procesar archivo según tipo
        if file.filename.endswith('.csv'):
            # Procesar CSV
            import csv
            import io
            import chardet
            
            # Detectar encoding automáticamente
            file_content = file.stream.read()
            detected_encoding = chardet.detect(file_content)
            encoding = detected_encoding.get('encoding', 'utf-8')
            
            print(f"📊 Encoding detectado: {encoding} (confianza: {detected_encoding.get('confidence', 0):.2f})")
            
            # Intentar diferentes encodings si falla
            encodings_to_try = [encoding, 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            
            decoded_content = None
            for enc in encodings_to_try:
                try:
                    decoded_content = file_content.decode(enc)
                    print(f"✅ Decodificado exitosamente con encoding: {enc}")
                    break
                except UnicodeDecodeError:
                    print(f"❌ Error con encoding: {enc}")
                    continue
            
            if not decoded_content:
                return jsonify({'error': 'No se pudo decodificar el archivo. Intenta guardar el CSV con encoding UTF-8.'}), 400
            
            # Leer contenido
            stream = io.StringIO(decoded_content, newline=None)
            csv_input = csv.reader(stream)
            
            headers = next(csv_input)
            rows = list(csv_input)
            
            return jsonify({
                'success': True,
                'data': {
                    'headers': headers,
                    'rows': rows
                }
            })
        
        elif file.filename.endswith(('.xlsx', '.xls')):
            # Procesar Excel
            try:
                import pandas as pd
                print("✅ Pandas importado exitosamente")
            except ImportError:
                return jsonify({'error': 'pandas no está instalado. Instálalo con: pip install pandas'}), 400
            
            try:
                # Leer el contenido del archivo en memoria
                file.stream.seek(0)  # Asegurar que estamos al inicio del archivo
                file_content = file.stream.read()
                
                # Crear un BytesIO object para pandas
                import io
                excel_buffer = io.BytesIO(file_content)
                
                # Intentar leer con openpyxl para .xlsx o xlrd para .xls
                if file.filename.endswith('.xlsx'):
                    df = pd.read_excel(excel_buffer, engine='openpyxl')
                else:  # .xls
                    df = pd.read_excel(excel_buffer, engine='xlrd')
                    
                print(f"📊 Excel leído exitosamente: {df.shape[0]} filas, {df.shape[1]} columnas")
                
            except ImportError as e:
                if 'openpyxl' in str(e):
                    return jsonify({'error': 'openpyxl no está instalado. Instálalo con: pip install openpyxl'}), 400
                elif 'xlrd' in str(e):
                    return jsonify({'error': 'xlrd no está instalado. Instálalo con: pip install xlrd'}), 400
                else:
                    return jsonify({'error': f'Error de dependencia: {str(e)}'}), 400
            except Exception as e:
                return jsonify({'error': f'Error procesando Excel: {str(e)}'}), 400
            
            # Convertir DataFrame a listas
            headers = df.columns.tolist()
            rows = df.values.tolist()
            
            # Convertir NaN values a strings vacíos y manejar tipos de datos
            for i, row in enumerate(rows):
                new_row = []
                for cell in row:
                    if pd.isna(cell):
                        new_row.append('')
                    elif isinstance(cell, (int, float)):
                        # Preservar números como strings para teléfonos
                        if isinstance(cell, float) and cell.is_integer():
                            new_row.append(str(int(cell)))
                        else:
                            new_row.append(str(cell))
                    else:
                        new_row.append(str(cell))
                rows[i] = new_row
            
            return jsonify({
                'success': True,
                'data': {
                    'headers': headers,
                    'rows': rows
                }
            })
        else:
            return jsonify({'error': 'Formato de archivo no soportado'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate-data', methods=['POST'])
def api_validate_data():
    """API endpoint para validar datos antes de importar"""
    try:
        data = request.get_json()
        file_data = data.get('data', {})
        validate_duplicates = data.get('validateDuplicates', True)
        validate_phones = data.get('validatePhones', True)
        
        headers = file_data.get('headers', [])
        rows = file_data.get('rows', [])
        
        # Validación básica
        valid_count = 0
        invalid_count = 0
        validation_results = []
        
        for i, row in enumerate(rows):
            is_valid = True
            errors = []
            
            # Validar que tenga nombre y teléfono
            if len(row) < 2:
                is_valid = False
                errors.append('Faltan campos requeridos')
            elif not row[0] or not row[1]:  # Asumiendo nombre y teléfono en primeras 2 columnas
                is_valid = False
                errors.append('Nombre o teléfono vacío')
            
            # Validar teléfono si está habilitado
            if validate_phones and len(row) > 1:
                telefono = str(row[1]).strip()
                if not re.match(r'^\+?[0-9]{10,12}$', telefono.replace(' ', '').replace('-', '')):
                    is_valid = False
                    errors.append('Formato de teléfono inválido')
            
            validation_results.append({
                'valid': is_valid,
                'errors': errors
            })
            
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
        
        return jsonify({
            'success': True,
            'results': {
                'rows': validation_results,
                'valid': valid_count,
                'invalid': invalid_count
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import-contacts', methods=['POST'])
def api_import_contacts():
    """API endpoint para importar contactos validados"""
    try:
        if not CONTACTOS_PROACTIVOS_AVAILABLE:
            return jsonify({'error': 'Servicio no disponible'}), 500
        
        data = request.get_json()
        file_data = data.get('data', {})
        validation = data.get('validation', {})
        config = data.get('config', {})
        
        headers = file_data.get('headers', [])
        rows = file_data.get('rows', [])
        validation_results = validation.get('rows', [])
        
        # Contadores
        total = 0
        success = 0
        duplicates = 0
        errors = 0
        error_details = []
        
        for i, (row, validation_result) in enumerate(zip(rows, validation_results)):
            total += 1
            
            if not validation_result.get('valid', False):
                errors += 1
                error_details.append({
                    'row': i + 1,
                    'data': str(row),
                    'error': ', '.join(validation_result.get('errors', []))
                })
                continue
            
            try:
                # Extraer datos (asumiendo orden: nombre, teléfono, contexto, ...)
                nombre = row[0] if len(row) > 0 else 'Sin nombre'
                telefono = str(row[1]) if len(row) > 1 else ''
                contexto = row[2] if len(row) > 2 else 'Importado desde archivo'
                
                # Verificar duplicados
                if SUPABASE_AVAILABLE:
                    existing = supabase.table('contactos_proactivos')\
                        .select('id')\
                        .eq('telefono', telefono)\
                        .execute()
                    
                    if existing.data:
                        duplicates += 1
                        continue
                
                # Agregar contacto
                exito = contactos_proactivos_service.agregar_contacto_proactivo(
                    telefono=telefono,
                    nombre=nombre,
                    contexto=contexto,
                    tipo_campana=config.get('campaignType', 'seguimiento'),
                    prioridad=config.get('priority', 2),
                    fecha_programada=datetime.fromisoformat(config['scheduledDate']) if config.get('scheduledDate') else None,
                    template_whatsapp=config.get('whatsappTemplate')
                )
                
                if exito:
                    success += 1
                else:
                    errors += 1
                    error_details.append({
                        'row': i + 1,
                        'data': str(row),
                        'error': 'Error al guardar en base de datos'
                    })
                    
            except Exception as e:
                errors += 1
                error_details.append({
                    'row': i + 1,
                    'data': str(row),
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'results': {
                'total': total,
                'success': success,
                'duplicates': duplicates,
                'errors': errors,
                'errorDetails': error_details
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-template')
def api_download_template():
    """API endpoint para descargar plantilla CSV"""
    try:
        import csv
        import io
        from flask import Response
        
        # Crear CSV template
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow(['nombre', 'telefono', 'contexto', 'observaciones'])
        
        # Ejemplo
        writer.writerow(['Juan Pérez', '+52XXXXXXXXXX', 'Interesado en Sentra', 'Cliente potencial'])
        writer.writerow(['María García', '+52XXXXXXXXXX', 'Consulta sobre financiamiento', 'Requiere seguimiento'])
        
        response = Response(output.getvalue(), mimetype='text/csv')
        response.headers['Content-Disposition'] = 'attachment; filename=plantilla_contactos.csv'
        
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-history')
def api_upload_history():
    """API endpoint para historial de cargas"""
    try:
        # Simular historial por ahora
        history = [
            {
                'date': datetime.now().isoformat(),
                'filename': 'contactos_ejemplo.csv',
                'total_records': 50,
                'success_count': 45,
                'error_count': 5,
                'user': 'Admin'
            }
        ]
        
        return jsonify({'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# API ENDPOINTS PARA WHATSAPP TOKEN MANAGEMENT
# ============================================================================

@app.route('/api/whatsapp/status')
def api_whatsapp_status():
    """API endpoint para verificar estado de WhatsApp"""
    try:
        if not WHATSAPP_SERVICE_AVAILABLE:
            return jsonify({'error': 'Servicio WhatsApp no disponible'}), 500
        
        from services.whatsapp_service import whatsapp_service
        
        token_info = {
            'enabled': whatsapp_service.enabled,
            'token_length': len(whatsapp_service.token) if whatsapp_service.token else 0,
            'token_preview': whatsapp_service.token[:20] + "..." if whatsapp_service.token and len(whatsapp_service.token) > 20 else "No disponible",
            'phone_number_id': whatsapp_service.phone_number_id,
            'connection_test': whatsapp_service.verificar_conexion()
        }
        
        return jsonify({
            'success': True,
            'whatsapp_status': token_info
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/whatsapp/reload-token', methods=['POST'])
def api_whatsapp_reload_token():
    """API endpoint para recargar token de WhatsApp"""
    try:
        if not WHATSAPP_SERVICE_AVAILABLE:
            return jsonify({'error': 'Servicio WhatsApp no disponible'}), 500
        
        from services.whatsapp_service import whatsapp_service
        
        success = whatsapp_service.reload_token()
        
        return jsonify({
            'success': success,
            'message': 'Token recargado exitosamente' if success else 'Error recargando token',
            'token_preview': whatsapp_service.token[:20] + "..." if whatsapp_service.token and len(whatsapp_service.token) > 20 else "No disponible",
            'enabled': whatsapp_service.enabled
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/whatsapp/test-message', methods=['POST'])
def api_whatsapp_test_message():
    """API endpoint para enviar mensaje de prueba"""
    try:
        if not WHATSAPP_SERVICE_AVAILABLE:
            return jsonify({'error': 'Servicio WhatsApp no disponible'}), 500
        
        data = request.get_json()
        telefono = data.get('telefono')
        
        if not telefono:
            return jsonify({'error': 'Teléfono requerido'}), 400
        
        from services.whatsapp_service import whatsapp_service
        
        mensaje_prueba = f"🧪 Mensaje de prueba desde el dashboard - {datetime.now().strftime('%H:%M:%S')}"
        
        result = whatsapp_service.enviar_mensaje(telefono, mensaje_prueba)
        
        return jsonify({
            'success': result.get('success', False),
            'result': result,
            'message': 'Mensaje de prueba enviado' if result.get('success') else 'Error enviando mensaje de prueba'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/temperature/config')
def api_get_temperature_config():
    """API endpoint para obtener configuración actual de temperaturas"""
    try:
        from config import get_config
        config = get_config()()
        
        return jsonify({
            'success': True,
            'temperature_config': {
                'default': config.TEMPERATURE_DEFAULT,
                'precise': config.TEMPERATURE_PRECISE,
                'financing': config.TEMPERATURE_FINANCING,
                'creative': config.TEMPERATURE_CREATIVE,
                'greeting': config.TEMPERATURE_GREETING
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/temperature/test', methods=['POST'])
def api_test_temperature():
    """API endpoint para probar respuesta con temperatura específica"""
    try:
        data = request.get_json()
        mensaje = data.get('mensaje', 'Hola')
        temperatura = float(data.get('temperatura', 0.4))
        
        if CONVERSATION_SERVICE_AVAILABLE:
            # Simular análisis de intención
            intent_info = conversation_service.analyze_message_intent(mensaje)
            
            # Obtener temperatura recomendada
            temp_recomendada = conversation_service.get_temperature_for_intent(intent_info)
            
            return jsonify({
                'success': True,
                'mensaje': mensaje,
                'intent_detectado': intent_info['intent'],
                'temperatura_solicitada': temperatura,
                'temperatura_recomendada': temp_recomendada,
                'explicacion': f"Para intención '{intent_info['intent']}' se recomienda temperatura {temp_recomendada}"
            })
        else:
            return jsonify({'error': 'Servicio de conversación no disponible'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/financing/test', methods=['POST'])
def api_test_financing_conversation():
    """API endpoint para probar conversación de financiamiento"""
    try:
        data = request.get_json()
        mensaje = data.get('mensaje', '¿Qué planes de financiamiento tienen?')
        
        if CONVERSATION_SERVICE_AVAILABLE:
            # Analizar intención y pasos conversacionales
            intent_info = conversation_service.analyze_message_intent(mensaje)
            
            # Simular historial vacío para primera consulta
            historial_simulado = []
            
            # Obtener contexto RAG específico para financiamiento
            try:
                from rag.buscador_supabase import recuperar_contexto
                contexto_rag = recuperar_contexto(mensaje, k=2)
            except:
                contexto_rag = "RAG no disponible"
            
            # Construir contexto del sistema
            system_context = conversation_service._build_system_context(
                lead=None, 
                intent_info=intent_info, 
                contexto_rag=contexto_rag
            )
            
            # Obtener temperatura recomendada
            temperatura = conversation_service.get_temperature_for_intent(intent_info)
            
            return jsonify({
                'success': True,
                'mensaje_analizado': mensaje,
                'intent_detectado': intent_info,
                'temperatura_aplicada': temperatura,
                'contexto_sistema': system_context[:500] + "..." if len(system_context) > 500 else system_context,
                'rag_context': contexto_rag[:200] + "..." if len(contexto_rag) > 200 else contexto_rag,
                'recomendaciones': {
                    'next_step': intent_info.get('conversation_step', 'initial'),
                    'should_ask_qualifying_questions': intent_info.get('conversation_step') == 'initial',
                    'has_vehicle_use': 'uso_vehiculo' in intent_info,
                    'has_down_payment_info': 'tiene_enganche' in intent_info
                }
            })
        else:
            return jsonify({'error': 'Servicio de conversación no disponible'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/status')
def api_system_status():
    """API endpoint para estado completo del sistema"""
    try:
        system_status = {
            'whatsapp': {'status': 'disconnected', 'message': 'Service not available'},
            'database': {'status': 'disconnected', 'message': 'Service not available'},
            'followup_service': {'status': 'inactive', 'message': 'Service not available'},
            'timestamp': datetime.now().isoformat()
        }
        
        # Check WhatsApp service
        if WHATSAPP_SERVICE_AVAILABLE:
            from services.whatsapp_service import whatsapp_service
            if whatsapp_service.enabled and whatsapp_service.verificar_conexion():
                system_status['whatsapp'] = {
                    'status': 'connected',
                    'message': 'WhatsApp Business API connected',
                    'token_preview': whatsapp_service.token[:20] + "..." if whatsapp_service.token else "No token"
                }
            elif whatsapp_service.enabled:
                system_status['whatsapp'] = {
                    'status': 'error',
                    'message': 'WhatsApp configured but connection failed'
                }
            else:
                system_status['whatsapp'] = {
                    'status': 'disabled',
                    'message': 'WhatsApp not configured'
                }
        
        # Check database
        if SUPABASE_AVAILABLE:
            try:
                test_response = supabase.table('contactos_proactivos').select('id').limit(1).execute()
                system_status['database'] = {
                    'status': 'connected',
                    'message': 'Database connection successful'
                }
            except Exception as e:
                system_status['database'] = {
                    'status': 'error',
                    'message': f'Database error: {str(e)}'
                }
        
        # Check followup service
        if CONTACTOS_PROACTIVOS_AVAILABLE:
            system_status['followup_service'] = {
                'status': 'active',
                'message': 'Proactive contacts service running'
            }
        
        return jsonify({
            'success': True,
            'system_status': system_status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# TESTING ENDPOINTS
# ============================================================================

@app.route('/test-webhook', methods=['POST'])
def test_webhook():
    """Endpoint para probar el webhook con datos simulados"""
    try:
        # Simular mensaje de WhatsApp
        test_data = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messages": [{
                            "from": "526647499577",
                            "id": f"test_msg_{datetime.now().timestamp()}",
                            "type": "text",
                            "text": {"body": request.json.get("message", "Hola, me interesa un auto")},
                            "timestamp": str(int(datetime.now().timestamp()))
                        }],
                        "contacts": [{
                            "wa_id": "526647499577",
                            "profile": {"name": request.json.get("name", "Cliente Test")}
                        }]
                    }
                }]
            }]
        }
        
        print(f"🧪 Probando webhook con datos simulados...")
        
        # Procesar mensaje simulado
        for entry in test_data.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "messages":
                    process_whatsapp_message(change.get("value", {}))
        
        return jsonify({
            "status": "success",
            "message": "Webhook test completed successfully"
        }), 200
        
    except Exception as e:
        print(f"❌ Error en test webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/test-conversation', methods=['POST'])
def test_conversation():
    """Endpoint para probar solo la generación de respuestas"""
    try:
        data = request.json
        telefono = data.get('telefono', '526647499577')
        mensaje = data.get('mensaje', 'Hola')
        nombre = data.get('nombre', 'Cliente Test')
        
        if CONVERSATION_SERVICE_AVAILABLE:
            respuesta = conversation_service.generate_response(
                telefono=telefono,
                mensaje_usuario=mensaje,
                nombre_usuario=nombre
            )
            
            return jsonify({
                "status": "success",
                "telefono": telefono,
                "mensaje_enviado": mensaje,
                "respuesta_generada": respuesta
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Conversation service not available"
            }), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/test-chatwoot-sync', methods=['POST'])
def test_chatwoot_sync():
    """Endpoint para probar sincronización con Chatwoot"""
    try:
        data = request.json
        telefono = data.get('telefono', '526647499577')
        mensaje = data.get('mensaje', 'Mensaje de prueba')
        nombre = data.get('nombre', 'Cliente Test')
        
        print(f"🧪 Probando sincronización con Chatwoot para {telefono}")
        
        # Probar envío de mensaje del cliente a Chatwoot
        resultado = send_customer_message_to_chatwoot(telefono, mensaje, nombre)
        
        return jsonify({
            "status": "success" if resultado else "error",
            "telefono": telefono,
            "mensaje": mensaje,
            "resultado_chatwoot": resultado,
            "message": "Mensaje enviado a Chatwoot" if resultado else "Error enviando a Chatwoot"
        }), 200
        
    except Exception as e:
        print(f"❌ Error en test-chatwoot-sync: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/debug-webhook', methods=['POST'])
def debug_webhook():
    """Endpoint para debugear webhooks entrantes"""
    try:
        data = request.json
        headers_dict = dict(request.headers)
        
        print(f"🔍 DEBUG WEBHOOK - Headers: {headers_dict}")
        print(f"🔍 DEBUG WEBHOOK - Data: {json.dumps(data, indent=2)}")
        
        # Detectar origen
        origen = "desconocido"
        if data.get("object") == "whatsapp_business_account":
            origen = "WhatsApp Business API"
        elif data.get("event") == "message_created":
            origen = "Chatwoot"
        
        return jsonify({
            "status": "success",
            "origen": origen,
            "data_received": data,
            "headers": headers_dict,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ Error en debug-webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================================
# WEBHOOK PRINCIPAL (mantener funcionalidad original)
# ============================================================================

@app.route('/webhook', methods=['GET', 'POST'])
@app.route('/whatsapp', methods=['GET', 'POST'])
def webhook():
    """Webhook principal para recibir eventos de WhatsApp y Chatwoot."""
    
    # GET: Verificación del Webhook (usado por WhatsApp y a veces por otros servicios)
    if request.method == 'GET':
        print("ℹ️ Recibida petición GET para verificación de webhook.")
        # Lógica de verificación para WhatsApp
        verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "nissan_verify_token")
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode == "subscribe" and token == verify_token:
            print(f"✅ Webhook de WhatsApp verificado exitosamente. Challenge: {challenge}")
            return challenge, 200
        else:
            print(f"❌ Falló la verificación del webhook. Modo: {mode}, Token recibido: {token}")
            return "Verification failed", 403

    # POST: Procesamiento de eventos (mensajes, etc.)
    if request.method == 'POST':
        headers = dict(request.headers)
        raw_data = request.get_data(as_text=True)
        print("📥 Recibida petición POST en /webhook.")
        print(f"   - Headers: {json.dumps(headers, indent=2)}")
        print(f"   - Raw Body: {raw_data}")

        try:
            data = request.get_json()
            print(f"   - JSON Body: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"❌ Error al parsear JSON del body: {e}")
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        try:
            # Identificar el origen del webhook y procesar
            if data.get("object") == "whatsapp_business_account":
                print("➡️ Origen detectado: WhatsApp Business API.")
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        if change.get("field") == "messages":
                            print("🔄 Ejecutando process_whatsapp_message() desde WhatsApp API")
                            process_whatsapp_message(change.get("value", {}))
            
            elif data.get("event") == "message_created":
                print("➡️ Origen detectado: Chatwoot.")
                message_type = data.get("message_type")
                sender_type = data.get("sender", {}).get("type", "unknown")
                
                print(f"   - Evento de Chatwoot: {data.get('event')}")
                print(f"   - Tipo de Mensaje: {message_type}")
                print(f"   - Tipo de Remitente: {sender_type}")

                # Filtrar mensajes del bot/agente para evitar loops
                sender_name = data.get("sender", {}).get("name", "")
                sender_id = data.get("sender", {}).get("id", 0)
                
                # Solo filtrar si es claramente un agente/bot, no por nombre del cliente
                is_bot_message = (
                    sender_type in ["agent_bot", "agent"] or
                    sender_id == 34  # ID del agente César según el JSON
                )
                
                if message_type == "incoming" and not is_bot_message:
                    print("✅ Procesando mensaje 'incoming' de cliente...")
                    print("🔄 Ejecutando process_chatwoot_message() desde Chatwoot")
                    process_chatwoot_message(data)
                else:
                    print(f"⚠️ Mensaje de Chatwoot ignorado - Tipo: {message_type}, Sender: {sender_type}, ID: {sender_id}, Nombre: {sender_name}")
            
            else:
                print("⚠️ Webhook no reconocido. No coincide con WhatsApp ni Chatwoot.")
                print(f"   - Object: {data.get('object', 'N/A')}, Event: {data.get('event', 'N/A')}")

            return jsonify({"status": "success"}), 200

        except Exception as e:
            print(f"❌ Error fatal durante el procesamiento del webhook: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # Manejar otros métodos HTTP si es necesario
    return "Method Not Allowed", 405

def process_chatwoot_message(data):
    """Procesa mensajes entrantes de Chatwoot (NUEVA ARQUITECTURA: Solo Chatwoot)"""
    try:
        # Extraer información del mensaje de Chatwoot
        mensaje_texto = data.get("content", "").strip()
        source_id = data.get("source_id", "")
        conversation_id = data.get("conversation", {}).get("id")
        
        # Obtener información del remitente
        sender = data.get("sender", {})
        telefono = sender.get("phone_number", "").replace("+", "")
        nombre_usuario = sender.get("name", "Cliente")
        
        # Validar que tengamos datos mínimos
        if not mensaje_texto or not telefono or not conversation_id:
            print("⚠️ Mensaje de Chatwoot inválido: falta contenido, teléfono o conversation_id")
            return
        
        print(f"📱 [CHATWOOT-ONLY] Procesando mensaje de {nombre_usuario} ({telefono}): {mensaje_texto}")
        print(f"💬 Conversation ID: {conversation_id}")
        
        # Verificar duplicados usando source_id de Chatwoot
        if is_message_already_processed(source_id):
            print(f"⚠️ Mensaje ya procesado: {source_id}")
            return
        
        # Marcar mensaje como procesado
        mark_message_as_processed(source_id)
        
        # Generar respuesta usando el servicio de conversación
        if CONVERSATION_SERVICE_AVAILABLE:
            try:
                respuesta = conversation_service.generate_response(
                    telefono=telefono,
                    mensaje_usuario=mensaje_texto,
                    nombre_usuario=nombre_usuario
                )
                
                # Enviar respuesta SOLO a Chatwoot (que se encarga de WhatsApp)
                if respuesta:
                    # Manejar nueva estructura de respuesta con posibles imágenes
                    if isinstance(respuesta, dict):
                        texto_respuesta = respuesta.get('text', '')
                        
                        # SOLO enviar a Chatwoot - él se encarga de WhatsApp
                        try:
                            from chatwoot_api import enviar_mensaje_publico
                            print(f"🔄 [CHATWOOT-ONLY] Enviando respuesta del bot: {texto_respuesta[:50]}...")
                            resultado = enviar_mensaje_publico(conversation_id, texto_respuesta)
                            
                            if resultado:
                                print(f"✅ Respuesta enviada a Chatwoot conversation {conversation_id}")
                            else:
                                print(f"❌ Error enviando respuesta a Chatwoot")
                        except Exception as e:
                            print(f"⚠️ Error enviando respuesta a Chatwoot: {e}")
                        
                        # TODO: Manejar imágenes a través de Chatwoot si es necesario
                        if respuesta.get('type') == 'text_with_image':
                            print(f"📸 [INFO] Cliente solicitó imagen: {respuesta.get('image_path')} - Enviando nota")
                            try:
                                from chatwoot_api import crear_mensaje_privado
                                nota_imagen = f"📸 Cliente solicitó imagen: {respuesta.get('modelo')} ({respuesta.get('image_type')})\n🔗 Ruta: {respuesta.get('image_path')}"
                                crear_mensaje_privado(conversation_id, nota_imagen)
                            except Exception as e:
                                print(f"⚠️ Error creando nota de imagen: {e}")
                    else:
                        # Compatibilidad con respuesta antigua (string)
                        try:
                            from chatwoot_api import enviar_mensaje_publico
                            print(f"🔄 [CHATWOOT-ONLY] Enviando respuesta: {respuesta[:50]}...")
                            resultado = enviar_mensaje_publico(conversation_id, respuesta)
                            
                            if resultado:
                                print(f"✅ Respuesta enviada a Chatwoot conversation {conversation_id}")
                            else:
                                print(f"❌ Error enviando respuesta a Chatwoot")
                        except Exception as e:
                            print(f"⚠️ Error enviando respuesta a Chatwoot: {e}")
                else:
                    print(f"⚠️ No se generó respuesta para {telefono}")
                    
            except Exception as e:
                print(f"❌ Error generando respuesta: {e}")
                # Respuesta de fallback SOLO a Chatwoot
                respuesta_fallback = "Hola! 😅 Tuve un problemita técnico, ¿me puedes escribir en un ratito?"
                
                try:
                    from chatwoot_api import enviar_mensaje_publico
                    print(f"🔄 [FALLBACK] Enviando mensaje de error...")
                    enviar_mensaje_publico(conversation_id, respuesta_fallback)
                except Exception as e:
                    print(f"⚠️ Error enviando fallback a Chatwoot: {e}")
        else:
            # Respuesta básica SOLO a Chatwoot
            respuesta_basica = f"¡Hola {nombre_usuario}! 😁 Soy César de Nissan. Gracias por escribir. ¿En qué te puedo ayudar?"
            
            try:
                from chatwoot_api import enviar_mensaje_publico
                print(f"🔄 [CHATWOOT-ONLY] Enviando respuesta básica...")
                enviar_mensaje_publico(conversation_id, respuesta_basica)
            except Exception as e:
                print(f"⚠️ Error enviando respuesta básica a Chatwoot: {e}")
            
    except Exception as e:
        print(f"❌ Error procesando mensaje de Chatwoot: {e}")

def process_whatsapp_message(message_data):
    """DEPRECADO: WhatsApp Business API directo - Ahora usamos solo Chatwoot"""
    print("⚠️ [DEPRECADO] Recibido mensaje directo de WhatsApp API - Redirigiendo a Chatwoot")
    print("💡 Configuración recomendada: Solo usar webhook de Chatwoot")
    print("📋 Para configurar: WhatsApp Business → Chatwoot → Tu Bot")
    
    # Log para debugging si alguien sigue enviando mensajes directos
    print(f"📊 Datos recibidos: {message_data}")
    
    # No procesar - todo debe venir de Chatwoot
    return

def is_message_already_processed(message_id: str) -> bool:
    """Verifica si un mensaje ya fue procesado"""
    current_time = time.time()
    
    # Limpiar mensajes antiguos (más de 1 hora)
    limpiar_mensajes_antiguos()
    
    # Verificar si el mensaje ya existe
    if message_id in mensajes_procesados:
        return True
    
    return False

def mark_message_as_processed(message_id: str):
    """Marca un mensaje como procesado"""
    mensajes_procesados[message_id] = time.time()

# Funciones deprecadas eliminadas - se usaba solo Chatwoot
# send_typing_indicator() - Chatwoot maneja automáticamente
# send_whatsapp_response() - Reemplazado por enviar_mensaje_publico()
# send_whatsapp_image() - Reemplazado por notas privadas en Chatwoot

def send_message_to_chatwoot(telefono: str, mensaje: str):
    """Envía mensaje también a Chatwoot para que aparezca en la interfaz"""
    try:
        from chatwoot_api import obtener_conversacion_por_telefono, enviar_mensaje_publico, buscar_contacto, crear_contacto, crear_conversacion
        
        # Buscar conversación activa del teléfono
        conversacion = obtener_conversacion_por_telefono(telefono)
        
        if conversacion:
            conversation_id = conversacion.get('id')
            resultado = enviar_mensaje_publico(conversation_id, mensaje)
            
            if resultado:
                print(f"✅ Mensaje enviado a Chatwoot para {telefono}")
                return True
            else:
                print(f"❌ Error enviando mensaje a Chatwoot para {telefono}")
                return False
        else:
            print(f"⚠️ No se encontró conversación activa en Chatwoot para {telefono}, creando una nueva...")
            
            # Buscar o crear contacto
            contacto = buscar_contacto(telefono)
            if not contacto:
                contacto = crear_contacto("Cliente", telefono)
                if not contacto:
                    print(f"❌ No se pudo crear contacto en Chatwoot para {telefono}")
                    return False
            
            # Crear nueva conversación
            nueva_conversacion = crear_conversacion(contacto['id'])
            if nueva_conversacion:
                conversation_id = nueva_conversacion.get('id')
                resultado = enviar_mensaje_publico(conversation_id, mensaje)
                
                if resultado:
                    print(f"✅ Nueva conversación creada y mensaje enviado a Chatwoot para {telefono}")
                    return True
                else:
                    print(f"❌ Error enviando mensaje a nueva conversación en Chatwoot para {telefono}")
                    return False
            else:
                print(f"❌ No se pudo crear conversación en Chatwoot para {telefono}")
                return False
            
    except Exception as e:
        print(f"❌ Error enviando a Chatwoot: {e}")
        return False

def send_customer_message_to_chatwoot(telefono: str, mensaje: str, nombre_usuario: str = None, message_id: str = None):
    """Envía el mensaje del CLIENTE a Chatwoot para que aparezca en la interfaz"""
    print(f"➡️ Iniciando send_customer_message_to_chatwoot para {telefono}")
    try:
        from chatwoot_api import obtener_conversacion_por_telefono, buscar_contacto, crear_contacto, crear_conversacion, enviar_mensaje_incoming
        
        # 1. Buscar contacto
        print("   - Buscando contacto...")
        contacto = buscar_contacto(telefono)
        if not contacto:
            print(f"   - Contacto no encontrado, creando uno nuevo para {telefono}")
            nombre = nombre_usuario or "Cliente"
            contacto = crear_contacto(nombre, telefono)
            if not contacto:
                print(f"   - ❌ FATAL: No se pudo crear contacto en Chatwoot para {telefono}")
                return False
        print(f"   - ✅ Contacto ID: {contacto.get('id')}")

        # 2. Buscar conversación
        print("   - Buscando conversación...")
        conversacion = obtener_conversacion_por_telefono(telefono)
        
        if not conversacion:
            print(f"   - Conversación no encontrada para {telefono}, creando una nueva...")
            nueva_conversacion = crear_conversacion(contacto['id'])
            if nueva_conversacion and 'id' in nueva_conversacion:
                conversacion = nueva_conversacion
                print(f"   - ✅ Nueva conversación creada ID: {conversacion.get('id')}")
            else:
                print(f"   - ❌ FATAL: No se pudo crear conversación en Chatwoot. Respuesta: {nueva_conversacion}")
                return False
        
        conversation_id = conversacion.get('id')
        print(f"   - ✅ Usando conversación ID: {conversation_id}")

        # 3. Enviar mensaje
        print(f"   - Enviando mensaje a Chatwoot (message_id: {message_id})...")
        resultado = enviar_mensaje_incoming(conversation_id, mensaje, telefono, message_id)
        
        if resultado:
            print(f"   - ✅ Mensaje del cliente enviado a Chatwoot exitosamente.")
            return True
        else:
            print(f"   - ❌ Error enviando mensaje del cliente a Chatwoot.")
            return False
            
    except Exception as e:
        import traceback
        print(f"❌ EXCEPCIÓN FATAL en send_customer_message_to_chatwoot: {e}")
        traceback.print_exc()
        return False

# ============================================================================
# RUTAS DE COMPATIBILIDAD (mantener URLs anteriores funcionando)
# ============================================================================

@app.route('/contactos_proactivos')
def contactos_proactivos_legacy():
    """Ruta de compatibilidad - redirigir al nuevo dashboard"""
    return redirect(url_for('main.dashboard'))

@app.route('/dashboard_legacy')
def dashboard_legacy():
    """Dashboard legacy - redirigir al nuevo"""
    return redirect(url_for('main.dashboard'))

# ============================================================================
# INICIALIZACIÓN Y EJECUCIÓN
# ============================================================================

def inicializar_servicios():
    """Inicializa todos los servicios de la aplicación"""
    print("🚀 Inicializando servicios...")
    
    # Inicializar servicio de contactos proactivos
    if CONTACTOS_PROACTIVOS_AVAILABLE:
        try:
            contactos_proactivos_service.iniciar_servicio_automatico()
            print("✅ Servicio de contactos proactivos iniciado")
        except Exception as e:
            print(f"⚠️ Error iniciando servicio de contactos proactivos: {e}")
    
    print("✅ Servicios inicializados")

# Para Railway/Gunicorn
initializer_done = False
if not initializer_done:
    inicializar_servicios()
    initializer_done = True

if __name__ == '__main__':
    # Configuración del servidor para desarrollo local
    try:
        port = int(os.environ.get('PORT', '5001'))
    except (ValueError, TypeError):
        Logger.warning("PORT inválida, usando 5001", "APP")
        port = 5001
    
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    Logger.startup("NISSAN CHATBOT SERVER")
    Logger.info(f"Puerto: {port}", "APP")
    Logger.info(f"Debug: {debug}", "APP")
    Logger.info(f"Dashboard: http://localhost:{port}/dashboard", "APP")
    Logger.success("Servidor listo y escuchando", "APP")
    
    app.run(host='0.0.0.0', port=port, debug=debug)