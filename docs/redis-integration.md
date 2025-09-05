# Redis Integration Documentation

## Overview
Redis is a **REQUIRED** dependency for the Career Jobs App. It provides critical security features including replay attack prevention, distributed rate limiting, and performance optimization through caching.

## Requirements
- Redis 7.0+ (recommended) or Redis 6.2+ (minimum)
- Connection via `REDIS_URL` environment variable
- Default: `redis://localhost:6379/0`

## Installation

### macOS
```bash
brew install redis
brew services start redis
```

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

### Docker
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## Configuration

### Environment Variables
```bash
# Required
REDIS_URL=redis://localhost:6379/0

# Optional (for Redis Cloud/AWS ElastiCache)
REDIS_URL=redis://username:password@host:port/database
```

### Connection Pool Settings
The application uses a connection pool with the following defaults:
- Max connections: 50
- Socket timeout: 5 seconds
- Health check interval: 30 seconds
- Keepalive enabled

## Features Using Redis

### 1. Security Features
- **HMAC Nonce Tracking**: Prevents replay attacks by tracking used nonces
- **Rate Limiting**: Per-user and per-IP rate limits across distributed servers
- **Session Management**: Secure session storage with TTL

### 2. Performance Features
- **Embedding Cache**: Caches OpenAI embeddings to reduce API calls
- **Research Cache**: Caches company research data (24-hour TTL)
- **Score Cache**: Caches job scoring results (1-hour TTL)

### 3. Application Features
- **Pitch History**: Temporary storage before database persistence
- **Activity Logging**: High-performance activity tracking
- **Job Processing Queue**: Background job management

## Key Namespaces

| Namespace | Purpose | Default TTL |
|-----------|---------|------------|
| `hmac:nonces` | HMAC nonce storage | 5 minutes |
| `rate_limit:*` | Rate limiting counters | 1 hour |
| `cache:embeddings` | OpenAI embeddings | 30 days |
| `cache:research` | Company research | 24 hours |
| `cache:scores` | Job scores | 1 hour |
| `sessions:*` | User sessions | 24 hours |

## Monitoring

### Health Check
```python
# Check Redis connection
python scripts/validate_dependencies.py
```

### Redis CLI Commands
```bash
# Check connection
redis-cli ping

# Monitor commands
redis-cli monitor

# Check memory usage
redis-cli info memory

# View all keys (development only)
redis-cli keys "*"
```

## Troubleshooting

### Connection Failed
1. Verify Redis is running: `redis-cli ping`
2. Check REDIS_URL environment variable
3. Verify firewall/network settings
4. Check Redis logs: `redis-server --loglevel debug`

### High Memory Usage
1. Check key count: `redis-cli dbsize`
2. Review TTL settings in code
3. Consider increasing `maxmemory` in redis.conf
4. Enable eviction policy: `maxmemory-policy allkeys-lru`

### Performance Issues
1. Monitor slow queries: `redis-cli slowlog get`
2. Check connection pool usage
3. Review pipeline usage for batch operations
4. Consider Redis cluster for scaling

## Testing

### Unit Tests
Tests automatically mock Redis unless `USE_REAL_REDIS=true`:
```bash
# With mocked Redis (default)
pytest

# With real Redis (integration tests)
USE_REAL_REDIS=true pytest
```

### Load Testing
```bash
# Simulate concurrent users
locust -f tests/load/redis_load_test.py
```

## Production Considerations

### High Availability
- Use Redis Sentinel for automatic failover
- Consider Redis Cluster for horizontal scaling
- Implement connection retry logic

### Persistence
```bash
# Enable AOF persistence (redis.conf)
appendonly yes
appendfsync everysec

# Enable RDB snapshots
save 900 1
save 300 10
save 60 10000
```

### Security
```bash
# Set password (redis.conf)
requirepass your_secure_password

# Bind to specific interface
bind 127.0.0.1 ::1

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command KEYS ""
rename-command CONFIG ""
```

### Monitoring
- Set up Redis monitoring with Prometheus/Grafana
- Configure alerts for:
  - Connection failures
  - High memory usage (>80%)
  - Slow queries (>100ms)
  - High connection count

## Migration from Previous Versions

The application previously supported optional Redis with graceful degradation. This has been removed for security reasons. All deployments MUST have Redis available.

### Breaking Changes
- Redis is now REQUIRED at startup
- No fallback to in-memory storage
- Application exits if Redis is unavailable
- All caching features require Redis

## References
- [Redis Documentation](https://redis.io/documentation)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
- [Redis Security](https://redis.io/docs/manual/security/)