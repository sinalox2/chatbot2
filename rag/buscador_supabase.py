"""
Buscador RAG usando Supabase con pgvector
"""
import os
import sys
from typing import List, Dict, Any

# Agregar el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from supabase_client import supabase
    from langchain_community.embeddings import OpenAIEmbeddings
    from services.embedding_cache import get_cached_embedding
    from dotenv import load_dotenv
    IMPORTS_OK = True
except ImportError as e:
    print(f"❌ Error importando: {e}")
    IMPORTS_OK = False

load_dotenv()

class SupabaseRAGSearcher:
    def __init__(self):
        if not IMPORTS_OK:
            raise ImportError("No se pudieron importar las dependencias necesarias")
        
        self.embeddings = OpenAIEmbeddings()
        self.tabla = 'chunks'
    
    def buscar_similares(self, query: str, k: int = 3, umbral_similitud: float = 0.7) -> List[Dict[str, Any]]:
        """
        Busca documentos similares usando búsqueda vectorial en Supabase
        """
        try:
            # Detectar si es una consulta de precios
            query_lower = query.lower()
            modelos_nissan = ['sentra', 'versa', 'march', 'kicks', 'x-trail', 'pathfinder', 'frontier', 'np300', 'v-drive', 'v drive', 'magnite', 'altima']
            
            modelo_mencionado = None
            for modelo in modelos_nissan:
                if modelo in query_lower:
                    modelo_mencionado = modelo
                    break
            
            # Solo buscar en precios si es específicamente una consulta de precios
            es_consulta_precio = any(palabra in query_lower for palabra in ['precio', 'cuesta', 'vale', 'cuanto cuesta', 'cuánto cuesta'])
            
            if modelo_mencionado and es_consulta_precio:
                # Búsqueda específica por modelo en precios
                return self._buscar_por_modelo(modelo_mencionado, k)
            
            # Generar embedding de la consulta usando caché
            query_embedding = get_cached_embedding(query)
            if not query_embedding:
                print("❌ Error generando embedding")
                return self._buscar_manual_simple(query, k)
            
            # Búsqueda vectorial directa usando operador de similitud
            return self._buscar_manual(query_embedding, k, umbral_similitud)
                
        except Exception as e:
            print(f"❌ Error en búsqueda vectorial: {e}")
            # Fallback a búsqueda manual
            return self._buscar_manual_simple(query, k)
    
    def _buscar_por_modelo(self, modelo: str, k: int) -> List[Dict[str, Any]]:
        """
        Busca específicamente el chunk que contiene información del modelo
        """
        try:
            # Buscar en chunks de precios que contengan el modelo específico
            response = supabase.table(self.tabla)\
                .select('contenido, documento, metadata')\
                .ilike('documento', '%precios%')\
                .ilike('contenido', f'%{modelo}%')\
                .execute()
            
            if response.data:
                print(f"✅ Encontrado chunk específico para {modelo}")
                return response.data[:k]
            
            # Si no encuentra el modelo específico, buscar en todos los precios
            response_all = supabase.table(self.tabla)\
                .select('contenido, documento, metadata')\
                .ilike('documento', '%precios%')\
                .execute()
            
            if response_all.data:
                print(f"⚠️ Modelo {modelo} no encontrado específicamente, devolviendo todos los precios")
                return response_all.data[:k]
            
            return []
            
        except Exception as e:
            print(f"❌ Error en búsqueda por modelo: {e}")
            return []
    
    def _buscar_manual(self, query_embedding: List[float], k: int, umbral: float) -> List[Dict[str, Any]]:
        """
        Búsqueda manual usando el operador de similitud pgvector de Supabase (RPC)
        con fallback manual en Python si el RPC falla.
        """
        try:
            # Intentar usar 'buscar_chunks_similares'
            try:
                embedding_str = str(query_embedding).replace(' ', '')
                response = supabase.rpc('buscar_chunks_similares', {
                    'query_embedding': embedding_str,
                    'match_threshold': float(umbral),
                    'match_count': int(k)
                }).execute()
                
                if response.data and len(response.data) > 0:
                    print(f"✅ Búsqueda vectorial (RPC) exitosa: {len(response.data)} resultados")
                    return response.data
            except Exception as e:
                print(f"⚠️ Error o sin resultados en RPC: {e}")

            # FALLBACK MANUAL: Búsqueda vectorial en memoria
            # Útil si el RPC no está configurado o falla
            print("🔄 Iniciando búsqueda vectorial manual (fallback)...")
            all_chunks = supabase.table(self.tabla).select('id, documento, contenido, metadata, embedding').execute()
            
            if not all_chunks.data:
                return []
                
            import numpy as np
            import json
            
            q_v = np.array(query_embedding)
            results = []
            
            for c in all_chunks.data:
                emb = c.get('embedding')
                if not emb: continue
                
                try:
                    if isinstance(emb, str):
                        v = np.array(json.loads(emb))
                    else:
                        v = np.array(emb)
                        
                    # Similitud coseno
                    norm_v = np.linalg.norm(v)
                    norm_q = np.linalg.norm(q_v)
                    
                    if norm_v > 0 and norm_q > 0:
                        sim = np.dot(q_v, v) / (norm_v * norm_q)
                        if sim >= umbral:
                            results.append({
                                'contenido': c['contenido'],
                                'documento': c['documento'],
                                'metadata': c['metadata'],
                                'similarity': float(sim)
                            })
                except:
                    continue
            
            # Ordenar por similitud
            results.sort(key=lambda x: x['similarity'], reverse=True)
            print(f"✅ Búsqueda manual finalizada: {len(results)} resultados encontrados")
            
            return results[:k]
            
        except Exception as e:
            print(f"❌ Error crítico en búsqueda: {e}")
            return []
    
    def _buscar_manual_simple(self, query: str, k: int) -> List[Dict[str, Any]]:
        """
        Búsqueda simple por texto como último recurso
        """
        try:
            # Intentar buscar términos clave específicos
            terminos_busqueda = []
            query_lower = query.lower()
            
            if 'si facil' in query_lower or 'sí fácil' in query_lower:
                terminos_busqueda.extend(['si facil', 'sí fácil', 'plan si'])
            elif 'autofinanciamiento' in query_lower:
                terminos_busqueda.append('autofinanciamiento')
            elif 'credito' in query_lower or 'crédito' in query_lower:
                terminos_busqueda.extend(['credito', 'crédito', 'financiamiento'])
            else:
                # Usar la query original
                terminos_busqueda.append(query.strip())
            
            # Buscar cada término
            all_results = []
            for termino in terminos_busqueda:
                response = supabase.table(self.tabla)\
                    .select('contenido, documento, metadata')\
                    .ilike('contenido', f'%{termino}%')\
                    .limit(k * 2)\
                    .execute()
                
                if response.data:
                    print(f"✅ Encontrado contenido para: {termino}")
                    all_results.extend(response.data)
            
            # Eliminar duplicados y retornar
            seen_content = set()
            unique_results = []
            for item in all_results:
                content_key = item.get('contenido', '')[:100]  # Usar primeros 100 chars como key
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    unique_results.append(item)
            
            return unique_results[:k]
            
        except Exception as e:
            print(f"❌ Error en búsqueda simple: {e}")
            return []
    
    def recuperar_contexto(self, query: str, k: int = 3) -> str:
        """
        Recupera contexto relevante para una consulta (compatible con buscador.py)
        OPTIMIZADO: Máximo 2 chunks y 600 palabras
        """
        # Limitar a máximo 2 chunks para optimizar tokens
        k = min(k, 2)
        
        resultados = self.buscar_similares(query, k)
        
        if not resultados:
            return "No se encontró información relevante."
        
        # Combinar contenido de los resultados con límite de palabras
        contexto_partes = []
        total_palabras = 0
        max_palabras = 600  # Límite estricto de palabras
        
        for resultado in resultados:
            contenido = resultado.get('contenido', '')
            documento = resultado.get('documento', 'Desconocido')
            
            if contenido and total_palabras < max_palabras:
                # Contar palabras en el contenido actual
                palabras_contenido = len(contenido.split())
                
                # Truncar si excede el límite
                if total_palabras + palabras_contenido > max_palabras:
                    palabras_restantes = max_palabras - total_palabras
                    contenido_truncado = ' '.join(contenido.split()[:palabras_restantes])
                    contenido = contenido_truncado + "..."
                
                parte = f"[{os.path.basename(documento)}] {contenido}"
                contexto_partes.append(parte)
                total_palabras += len(parte.split())
                
                if total_palabras >= max_palabras:
                    break
        
        contexto_final = "\n\n".join(contexto_partes)
        print(f"📝 Contexto RAG: {len(contexto_final.split())} palabras, {len(contexto_partes)} chunks")
        
        return contexto_final
    
    def estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la base de conocimiento
        """
        try:
            # Contar total de chunks
            count_response = supabase.table(self.tabla)\
                .select('id', count='exact')\
                .execute()
            
            total_chunks = count_response.count if count_response.count else 0
            
            # Obtener documentos únicas
            sources_response = supabase.table(self.tabla)\
                .select('documento')\
                .execute()
            
            documentos = set()
            if sources_response.data:
                for item in sources_response.data:
                    documento = item.get('documento')
                    if documento:
                        documentos.add(os.path.basename(documento))
            
            return {
                'total_chunks': total_chunks,
                'documentos_unicas': len(documentos),
                'documentos': list(documentos)
            }
            
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
            return {'error': str(e)}

# Instancia global para compatibilidad
_searcher = None

def inicializar_buscador():
    """Inicializa el buscador global"""
    global _searcher
    if _searcher is None:
        _searcher = SupabaseRAGSearcher()
    return _searcher

def recuperar_contexto(query: str, k: int = 3) -> str:
    """
    Función compatible con el buscador.py original
    """
    try:
        searcher = inicializar_buscador()
        return searcher.recuperar_contexto(query, k)
    except Exception as e:
        print(f"❌ Error en recuperar_contexto: {e}")
        return "Error accediendo a la base de conocimiento."

# Función de prueba
if __name__ == "__main__":
    print("🧪 Probando Supabase RAG Searcher")
    print("=" * 40)
    
    searcher = SupabaseRAGSearcher()
    
    # Estadísticas
    stats = searcher.estadisticas()
    print(f"📊 Estadísticas:")
    print(f"   Total chunks: {stats.get('total_chunks', 0)}")
    print(f"   Fuentes únicas: {stats.get('documentos_unicas', 0)}")
    
    if stats.get('documentos'):
        print("   Fuentes disponibles:")
        for documento in stats['documentos']:
            print(f"     - {documento}")
    
    # Prueba de búsqueda
    query = input("\n🔍 Escribe tu consulta: ")
    if query:
        contexto = searcher.recuperar_contexto(query)
        print(f"\n📋 Contexto recuperado:")
        print(contexto)