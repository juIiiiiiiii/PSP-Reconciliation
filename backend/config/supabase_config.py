"""
Supabase Configuration
"""

import os
from typing import Optional

class SupabaseConfig:
    """Supabase configuration"""
    
    SUPABASE_URL: Optional[str] = os.getenv('SUPABASE_URL')
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    SUPABASE_ANON_KEY: Optional[str] = os.getenv('SUPABASE_ANON_KEY')
    
    # Database connection (Supabase provides connection pooling)
    DATABASE_URL: Optional[str] = os.getenv('DATABASE_URL')
    
    # Use Supabase connection pool if available
    @classmethod
    def get_database_url(cls) -> str:
        """Get database connection URL (prefer Supabase pool)"""
        if cls.SUPABASE_URL and cls.DATABASE_URL:
            # Supabase connection string format
            # postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
            return cls.DATABASE_URL
        return cls.DATABASE_URL or "postgresql://postgres:postgres@localhost:5432/psp_reconciliation"


