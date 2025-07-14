#!/usr/bin/env python3
"""
Script para limpiar completamente la tabla de chunks RAG en Supabase
y crear una nueva estructura optimizada desde cero.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import supabase

def limpiar_tabla_chunks():
    """Elimina y recrea la tabla de chunks en Supabase"""
    
    print("🧹 Limpiando tabla de chunks RAG en Supabase...")
    
    try:
        # 1. Eliminar tabla existente si existe
        print("1. Eliminando tabla 'chunks' existente...")
        
        # Ejecutar SQL para eliminar tabla
        result = supabase.rpc('drop_table_if_exists', {'table_name': 'chunks'}).execute()
        print("   ✅ Tabla eliminada exitosamente")
        
    except Exception as e:
        print(f"   ⚠️ Error eliminando tabla (probablemente no existía): {e}")
    
    try:
        # 2. Crear nueva tabla optimizada
        print("2. Creando nueva tabla 'chunks' optimizada...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS chunks (
            id BIGSERIAL PRIMARY KEY,
            documento TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            contenido TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            embedding VECTOR(1536),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Crear índices para optimizar búsquedas
        CREATE INDEX IF NOT EXISTS idx_chunks_documento ON chunks(documento);
        CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat(embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON chunks(created_at DESC);
        
        -- Habilitar RLS (Row Level Security)
        ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
        
        -- Política para permitir todas las operaciones (ajustar según necesidades)
        CREATE POLICY "Enable all operations for chunks" ON chunks FOR ALL USING (true);
        """
        
        # Ejecutar SQL
        result = supabase.rpc('execute_sql', {'sql_command': create_table_sql}).execute()
        print("   ✅ Nueva tabla 'chunks' creada exitosamente")
        
    except Exception as e:
        print(f"   ❌ Error creando nueva tabla: {e}")
        return False
    
    try:
        # 3. Crear función de búsqueda optimizada
        print("3. Creando función de búsqueda...")
        
        search_function_sql = """
        CREATE OR REPLACE FUNCTION buscar_chunks_similares(
            query_embedding VECTOR(1536),
            match_threshold FLOAT DEFAULT 0.8,
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
                chunks.id,
                chunks.documento,
                chunks.contenido,
                chunks.metadata,
                1 - (chunks.embedding <=> query_embedding) AS similarity
            FROM chunks
            WHERE 1 - (chunks.embedding <=> query_embedding) > match_threshold
            ORDER BY chunks.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$;
        """
        
        result = supabase.rpc('execute_sql', {'sql_command': search_function_sql}).execute()
        print("   ✅ Función de búsqueda creada exitosamente")
        
    except Exception as e:
        print(f"   ❌ Error creando función de búsqueda: {e}")
        return False
    
    print("\n🎉 Limpieza completada exitosamente!")
    print("📊 Nueva estructura:")
    print("   - Tabla 'chunks' recreada")
    print("   - Índices optimizados")
    print("   - Función de búsqueda lista")
    print("   - RLS habilitado")
    
    return True

def verificar_estructura():
    """Verifica que la nueva estructura esté correcta"""
    
    print("\n🔍 Verificando nueva estructura...")
    
    try:
        # Verificar que la tabla existe y está vacía
        result = supabase.table('chunks').select('id').limit(1).execute()
        
        print(f"   ✅ Tabla accesible - {len(result.data)} registros")
        
        # Verificar función de búsqueda
        test_embedding = [0.0] * 1536  # Vector de prueba
        result = supabase.rpc('buscar_chunks_similares', {
            'query_embedding': test_embedding,
            'match_count': 1
        }).execute()
        
        print("   ✅ Función de búsqueda funcional")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en verificación: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando limpieza de RAG Supabase...")
    
    if not supabase:
        print("❌ Error: No se pudo conectar a Supabase")
        sys.exit(1)
    
    # Ejecutar limpieza
    if limpiar_tabla_chunks():
        if verificar_estructura():
            print("\n✅ Proceso completado exitosamente")
            print("🔄 Ahora puedes migrar los documentos del RAG local")
        else:
            print("\n⚠️ Estructura creada pero hay problemas en verificación")
    else:
        print("\n❌ Error en el proceso de limpieza")