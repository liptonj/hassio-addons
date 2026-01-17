"""Unit tests for performance testing module."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from radius_app.core.performance_tester import (
    PerformanceTester,
    PerformanceTestResult,
    get_performance_tester
)
from radius_app.core.test_user_generator import (
    TestUserGenerator,
    get_test_user_generator
)


class TestTestUserGenerator:
    """Test test user generator."""
    
    def test_generate_password(self):
        """Test password generation."""
        generator = TestUserGenerator()
        password = generator.generate_password()
        
        assert len(password) == 12
        assert password.isalnum()
    
    def test_generate_username(self):
        """Test username generation."""
        generator = TestUserGenerator()
        
        # With index
        username = generator.generate_username("test", 123)
        assert username == "test000123"
        
        # Without index (random)
        username = generator.generate_username("test")
        assert username.startswith("test")
        assert len(username) > 4
    
    def test_generate_users(self):
        """Test user generation."""
        generator = TestUserGenerator()
        users = generator.generate_users(10, "user", 1)
        
        assert len(users) == 10
        assert users[0]["username"] == "user000001"
        assert users[9]["username"] == "user000010"
        assert all("password" in user for user in users)
        assert all(len(user["password"]) == 12 for user in users)
    
    def test_generate_mac_based_users(self):
        """Test MAC-based user generation."""
        generator = TestUserGenerator()
        users = generator.generate_mac_based_users(5, "aa:bb:cc")
        
        assert len(users) == 5
        assert users[0]["username"].startswith("aa:bb:cc:")
        assert all("password" in user for user in users)
    
    def test_save_to_file_radclient(self, tmp_path):
        """Test saving users to radclient format."""
        generator = TestUserGenerator()
        users = generator.generate_users(3, "test", 1)
        
        output_file = tmp_path / "test.radclient"
        generator.save_to_file(users, output_file, format="radclient")
        
        assert output_file.exists()
        content = output_file.read_text()
        assert 'User-Name = "test000001"' in content
        assert 'User-Password = "' in content
    
    def test_save_to_file_users(self, tmp_path):
        """Test saving users to FreeRADIUS users format."""
        generator = TestUserGenerator()
        users = generator.generate_users(2, "test", 1)
        
        output_file = tmp_path / "test.users"
        generator.save_to_file(users, output_file, format="users")
        
        assert output_file.exists()
        content = output_file.read_text()
        assert '"test000001"' in content
        assert "Cleartext-Password" in content
        assert "Reply-Message" in content
    
    def test_get_test_user_generator(self):
        """Test global generator instance."""
        generator1 = get_test_user_generator()
        generator2 = get_test_user_generator()
        
        # Should return same instance
        assert generator1 is generator2


class TestPerformanceTester:
    """Test performance tester."""
    
    def test_check_radclient_available(self):
        """Test radclient availability check."""
        tester = PerformanceTester()
        # Should not raise exception
        assert isinstance(tester.radclient_available, bool)
    
    @patch('subprocess.run')
    def test_radclient_not_available(self, mock_run):
        """Test behavior when radclient is not available."""
        mock_run.side_effect = FileNotFoundError()
        
        tester = PerformanceTester()
        assert tester.radclient_available is False
    
    def test_create_test_file(self, tmp_path):
        """Test test file creation."""
        tester = PerformanceTester()
        
        test_users = [
            {"username": "user1", "password": "pass1"},
            {"username": "user2", "password": "pass2"}
        ]
        
        output_file = tmp_path / "test.radclient"
        result_file = tester.create_test_file(test_users, output_file)
        
        assert result_file == output_file
        assert output_file.exists()
        
        content = output_file.read_text()
        assert 'User-Name = "user1"' in content
        assert 'User-Password = "pass1"' in content
        assert 'User-Name = "user2"' in content
    
    def test_create_test_file_temp(self):
        """Test test file creation with temp file."""
        tester = PerformanceTester()
        
        test_users = [
            {"username": "user1", "password": "pass1"}
        ]
        
        result_file = tester.create_test_file(test_users)
        
        assert result_file.exists()
        assert result_file.suffix == ".test"
        
        # Cleanup
        result_file.unlink()
    
    @patch('subprocess.run')
    def test_run_performance_test_success(self, mock_run, tmp_path):
        """Test successful performance test."""
        # Mock radclient success
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Received Access-Accept\n" * 10
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        tester = PerformanceTester()
        tester.radclient_available = True  # Override check
        
        test_file = tmp_path / "test.radclient"
        test_file.write_text('User-Name = "test", User-Password = "test"\n' * 10)
        
        result = tester.run_performance_test(
            test_file=test_file,
            server_host="localhost",
            server_port=1812,
            secret="testing123",
            num_requests=10
        )
        
        assert isinstance(result, PerformanceTestResult)
        assert result.total_requests == 10
        assert result.successful_requests == 10
        assert result.failed_requests == 0
        assert result.requests_per_second > 0
    
    @patch('subprocess.run')
    def test_run_performance_test_failure(self, mock_run, tmp_path):
        """Test performance test with failures."""
        # Mock radclient with failures
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Received Access-Accept\n" * 7 + "Received Access-Reject\n" * 3
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        tester = PerformanceTester()
        tester.radclient_available = True
        
        test_file = tmp_path / "test.radclient"
        test_file.write_text('User-Name = "test", User-Password = "test"\n' * 10)
        
        result = tester.run_performance_test(
            test_file=test_file,
            server_host="localhost",
            server_port=1812,
            secret="testing123",
            num_requests=10
        )
        
        assert result.successful_requests == 7
        assert result.failed_requests == 3
    
    @patch('subprocess.run')
    def test_run_performance_test_timeout(self, mock_run, tmp_path):
        """Test performance test timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("radclient", 10)
        
        tester = PerformanceTester()
        tester.radclient_available = True
        
        test_file = tmp_path / "test.radclient"
        test_file.write_text('User-Name = "test", User-Password = "test"\n')
        
        result = tester.run_performance_test(
            test_file=test_file,
            server_host="localhost",
            server_port=1812,
            secret="testing123",
            num_requests=1,
            timeout=10
        )
        
        assert result.error is not None
        assert "timeout" in result.error.lower()
    
    def test_run_performance_test_radclient_not_available(self, tmp_path):
        """Test performance test when radclient not available."""
        tester = PerformanceTester()
        tester.radclient_available = False
        
        test_file = tmp_path / "test.radclient"
        test_file.write_text('User-Name = "test", User-Password = "test"\n')
        
        with pytest.raises(RuntimeError, match="radclient is not available"):
            tester.run_performance_test(
                test_file=test_file,
                server_host="localhost",
                server_port=1812,
                secret="testing123"
            )
    
    def test_run_performance_test_file_not_found(self):
        """Test performance test with missing file."""
        tester = PerformanceTester()
        tester.radclient_available = True
        
        with pytest.raises(FileNotFoundError):
            tester.run_performance_test(
                test_file=Path("/nonexistent/file"),
                server_host="localhost",
                server_port=1812,
                secret="testing123"
            )
    
    @patch('subprocess.run')
    def test_benchmark_configuration(self, mock_run, tmp_path):
        """Test benchmark configuration."""
        # Mock successful radclient runs
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Received Access-Accept\n" * 10
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        tester = PerformanceTester()
        tester.radclient_available = True
        
        test_users = [
            {"username": f"user{i}", "password": f"pass{i}"}
            for i in range(10)
        ]
        
        results = tester.benchmark_configuration(
            test_users=test_users,
            server_host="localhost",
            server_port=1812,
            secret="testing123",
            iterations=3
        )
        
        assert "results" in results
        assert "average" in results
        assert results["iterations"] == 3
        assert len(results["results"]) == 3
        assert isinstance(results["average"], PerformanceTestResult)
    
    def test_get_performance_tester(self):
        """Test global tester instance."""
        tester1 = get_performance_tester()
        tester2 = get_performance_tester()
        
        # Should return same instance
        assert tester1 is tester2
