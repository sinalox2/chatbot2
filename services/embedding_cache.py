"""
Sistema de caché de embeddings para evitar llamadas innecesarias a OpenAI
"""
import hashlib
import sys
import os
from typing import List, Optional, Dict, Any
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from supabase_client import supabase
    from langchain_community.embeddings import OpenAIEmbeddings
    CACHE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Error importando caché de embeddings: {e}")
    CACHE_AVAILABLE = False

class EmbeddingCache:
    """Maneja el caché de embeddings en Supabase"""
    
    def __init__(self):
        if not CACHE_AVAILABLE:
            raise ImportError("Dependencias de caché no disponibles")
        
        self.embeddings_client = OpenAIEmbeddings()
        self.tabla_cache = 'embedding_cache'
        self._ensure_cache_table()
    
    def _ensure_cache_table(self):
        """Asegura que la tabla de caché existe"""
        try:
            # Intentar hacer una consulta simple para verificar si la tabla existe
            supabase.table(self.tabla_cache).select('id').limit(1).execute()
        except Exception as e:
            print(f"⚠️ Tabla {self.tabla_cache} no existe o no es accesible: {e}")
            print("💡 Crear tabla con: CREATE TABLE embedding_cache (id SERIAL PRIMARY KEY, text_hash VARCHAR(64) UNIQUE, text_content TEXT, embedding VECTOR(1536), created_at TIMESTAMP DEFAULT NOW());")
    
    def _get_text_hash(self, text: str) -> str:
        """Genera hash único para el texto"""
        return hashlib.sha256(text.strip().lower().encode('utf-8')).hexdigest()
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Obtiene embedding del caché o genera uno nuevo
        
        Args:
            text: Texto para el cual obtener embedding
            
        Returns:
            Lista de floats representando el embedding o None si hay error
        """
        if not text or not text.strip():
            return None
            
        text_hash = self._get_text_hash(text)
        
        try:
            # Buscar en caché primero
            response = supabase.table(self.tabla_cache)\
                .select('embedding')\
                .eq('text_hash', text_hash)\
                .limit(1)\
                .execute()
            
            if response.data and len(response.data) > 0:
                embedding_data = response.data[0].get('embedding')
                if embedding_data:
                    return embedding_data
            
            # No está en caché, generar nuevo embedding
            print(f"🔄 Generando nuevo embedding para: {text[:50]}...")
            embedding = self.embeddings_client.embed_query(text)
            
            # Guardar en caché
            self._save_to_cache(text_hash, text, embedding)
            
            return embedding
            
        except Exception as e:
            print(f"❌ Error obteniendo embedding: {e}")
            # Fallback: generar embedding sin caché
            try:
                return self.embeddings_client.embed_query(text)
            except Exception as fallback_error:
                print(f"❌ Error en fallback de embedding: {fallback_error}")
                return None
    
    def _save_to_cache(self, text_hash: str, text: str, embedding: List[float]):
        """Guarda embedding en el caché"""
        try:
            supabase.table(self.tabla_cache).insert({
                'text_hash': text_hash,
                'text_content': text[:500],  # Limitar tamaño del texto guardado
                'embedding': embedding
            }).execute()
            print(f"💾 Embedding guardado en caché")
        except Exception as e:
            print(f"⚠️ Error guardando en caché: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché"""
        try:
            response = supabase.table(self.tabla_cache)\
                .select('id', count='exact')\
                .execute()
            
            return {
                'total_embeddings': response.count or 0,
                'status': 'active'
            }
        except Exception as e:
            return {
                'total_embeddings': 0,
                'status': 'error',
                'error': str(e)
            }

# Instancia global
_embedding_cache = None

def get_cached_embedding(text: str) -> Optional[List[float]]:
    """
    Función global para obtener embeddings con caché
    """
    global _embedding_cache
    
    if not CACHE_AVAILABLE:
        # Fallback sin caché
        try:
            embeddings = OpenAIEmbeddings()
            return embeddings.embed_query(text)
        except Exception as e:
            print(f"❌ Error generando embedding sin caché: {e}")
            return None
    
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache()
    
    return _embedding_cache.get_embedding(text)

# Test del sistema
if __name__ == "__main__":
    print("🧪 Probando sistema de caché de embeddings")
    
    cache = EmbeddingCache()
    stats = cache.get_cache_stats()
    print(f"📊 Estadísticas del caché: {stats}")
    
    # Probar embedding
    test_text = "¿Cuánto cuesta el Nissan Sentra?"
    embedding = cache.get_embedding(test_text)
    
    if embedding:
        print(f"✅ Embedding generado: {len(embedding)} dimensiones")
        
        # Probar segunda vez (debería venir del caché)
        embedding2 = cache.get_embedding(test_text)
        print(f"✅ Segundo embedding (desde caché): {len(embedding2) if embedding2 else 0} dimensiones")
    else:
        print("❌ Error generando embedding")