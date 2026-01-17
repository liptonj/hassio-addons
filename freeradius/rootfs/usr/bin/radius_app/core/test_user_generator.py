"""Test user generation utilities for performance testing.

Generates random test users and passwords for RADIUS performance testing.
Based on FreeRADIUS create-users.pl script approach.
"""

import random
import string
import secrets
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TestUserGenerator:
    """Generates test users for performance testing."""
    
    def __init__(self, password_length: int = 12):
        """Initialize test user generator.
        
        Args:
            password_length: Length of generated passwords
        """
        self.password_length = password_length
    
    def generate_password(self) -> str:
        """Generate a random password.
        
        Returns:
            Random password string
        """
        # Use alphanumeric characters for passwords
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(self.password_length))
    
    def generate_username(self, prefix: str = "testuser", index: int = None) -> str:
        """Generate a username.
        
        Args:
            prefix: Username prefix
            index: Optional index (if None, generates random)
            
        Returns:
            Username string
        """
        if index is not None:
            return f"{prefix}{index:06d}"
        else:
            # Random username
            random_suffix = ''.join(random.choices(string.digits, k=6))
            return f"{prefix}{random_suffix}"
    
    def generate_users(
        self,
        count: int,
        username_prefix: str = "testuser",
        start_index: int = 1
    ) -> List[Dict[str, str]]:
        """Generate a list of test users.
        
        Args:
            count: Number of users to generate
            username_prefix: Prefix for usernames
            start_index: Starting index for usernames
            
        Returns:
            List of dicts with 'username' and 'password' keys
        """
        users = []
        
        for i in range(count):
            username = self.generate_username(username_prefix, start_index + i)
            password = self.generate_password()
            
            users.append({
                "username": username,
                "password": password
            })
        
        logger.info(f"Generated {count} test users")
        return users
    
    def generate_mac_based_users(
        self,
        count: int,
        mac_prefix: str = "aa:bb:cc"
    ) -> List[Dict[str, str]]:
        """Generate users based on MAC addresses.
        
        Args:
            count: Number of users to generate
            mac_prefix: MAC address prefix
            
        Returns:
            List of dicts with 'username' (MAC) and 'password' keys
        """
        users = []
        
        for i in range(count):
            # Generate MAC address suffix
            suffix = f"{i % 256:02x}:{(i // 256) % 256:02x}:{(i // 65536) % 256:02x}"
            mac_address = f"{mac_prefix}:{suffix}"
            
            # Use MAC as username, generate password
            password = self.generate_password()
            
            users.append({
                "username": mac_address,
                "password": password
            })
        
        logger.info(f"Generated {count} MAC-based test users")
        return users
    
    def save_to_file(
        self,
        users: List[Dict[str, str]],
        output_path: Path,
        format: str = "radclient"
    ) -> Path:
        """Save test users to a file.
        
        Args:
            users: List of test users
            output_path: Output file path
            format: File format ("radclient" or "users")
            
        Returns:
            Path to saved file
        """
        output_path = Path(output_path)
        
        with output_path.open('w') as f:
            if format == "radclient":
                # radclient format: User-Name = "username", User-Password = "password"
                for user in users:
                    f.write(f'User-Name = "{user["username"]}", User-Password = "{user["password"]}"\n')
            elif format == "users":
                # FreeRADIUS users file format
                for user in users:
                    f.write(f'"{user["username"]}" Cleartext-Password := "{user["password"]}"\n')
                    f.write('    Reply-Message := "Test User"\n\n')
            else:
                raise ValueError(f"Unknown format: {format}")
        
        logger.info(f"Saved {len(users)} users to {output_path} ({format} format)")
        return output_path


# Global generator instance
_generator: Optional[TestUserGenerator] = None


def get_test_user_generator() -> TestUserGenerator:
    """Get global test user generator instance.
    
    Returns:
        TestUserGenerator instance
    """
    global _generator
    if _generator is None:
        _generator = TestUserGenerator()
    return _generator
