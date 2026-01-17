"""Pydantic schemas for RadSec (RADIUS over TLS) configuration."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CertificateInfo(BaseModel):
    """TLS certificate information."""
    
    subject: str = Field(..., description="Certificate subject")
    issuer: str = Field(..., description="Certificate issuer")
    valid_from: datetime = Field(..., description="Certificate valid from")
    valid_until: datetime = Field(..., description="Certificate valid until")
    is_expired: bool = Field(..., description="Certificate is expired")
    days_until_expiry: int = Field(..., description="Days until expiration")
    serial_number: str = Field(..., description="Certificate serial number")
    fingerprint_sha256: str = Field(..., description="SHA-256 fingerprint")


class RadSecConfigBase(BaseModel):
    """Base schema for RadSec configuration."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Configuration name")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    
    # Network configuration
    listen_address: str = Field(default="0.0.0.0", description="Listen address")
    listen_port: int = Field(default=2083, ge=1024, le=65535, description="Listen port")
    
    # TLS configuration
    tls_min_version: str = Field(default="1.2", description="Minimum TLS version (1.2 or 1.3)")
    tls_max_version: str = Field(default="1.3", description="Maximum TLS version")
    
    # Cipher suites (modern, secure defaults)
    cipher_list: str = Field(
        default="ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256",
        description="TLS cipher suite list"
    )
    
    # Certificate configuration
    certificate_file: str = Field(..., description="Server certificate path")
    private_key_file: str = Field(..., description="Private key path")
    ca_certificate_file: str = Field(..., description="CA certificate path")
    
    # Client certificate validation
    require_client_cert: bool = Field(default=True, description="Require client certificate")
    verify_client_cert: bool = Field(default=True, description="Verify client certificate")
    verify_depth: int = Field(default=2, ge=1, le=10, description="Certificate chain verify depth")
    
    # Certificate revocation
    crl_file: Optional[str] = Field(None, description="Certificate revocation list path")
    check_crl: bool = Field(default=False, description="Check certificate revocation list")
    
    # OCSP (Online Certificate Status Protocol)
    ocsp_enable: bool = Field(default=False, description="Enable OCSP checking")
    ocsp_url: Optional[str] = Field(None, description="OCSP responder URL")
    
    # Connection limits
    max_connections: int = Field(default=100, ge=1, le=1000, description="Maximum connections")
    connection_timeout: int = Field(default=30, ge=5, le=300, description="Connection timeout (seconds)")
    
    # Status
    is_active: bool = Field(default=True, description="RadSec is active")


class RadSecConfigCreate(RadSecConfigBase):
    """Schema for creating RadSec configuration."""
    
    created_by: Optional[str] = Field(None, description="Creator username")


class RadSecConfigUpdate(BaseModel):
    """Schema for updating RadSec configuration (all fields optional)."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    listen_address: Optional[str] = None
    listen_port: Optional[int] = Field(None, ge=1024, le=65535)
    tls_min_version: Optional[str] = None
    tls_max_version: Optional[str] = None
    cipher_list: Optional[str] = None
    certificate_file: Optional[str] = None
    private_key_file: Optional[str] = None
    ca_certificate_file: Optional[str] = None
    require_client_cert: Optional[bool] = None
    verify_client_cert: Optional[bool] = None
    verify_depth: Optional[int] = Field(None, ge=1, le=10)
    crl_file: Optional[str] = None
    check_crl: Optional[bool] = None
    ocsp_enable: Optional[bool] = None
    ocsp_url: Optional[str] = None
    max_connections: Optional[int] = Field(None, ge=1, le=1000)
    connection_timeout: Optional[int] = Field(None, ge=5, le=300)
    is_active: Optional[bool] = None


class RadSecConfigResponse(RadSecConfigBase):
    """Schema for RadSec configuration response."""
    
    id: int = Field(..., description="Configuration ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator username")
    
    # Certificate information (computed)
    server_cert_info: Optional[CertificateInfo] = Field(None, description="Server certificate info")
    ca_cert_info: Optional[CertificateInfo] = Field(None, description="CA certificate info")
    
    # Connection statistics
    active_connections: int = Field(default=0, description="Current active connections")
    total_connections: int = Field(default=0, description="Total connections since start")
    
    model_config = {"from_attributes": True}


class RadSecConfigListResponse(BaseModel):
    """Paginated list of RadSec configurations."""
    
    items: list[RadSecConfigResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RadSecClientBase(BaseModel):
    """RadSec client configuration."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Client name")
    description: Optional[str] = Field(None, max_length=500, description="Client description")
    
    # Client certificate
    certificate_subject: str = Field(..., description="Client certificate subject (CN or full DN)")
    certificate_fingerprint: Optional[str] = Field(None, description="Certificate fingerprint for pinning")
    
    # Client identification
    client_id: Optional[str] = Field(None, max_length=100, description="Client identifier")
    
    # Associated RADIUS client
    radius_client_id: Optional[int] = Field(None, description="Associated RADIUS client ID")
    
    # Status
    is_active: bool = Field(default=True, description="Client is active")


class RadSecClientCreate(RadSecClientBase):
    """Schema for creating RadSec client."""
    
    created_by: Optional[str] = Field(None, description="Creator username")


class RadSecClientUpdate(BaseModel):
    """Schema for updating RadSec client (all fields optional)."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    certificate_subject: Optional[str] = None
    certificate_fingerprint: Optional[str] = None
    client_id: Optional[str] = Field(None, max_length=100)
    radius_client_id: Optional[int] = None
    is_active: Optional[bool] = None


class RadSecClientResponse(RadSecClientBase):
    """Schema for RadSec client response."""
    
    id: int = Field(..., description="Client ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator username")
    
    # Statistics
    connection_count: int = Field(default=0, description="Total connections")
    last_connected: Optional[datetime] = Field(None, description="Last connection time")
    
    model_config = {"from_attributes": True}


class RadSecClientListResponse(BaseModel):
    """Paginated list of RadSec clients."""
    
    items: list[RadSecClientResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CertificateGenerateRequest(BaseModel):
    """Request to generate new certificates."""
    
    common_name: str = Field(..., description="Certificate common name")
    organization: Optional[str] = Field("FreeRADIUS", description="Organization name")
    country: Optional[str] = Field("US", description="Country code")
    validity_days: int = Field(default=397, ge=1, le=825, description="Certificate validity (max 825 days)")
    key_size: int = Field(default=4096, description="RSA key size (2048 or 4096)")


class CertificateGenerateResponse(BaseModel):
    """Response from certificate generation."""
    
    success: bool = Field(..., description="Generation successful")
    message: str = Field(..., description="Result message")
    certificate_path: Optional[str] = Field(None, description="Generated certificate path")
    key_path: Optional[str] = Field(None, description="Generated key path")
    certificate_info: Optional[CertificateInfo] = Field(None, description="Certificate information")
