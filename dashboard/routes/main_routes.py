from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime, timedelta
import json
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from dashboard.services.advanced_dashboard import AdvancedDashboard
    from services.lead_tracking_service import LeadTrackingService
    from services.contactos_proactivos import ContactosProactivosService
    from supabase_client import supabase
except ImportError as e:
    print(f"⚠️ Error importing dependencies in main_routes: {e}")

# Create blueprint
main_bp = Blueprint('main', __name__, template_folder='../templates')

# Initialize services
dashboard_service = AdvancedDashboard()
lead_service = LeadTrackingService()
contactos_service = ContactosProactivosService()

@main_bp.route('/')
@main_bp.route('/dashboard')
def dashboard():
    """Dashboard principal con métricas en tiempo real"""
    try:
        # Get dashboard stats
        stats = get_dashboard_stats()
        chart_data = get_chart_data()
        status_data = get_status_distribution()
        recent_activity = get_recent_activity()
        
        return render_template('dashboard_main.html',
                             stats=stats,
                             chart_data=chart_data,
                             status_data=status_data,
                             recent_activity=recent_activity,
                             last_update=datetime.now().strftime('%H:%M:%S'),
                             last_sync=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        print(f"❌ Error en dashboard: {e}")
        return render_template('dashboard_main.html',
                             stats={},
                             chart_data={'labels': [], 'leads_data': []},
                             status_data={'labels': [], 'values': []},
                             recent_activity=[],
                             last_update=datetime.now().strftime('%H:%M:%S'),
                             last_sync=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@main_bp.route('/api/dashboard-data')
def api_dashboard_data():
    """API endpoint para obtener datos del dashboard en tiempo real"""
    try:
        data = {
            'stats': get_dashboard_stats(),
            'chart_data': get_chart_data(),
            'status_data': get_status_distribution(),
            'recent_activity': get_recent_activity(),
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/real-time-stats')
def api_real_time_stats():
    """API endpoint para estadísticas en tiempo real (sidebar)"""
    try:
        # Get pending contacts count
        pending_contacts = 0
        follow_ups = 0
        
        if supabase:
            # Count pending contacts
            pending_response = supabase.table('contactos_proactivos')\
                .select('*', count='exact')\
                .eq('estado', 'pendiente')\
                .execute()
            pending_contacts = pending_response.count or 0
            
            # Count follow-ups needed
            leads_response = supabase.table('leads_tracking_pro')\
                .select('*', count='exact')\
                .not_.in_('estado', ['vendido', 'perdido_interes', 'descalificado'])\
                .lte('proximo_seguimiento', datetime.now().isoformat())\
                .execute()
            follow_ups = leads_response.count or 0
        
        return jsonify({
            'pending_contacts': pending_contacts,
            'follow_ups': follow_ups,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/send-pending-contacts', methods=['POST'])
def api_send_pending_contacts():
    """API endpoint para enviar contactos pendientes"""
    try:
        # Process pending contacts
        result = contactos_service.procesar_contactos_pendientes()
        
        return jsonify({
            'success': True,
            'sent': result.get('sent', 0),
            'errors': result.get('errors', 0),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/export-dashboard-data')
def api_export_dashboard_data():
    """API endpoint para exportar datos del dashboard"""
    try:
        # Get all data for export
        data = {
            'stats': get_dashboard_stats(),
            'leads': get_leads_data(),
            'contacts': get_contacts_data(),
            'generated_at': datetime.now().isoformat()
        }
        
        # Create CSV response
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Métrica', 'Valor'])
        
        # Write stats
        for key, value in data['stats'].items():
            writer.writerow([key, value])
        
        # Create response
        from flask import Response
        response = Response(output.getvalue(), mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename=dashboard_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_dashboard_stats():
    """Obtiene estadísticas principales del dashboard"""
    try:
        stats = {
            'total_leads': 0,
            'hot_leads': 0,
            'pending_followups': 0,
            'monthly_revenue': 0
        }
        
        if supabase:
            # Total leads
            total_response = supabase.table('leads_tracking_pro')\
                .select('*', count='exact')\
                .execute()
            stats['total_leads'] = total_response.count or 0
            
            # Hot leads
            hot_response = supabase.table('leads_tracking_pro')\
                .select('*', count='exact')\
                .eq('temperatura', 'caliente')\
                .execute()
            stats['hot_leads'] = hot_response.count or 0
            
            # Pending follow-ups
            followup_response = supabase.table('leads_tracking_pro')\
                .select('*', count='exact')\
                .not_.in_('estado', ['vendido', 'perdido_interes', 'descalificado'])\
                .lte('proximo_seguimiento', datetime.now().isoformat())\
                .execute()
            stats['pending_followups'] = followup_response.count or 0
            
            # Monthly revenue estimate
            current_month = datetime.now().strftime('%Y-%m')
            sold_response = supabase.table('leads_tracking_pro')\
                .select('valor_estimado_venta')\
                .eq('estado', 'vendido')\
                .gte('fecha_creacion', f'{current_month}-01')\
                .execute()
            
            monthly_revenue = sum(lead.get('valor_estimado_venta', 0) for lead in sold_response.data or [])
            stats['monthly_revenue'] = int(monthly_revenue)
        
        return stats
    except Exception as e:
        print(f"❌ Error getting dashboard stats: {e}")
        return {'total_leads': 0, 'hot_leads': 0, 'pending_followups': 0, 'monthly_revenue': 0}

def get_chart_data():
    """Obtiene datos para gráficos del dashboard"""
    try:
        # Get last 30 days
        dates = []
        leads_data = []
        
        for i in range(30):
            date = datetime.now() - timedelta(days=i)
            dates.append(date.strftime('%m/%d'))
            
            if supabase:
                day_start = date.strftime('%Y-%m-%d')
                day_end = (date + timedelta(days=1)).strftime('%Y-%m-%d')
                
                response = supabase.table('leads_tracking_pro')\
                    .select('*', count='exact')\
                    .gte('fecha_creacion', day_start)\
                    .lt('fecha_creacion', day_end)\
                    .execute()
                
                leads_data.append(response.count or 0)
            else:
                leads_data.append(0)
        
        # Reverse to show chronological order
        dates.reverse()
        leads_data.reverse()
        
        return {
            'labels': json.dumps(dates),
            'leads_data': json.dumps(leads_data)
        }
    except Exception as e:
        print(f"❌ Error getting chart data: {e}")
        return {'labels': json.dumps([]), 'leads_data': json.dumps([])}

def get_status_distribution():
    """Obtiene distribución de leads por estado"""
    try:
        if not supabase:
            return {'labels': json.dumps([]), 'values': json.dumps([])}
        
        response = supabase.table('leads_tracking_pro')\
            .select('estado')\
            .execute()
        
        # Count by status
        status_counts = {}
        for lead in response.data or []:
            status = lead.get('estado', 'desconocido')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Get top 5 statuses
        top_statuses = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        labels = [status[0] for status in top_statuses]
        values = [status[1] for status in top_statuses]
        
        return {
            'labels': json.dumps(labels),
            'values': json.dumps(values)
        }
    except Exception as e:
        print(f"❌ Error getting status distribution: {e}")
        return {'labels': json.dumps([]), 'values': json.dumps([])}

def get_recent_activity():
    """Obtiene actividad reciente"""
    try:
        activities = []
        
        if supabase:
            # Get recent interactions
            response = supabase.table('interacciones_leads')\
                .select('*')\
                .order('fecha', desc=True)\
                .limit(10)\
                .execute()
            
            for interaction in response.data or []:
                activities.append({
                    'time': datetime.fromisoformat(interaction['fecha'].replace('Z', '+00:00')).strftime('%H:%M'),
                    'contact': interaction.get('telefono', 'Unknown'),
                    'action': interaction.get('descripcion', 'No description'),
                    'status': 'completed',
                    'status_text': 'Completado'
                })
        
        return activities
    except Exception as e:
        print(f"❌ Error getting recent activity: {e}")
        return []

def get_leads_data():
    """Obtiene datos de leads para exportación"""
    try:
        if not supabase:
            return []
        
        response = supabase.table('leads_tracking_pro')\
            .select('*')\
            .order('fecha_creacion', desc=True)\
            .execute()
        
        return response.data or []
    except Exception as e:
        print(f"❌ Error getting leads data: {e}")
        return []

def get_contacts_data():
    """Obtiene datos de contactos para exportación"""
    try:
        if not supabase:
            return []
        
        response = supabase.table('contactos_proactivos')\
            .select('*')\
            .order('fecha_creacion', desc=True)\
            .execute()
        
        return response.data or []
    except Exception as e:
        print(f"❌ Error getting contacts data: {e}")
        return []