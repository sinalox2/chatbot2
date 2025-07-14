#!/usr/bin/env python3
"""
Script directo para crear tabla chunks en Supabase usando SQL directo.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import supabase

def crear_tabla_chunks():
    """Crea la tabla chunks directamente"""
    
    print("🔧 Creando tabla chunks en Supabase...")
    
    try:
        # Eliminar tabla si existe
        print("1. Eliminando tabla si existe...")
        result = supabase.table('chunks').delete().neq('id', 0).execute()
        print("   ✅ Tabla limpiada (si existía)")
    except:
        print("   ℹ️ Tabla no existía")
    
    # SQL para crear tabla (ejecutar en Supabase SQL Editor)
    sql_create = """
-- Crear tabla chunks
CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    documento TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    contenido TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_chunks_documento ON chunks(documento);
CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON chunks(created_at DESC);

-- Habilitar RLS
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;

-- Política para permitir operaciones
DROP POLICY IF EXISTS "Enable all operations for chunks" ON chunks;
CREATE POLICY "Enable all operations for chunks" ON chunks FOR ALL USING (true);

-- Función de búsqueda por similitud
CREATE OR REPLACE FUNCTION buscar_chunks_similares(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id BIGINT,
    documento TEXT,
    contenido TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.documento,
        c.contenido,
        c.metadata,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    WHERE 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
"""

    print("\n📋 SQL para ejecutar en Supabase:")
    print("="*60)
    print(sql_create)
    print("="*60)
    
    print("\n🔧 Pasos manuales:")
    print("1. Abre https://supabase.com/dashboard")
    print("2. Ve a tu proyecto")
    print("3. Ve a 'SQL Editor'")
    print("4. Copia y pega el SQL de arriba")
    print("5. Ejecuta el SQL")
    
    return True

def verificar_tabla():
    """Verifica si la tabla fue creada correctamente"""
    
    print("\n🔍 Verificando tabla chunks...")
    
    try:
        # Verificar estructura básica
        result = supabase.table('chunks').select('*').limit(1).execute()
        print(f"   ✅ Tabla accesible - {len(result.data)} registros")
        
        # Insertar registro de prueba
        test_chunk = {
            'documento': 'test.pdf',
            'chunk_index': 0,
            'contenido': 'Este es un chunk de prueba',
            'metadata': {'test': True},
            'embedding': [0.0] * 1536  # Vector de prueba
        }
        
        result = supabase.table('chunks').insert(test_chunk).execute()
        
        if result.data:
            print("   ✅ Inserción de prueba exitosa")
            
            # Eliminar registro de prueba
            supabase.table('chunks').delete().eq('documento', 'test.pdf').execute()
            print("   ✅ Limpieza de prueba completada")
            
            return True
        else:
            print("   ❌ Error en inserción de prueba")
            return False
            
    except Exception as e:
        print(f"   ❌ Error verificando tabla: {e}")
        return False

if __name__ == "__main__":
    crear_tabla_chunks()
    
    input("\n⏸️ Presiona ENTER después de ejecutar el SQL en Supabase...")
    
    if verificar_tabla():
        print("\n🎉 ¡Tabla chunks creada exitosamente!")
        print("✅ Lista para migración")
    else:
        print("\n❌ Problemas con la tabla chunks")
        print("Revisa la configuración en Supabase")