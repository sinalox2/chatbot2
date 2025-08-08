# 🚀 Optimización de Tokens - Chatbot Nissan

## ✅ Optimizaciones Implementadas

### 1. **Caché de Embeddings** 
- **Archivo**: `services/embedding_cache.py`
- **Función**: Evita regenerar embeddings para el mismo texto
- **Ahorro**: ~50-80% de llamadas a OpenAI Embeddings API
- **Implementación**: 
  - Hash SHA256 del texto como clave única
  - Almacenamiento en Supabase con tabla `embedding_cache`
  - Fallback automático si el caché falla

### 2. **Límite de Contexto RAG**
- **Archivo**: `rag/buscador_supabase.py`
- **Límites**: Máximo 2 chunks y 800 palabras total
- **Ahorro**: ~60-70% de tokens en contexto RAG
- **Implementación**:
  - `k = min(k, 2)` en todas las búsquedas
  - Contador de palabras con truncado inteligente
  - Log de estadísticas: `📝 Contexto RAG: X palabras, Y chunks`

### 3. **Historial Limitado**
- **Archivo**: `services/conversation_service.py`
- **Límite**: Últimos 5 turnos (10 mensajes: 5 usuario + 5 bot)
- **Ahorro**: ~40-60% de tokens en historial
- **Implementación**:
  - `limit = min(limit, 10)` en `get_conversation_history()`
  - Contador `historial_procesado` para control exacto

### 4. **Monitoreo de Tokens**
- **Archivo**: `services/conversation_service.py`
- **Función**: Log de tokens usados por request
- **Formato**: `🎫 Tokens: X`
- **Implementación**: `response.usage.total_tokens`

### 5. **Logs Simplificados**
- **Formato optimizado**:
  ```
  📞 +5216871006601 | 📨 ¿Cuánto cuesta el Sentra?... | 📤 El Sentra tiene un precio desde $389,900... | 🔍 RAG: ✅ | 🎫 Tokens: 245
  ```
- **Información clave**:
  - Teléfono del usuario
  - Mensaje recibido (primeros 50 chars)
  - Respuesta enviada (primeros 50 chars)
  - Si se usó RAG (✅/❌)
  - Tokens consumidos
- **Errores simplificados**: Solo código y primeros 100 chars del error

## 📊 Impacto Estimado

| Optimización | Ahorro de Tokens | Ahorro de Costos |
|--------------|------------------|------------------|
| Caché de Embeddings | 50-80% embeddings | ~60% en embed API |
| Límite RAG (2 chunks/800 palabras) | 60-70% contexto | ~35% en completion |
| Historial limitado (5 turnos) | 40-60% historial | ~25% en completion |
| **TOTAL ESTIMADO** | **45-65%** | **40-55%** |

## 🔧 Configuración Requerida

### Tabla de Caché en Supabase
```sql
CREATE TABLE embedding_cache (
    id SERIAL PRIMARY KEY,
    text_hash VARCHAR(64) UNIQUE,
    text_content TEXT,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índice para búsquedas rápidas
CREATE INDEX idx_embedding_cache_hash ON embedding_cache(text_hash);
```

## 📈 Métricas de Monitoreo

### En Logs de Consola
- **Token usage**: `🎫 Tokens: X` por cada request
- **RAG usage**: `🔍 RAG: ✅/❌` indica si se usó contexto
- **Contexto RAG**: `📝 Contexto RAG: X palabras, Y chunks`
- **Caché**: `🔄 Generando nuevo embedding` vs `💾 Embedding guardado en caché`

### Estadísticas del Caché
```python
from services.embedding_cache import EmbeddingCache
cache = EmbeddingCache()
stats = cache.get_cache_stats()
print(f"Total embeddings en caché: {stats['total_embeddings']}")
```

## 🚨 Consideraciones Importantes

1. **Caché Persistence**: Los embeddings se guardan permanentemente en Supabase
2. **Calidad vs Tokens**: El límite de 2 chunks puede reducir calidad en consultas complejas
3. **Historial**: 5 turnos pueden ser insuficientes para conversaciones muy largas
4. **Fallbacks**: Todos los sistemas tienen fallbacks si fallan las optimizaciones

## 🧪 Testing

Para probar las optimizaciones:

```bash
# Test del caché de embeddings
python services/embedding_cache.py

# Test del sistema RAG optimizado
python rag/buscador_supabase.py

# Test completo del conversation service
python services/conversation_service.py
```

## 📝 Archivos Modificados

- `services/embedding_cache.py` *(nuevo)*
- `services/conversation_service.py` *(optimizado)*
- `rag/buscador_supabase.py` *(optimizado)*
- `OPTIMIZACION_TOKENS.md` *(documentación)*

---

*Optimizaciones implementadas para reducir el uso excesivo de tokens en el chatbot Nissan con LangChain, OpenAI API, Supabase y RAG.*