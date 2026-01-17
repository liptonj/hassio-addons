"""
Performance and load tests for RADIUS authentication.

Tests concurrent authentication requests, response times, and throughput.
"""

import pytest
import time
import statistics
import concurrent.futures
from pathlib import Path

from tests.utils.radius_client import RadiusTestClient
from tests.utils.docker_helpers import is_docker_available


pytestmark = [
    pytest.mark.performance,
    pytest.mark.radius,
    pytest.mark.slow,
    pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
]


@pytest.fixture
def radius_client():
    """Create RADIUS test client."""
    return RadiusTestClient(
        server_host="localhost",
        server_port=1812,
        shared_secret="testing123",
        timeout=5,
    )


@pytest.mark.performance
class TestAuthenticationPerformance:
    """Test RADIUS authentication performance."""

    def test_single_authentication_latency(self, radius_client):
        """Test latency of single authentication request."""
        mac = "aa:bb:cc:dd:ee:ff"
        
        # Warm up
        radius_client.authenticate_mac(mac)
        
        # Measure 10 requests
        latencies = []
        for _ in range(10):
            start = time.time()
            radius_client.authenticate_mac(mac)
            latency = (time.time() - start) * 1000  # milliseconds
            latencies.append(latency)
        
        # Calculate statistics
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
        p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies)
        
        print(f"\\nLatency stats: p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")
        
        # Assert reasonable performance (p95 < 100ms)
        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms target"

    @pytest.mark.slow
    def test_sequential_throughput(self, radius_client):
        """Test sequential authentication throughput."""
        num_requests = 100
        
        start = time.time()
        for i in range(num_requests):
            mac = f"aa:bb:cc:dd:ee:{i%256:02x}"
            radius_client.authenticate_mac(mac)
        elapsed = time.time() - start
        
        throughput = num_requests / elapsed
        print(f"\\nSequential throughput: {throughput:.2f} req/s")
        
        # Should handle at least 50 req/s sequentially
        assert throughput >= 50, f"Throughput {throughput:.2f} req/s below 50 req/s target"

    @pytest.mark.slow
    def test_concurrent_authentication_performance(self, radius_client):
        """Test performance with concurrent authentication requests."""
        num_concurrent = 50
        
        def authenticate(i):
            mac = f"aa:bb:cc:dd:ee:{i%256:02x}"
            start = time.time()
            response = radius_client.authenticate_mac(mac)
            latency = (time.time() - start) * 1000
            return latency, response is not None
        
        # Execute concurrent requests
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(authenticate, range(num_concurrent)))
        elapsed = time.time() - start
        
        # Extract latencies and success rate
        latencies = [r[0] for r in results]
        successes = sum(1 for r in results if r[1])
        
        # Calculate stats
        throughput = num_concurrent / elapsed
        p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
        success_rate = (successes / num_concurrent) * 100
        
        print(f"\\nConcurrent performance:")
        print(f"  Throughput: {throughput:.2f} req/s")
        print(f"  p95 Latency: {p95_latency:.2f}ms")
        print(f"  Success rate: {success_rate:.1f}%")
        
        # Assert performance targets
        assert throughput >= 100, f"Concurrent throughput {throughput:.2f} below 100 req/s"
        assert p95_latency < 100, f"p95 latency {p95_latency:.2f}ms exceeds 100ms"
        assert success_rate >= 95, f"Success rate {success_rate:.1f}% below 95%"

    @pytest.mark.slow
    def test_sustained_load(self, radius_client):
        """Test performance under sustained load."""
        duration_seconds = 10
        concurrent_requests = 5
        
        results = []
        
        def worker():
            """Worker that continuously sends requests."""
            worker_results = []
            end_time = time.time() + duration_seconds
            
            i = 0
            while time.time() < end_time:
                mac = f"aa:bb:cc:dd:ee:{i%256:02x}"
                start = time.time()
                response = radius_client.authenticate_mac(mac)
                latency = (time.time() - start) * 1000
                worker_results.append((latency, response is not None))
                i += 1
            
            return worker_results
        
        # Run sustained load test
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
            futures = [executor.submit(worker) for _ in range(concurrent_requests)]
            for future in concurrent.futures.as_completed(futures):
                results.extend(future.result())
        elapsed = time.time() - start
        
        # Calculate statistics
        total_requests = len(results)
        latencies = [r[0] for r in results]
        successes = sum(1 for r in results if r[1])
        
        throughput = total_requests / elapsed
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
        success_rate = (successes / total_requests) * 100
        
        print(f"\\nSustained load test ({duration_seconds}s):")
        print(f"  Total requests: {total_requests}")
        print(f"  Throughput: {throughput:.2f} req/s")
        print(f"  Avg latency: {avg_latency:.2f}ms")
        print(f"  p95 latency: {p95_latency:.2f}ms")
        print(f"  Success rate: {success_rate:.1f}%")
        
        # Assert sustained performance
        assert throughput >= 80, f"Sustained throughput {throughput:.2f} below 80 req/s"
        assert p95_latency < 150, f"Sustained p95 latency {p95_latency:.2f}ms exceeds 150ms"
        assert success_rate >= 95, f"Success rate {success_rate:.1f}% below 95%"


@pytest.mark.performance
class TestDatabasePerformance:
    """Test database query performance for UDN lookups."""

    def test_udn_lookup_performance(self, db):
        """Test UDN assignment lookup performance."""
        from app.core.udn_manager import UdnManager
        
        manager = UdnManager(db)
        
        # Create test assignments
        num_assignments = 1000
        for i in range(num_assignments):
            manager.assign_udn_id(f"aa:bb:cc:dd:{i//256:02x}:{i%256:02x}")
        
        # Test lookup performance
        lookups = 100
        start = time.time()
        for i in range(lookups):
            mac = f"aa:bb:cc:dd:{i//256:02x}:{i%256:02x}"
            assignment = manager.get_assignment_by_mac(mac)
            assert assignment is not None
        elapsed = time.time() - start
        
        avg_lookup_time = (elapsed / lookups) * 1000  # milliseconds
        print(f"\\nUDN lookup performance: {avg_lookup_time:.2f}ms avg")
        
        # Should be very fast (< 10ms avg)
        assert avg_lookup_time < 10, f"Average lookup time {avg_lookup_time:.2f}ms exceeds 10ms"

    def test_udn_pool_status_performance(self, db):
        """Test UDN pool status calculation performance."""
        from app.core.udn_manager import UdnManager
        
        manager = UdnManager(db)
        
        # Create assignments
        for i in range(100):
            manager.assign_udn_id(f"aa:bb:cc:dd:ee:{i:02x}")
        
        # Test pool status performance
        iterations = 50
        start = time.time()
        for _ in range(iterations):
            status = manager.get_udn_pool_status()
            assert status["assigned"] == 100
        elapsed = time.time() - start
        
        avg_time = (elapsed / iterations) * 1000
        print(f"\\nPool status calculation: {avg_time:.2f}ms avg")
        
        # Should be fast
        assert avg_time < 50, f"Pool status calculation {avg_time:.2f}ms exceeds 50ms"
