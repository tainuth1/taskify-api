from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from app.core.config import settings

# Initialize the limiter
limiter = Limiter(
    key_func=get_remote_address,  # Uses client IP address for rate limiting
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"] if settings.RATE_LIMIT_ENABLED else [],
    storage_uri="memory://",  # In-memory storage (use Redis in production)
)

# Custom rate limit exceeded handler
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors.
    Returns a JSON response matching your API's error format.
    """
    from fastapi.responses import JSONResponse
    
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": f"Rate limit exceeded: {exc.detail}",
            "data": None,
        },
    )
