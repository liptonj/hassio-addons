"""Pydantic schemas package."""

from .clients import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientListResponse,
    ClientTestRequest,
    ClientTestResponse,
)
from .udn_assignments import (
    UdnAssignmentCreate,
    UdnAssignmentUpdate,
    UdnAssignmentResponse,
    UdnAssignmentListResponse,
    AvailableUdnResponse,
    normalize_mac_address,
)
from .mac_bypass import (
    MacBypassConfigBase,
    MacBypassConfigCreate,
    MacBypassConfigUpdate,
    MacBypassConfigResponse,
)
from .unlang_policy import (
    UnlangPolicyBase,
    UnlangPolicyCreate,
    UnlangPolicyUpdate,
    UnlangPolicyResponse,
    UnlangPolicyListResponse,
    AdditionalCondition,
)
from .psk_config import (
    PskConfigBase,
    PskConfigCreate,
    PskConfigUpdate,
    PskConfigResponse,
)

__all__ = [
    # Client schemas
    "ClientCreate",
    "ClientUpdate",
    "ClientResponse",
    "ClientListResponse",
    "ClientTestRequest",
    "ClientTestResponse",
    # UDN assignment schemas
    "UdnAssignmentCreate",
    "UdnAssignmentUpdate",
    "UdnAssignmentResponse",
    "UdnAssignmentListResponse",
    "AvailableUdnResponse",
    "normalize_mac_address",
    # MAC bypass schemas
    "MacBypassConfigBase",
    "MacBypassConfigCreate",
    "MacBypassConfigUpdate",
    "MacBypassConfigResponse",
    # Unlang policy schemas
    "UnlangPolicyBase",
    "UnlangPolicyCreate",
    "UnlangPolicyUpdate",
    "UnlangPolicyResponse",
    "UnlangPolicyListResponse",
    "AdditionalCondition",
    # PSK config schemas
    "PskConfigBase",
    "PskConfigCreate",
    "PskConfigUpdate",
    "PskConfigResponse",
]
