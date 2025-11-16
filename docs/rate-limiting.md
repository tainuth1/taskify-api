# Rate Limiting

## What it does?

Rate limiting protects your API from abuse by restricting the number of requests a client can make within a specific time period. This helps prevent:

- **DDoS attacks**: Malicious users flooding your API with requests
- **Resource exhaustion**: Preventing one user from consuming all server resources
- **API abuse**: Limiting automated bots or scrapers
- **Cost control**: Reducing unnecessary server load and costs

## Why is it needed?

Rate limiting is essential for:

- **Security**: Protecting your API from malicious attacks
- **Fair usage**: Ensuring all users get fair access to resources
- **Stability**: Preventing server overload and crashes
- **Cost management**: Reducing unnecessary resource consumption
- **Compliance**: Meeting API usage policies and terms of service

## Implementation Overview

This project uses `slowapi`, a rate limiting library for FastAPI based on Flask-Limiter. Rate limiting is configured in `app/core/limiter.py` and can be enabled/disabled via configuration.

## Configuration

Rate limiting settings are defined in `app/core/config.py`:

```python
# Rate Limiting Configuration
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_PER_MINUTE: int = 60  # Default: 60 requests per minute
RATE_LIMIT_PER_HOUR: int = 1000  # Default: 1000 requests per hour
```

### Configuration Options

- **RATE_LIMIT_ENABLED**: Enable or disable rate limiting globally
- **RATE_LIMIT_PER_MINUTE**: Default requests allowed per minute for endpoints using `@limiter.limit()`
- **RATE_LIMIT_PER_HOUR**: Default requests allowed per hour (currently not used, but available for future use)

## How It Works

### Limiter Initialization

The rate limiter is initialized in `app/core/limiter.py`:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,  # Uses client IP address for rate limiting
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"] if settings.RATE_LIMIT_ENABLED else [],
    storage_uri="memory://",  # In-memory storage (use Redis in production)
)
```

### Applying Rate Limits

There are two ways to apply rate limiting to endpoints:

#### 1. Using Default Limits

```python
from app.core.limiter import limiter

@router.get("/endpoint")
@limiter.limit()  # Uses default_limits: "60/minute"
def my_endpoint(request: Request):
    ...
```

When you use `@limiter.limit()` without arguments, it uses the `default_limits` from the limiter configuration (60/minute in this case).

#### 2. Using Custom Limits

```python
@router.post("/signin")
@limiter.limit("5/minute")  # Custom limit: 5 requests per minute
def signin(request: Request):
    ...
```

When you specify a limit string like `"5/minute"`, it overrides the default and applies that specific limit.

### Important Notes

- **Endpoints without `@limiter.limit()` decorator are NOT rate limited**, even if `default_limits` are set
- **Explicit limits override defaults**: `@limiter.limit("X/minute")` always uses X, not the default
- **Default limits only apply** when using `@limiter.limit()` without arguments

## Storage Options

### In-Memory Storage (`memory://`)

**Current Setup**: The project uses in-memory storage by default.

```python
storage_uri="memory://"
```

**Characteristics:**
- ✅ Simple setup, no external dependencies
- ✅ Fast (direct memory access)
- ✅ Good for development and single-server deployments
- ❌ Data lost on server restart
- ❌ Not shared across multiple app instances
- ❌ Not suitable for horizontal scaling

**When to use:**
- Development and testing
- Single server deployments
- Low traffic applications
- Prototyping

### Redis Storage (`redis://`)

**Production Setup**: Use Redis for distributed rate limiting.

```python
storage_uri="redis://localhost:6379"
```

**Characteristics:**
- ✅ Shared across all app instances
- ✅ Works with horizontal scaling and load balancers
- ✅ Data persists across server restarts
- ✅ Industry standard for distributed systems
- ❌ Requires Redis installation
- ❌ Additional infrastructure to manage

**When to use:**
- Production environments
- Multiple server instances
- Load-balanced deployments
- High availability requirements

