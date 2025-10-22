# config.py - Configuración centralizada del proyecto
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuración base"""
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    # WhatsApp Business API (DEPRECATED - Using Chatwoot integration)
    # WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")  # No longer needed with Chatwoot
    # PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # No longer needed with Chatwoot
    
    # Chatwoot Configuration
    CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "https://chat.progreweb.com")
    CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID", "4")
    CHATWOOT_API_TOKEN = os.getenv("CHATWOOT_API_TOKEN")
    CHATWOOT_INBOX_ID = os.getenv("CHATWOOT_INBOX_ID", "35")
    
    # WhatsApp verification token for webhook (if needed)
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "nissan_verify_token")
    
    # Notificaciones
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL")
    
    # Email
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL")
    
    # App settings
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # Business metrics
    PRECIO_PROMEDIO_AUTO = float(os.getenv("PRECIO_PROMEDIO_AUTO", "350000"))
    COMISION_PROMEDIO = float(os.getenv("COMISION_PROMEDIO", "0.05"))
    COSTO_LEAD = float(os.getenv("COSTO_LEAD", "50"))
    META_DIARIA_LEADS = int(os.getenv("META_DIARIA_LEADS", "10"))
    
    # AI Temperature Settings
    TEMPERATURE_DEFAULT = float(os.getenv("AI_TEMPERATURE_DEFAULT", "0.4"))
    TEMPERATURE_PRECISE = float(os.getenv("AI_TEMPERATURE_PRECISE", "0.2"))
    TEMPERATURE_FINANCING = float(os.getenv("AI_TEMPERATURE_FINANCING", "0.3"))
    TEMPERATURE_CREATIVE = float(os.getenv("AI_TEMPERATURE_CREATIVE", "0.7"))
    TEMPERATURE_GREETING = float(os.getenv("AI_TEMPERATURE_GREETING", "0.6"))

class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True

class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False

# Determinar configuración según entorno
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    return config.get(os.getenv('FLASK_ENV', 'default'), DevelopmentConfig)