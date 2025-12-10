# Schema Caching Implementation

## Overview

Implemented TTL-based caching for `TrinoSchemaLoader` to improve performance by reducing repetitive Trino queries.

## Architecture

### Cache Structure

```python
# In TrinoSchemaLoader.__init__()
self._cache: Dict[str, any] = {}              # Stores cached data
self._cache_timestamps: Dict[str, datetime] = {}  # Tracks cache age
self.cache_ttl: int = cache_ttl_seconds       # Default: 300s (5 minutes)
```

### Cache Keys

| Key Pattern                         | Purpose                      | Example                           |
| ----------------------------------- | ---------------------------- | --------------------------------- |
| `tables_{catalog}_{schema}`         | List of tables               | `tables_delta_gold`               |
| `schema_{catalog}_{schema}_{table}` | Table columns                | `schema_delta_gold_state_summary` |
| `formatted_schema`                  | Full formatted schema string | `formatted_schema`                |

## Implementation

### Core Methods

#### 1. Cache Validation

```python
def _is_cache_valid(self, key: str) -> bool:
    """Check if cached data hasn't expired"""
    if key not in self._cache or key not in self._cache_timestamps:
        return False

    cache_time = self._cache_timestamps[key]
    elapsed = (datetime.now() - cache_time).total_seconds()
    return elapsed < self.cache_ttl
```

#### 2. Cache Storage

```python
def _set_cache(self, key: str, value: any):
    """Store data with timestamp"""
    self._cache[key] = value
    self._cache_timestamps[key] = datetime.now()
    logger.debug(f"Cached '{key}' with TTL {self.cache_ttl}s")
```

#### 3. Cache Retrieval

```python
def _get_cache(self, key: str) -> Optional[any]:
    """Get cached data if valid, else None"""
    if self._is_cache_valid(key):
        logger.debug(f"Cache HIT for '{key}'")
        return self._cache[key]
    logger.debug(f"Cache MISS for '{key}'")
    return None
```

#### 4. Cache Clearing

```python
def clear_cache(self):
    """Manually clear all cached data"""
    self._cache.clear()
    self._cache_timestamps.clear()
    logger.info("Schema cache cleared")
```

### Usage in Methods

#### `get_tables()`

```python
cache_key = f"tables_{self.catalog}_{self.schema}"

# Check cache first
cached = self._get_cache(cache_key)
if cached is not None:
    logger.debug(f"Cache HIT for {cache_key}")
    return cached

# Query Trino and cache result
tables = [row[0] for row in result]
self._set_cache(cache_key, tables)
```

#### `get_table_schema(table_name)`

```python
cache_key = f"schema_{self.catalog}_{self.schema}_{table_name}"

# Check cache
cached = self._get_cache(cache_key)
if cached is not None:
    logger.debug(f"Cache HIT for {cache_key}")
    return cached

# Query and cache
columns = [...]
self._set_cache(cache_key, columns)
```

#### `format_schema_for_prompt()`

```python
cache_key = "formatted_schema"

# Check cache
cached = self._get_cache(cache_key)
if cached is not None:
    logger.debug(f"Cache HIT for {cache_key}")
    return cached

# Format and cache
result = "\n".join(formatted)
self._set_cache(cache_key, result)
```

## Configuration

### Default TTL

- **Default**: 300 seconds (5 minutes)
- **Rationale**: Balance between freshness and performance

### Custom TTL

```python
# Global singleton with custom TTL
from utils.schema_loader import get_schema_loader

loader = get_schema_loader(cache_ttl_seconds=600)  # 10 minutes
```

### Clear Cache Globally

```python
from utils.schema_loader import clear_schema_cache

clear_schema_cache()  # Clears singleton cache
```

## Logging

### Cache Events

```log
# Cache initialization
INFO - Schema loader initialized with cache TTL: 300s

# Cache miss (first load)
INFO - Cache MISS for tables_delta_gold - querying Trino...
INFO - Loaded 12 tables from delta.gold
DEBUG - Cached 'tables_delta_gold' with TTL 300s

# Cache hit (subsequent loads)
DEBUG - Cache HIT for tables_delta_gold

# Manual clear
INFO - Global schema cache cleared
```

