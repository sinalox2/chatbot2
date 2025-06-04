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
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
    
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