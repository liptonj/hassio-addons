"""SQL Counter module configuration generator for FreeRADIUS.

Per FreeRADIUS SQL Counter documentation:
https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sqlcounter/index.html

SQL Counter tracks usage from accounting data (radacct table) and can enforce:
- Total session time limits (never reset)
- Daily session time limits (reset daily)
- Monthly session time limits (reset monthly)

Uses Jinja2 templates for clean, maintainable configuration generation.
"""

import logging
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy.orm import Session

from radius_app.config import get_settings

logger = logging.getLogger(__name__)


class SqlCounterGenerator:
    """Generate FreeRADIUS SQL Counter module configuration.
    
    Per FreeRADIUS SQL Counter documentation:
    - SQL Counter queries radacct table for usage tracking
    - Can track total, daily, or monthly session time
    - Enforces limits via Max-All-Session, Max-Daily-Session, Max-Monthly-Session
    - Requires SQL module to be configured and accounting via SQL
    """
    
    def __init__(self):
        """Initialize SQL Counter config generator."""
        self.settings = get_settings()
        self.config_path = Path(self.settings.radius_config_path)
        self.mods_available = self.config_path / "mods-available"
        self.mods_enabled = self.config_path / "mods-enabled"
        
        # Ensure directories exist
        self.mods_available.mkdir(parents=True, exist_ok=True)
        self.mods_enabled.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        logger.info(f"SQL Counter generator initialized: {self.config_path}")
    
    def write_sql_counter_config(self, db: Session, sql_module_instance: str = "sql") -> Path:
        """Generate and write SQL Counter module configuration, then enable it.
        
        Per FreeRADIUS modules documentation:
        - Modules are enabled by creating symlinks from mods-enabled/ to mods-available/
        - This method writes the config and creates the symlink
        
        Args:
            db: Database session
            sql_module_instance: Name of SQL module instance to use
            
        Returns:
            Path to generated SQL Counter module config file
        """
        logger.info(f"Generating and enabling SQL Counter module configuration (SQL instance: {sql_module_instance})")
        
        # Ensure directories exist
        self.mods_available.mkdir(parents=True, exist_ok=True)
        self.mods_enabled.mkdir(parents=True, exist_ok=True)
        
        # Generate config
        config = self.generate_sql_counter_config(db, sql_module_instance)
        
        # Write to mods-available
        sqlcounter_file = self.mods_available / "sqlcounter"
        sqlcounter_file.write_text(config)
        logger.info(f"✅ Wrote SQL Counter module config: {sqlcounter_file}")
        
        # Create symlink in mods-enabled (enable module)
        sqlcounter_enabled = self.mods_enabled / "sqlcounter"
        if sqlcounter_enabled.exists() or sqlcounter_enabled.is_symlink():
            sqlcounter_enabled.unlink()
        sqlcounter_enabled.symlink_to(sqlcounter_file)
        logger.info(f"✅ Enabled SQL Counter module: {sqlcounter_enabled} -> {sqlcounter_file}")
        
        return sqlcounter_file
    
    def _detect_db_type(self) -> str:
        """Detect database type from connection URL.
        
        Returns:
            Database type string: 'mysql', 'postgresql', or 'sqlite'
        """
        db_url = self.settings.database_url
        
        if db_url.startswith("mysql") or db_url.startswith("mariadb"):
            return "mysql"
        elif db_url.startswith("postgresql"):
            return "postgresql"
        elif db_url.startswith("sqlite"):
            return "sqlite"
        else:
            return "mysql"  # Default to MySQL syntax
    
    def generate_sql_counter_config(self, db: Session, sql_module_instance: str = "sql") -> str:
        """Generate SQL Counter module configuration.
        
        Per FreeRADIUS SQL Counter documentation:
        - SQL Counter requires SQL module instance name
        - Queries radacct table for session time tracking
        - Supports never, daily, and monthly reset intervals
        
        Args:
            db: Database session (for detecting database type)
            sql_module_instance: Name of SQL module instance to use
            
        Returns:
            SQL Counter configuration as string
        """
        logger.info(f"Generating SQL Counter configuration (SQL instance: {sql_module_instance})")
        
        db_type = self._detect_db_type()
        
        # Build template context
        context = {
            "sql_module_instance": sql_module_instance,
            "db_type": db_type,
            "acct_table": "radacct",
            "include_weekly": False,
            "include_data_counters": False,
        }
        
        try:
            template = self.jinja_env.get_template("sql_counter.j2")
            config_content = template.render(**context)
            return config_content
        except TemplateNotFound:
            logger.error("SQL Counter template not found - falling back to code generation")
            return self._generate_fallback_counter_config(sql_module_instance, db_type)
        except Exception as e:
            logger.error(f"Error rendering SQL Counter template: {e}", exc_info=True)
            return self._generate_fallback_counter_config(sql_module_instance, db_type)
    
    def _generate_fallback_counter_config(self, sql_module_instance: str, db_type: str) -> str:
        """Fallback SQL Counter config generation if template fails.
        
        Args:
            sql_module_instance: Name of SQL module instance
            db_type: Database type (mysql, postgresql, sqlite)
            
        Returns:
            SQL Counter configuration as string
        """
        logger.warning("Using fallback code-based SQL Counter configuration generation")
        
        config_lines = [
            "# SQL Counter module configuration - Generated (fallback mode)",
            "",
            "sqlcounter noresetcounter {",
            f"    sql_module_instance = {sql_module_instance}",
            "    counter_name = Max-All-Session-Time",
            "    check_name = Max-All-Session",
            "    reply_name = Session-Timeout",
            "    key = User-Name",
            "    reset = never",
            '    query = "SELECT SUM(AcctSessionTime) FROM radacct WHERE UserName=\'%{%k}\'"',
            "}",
            "",
            "sqlcounter dailycounter {",
            f"    sql_module_instance = {sql_module_instance}",
            "    counter_name = Daily-Session-Time",
            "    check_name = Max-Daily-Session",
            "    reply_name = Session-Timeout",
            "    key = User-Name",
            "    reset = daily",
        ]
        
        if db_type in ("mysql", "mariadb"):
            config_lines.append(
                '    query = "SELECT SUM(AcctSessionTime - GREATEST((%b - UNIX_TIMESTAMP(AcctStartTime)), 0)) '
                'FROM radacct WHERE UserName=\'%{%k}\' AND UNIX_TIMESTAMP(AcctStartTime) + AcctSessionTime > \'%b\'"'
            )
        else:
            config_lines.append(
                '    query = "SELECT SUM(AcctSessionTime) FROM radacct WHERE UserName=\'%{%k}\'"'
            )
        
        config_lines.extend([
            "}",
            "",
            "sqlcounter monthlycounter {",
            f"    sql_module_instance = {sql_module_instance}",
            "    counter_name = Monthly-Session-Time",
            "    check_name = Max-Monthly-Session",
            "    reply_name = Session-Timeout",
            "    key = User-Name",
            "    reset = monthly",
        ])
        
        if db_type in ("mysql", "mariadb"):
            config_lines.append(
                '    query = "SELECT SUM(AcctSessionTime - GREATEST((%b - UNIX_TIMESTAMP(AcctStartTime)), 0)) '
                'FROM radacct WHERE UserName=\'%{%k}\' AND UNIX_TIMESTAMP(AcctStartTime) + AcctSessionTime > \'%b\'"'
            )
        else:
            config_lines.append(
                '    query = "SELECT SUM(AcctSessionTime) FROM radacct WHERE UserName=\'%{%k}\'"'
            )
        
        config_lines.append("}")
        
        return "\n".join(config_lines)
    
    def sync_session_limits_to_radcheck(
        self,
        db: Session,
        username: str,
        max_all_session: Optional[int] = None,
        max_daily_session: Optional[int] = None,
        max_monthly_session: Optional[int] = None,
        portal_db_url: Optional[str] = None,
    ) -> dict:
        """Sync session time limits to radcheck table.
        
        Per FreeRADIUS SQL Counter documentation:
        - Max-All-Session: Total session time limit (seconds)
        - Max-Daily-Session: Daily session time limit (seconds)
        - Max-Monthly-Session: Monthly session time limit (seconds)
        
        Args:
            db: FreeRADIUS database session
            username: Username (PSK ID or email)
            max_all_session: Total session time limit in seconds (optional)
            max_daily_session: Daily session time limit in seconds (optional)
            max_monthly_session: Monthly session time limit in seconds (optional)
            portal_db_url: Portal database URL (if different)
            
        Returns:
            Dictionary with sync statistics
        """
        logger.info(f"Syncing session limits for user {username}")
        
        stats = {
            "radcheck_entries": 0,
            "errors": [],
        }
        
        try:
            from sqlalchemy import text, inspect
            
            # Check if radcheck table exists
            inspector = inspect(db.bind)
            tables = inspector.get_table_names()
            
            if "radcheck" not in tables:
                logger.warning("radcheck table not found - creating schema")
                from radius_app.core.sql_config_generator import SqlConfigGenerator
                sql_gen = SqlConfigGenerator()
                schema = sql_gen.generate_sql_schema_script()
                # Execute schema creation
                for statement in schema.split(";"):
                    statement = statement.strip()
                    if statement and not statement.startswith("--"):
                        try:
                            db.execute(text(statement))
                        except Exception as e:
                            logger.warning(f"Schema creation warning: {e}")
                db.commit()
            
            # Delete existing session limit entries for this user
            db.execute(text("""
                DELETE FROM radcheck 
                WHERE username = :username 
                AND attribute IN ('Max-All-Session', 'Max-Daily-Session', 'Max-Monthly-Session')
            """), {"username": username})
            
            # Insert session limits
            # Per FreeRADIUS SQL Counter docs: operator := means "always matches"
            if max_all_session is not None:
                db.execute(text("""
                    INSERT INTO radcheck (username, attribute, op, value)
                    VALUES (:username, 'Max-All-Session', ':=', :value)
                """), {"username": username, "value": str(max_all_session)})
                stats["radcheck_entries"] += 1
                logger.info(f"Set Max-All-Session = {max_all_session} seconds for {username}")
            
            if max_daily_session is not None:
                db.execute(text("""
                    INSERT INTO radcheck (username, attribute, op, value)
                    VALUES (:username, 'Max-Daily-Session', ':=', :value)
                """), {"username": username, "value": str(max_daily_session)})
                stats["radcheck_entries"] += 1
                logger.info(f"Set Max-Daily-Session = {max_daily_session} seconds for {username}")
            
            if max_monthly_session is not None:
                db.execute(text("""
                    INSERT INTO radcheck (username, attribute, op, value)
                    VALUES (:username, 'Max-Monthly-Session', ':=', :value)
                """), {"username": username, "value": str(max_monthly_session)})
                stats["radcheck_entries"] += 1
                logger.info(f"Set Max-Monthly-Session = {max_monthly_session} seconds for {username}")
            
            db.commit()
            logger.info(f"✅ Synced {stats['radcheck_entries']} session limits for {username}")
            
        except Exception as e:
            logger.error(f"Failed to sync session limits: {e}", exc_info=True)
            stats["errors"].append(f"Sync failed: {str(e)}")
            db.rollback()
        
        return stats
