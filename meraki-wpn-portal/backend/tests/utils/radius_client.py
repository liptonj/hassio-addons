"""
RADIUS test client using pyrad library.

This module provides a convenient wrapper around pyrad for testing
RADIUS authentication in the WPN Portal integration tests.
"""

import logging
from typing import Optional

from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessAccept, AccessReject, AccessRequest, Packet

logger = logging.getLogger(__name__)


class RadiusResponse:
    """RADIUS authentication response wrapper."""

    def __init__(self, packet: Optional[Packet], success: bool, error: Optional[str] = None):
        """
        Initialize RADIUS response.

        Args:
            packet: RADIUS response packet
            success: Whether authentication succeeded
            error: Error message if failed
        """
        self.packet = packet
        self.success = success
        self.error = error
        self.attributes = {}

        if packet:
            # Extract attributes from response
            for attr in packet.keys():
                values = packet.get(attr)
                if values:
                    # Store first value (most common case)
                    self.attributes[attr] = values[0] if isinstance(values, list) else values

    def get_attribute(self, name: str) -> Optional[str]:
        """
        Get attribute value from response.

        Args:
            name: Attribute name

        Returns:
            Attribute value or None
        """
        return self.attributes.get(name)

    def has_attribute(self, name: str) -> bool:
        """
        Check if response has attribute.

        Args:
            name: Attribute name

        Returns:
            True if attribute exists
        """
        return name in self.attributes

    def get_cisco_avpair_udn_id(self) -> Optional[int]:
        """
        Extract UDN ID from Cisco-AVPair attribute.

        Returns:
            UDN ID or None

        Example:
            Cisco-AVPair = "udn:private-group-id=500" -> 500
        """
        avpair = self.get_attribute("Cisco-AVPair")
        if not avpair:
            return None

        # Parse "udn:private-group-id=<ID>"
        if isinstance(avpair, bytes):
            avpair = avpair.decode("utf-8")

        if "udn:private-group-id=" in avpair:
            try:
                return int(avpair.split("=")[1])
            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse UDN ID from {avpair}: {e}")
                return None

        return None


class RadiusTestClient:
    """
    RADIUS test client for integration testing.

    This client uses pyrad to send RADIUS authentication requests
    to a FreeRADIUS server for testing purposes.
    """

    def __init__(
        self,
        server_host: str = "localhost",
        server_port: int = 1812,
        shared_secret: str = "testing123",
        timeout: int = 5,
        retries: int = 3,
        dictionary_path: Optional[str] = None,
    ):
        """
        Initialize RADIUS test client.

        Args:
            server_host: RADIUS server hostname/IP
            server_port: RADIUS server port (default: 1812)
            shared_secret: Shared secret for authentication
            timeout: Request timeout in seconds
            retries: Number of retries
            dictionary_path: Path to RADIUS dictionary file
        """
        self.server_host = server_host
        self.server_port = server_port
        self.shared_secret = shared_secret.encode("utf-8")
        self.timeout = timeout
        self.retries = retries

        # Load RADIUS dictionary
        if dictionary_path:
            self.dictionary = Dictionary(dictionary_path)
        else:
            # Use default dictionary (pyrad includes basic dictionary)
            self.dictionary = Dictionary("dictionary")

        # Create client
        self.client = Client(
            server=server_host,
            authport=server_port,
            secret=self.shared_secret,
            dict=self.dictionary,
        )
        self.client.timeout = timeout
        self.client.retries = retries

        logger.info(f"RADIUS test client initialized: {server_host}:{server_port}")

    def authenticate_mac(
        self,
        mac_address: str,
        calling_station_id: Optional[str] = None,
        nas_identifier: Optional[str] = None,
    ) -> RadiusResponse:
        """
        Authenticate a MAC address (MAC-based auth).

        Args:
            mac_address: MAC address to authenticate
            calling_station_id: Optional calling station ID (usually MAC)
            nas_identifier: Optional NAS identifier

        Returns:
            RadiusResponse object
        """
        logger.info(f"Authenticating MAC address: {mac_address}")

        try:
            # Create Access-Request packet
            req = self.client.CreateAuthPacket(
                code=AccessRequest,
                User_Name=mac_address,
            )

            # Add optional attributes
            if calling_station_id:
                req["Calling-Station-Id"] = calling_station_id
            if nas_identifier:
                req["NAS-Identifier"] = nas_identifier

            # Send request
            reply = self.client.SendPacket(req)

            # Check response
            if reply.code == AccessAccept:
                logger.info(f"Authentication succeeded for {mac_address}")
                return RadiusResponse(reply, success=True)
            elif reply.code == AccessReject:
                logger.info(f"Authentication rejected for {mac_address}")
                return RadiusResponse(reply, success=False, error="Access-Reject received")
            else:
                logger.warning(f"Unexpected response code: {reply.code}")
                return RadiusResponse(reply, success=False, error=f"Unexpected code: {reply.code}")

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return RadiusResponse(None, success=False, error=str(e))

    def send_access_request(
        self,
        username: str,
        password: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> RadiusResponse:
        """
        Send generic Access-Request with custom attributes.

        Args:
            username: Username
            password: Password (optional for MAC auth)
            attributes: Additional RADIUS attributes

        Returns:
            RadiusResponse object
        """
        logger.debug(f"Sending Access-Request for user: {username}")

        try:
            # Create Access-Request packet
            req = self.client.CreateAuthPacket(
                code=AccessRequest,
                User_Name=username,
            )

            # Add password if provided
            if password:
                req["User-Password"] = req.PwCrypt(password)

            # Add custom attributes
            if attributes:
                for key, value in attributes.items():
                    req[key] = value

            # Send request
            reply = self.client.SendPacket(req)

            # Process response
            if reply.code == AccessAccept:
                return RadiusResponse(reply, success=True)
            elif reply.code == AccessReject:
                return RadiusResponse(reply, success=False, error="Access-Reject")
            else:
                return RadiusResponse(reply, success=False, error=f"Code: {reply.code}")

        except Exception as e:
            logger.error(f"Request failed: {e}")
            return RadiusResponse(None, success=False, error=str(e))

    def verify_cisco_avpair(self, response: RadiusResponse, expected_udn_id: int) -> bool:
        """
        Verify Cisco-AVPair contains expected UDN ID.

        Args:
            response: RADIUS response
            expected_udn_id: Expected UDN ID

        Returns:
            True if UDN ID matches
        """
        actual_udn_id = response.get_cisco_avpair_udn_id()

        if actual_udn_id is None:
            logger.error("No Cisco-AVPair found in response")
            return False

        if actual_udn_id != expected_udn_id:
            logger.error(f"UDN ID mismatch: expected {expected_udn_id}, got {actual_udn_id}")
            return False

        logger.info(f"UDN ID verified: {actual_udn_id}")
        return True

    def test_connectivity(self) -> bool:
        """
        Test connectivity to RADIUS server.

        Returns:
            True if server is reachable
        """
        try:
            # Try to authenticate with a dummy user
            response = self.authenticate_mac("00:00:00:00:00:00")
            # Even if rejected, server is reachable
            return True
        except Exception as e:
            logger.error(f"Connectivity test failed: {e}")
            return False
