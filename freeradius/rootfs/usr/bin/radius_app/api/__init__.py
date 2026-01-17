"""API endpoints."""

from .health import router as health_router
from .config import router as config_router
from .clients import router as clients_router
from .udn_assignments import router as udn_assignments_router
from .monitoring import router as monitoring_router
from .nads import router as nads_router
from .policies import router as policies_router
from .radsec import router as radsec_router
from .mac_bypass import router as mac_bypass_router
from .auth_config import router as auth_config_router
from .sql_sync import router as sql_sync_router
from .sql_counter import router as sql_counter_router
from .performance import router as performance_router
from .coa import router as coa_router
from .cloudflare import router as cloudflare_router
from .eap import router as eap_router
from .psk_config import router as psk_config_router
from .unlang_policies import router as unlang_policies_router

__all__ = [
    "health_router",
    "config_router",
    "clients_router",
    "udn_assignments_router",
    "monitoring_router",
    "nads_router",
    "policies_router",
    "radsec_router",
    "mac_bypass_router",
    "auth_config_router",
    "sql_sync_router",
    "sql_counter_router",
    "performance_router",
    "coa_router",
    "cloudflare_router",
    "eap_router",
    "psk_config_router",
    "unlang_policies_router",
]
