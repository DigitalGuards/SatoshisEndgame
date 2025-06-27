import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.pool import NullPool

from src.config import settings
from src.data.models import Base

logger = structlog.get_logger()


class Database:
    """Async database connection manager"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self.logger = logger.bind(component="database")
    
    async def initialize(self):
        """Initialize database engine and session factory"""
        try:
            # Check if using SQLite
            if self.database_url.startswith('sqlite'):
                # SQLite configuration
                self.engine = create_async_engine(
                    self.database_url,
                    echo=False,
                    connect_args={"check_same_thread": False},
                    poolclass=NullPool
                )
            else:
                # PostgreSQL configuration
                self.engine = create_async_engine(
                    self.database_url,
                    echo=False,  # Set to True for SQL debugging
                    pool_size=20,
                    max_overflow=40,
                    pool_pre_ping=True,  # Verify connections before use
                    pool_recycle=3600,  # Recycle connections after 1 hour
                )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            async with self.engine.begin() as conn:
                await conn.run_sync(lambda conn: conn.execute("SELECT 1"))
            
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize database", error=str(e))
            raise
    
    async def create_tables(self):
        """Create all database tables"""
        if not self.engine:
            raise RuntimeError("Database not initialized")
            
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            self.logger.info("Database tables created")
        except Exception as e:
            self.logger.error("Failed to create tables", error=str(e))
            raise
    
    async def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        if not self.engine:
            raise RuntimeError("Database not initialized")
            
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            self.logger.info("Database tables dropped")
        except Exception as e:
            self.logger.error("Failed to drop tables", error=str(e))
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session"""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
            
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            self.logger.info("Database connections closed")


# Global database instance
db = Database()


async def init_db():
    """Initialize the database"""
    await db.initialize()
    await db.create_tables()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with db.get_session() as session:
        yield session