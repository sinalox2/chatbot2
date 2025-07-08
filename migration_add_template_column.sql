-- Migración para agregar columna template_whatsapp a contactos_proactivos
-- Fecha: 2025-07-08

-- Agregar columna template_whatsapp
ALTER TABLE contactos_proactivos 
ADD COLUMN template_whatsapp VARCHAR(100) NULL;

-- Agregar comentario para documentar la columna
COMMENT ON COLUMN contactos_proactivos.template_whatsapp IS 'Nombre de la plantilla de WhatsApp Business a usar para el contacto';

-- Crear índice para optimizar búsquedas por plantilla
CREATE INDEX IF NOT EXISTS idx_contactos_proactivos_template ON contactos_proactivos(template_whatsapp);

-- Verificar estructura
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'contactos_proactivos' 
ORDER BY ordinal_position;