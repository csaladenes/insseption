"""insseption — JSON API + Python client for INSSE TEMPO-Online."""

from .client import DEFAULT_BASE_URL, Client, InsseClient, InsseptionError

__version__ = "0.1.0"
__all__ = [
    "Client",
    "InsseClient",
    "InsseptionError",
    "DEFAULT_BASE_URL",
    "__version__",
]
