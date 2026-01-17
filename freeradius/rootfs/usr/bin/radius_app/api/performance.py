"""Performance testing API endpoints."""

import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from radius_app.api.deps import AdminUser, DbSession
from radius_app.core.performance_tester import get_performance_tester, PerformanceTestResult
from radius_app.core.test_user_generator import get_test_user_generator
from radius_app.db.models import RadiusClient

logger = logging.getLogger(__name__)

router = APIRouter()


class PerformanceTestRequest(BaseModel):
    """Request for performance test."""
    client_id: Optional[int] = Field(None, description="Client ID to test (uses localhost if not provided)")
    num_users: int = Field(100, ge=1, le=10000, description="Number of test users to generate")
    server_host: Optional[str] = Field(None, description="Server hostname (uses client IP if client_id provided)")
    server_port: int = Field(1812, ge=1, le=65535, description="Server port")
    secret: Optional[str] = Field(None, description="Shared secret (uses client secret if client_id provided)")
    iterations: int = Field(1, ge=1, le=10, description="Number of test iterations")
    username_prefix: str = Field("testuser", description="Prefix for generated usernames")
    use_mac_addresses: bool = Field(False, description="Use MAC addresses as usernames")


class PerformanceTestResponse(BaseModel):
    """Response from performance test."""
    success: bool
    message: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    elapsed_time: float
    requests_per_second: float
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    iterations: int
    output: Optional[str] = None
    error: Optional[str] = None


@router.post("/api/v1/performance/test", response_model=PerformanceTestResponse)
async def run_performance_test(
    request: PerformanceTestRequest,
    admin: AdminUser,
    db: DbSession
) -> PerformanceTestResponse:
    """
    Run RADIUS performance test using radclient.
    
    Generates test users and measures authentication throughput.
    
    Args:
        request: Performance test parameters
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Performance test results
    """
    logger.info(f"Performance test requested by {admin['sub']}: {request.num_users} users, {request.iterations} iterations")
    
    tester = get_performance_tester()
    
    if not tester.radclient_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="radclient is not available - performance testing disabled"
        )
    
    # Get client configuration if client_id provided
    server_host = request.server_host or "localhost"
    server_port = request.server_port
    secret = request.secret or "testing123"
    
    if request.client_id:
        client = db.get(RadiusClient, request.client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client with ID {request.client_id} not found"
            )
        
        # Use client configuration
        if not request.server_host:
            # Extract IP from client IP address (could be CIDR)
            server_host = client.ipaddr.split('/')[0]
        if not request.secret:
            secret = client.secret
    
    # Generate test users
    generator = get_test_user_generator()
    
    if request.use_mac_addresses:
        test_users = generator.generate_mac_based_users(request.num_users)
    else:
        test_users = generator.generate_users(
            request.num_users,
            username_prefix=request.username_prefix
        )
    
    try:
        # Run performance test
        if request.iterations > 1:
            # Benchmark mode - multiple iterations
            benchmark_results = tester.benchmark_configuration(
                test_users=test_users,
                server_host=server_host,
                server_port=server_port,
                secret=secret,
                iterations=request.iterations
            )
            
            result = benchmark_results["average"]
            iterations = request.iterations
        else:
            # Single test
            test_file = tester.create_test_file(test_users)
            try:
                result = tester.run_performance_test(
                    test_file=test_file,
                    server_host=server_host,
                    server_port=server_port,
                    secret=secret
                )
                iterations = 1
            finally:
                if test_file.exists():
                    test_file.unlink()
        
        # Format response
        success_rate = (result.successful_requests / result.total_requests * 100) if result.total_requests > 0 else 0
        
        message = (
            f"Performance test completed: {result.successful_requests}/{result.total_requests} successful "
            f"({success_rate:.1f}%), {result.requests_per_second:.2f} req/s"
        )
        
        return PerformanceTestResponse(
            success=result.error is None,
            message=message,
            total_requests=result.total_requests,
            successful_requests=result.successful_requests,
            failed_requests=result.failed_requests,
            elapsed_time=round(result.elapsed_time, 3),
            requests_per_second=round(result.requests_per_second, 2),
            average_latency_ms=round(result.average_latency_ms, 2),
            p50_latency_ms=round(result.p50_latency_ms, 2),
            p95_latency_ms=round(result.p95_latency_ms, 2),
            p99_latency_ms=round(result.p99_latency_ms, 2),
            iterations=iterations,
            output=result.output[:1000] if result.output else None,  # Limit output length
            error=result.error
        )
        
    except Exception as e:
        logger.error(f"Performance test failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance test failed: {str(e)}"
        )


@router.get("/api/v1/performance/status")
async def get_performance_test_status(admin: AdminUser) -> dict:
    """
    Get performance testing status and capabilities.
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Status information
    """
    tester = get_performance_tester()
    
    return {
        "radclient_available": tester.radclient_available,
        "capabilities": {
            "single_test": tester.radclient_available,
            "benchmark": tester.radclient_available,
            "test_user_generation": True
        },
        "limits": {
            "max_users": 10000,
            "max_iterations": 10
        }
    }
