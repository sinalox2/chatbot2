#!/usr/bin/env python3
"""
Script para debuggear el flujo de contactos proactivos
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(override=True)

from services.contactos_proactivos import ContactosProactivosService

def debug_contacto_proactivo():
    """Debug del flujo completo"""
    print("🔍 Debug del sistema de contactos proactivos")
    print("=" * 50)
    
    service = ContactosProactivosService()
    
    # Simular un contacto con template y primer contacto
    contacto_test = {
        'id': 999,
        'telefono': '+5266871006601',
        'nombre': 'Juan Test',
        'contexto': 'Cliente interesado en Sentra',
        'tipo_campana': 'seguimiento',
        'template_whatsapp': 'saludo_lead',
        'observaciones': 'Template: saludo_lead | Primer contacto: Si',
        'mensaje_personalizado': None
    }
    
    print("📱 Contacto de prueba:")
    for key, value in contacto_test.items():
        print(f"  {key}: {value}")
    
    print("\n🔍 Verificando lógica de detección:")
    
    # Extraer template de observaciones
    template_whatsapp = contacto_test.get('template_whatsapp')
    if not template_whatsapp and contacto_test.get('observaciones'):
        observaciones = contacto_test.get('observaciones', '')
        if 'Template:' in observaciones:
            template_part = observaciones.split('Template:')[1].strip()
            if '|' in template_part:
                template_whatsapp = template_part.split('|')[0].strip()
            else:
                template_whatsapp = template_part.strip()
            print(f"  📱 Template encontrado en observaciones: {template_whatsapp}")
    
    # Validar que el template no esté vacío
    if template_whatsapp and template_whatsapp.strip() == '':
        template_whatsapp = None
    
    # Verificar si es primer contacto o contacto existente
    observaciones = contacto_test.get('observaciones', '')
    es_primer_contacto = 'Primer contacto' in observaciones
    es_contacto_existente = 'Contacto existente' in observaciones
    
    print(f"  📱 Template final: {template_whatsapp}")
    print(f"  🆕 Es primer contacto: {es_primer_contacto}")
    print(f"  👤 Es contacto existente: {es_contacto_existente}")
    
    # Determinar flujo
    print("\n🚀 Determinando flujo:")
    
    if es_primer_contacto and template_whatsapp:
        print("  ✅ PRIMER CONTACTO + TEMPLATE → Enviar plantilla")
        
        # Probar envío de plantilla
        print("\n📱 Probando envío de plantilla...")
        resultado = service.enviar_plantilla_whatsapp(
            telefono=contacto_test['telefono'],
            template_name=template_whatsapp,
            contacto=contacto_test
        )
        print(f"  Resultado: {resultado}")
        
    elif es_contacto_existente:
        print("  ✅ CONTACTO EXISTENTE → Mensaje personalizado")
        
        # Probar mensaje personalizado
        print("\n💬 Generando mensaje personalizado...")
        mensaje = service.generar_mensaje_personalizado(contacto_test)
        print(f"  Mensaje: {mensaje}")
        
    elif template_whatsapp:
        print("  ✅ FALLBACK → Enviar plantilla (sin marcado específico)")
        
        # Probar envío de plantilla
        print("\n📱 Probando envío de plantilla (fallback)...")
        resultado = service.enviar_plantilla_whatsapp(
            telefono=contacto_test['telefono'],
            template_name=template_whatsapp,
            contacto=contacto_test
        )
        print(f"  Resultado: {resultado}")
        
    else:
        print("  ⚠️ ÚLTIMO FALLBACK → Mensaje personalizado")
        
        # Probar mensaje personalizado
        print("\n💬 Generando mensaje personalizado (último fallback)...")
        mensaje = service.generar_mensaje_personalizado(contacto_test)
        print(f"  Mensaje: {mensaje}")

if __name__ == "__main__":
    debug_contacto_proactivo()