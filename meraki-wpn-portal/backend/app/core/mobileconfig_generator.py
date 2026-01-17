"""Apple .mobileconfig profile generator for WiFi provisioning.

Generates iOS/macOS configuration profiles with embedded certificates
for WPA2-Enterprise (EAP-TLS) authentication.
"""

import logging
import plistlib
import uuid
from typing import Literal

logger = logging.getLogger(__name__)


class MobileConfigGenerator:
    """Generate Apple .mobileconfig profiles for WiFi provisioning."""

    def generate_eap_tls_profile(
        self,
        ssid: str,
        user_certificate_p12: bytes,
        ca_certificate_pem: str,
        profile_name: str,
        organization: str,
        description: str | None = None
    ) -> bytes:
        """Generate .mobileconfig profile for EAP-TLS authentication.
        
        Args:
            ssid: WiFi network SSID
            user_certificate_p12: User certificate in PKCS#12 format
            ca_certificate_pem: CA certificate in PEM format
            profile_name: Display name for the profile
            organization: Organization name
            description: Optional description
        
        Returns:
            .mobileconfig file as bytes
        """
        logger.info(f"Generating EAP-TLS mobileconfig for SSID: {ssid}")
        
        # Generate UUIDs for payloads
        profile_uuid = str(uuid.uuid4())
        wifi_uuid = str(uuid.uuid4())
        cert_uuid = str(uuid.uuid4())
        ca_uuid = str(uuid.uuid4())
        
        # Convert CA certificate PEM to DER
        ca_cert_der = self._pem_to_der(ca_certificate_pem)
        
        # Build WiFi payload with EAP-TLS configuration
        wifi_payload = {
            "PayloadType": "com.apple.wifi.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.wifi.{wifi_uuid}",
            "PayloadUUID": wifi_uuid,
            "PayloadDisplayName": f"WiFi ({ssid})",
            "PayloadDescription": f"Configures WiFi network {ssid} with EAP-TLS",
            
            # WiFi settings
            "SSID_STR": ssid,
            "HIDDEN_NETWORK": False,
            "AutoJoin": True,
            "CaptiveBypass": False,
            
            # Security settings
            "EncryptionType": "WPA2",
            "PayloadCertificateUUID": cert_uuid,  # Link to certificate payload
            
            # EAP configuration
            "EAPClientConfiguration": {
                "AcceptEAPTypes": [13],  # EAP-TLS (type 13)
                "EAPFASTUsePAC": False,
                "EAPFASTProvisionPAC": False,
                
                # Certificate authentication
                "PayloadCertificateAnchorUUID": [ca_uuid],  # Trust this CA
                "TLSCertificateIsRequired": True,
                "TLSTrustedServerNames": [],  # Trust any server with valid cert from CA
                "TLSAllowTrustExceptions": False,
                "TLSMinimumVersion": "1.2",
                "TLSMaximumVersion": "1.3",
                
                # Use certificate for authentication (no username/password)
                "UserName": "",
                "UserPassword": "",
            },
        }
        
        # Build certificate payload (PKCS#12)
        cert_payload = {
            "PayloadType": "com.apple.security.pkcs12",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.cert.{cert_uuid}",
            "PayloadUUID": cert_uuid,
            "PayloadDisplayName": "WiFi Authentication Certificate",
            "PayloadDescription": "User certificate for EAP-TLS authentication",
            
            # PKCS#12 data
            "PayloadContent": user_certificate_p12,
            
            # Password is not included for security
            # User will be prompted on installation if needed
        }
        
        # Build CA certificate payload
        ca_payload = {
            "PayloadType": "com.apple.security.root",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.ca.{ca_uuid}",
            "PayloadUUID": ca_uuid,
            "PayloadDisplayName": "CA Certificate",
            "PayloadDescription": "Root CA certificate for WiFi network",
            
            # CA certificate in DER format
            "PayloadContent": ca_cert_der,
        }
        
        # Build top-level profile
        profile = {
            "PayloadType": "Configuration",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.profile.{profile_uuid}",
            "PayloadUUID": profile_uuid,
            "PayloadDisplayName": profile_name,
            "PayloadDescription": description or f"WiFi configuration for {ssid}",
            "PayloadOrganization": organization,
            
            # Remove after installation
            "PayloadRemovalDisallowed": False,
            
            # Consent text
            "ConsentText": {
                "default": (
                    f"This profile configures your device to connect to {ssid} "
                    "using certificate-based authentication (EAP-TLS). "
                    "Your device will automatically connect when in range."
                )
            },
            
            # Array of payloads
            "PayloadContent": [
                wifi_payload,
                cert_payload,
                ca_payload,
            ],
        }
        
        # Convert to plist (binary format)
        try:
            plist_bytes = plistlib.dumps(profile, fmt=plistlib.FMT_XML)
            logger.info(f"✅ Generated .mobileconfig profile: {len(plist_bytes)} bytes")
            return plist_bytes
        except Exception as e:
            logger.error(f"Failed to generate plist: {e}", exc_info=True)
            raise ValueError(f"Failed to generate profile: {e}") from e

    def generate_ipsk_profile(
        self,
        ssid: str,
        passphrase: str,
        profile_name: str,
        organization: str,
        description: str | None = None,
        hidden: bool = False
    ) -> bytes:
        """Generate .mobileconfig profile for IPSK (WPA2-PSK) authentication.
        
        Args:
            ssid: WiFi network SSID
            passphrase: WiFi passphrase (IPSK)
            profile_name: Display name for the profile
            organization: Organization name
            description: Optional description
            hidden: Whether the network is hidden
        
        Returns:
            .mobileconfig file as bytes
        """
        logger.info(f"Generating IPSK mobileconfig for SSID: {ssid}")
        
        # Generate UUIDs
        profile_uuid = str(uuid.uuid4())
        wifi_uuid = str(uuid.uuid4())
        
        # Build WiFi payload with PSK
        wifi_payload = {
            "PayloadType": "com.apple.wifi.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.wifi.{wifi_uuid}",
            "PayloadUUID": wifi_uuid,
            "PayloadDisplayName": f"WiFi ({ssid})",
            "PayloadDescription": f"Configures WiFi network {ssid}",
            
            # WiFi settings
            "SSID_STR": ssid,
            "HIDDEN_NETWORK": hidden,
            "AutoJoin": True,
            "CaptiveBypass": False,
            
            # Security settings (WPA2-PSK)
            "EncryptionType": "WPA2",
            "Password": passphrase,
        }
        
        # Build top-level profile
        profile = {
            "PayloadType": "Configuration",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.profile.{profile_uuid}",
            "PayloadUUID": profile_uuid,
            "PayloadDisplayName": profile_name,
            "PayloadDescription": description or f"WiFi configuration for {ssid}",
            "PayloadOrganization": organization,
            
            # Remove after installation
            "PayloadRemovalDisallowed": False,
            
            # Array of payloads
            "PayloadContent": [wifi_payload],
        }
        
        # Convert to plist
        try:
            plist_bytes = plistlib.dumps(profile, fmt=plistlib.FMT_XML)
            logger.info(f"✅ Generated .mobileconfig profile: {len(plist_bytes)} bytes")
            return plist_bytes
        except Exception as e:
            logger.error(f"Failed to generate plist: {e}", exc_info=True)
            raise ValueError(f"Failed to generate profile: {e}") from e

    def generate_dual_profile(
        self,
        ssid: str,
        passphrase: str,
        user_certificate_p12: bytes,
        ca_certificate_pem: str,
        profile_name: str,
        organization: str,
        description: str | None = None
    ) -> bytes:
        """Generate .mobileconfig profile with both IPSK and EAP-TLS.
        
        This creates two separate WiFi profiles: one for IPSK (fallback) and
        one for EAP-TLS (preferred).
        
        Args:
            ssid: WiFi network SSID
            passphrase: WiFi passphrase (IPSK)
            user_certificate_p12: User certificate in PKCS#12 format
            ca_certificate_pem: CA certificate in PEM format
            profile_name: Display name for the profile
            organization: Organization name
            description: Optional description
        
        Returns:
            .mobileconfig file as bytes
        """
        logger.info(f"Generating dual-mode mobileconfig for SSID: {ssid}")
        
        # Generate UUIDs
        profile_uuid = str(uuid.uuid4())
        wifi_eap_uuid = str(uuid.uuid4())
        wifi_psk_uuid = str(uuid.uuid4())
        cert_uuid = str(uuid.uuid4())
        ca_uuid = str(uuid.uuid4())
        
        # Convert CA certificate
        ca_cert_der = self._pem_to_der(ca_certificate_pem)
        
        # Build EAP-TLS WiFi payload (preferred)
        wifi_eap_payload = {
            "PayloadType": "com.apple.wifi.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.wifi.eap.{wifi_eap_uuid}",
            "PayloadUUID": wifi_eap_uuid,
            "PayloadDisplayName": f"WiFi ({ssid} - Enterprise)",
            "PayloadDescription": f"EAP-TLS configuration for {ssid}",
            
            "SSID_STR": ssid,
            "HIDDEN_NETWORK": False,
            "AutoJoin": True,
            "Priority": 1,  # Higher priority than PSK
            
            "EncryptionType": "WPA2",
            "PayloadCertificateUUID": cert_uuid,
            
            "EAPClientConfiguration": {
                "AcceptEAPTypes": [13],
                "PayloadCertificateAnchorUUID": [ca_uuid],
                "TLSCertificateIsRequired": True,
                "TLSMinimumVersion": "1.2",
                "TLSMaximumVersion": "1.3",
            },
        }
        
        # Build IPSK WiFi payload (fallback)
        wifi_psk_payload = {
            "PayloadType": "com.apple.wifi.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.wifi.psk.{wifi_psk_uuid}",
            "PayloadUUID": wifi_psk_uuid,
            "PayloadDisplayName": f"WiFi ({ssid} - Fallback)",
            "PayloadDescription": f"IPSK fallback configuration for {ssid}",
            
            "SSID_STR": ssid,
            "HIDDEN_NETWORK": False,
            "AutoJoin": True,
            "Priority": 0,  # Lower priority
            
            "EncryptionType": "WPA2",
            "Password": passphrase,
        }
        
        # Certificate payloads
        cert_payload = {
            "PayloadType": "com.apple.security.pkcs12",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.cert.{cert_uuid}",
            "PayloadUUID": cert_uuid,
            "PayloadDisplayName": "WiFi Authentication Certificate",
            "PayloadContent": user_certificate_p12,
        }
        
        ca_payload = {
            "PayloadType": "com.apple.security.root",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.ca.{ca_uuid}",
            "PayloadUUID": ca_uuid,
            "PayloadDisplayName": "CA Certificate",
            "PayloadContent": ca_cert_der,
        }
        
        # Build top-level profile
        profile = {
            "PayloadType": "Configuration",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"com.merakiwpn.profile.{profile_uuid}",
            "PayloadUUID": profile_uuid,
            "PayloadDisplayName": profile_name,
            "PayloadDescription": description or f"Dual-mode WiFi configuration for {ssid}",
            "PayloadOrganization": organization,
            "PayloadRemovalDisallowed": False,
            
            "ConsentText": {
                "default": (
                    f"This profile configures {ssid} with both certificate-based "
                    "and password-based authentication for maximum compatibility."
                )
            },
            
            "PayloadContent": [
                wifi_eap_payload,  # Preferred
                wifi_psk_payload,  # Fallback
                cert_payload,
                ca_payload,
            ],
        }
        
        # Convert to plist
        try:
            plist_bytes = plistlib.dumps(profile, fmt=plistlib.FMT_XML)
            logger.info(f"✅ Generated dual-mode .mobileconfig profile: {len(plist_bytes)} bytes")
            return plist_bytes
        except Exception as e:
            logger.error(f"Failed to generate plist: {e}", exc_info=True)
            raise ValueError(f"Failed to generate profile: {e}") from e

    def _pem_to_der(self, pem_cert: str) -> bytes:
        """Convert PEM certificate to DER format.
        
        Args:
            pem_cert: Certificate in PEM format
        
        Returns:
            Certificate in DER format
        """
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        
        try:
            # Load PEM certificate
            cert = x509.load_pem_x509_certificate(pem_cert.encode('utf-8'))
            
            # Convert to DER
            der_bytes = cert.public_bytes(serialization.Encoding.DER)
            
            return der_bytes
        except Exception as e:
            logger.error(f"Failed to convert PEM to DER: {e}")
            raise ValueError(f"Invalid PEM certificate: {e}") from e
