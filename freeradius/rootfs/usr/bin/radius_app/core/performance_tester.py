"""FreeRADIUS performance testing module.

Performs bulk authentication testing using radclient to measure
authentication throughput and performance.

Reference: https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/tuning/performance-testing.html
"""

import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PerformanceTestResult:
    """Results from a performance test."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    elapsed_time: float
    requests_per_second: float
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    latencies: List[float]
    output: str
    error: Optional[str] = None


class PerformanceTester:
    """Performs RADIUS performance testing using radclient."""
    
    def __init__(self):
        """Initialize performance tester."""
        self.radclient_available = self._check_radclient_available()
        if not self.radclient_available:
            logger.warning("⚠️  radclient not available - performance testing disabled")
    
    def _check_radclient_available(self) -> bool:
        """Check if radclient is available.
        
        Returns:
            True if radclient is available
        """
        try:
            result = subprocess.run(
                ["radclient", "-v"],
                capture_output=True,
                timeout=5,
                text=True
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def create_test_file(
        self,
        test_users: List[Dict[str, str]],
        output_path: Optional[Path] = None
    ) -> Path:
        """Create a radclient test file from test users.
        
        Args:
            test_users: List of dicts with 'username' and 'password' keys
            output_path: Optional output path (uses temp file if not provided)
            
        Returns:
            Path to created test file
        """
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.test',
                delete=False
            )
            output_path = Path(temp_file.name)
            temp_file.close()
        
        output_path = Path(output_path)
        
        # radclient format: one request per line
        # Format: User-Name = "username", User-Password = "password"
        with output_path.open('w') as f:
            for user in test_users:
                username = user.get('username', '')
                password = user.get('password', '')
                f.write(f'User-Name = "{username}", User-Password = "{password}"\n')
        
        logger.debug(f"Created test file with {len(test_users)} users: {output_path}")
        return output_path
    
    def run_performance_test(
        self,
        test_file: Path,
        server_host: str = "localhost",
        server_port: int = 1812,
        secret: str = "testing123",
        num_requests: Optional[int] = None,
        timeout: int = 30
    ) -> PerformanceTestResult:
        """Run performance test using radclient.
        
        Args:
            test_file: Path to radclient test file
            server_host: RADIUS server hostname
            server_port: RADIUS server port
            secret: Shared secret for RADIUS client
            num_requests: Number of requests to send (None = all in file)
            timeout: Timeout in seconds
            
        Returns:
            PerformanceTestResult with test metrics
            
        Raises:
            RuntimeError: If radclient is not available or test fails
        """
        if not self.radclient_available:
            raise RuntimeError("radclient is not available")
        
        if not test_file.exists():
            raise FileNotFoundError(f"Test file not found: {test_file}")
        
        # Count requests in file if num_requests not specified
        if num_requests is None:
            with test_file.open('r') as f:
                num_requests = sum(1 for line in f if line.strip())
        
        logger.info(f"Running performance test: {num_requests} requests to {server_host}:{server_port}")
        
        # Run radclient
        # -q: quiet mode (less output)
        # -s: single-threaded (for accurate timing)
        # -f: read requests from file
        start_time = time.time()
        
        try:
            result = subprocess.run(
                [
                    "radclient",
                    "-q",
                    "-s",
                    "-f",
                    str(test_file),
                    server_host,
                    str(server_port),
                    secret
                ],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            elapsed_time = time.time() - start_time
            
            # Parse output to count successes/failures
            output = result.stdout + result.stderr
            successful = output.count("Received Access-Accept")
            failed = output.count("Received Access-Reject") + output.count("ERROR")
            
            # Calculate metrics
            requests_per_second = num_requests / elapsed_time if elapsed_time > 0 else 0
            
            # For latency, we'd need to parse individual request times
            # For now, estimate average latency
            average_latency_ms = (elapsed_time / num_requests * 1000) if num_requests > 0 else 0
            
            # Estimate percentiles (simplified - would need individual timings for accurate)
            latencies = [average_latency_ms] * num_requests  # Placeholder
            p50_latency_ms = average_latency_ms
            p95_latency_ms = average_latency_ms * 1.5
            p99_latency_ms = average_latency_ms * 2
            
            return PerformanceTestResult(
                total_requests=num_requests,
                successful_requests=successful,
                failed_requests=failed,
                elapsed_time=elapsed_time,
                requests_per_second=requests_per_second,
                average_latency_ms=average_latency_ms,
                p50_latency_ms=p50_latency_ms,
                p95_latency_ms=p95_latency_ms,
                p99_latency_ms=p99_latency_ms,
                latencies=latencies,
                output=output,
                error=None if result.returncode == 0 else result.stderr
            )
            
        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            return PerformanceTestResult(
                total_requests=num_requests or 0,
                successful_requests=0,
                failed_requests=0,
                elapsed_time=elapsed_time,
                requests_per_second=0,
                average_latency_ms=0,
                p50_latency_ms=0,
                p95_latency_ms=0,
                p99_latency_ms=0,
                latencies=[],
                output="",
                error=f"Test timeout after {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Performance test error: {e}", exc_info=True)
            raise RuntimeError(f"Performance test failed: {str(e)}")
    
    def benchmark_configuration(
        self,
        test_users: List[Dict[str, str]],
        server_host: str = "localhost",
        server_port: int = 1812,
        secret: str = "testing123",
        iterations: int = 3
    ) -> Dict[str, PerformanceTestResult]:
        """Run multiple performance tests and return average results.
        
        Args:
            test_users: List of test users
            server_host: RADIUS server hostname
            server_port: RADIUS server port
            secret: Shared secret
            iterations: Number of test iterations
            
        Returns:
            Dictionary with 'results' (list of results) and 'average' (averaged result)
        """
        results = []
        
        # Create test file
        test_file = self.create_test_file(test_users)
        
        try:
            for i in range(iterations):
                logger.info(f"Running benchmark iteration {i+1}/{iterations}")
                result = self.run_performance_test(
                    test_file=test_file,
                    server_host=server_host,
                    server_port=server_port,
                    secret=secret
                )
                results.append(result)
                time.sleep(1)  # Brief pause between iterations
            
            # Calculate averages
            if results:
                avg_result = PerformanceTestResult(
                    total_requests=results[0].total_requests,
                    successful_requests=int(sum(r.successful_requests for r in results) / len(results)),
                    failed_requests=int(sum(r.failed_requests for r in results) / len(results)),
                    elapsed_time=sum(r.elapsed_time for r in results) / len(results),
                    requests_per_second=sum(r.requests_per_second for r in results) / len(results),
                    average_latency_ms=sum(r.average_latency_ms for r in results) / len(results),
                    p50_latency_ms=sum(r.p50_latency_ms for r in results) / len(results),
                    p95_latency_ms=sum(r.p95_latency_ms for r in results) / len(results),
                    p99_latency_ms=sum(r.p99_latency_ms for r in results) / len(results),
                    latencies=[],
                    output=f"Averaged over {iterations} iterations",
                    error=None
                )
                
                return {
                    "results": results,
                    "average": avg_result,
                    "iterations": iterations
                }
            else:
                raise RuntimeError("No test results collected")
                
        finally:
            # Clean up test file
            if test_file.exists():
                try:
                    test_file.unlink()
                except Exception:
                    pass


# Global tester instance
_tester: Optional[PerformanceTester] = None


def get_performance_tester() -> PerformanceTester:
    """Get global performance tester instance.
    
    Returns:
        PerformanceTester instance
    """
    global _tester
    if _tester is None:
        _tester = PerformanceTester()
    return _tester
