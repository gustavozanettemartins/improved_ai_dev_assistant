# Import non-circular dependencies only
from utils.structured_logger import get_logger

__all__ = ['get_logger']

# Don't import response_cache here to avoid circular imports