## Performance Impact

### Before Caching

- Every chatbot query → 1+ Trino queries
- Average latency: **2-5 seconds** per schema load
- Network overhead on every request

### After Caching

- First query → Trino query + cache (2-5s)
- Subsequent queries → Cache hit (**<1ms**)
- 99%+ reduction in Trino load for repeated queries

### Example Scenario

```
User: "Show me fraud patterns"
→ Cache MISS → Query Trino (3s)

User: "What about merchant analysis?"
→ Cache HIT → Instant (<1ms)

User: "Show daily summary"
→ Cache HIT → Instant (<1ms)

... 5 minutes later ...

User: "Check state summary"
→ Cache EXPIRED → Query Trino (3s)
→ Cache refreshed
```

## Testing

### Unit Tests

```python
def test_cache_hit():
    loader = TrinoSchemaLoader(cache_ttl_seconds=300)

    # First call - cache miss
    tables1 = loader.get_tables()

    # Second call - cache hit
    tables2 = loader.get_tables()

    assert tables1 == tables2

def test_cache_expiration():
    loader = TrinoSchemaLoader(cache_ttl_seconds=1)

    tables1 = loader.get_tables()
    time.sleep(2)  # Wait for expiration
    tables2 = loader.get_tables()  # Should query again

    assert tables1 == tables2

def test_clear_cache():
    loader = TrinoSchemaLoader()
    loader.get_tables()  # Populate cache

    assert len(loader._cache) > 0

    loader.clear_cache()
    assert len(loader._cache) == 0
```

### Manual Testing

```python
from utils.schema_loader import get_schema_loader, clear_schema_cache

# Load with logging
import logging
logging.basicConfig(level=logging.DEBUG)

loader = get_schema_loader()

# First load (should see "Cache MISS")
schema1 = loader.format_schema_for_prompt()

# Second load (should see "Cache HIT")
schema2 = loader.format_schema_for_prompt()

# Clear and reload
clear_schema_cache()
schema3 = loader.format_schema_for_prompt()  # Should see "Cache MISS" again
```

## Maintenance

### When to Clear Cache Manually

1. **Schema changes** - New tables/views added
2. **Column changes** - ALTER TABLE operations
3. **Testing** - Need fresh data
4. **Troubleshooting** - Stale data suspected

### Monitoring

Monitor cache effectiveness via logs:

```bash
# Count cache hits vs misses
docker logs fraud-chatbot 2>&1 | grep "Cache HIT" | wc -l
docker logs fraud-chatbot 2>&1 | grep "Cache MISS" | wc -l

# Check cache TTL
docker logs fraud-chatbot 2>&1 | grep "initialized with cache TTL"
```

## Future Improvements

### 1. Redis-based Caching

For multi-instance deployments:

```python
import redis

class RedisSchemaCache:
    def __init__(self, redis_client: redis.Redis, ttl: int = 300):
        self.redis = redis_client
        self.ttl = ttl

    def get(self, key: str):
        return self.redis.get(key)

    def set(self, key: str, value: any):
        self.redis.setex(key, self.ttl, value)
```

### 2. Cache Warming

Pre-populate cache on startup:

```python
def warm_cache():
    loader = get_schema_loader()
    loader.get_tables()
    for table in priority_tables:
        loader.get_table_schema(table)
    logger.info("Schema cache warmed")
```

### 3. Metrics Collection

Track cache performance:

```python
self.cache_hits = 0
self.cache_misses = 0

def get_cache_stats(self) -> dict:
    total = self.cache_hits + self.cache_misses
    hit_rate = self.cache_hits / total if total > 0 else 0
    return {
        "hits": self.cache_hits,
        "misses": self.cache_misses,
        "hit_rate": f"{hit_rate:.2%}"
    }
```

## References

- Source: `services/fraud-chatbot/src/utils/schema_loader.py`
- Related: `docs/CHATBOT_REFACTORING.md`
- Config: `services/fraud-chatbot/config/prompts.yaml`
