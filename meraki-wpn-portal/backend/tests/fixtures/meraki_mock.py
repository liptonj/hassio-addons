"""Meraki API mock fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_meraki_client():
    """Mock Meraki client for testing."""
    client = AsyncMock()
    
    # Organization methods
    client.get_organizations = AsyncMock(return_value=[
        {"id": "123456", "name": "Test Org"}
    ])
    
    # Network methods
    client.get_networks = AsyncMock(return_value=[
        {"id": "L_test_network", "name": "Test Network", "organizationId": "123456"}
    ])
    client.get_network = AsyncMock(return_value={
        "id": "L_test_network",
        "name": "Test Network",
        "organizationId": "123456"
    })
    
    # SSID methods
    client.get_ssids = AsyncMock(return_value=[
        {
            "number": 0,
            "name": "Test SSID",
            "enabled": True,
            "authMode": "psk",
        }
    ])
    client.get_ssid = AsyncMock(return_value={
        "number": 0,
        "name": "Test SSID",
        "enabled": True,
        "authMode": "psk",
    })
    
    # Certificate methods
    client.upload_radsec_ca_certificate = AsyncMock(return_value={
        "certificate_id": "cert_123",
        "contents": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
    })
    
    client.get_radsec_device_certificate_authorities = AsyncMock(return_value=[
        {
            "id": "ca_123",
            "certificate_authority_id": "ca_123",
            "contents": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
            "status": "trusted",
            "ready": True,
        }
    ])
    
    client.get_radsec_device_certificate_authority = AsyncMock(return_value={
        "id": "ca_123",
        "certificate_authority_id": "ca_123",
        "contents": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
        "status": "trusted",
        "ready": True,
    })
    
    client.create_radsec_device_certificate_authority = AsyncMock(return_value={
        "certificate_authority_id": "ca_new",
        "contents": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
        "status": "pending",
        "ready": True,
    })
    
    client.trust_radsec_device_certificate_authority = AsyncMock(return_value={
        "id": "ca_123",
        "status": "trusted",
        "contents": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
    })
    
    # RadSec configuration
    client.configure_network_radsec = AsyncMock(return_value={
        "ssid_number": 0,
        "authMode": "8021x-radius",
        "radiusServers": [{"host": "radius.local", "port": 2083}],
        "wpn_enabled": True,
        "wifiPersonalNetworkId": "wpn_123",
    })
    
    # Splash page configuration
    client.configure_splash_page = AsyncMock(return_value={
        "splashUrl": "https://portal.local/register",
        "useSplashUrl": True,
        "splashTimeout": 1440,
    })
    
    client.get_splash_settings = AsyncMock(return_value={
        "splashUrl": "https://portal.local/register",
        "useSplashUrl": True,
        "splashTimeout": 1440,
    })
    
    return client


@pytest.fixture
def meraki_org_data():
    """Sample Meraki organization data."""
    return {
        "id": "123456",
        "name": "Test Organization",
        "url": "https://n123.meraki.com/o/abc/manage/organization/overview",
    }


@pytest.fixture
def meraki_network_data():
    """Sample Meraki network data."""
    return {
        "id": "L_test_network",
        "organizationId": "123456",
        "name": "Test Network",
        "productTypes": ["wireless"],
        "timeZone": "America/Los_Angeles",
        "tags": [],
        "enrollmentString": None,
        "url": "https://n123.meraki.com/test-network/n/abc/manage/nodes/list",
        "notes": "Test network for integration tests",
    }


@pytest.fixture
def meraki_ssid_data():
    """Sample Meraki SSID data."""
    return {
        "number": 0,
        "name": "Test WPN SSID",
        "enabled": True,
        "splashPage": "None",
        "ssidAdminAccessible": False,
        "authMode": "8021x-radius",
        "encryptionMode": "wpa",
        "wpaEncryptionMode": "WPA2 only",
        "radiusServers": [
            {
                "host": "radius.local",
                "port": 2083,
                "openRoamingCertificateId": None,
                "caCertificate": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
            }
        ],
        "radiusAccountingEnabled": True,
        "radiusAccountingServers": [],
        "radiusAttributeForGroupPolicies": "Filter-Id",
        "ipAssignmentMode": "NAT mode",
        "useVlanTagging": False,
        "defaultVlanId": 1,
        "perClientBandwidthLimitUp": 0,
        "perClientBandwidthLimitDown": 0,
        "visible": True,
        "availableOnAllAps": True,
        "availabilityTags": [],
    }
