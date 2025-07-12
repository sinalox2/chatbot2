from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from services.contactos_proactivos import ContactosProactivosService
    from supabase_client import supabase
except ImportError as e:
    print(f"⚠️ Error importing dependencies in contacts_routes: {e}")

# Create blueprint
contacts_bp = Blueprint('contacts', __name__, template_folder='../templates')

# Initialize service
try:
    contactos_service = ContactosProactivosService()
except:
    contactos_service = None

@contacts_bp.route('/contactos_proactivos')
def contactos_proactivos():
    """Dashboard de contactos proactivos"""
    try:
        # Get basic stats
        stats = {
            'pending_count': 0,
            'sent_count': 0,
            'responded_count': 0,
            'error_count': 0
        }
        
        if supabase:
            # Get stats from database
            response = supabase.table('contactos_proactivos').select('estado').execute()
            contacts = response.data or []
            
            for contact in contacts:
                estado = contact.get('estado', 'pendiente')
                if estado == 'pendiente':
                    stats['pending_count'] += 1
                elif estado == 'enviado':
                    stats['sent_count'] += 1
                elif estado == 'respondido':
                    stats['responded_count'] += 1
                elif estado == 'error':
                    stats['error_count'] += 1
        
        return render_template('contactos_proactivos.html', stats=stats)
    except Exception as e:
        print(f"❌ Error en contactos proactivos: {e}")
        return render_template('contactos_proactivos.html', stats={})

@contacts_bp.route('/carga_masiva')
def carga_masiva():
    """Dashboard de carga masiva"""
    return render_template('carga_masiva.html')