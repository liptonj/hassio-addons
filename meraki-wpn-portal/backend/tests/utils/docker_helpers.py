"""
Docker helper utilities for E2E tests.

Utilities for managing Docker containers in integration tests.
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class DockerComposeManager:
    """Manages Docker Compose services for testing."""

    def __init__(self, compose_file: Path, project_name: str = "wpn-test"):
        """
        Initialize Docker Compose manager.

        Args:
            compose_file: Path to docker-compose.yml
            project_name: Docker Compose project name
        """
        self.compose_file = compose_file
        self.project_name = project_name
        self.is_running = False

        logger.info(f"Docker Compose manager initialized: {compose_file}")

    def start(self, services: Optional[list[str]] = None, build: bool = True) -> None:
        """
        Start Docker Compose services.

        Args:
            services: List of services to start (all if None)
            build: Whether to build images first
        """
        logger.info(f"Starting Docker Compose services: {services or 'all'}")

        cmd = [
            "docker-compose",
            "-f", str(self.compose_file),
            "-p", self.project_name,
        ]

        # Build if requested
        if build:
            build_cmd = cmd + ["build"]
            if services:
                build_cmd.extend(services)

            logger.info("Building Docker images...")
            result = subprocess.run(build_cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.error(f"Build failed: {result.stderr}")
                raise RuntimeError(f"Docker build failed: {result.stderr}")

        # Start services
        up_cmd = cmd + ["up", "-d"]
        if services:
            up_cmd.extend(services)

        result = subprocess.run(up_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error(f"Start failed: {result.stderr}")
            raise RuntimeError(f"Docker Compose up failed: {result.stderr}")

        self.is_running = True
        logger.info("Docker Compose services started")

    def stop(self, remove_volumes: bool = False) -> None:
        """
        Stop Docker Compose services.

        Args:
            remove_volumes: Whether to remove volumes
        """
        if not self.is_running:
            return

        logger.info("Stopping Docker Compose services...")

        cmd = [
            "docker-compose",
            "-f", str(self.compose_file),
            "-p", self.project_name,
            "down",
        ]

        if remove_volumes:
            cmd.append("--volumes")

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.warning(f"Stop failed: {result.stderr}")

        self.is_running = False
        logger.info("Docker Compose services stopped")

    def get_logs(self, service: str, tail: int = 100) -> str:
        """
        Get logs from a service.

        Args:
            service: Service name
            tail: Number of lines to retrieve

        Returns:
            Log output
        """
        cmd = [
            "docker-compose",
            "-f", str(self.compose_file),
            "-p", self.project_name,
            "logs",
            "--tail", str(tail),
            service,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout

    def exec_command(self, service: str, command: list[str]) -> tuple[int, str, str]:
        """
        Execute command in a service container.

        Args:
            service: Service name
            command: Command to execute

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = [
            "docker-compose",
            "-f", str(self.compose_file),
            "-p", self.project_name,
            "exec",
            "-T",  # Disable pseudo-TTY
            service,
        ] + command

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr

    def wait_for_health(
        self,
        service: str,
        url: str,
        timeout: int = 60,
        interval: int = 2,
    ) -> bool:
        """
        Wait for service to be healthy.

        Args:
            service: Service name
            url: Health check URL
            timeout: Maximum wait time in seconds
            interval: Check interval in seconds

        Returns:
            True if service is healthy, False if timeout
        """
        logger.info(f"Waiting for {service} to be healthy at {url}...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = httpx.get(url, timeout=5)
                if response.status_code == 200:
                    logger.info(f"{service} is healthy")
                    return True
            except Exception as e:
                logger.debug(f"Health check failed: {e}")

            time.sleep(interval)

        logger.error(f"{service} health check timeout after {timeout}s")
        return False

    def wait_for_port(
        self,
        host: str,
        port: int,
        timeout: int = 60,
        interval: int = 2,
    ) -> bool:
        """
        Wait for port to be open.

        Args:
            host: Hostname
            port: Port number
            timeout: Maximum wait time in seconds
            interval: Check interval in seconds

        Returns:
            True if port is open, False if timeout
        """
        import socket

        logger.info(f"Waiting for {host}:{port} to be open...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    logger.info(f"{host}:{port} is open")
                    return True
            except Exception as e:
                logger.debug(f"Port check failed: {e}")

            time.sleep(interval)

        logger.error(f"{host}:{port} timeout after {timeout}s")
        return False


def is_docker_available() -> bool:
    """
    Check if Docker is available.

    Returns:
        True if Docker is running
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=False
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_docker_compose_available() -> bool:
    """
    Check if Docker Compose is available.

    Returns:
        True if docker-compose is available
    """
    try:
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            timeout=5,
            check=False
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
