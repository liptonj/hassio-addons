"""Health monitoring service for NADs."""

import asyncio
import logging
import socket
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from radius_app.db.database import get_db
from radius_app.db.models import RadiusClient, RadiusNadExtended, RadiusNadHealth

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors NAD health and connectivity."""
    
    def __init__(self, check_interval: int = 60):
        """Initialize health monitor.
        
        Args:
            check_interval: How often to check health (seconds)
        """
        self.check_interval = check_interval
        self.running = False
        logger.info(f"Health monitor initialized (check interval: {check_interval}s)")
    
    def _test_nad_connectivity(self, ip_addr: str) -> tuple[bool, float | None]:
        """Test connectivity to a NAD.
        
        Args:
            ip_addr: IP address to test
            
        Returns:
            Tuple of (is_reachable, latency_ms)
        """
        # Extract IP if CIDR notation
        ip_addr = ip_addr.split('/')[0]
        
        # Try connecting to RADIUS authentication port
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip_addr, 1812))
            sock.close()
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Port open or connection refused both mean host is reachable
            is_reachable = result in (0, 111)  # 0 = connected, 111 = connection refused (but host alive)
            
            return is_reachable, latency_ms if is_reachable else None
            
        except socket.timeout:
            return False, None
        except Exception as e:
            logger.debug(f"Connection test failed for {ip_addr}: {e}")
            return False, None
    
    async def check_all_nads(self, db: Session) -> int:
        """Check health of all active NADs.
        
        Args:
            db: Database session
            
        Returns:
            Number of NADs checked
        """
        checked_count = 0
        
        try:
            # Get all active clients with extended info
            stmt = select(RadiusClient).where(RadiusClient.is_active == True)
            clients = db.execute(stmt).scalars().all()
            
            for client in clients:
                try:
                    # Get or create extended info
                    extended = db.execute(
                        select(RadiusNadExtended).where(
                            RadiusNadExtended.radius_client_id == client.id
                        )
                    ).scalar_one_or_none()
                    
                    if not extended:
                        # Create extended record for backward compatibility
                        extended = RadiusNadExtended(
                            radius_client_id=client.id,
                        )
                        db.add(extended)
                        db.flush()
                    
                    # Get or create health record
                    health = db.execute(
                        select(RadiusNadHealth).where(
                            RadiusNadHealth.nad_id == extended.id
                        )
                    ).scalar_one_or_none()
                    
                    if not health:
                        health = RadiusNadHealth(
                            nad_id=extended.id,
                            is_reachable=False,
                            request_count=0,
                            success_count=0,
                            failure_count=0,
                        )
                        db.add(health)
                        db.flush()
                    
                    # Test connectivity
                    is_reachable, latency_ms = self._test_nad_connectivity(client.ipaddr)
                    
                    # Update health record
                    health.is_reachable = is_reachable
                    health.checked_at = datetime.now(timezone.utc)
                    
                    if is_reachable:
                        health.last_seen = datetime.now(timezone.utc)
                        
                        # Update average response time (simple moving average)
                        if health.avg_response_time_ms is None:
                            health.avg_response_time_ms = latency_ms
                        else:
                            # Weighted average (70% old, 30% new)
                            health.avg_response_time_ms = (
                                health.avg_response_time_ms * 0.7 + latency_ms * 0.3
                            )
                    
                    checked_count += 1
                    
                except Exception as e:
                    logger.error(f"Error checking NAD {client.id} ({client.name}): {e}")
                    continue
            
            # Commit all changes
            db.commit()
            
        except Exception as e:
            logger.error(f"Error in NAD health check: {e}", exc_info=True)
            db.rollback()
        
        return checked_count
    
    async def monitor_loop(self):
        """Main monitoring loop - runs continuously."""
        logger.info("🏥 Starting NAD health monitoring loop...")
        self.running = True
        
        # Initial check after short delay
        await asyncio.sleep(10)
        
        # Monitoring loop
        while self.running:
            try:
                # Get database session
                db_generator = get_db()
                db = next(db_generator)
                
                try:
                    checked = await self.check_all_nads(db)
                    if checked > 0:
                        logger.debug(f"Health check completed for {checked} NADs")
                finally:
                    db.close()
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Health monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(self.check_interval)
        
        logger.info("NAD health monitoring loop stopped")
    
    def stop(self):
        """Stop the monitoring loop."""
        self.running = False
