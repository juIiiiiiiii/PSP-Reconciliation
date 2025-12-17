"""
Supabase Integration Client
Provides database connection and migration management via Supabase MCP
"""

import logging
import os
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from supabase import create_client, Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Supabase client wrapper for database operations"""
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        db_connection_string: Optional[str] = None
    ):
        """
        Initialize Supabase client
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key (for admin operations)
            db_connection_string: Direct PostgreSQL connection string (for SQLAlchemy)
        """
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.db_connection_string = db_connection_string or os.getenv('DATABASE_URL')
        
        if self.supabase_url and self.supabase_key:
            self.client: Optional[Client] = create_client(self.supabase_url, self.supabase_key)
        else:
            self.client = None
            logger.warning("Supabase credentials not provided, using direct PostgreSQL connection")
        
        # SQLAlchemy engine for direct database access
        if self.db_connection_string:
            # Convert Supabase connection string format if needed
            if 'supabase.co' in self.db_connection_string:
                # Supabase uses connection pooling, adjust connection string
                parsed = urlparse(self.db_connection_string)
                # Use transaction mode for connection pooling
                pool_url = self.db_connection_string.replace(
                    parsed.path,
                    f"{parsed.path}?pgbouncer=true"
                )
                self.db_engine = create_engine(pool_url, pool_pre_ping=True)
            else:
                self.db_engine = create_engine(self.db_connection_string, pool_pre_ping=True)
            
            self.SessionLocal = sessionmaker(bind=self.db_engine)
        else:
            self.db_engine = None
            self.SessionLocal = None
    
    def get_session(self):
        """Get SQLAlchemy session"""
        if not self.SessionLocal:
            raise ValueError("Database connection not configured")
        return self.SessionLocal()
    
    async def apply_migration_via_mcp(
        self,
        migration_name: str,
        sql_query: str
    ) -> Dict[str, Any]:
        """
        Apply migration via Supabase MCP tool
        
        This would be called via MCP tool, not directly
        """
        # This is a placeholder - actual implementation would use MCP tool
        logger.info(f"Migration {migration_name} would be applied via MCP")
        return {
            'migration_name': migration_name,
            'status': 'pending_mcp_call'
        }
    
    async def execute_sql_via_mcp(
        self,
        sql_query: str
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL via Supabase MCP tool
        
        This would be called via MCP tool, not directly
        """
        # This is a placeholder - actual implementation would use MCP tool
        logger.info("SQL query would be executed via MCP")
        return []