### The Problem In-Memory Causes

Without Redis, each server instance has separate rate limit counters:

```
User makes requests:
- 60 requests → Server 1 (rate limited ✅)
- 60 requests → Server 2 (not rate limited ❌ - different memory!)
- 60 requests → Server 3 (not rate limited ❌ - different memory!)

Total: 180 requests (should be limited to 60!)
```

With Redis, all servers share the same counters:

```
User makes requests:
- 20 requests → Server 1 (counted in Redis: 20/60)
- 20 requests → Server 2 (counted in Redis: 40/60)
- 20 requests → Server 3 (counted in Redis: 60/60)
- Next request → ALL servers reject (Redis says: 60/60 limit reached)

Total: 60 requests (correctly limited!)
```

## Rate Limit Format

Rate limits use the format: `"number/time_unit"`

**Examples:**
- `"10/minute"` - 10 requests per minute
- `"100/hour"` - 100 requests per hour
- `"1000/day"` - 1000 requests per day
- `"5/second"` - 5 requests per second

## Error Response

When a rate limit is exceeded, the API returns a 429 status code:

```json
{
  "success": false,
  "message": "Rate limit exceeded: 5 per 1 minute",
  "data": null
}
```

## Example Usage

### Authentication Endpoints

Authentication endpoints typically have stricter limits:

```python
from app.core.limiter import limiter

@router.post("/signin")
@limiter.limit("5/minute")  # Stricter limit for login
def signin(request: Request):
    ...

@router.post("/signup")
@limiter.limit("3/hour")  # Very strict limit for registration
def signup(request: Request):
    ...

@router.post("/forgot-password")
@limiter.limit("3/hour")  # Prevent abuse of password reset
def forgot_password(request: Request):
    ...
```

### General Endpoints

General endpoints can use default limits:

```python
@router.get("/projects")
@limiter.limit()  # Uses default: 60/minute
def get_projects(request: Request):
    ...
```

## Switching to Redis (Production)

### Step 1: Install Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Or use Docker
docker run -d -p 6379:6379 redis:alpine
```

### Step 2: Install Python Redis Client

```bash
pip install redis
```

### Step 3: Update Configuration

Add Redis URL to `app/core/config.py`:

```python
REDIS_URL: str = "redis://localhost:6379"
```

### Step 4: Update Limiter

Modify `app/core/limiter.py`:

```python
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"] if settings.RATE_LIMIT_ENABLED else [],
    storage_uri=settings.REDIS_URL if settings.RATE_LIMIT_ENABLED else "memory://",
)
```

## Best Practices

1. **Enable rate limiting in production**: Always have rate limiting enabled in production environments
2. **Use appropriate limits**: Different endpoints may need different limits (stricter for auth, more lenient for read operations)
3. **Use Redis in production**: Switch to Redis when deploying multiple server instances
4. **Monitor rate limit hits**: Track 429 responses to identify potential issues or attacks
5. **Set reasonable defaults**: Default limits should accommodate normal usage patterns
6. **Document rate limits**: Inform API consumers about rate limits in your API documentation
7. **Consider user-based limits**: For authenticated endpoints, consider per-user limits instead of per-IP limits

## Testing Rate Limiting

You can test rate limiting using curl or any HTTP client:

```bash
# Test rate limiting
for i in {1..10}; do
  curl -X POST http://127.0.0.1:8000/api/auth/signin
  echo ""
done
```

After exceeding the limit, you'll receive a 429 response with the rate limit error message.

## Disabling Rate Limiting

To disable rate limiting globally:

1. Set `RATE_LIMIT_ENABLED = False` in `app/core/config.py`
2. Remove or comment out all `@limiter.limit()` decorators from endpoints

**Note**: Even with `RATE_LIMIT_ENABLED = False`, endpoints with explicit `@limiter.limit("X/minute")` decorators will still be rate limited. To fully disable, remove the decorators.

