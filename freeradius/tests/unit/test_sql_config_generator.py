"""Unit tests for SQL module configuration generator."""

import pytest
from pathlib import Path
from unittest.mock import patch

from radius_app.core.sql_config_generator import SqlConfigGenerator


@pytest.mark.unit
class TestSqlConfigGenerator:
    """Test SQL module configuration generator."""
    
    def test_init(self, temp_config_dir):
        """Test SQL config generator initialization."""
        with patch('radius_app.core.sql_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.database_url = "mysql+pymysql://user:pass@host:3306/db"
            
            generator = SqlConfigGenerator()
            assert generator.config_path == temp_config_dir
    
    def test_generate_sql_module_config_mysql(self, db, temp_config_dir):
        """Test generating SQL module config for MySQL."""
        with patch('radius_app.core.sql_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.database_url = "mysql+pymysql://radius:secret@localhost:3306/radius"
            
            generator = SqlConfigGenerator()
            config = generator.generate_sql_module_config(db)
            
            assert "driver = \"rlm_sql_mysql\"" in config
            assert "server = \"localhost\"" in config
            assert "port = 3306" in config
            assert "login = \"radius\"" in config
            assert "password = \"secret\"" in config
            assert "radius_db = \"radius\"" in config
    
    def test_generate_sql_module_config_postgresql(self, db, temp_config_dir):
        """Test generating SQL module config for PostgreSQL."""
        with patch('radius_app.core.sql_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.database_url = "postgresql://radius:secret@localhost:5432/radius"
            
            generator = SqlConfigGenerator()
            config = generator.generate_sql_module_config(db)
            
            assert "driver = \"rlm_sql_postgresql\"" in config
            assert "server = \"localhost\"" in config
            assert "port = 5432" in config
    
    def test_generate_sql_module_config_sqlite(self, db, temp_config_dir):
        """Test generating SQL module config for SQLite."""
        with patch('radius_app.core.sql_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.database_url = "sqlite:///path/to/db.sqlite"
            
            generator = SqlConfigGenerator()
            config = generator.generate_sql_module_config(db)
            
            assert "driver = \"rlm_sql_sqlite\"" in config
            assert "filename = \"path/to/db.sqlite\"" in config
    
    def test_generate_sql_schema_script(self, temp_config_dir):
        """Test generating SQL schema script."""
        with patch('radius_app.core.sql_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = SqlConfigGenerator()
            schema = generator.generate_sql_schema_script()
            
            # Should include all required tables per FreeRADIUS SQL docs
            assert "CREATE TABLE IF NOT EXISTS radcheck" in schema
            assert "CREATE TABLE IF NOT EXISTS radreply" in schema
            assert "CREATE TABLE IF NOT EXISTS radusergroup" in schema
            assert "CREATE TABLE IF NOT EXISTS radgroupcheck" in schema
            assert "CREATE TABLE IF NOT EXISTS radgroupreply" in schema
            assert "CREATE TABLE IF NOT EXISTS radacct" in schema
            assert "CREATE TABLE IF NOT EXISTS radpostauth" in schema
            
            # Should include proper operators documentation
            assert "op CHAR(2)" in schema
            assert "DEFAULT '=='" in schema  # Default operator for radcheck
    
    def test_sql_config_includes_queries(self, db, temp_config_dir):
        """Test that SQL config includes proper queries."""
        with patch('radius_app.core.sql_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.database_url = "mysql+pymysql://user:pass@host:3306/db"
            
            generator = SqlConfigGenerator()
            config = generator.generate_sql_module_config(db)
            
            # Should include authorization queries per FreeRADIUS SQL docs
            assert "authorize_check_query" in config
            assert "authorize_reply_query" in config
            assert "authorize_group_query" in config
            assert "group_membership_query" in config
            assert "group_reply_query" in config
            
            # Should reference proper tables
            assert "FROM radcheck" in config
            assert "FROM radreply" in config
            assert "FROM radusergroup" in config
    
    def test_sql_config_includes_accounting(self, db, temp_config_dir):
        """Test that SQL config includes accounting queries."""
        with patch('radius_app.core.sql_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.database_url = "mysql+pymysql://user:pass@host:3306/db"
            
            generator = SqlConfigGenerator()
            config = generator.generate_sql_module_config(db)
            
            # Should include accounting section
            assert "accounting {" in config
            assert "type {" in config
            assert "start {" in config
            assert "stop {" in config
            assert "interim-update {" in config
