# models/__init__.py
from .lead_tracking import (
    EstadoLead,
    TipoInteraccion, 
    CanalOrigen,
    TemperaturaMercado,
    PrioridadLead,
    ProspectoInfo,
    Lead,
    Interaccion
)

__all__ = [
    'EstadoLead',
    'TipoInteraccion',
    'CanalOrigen', 
    'TemperaturaMercado',
    'PrioridadLead',
    'ProspectoInfo',
    'Lead',
    'Interaccion'
]