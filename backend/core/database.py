"""
Database connection management with Supabase support
"""

import os
import logging
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from backend.services.integrations.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection manager with Supabase integration"""
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        use_supabase: bool = True
    ):
        """
        Initialize database manager
        
        Args:
            database_url: Database connection URL
            use_supabase: Whether to use Supabase connection pooling
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.use_supabase = use_supabase and os.getenv('SUPABASE_URL') is not None
        
        if self.use_supabase:
            # Use Supabase client for connection pooling
            self.supabase_client = SupabaseClient(
                supabase_url=os.getenv('SUPABASE_URL'),
                supabase_key=os.getenv('SUPABASE_SERVICE_ROLE_KEY'),
                db_connection_string=self.database_url
            )
            self.db_engine = self.supabase_client.db_engine
            self.SessionLocal = self.supabase_client.SessionLocal
        else:
            # Direct PostgreSQL connection
            self.db_engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            self.SessionLocal = sessionmaker(bind=self.db_engine)
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connections"""
        if self.db_engine:
            self.db_engine.dispose()


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager


def get_db_session() -> Session:
    """Get database session"""
    return get_db_manager().get_session()


