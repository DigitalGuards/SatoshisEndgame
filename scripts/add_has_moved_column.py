#!/usr/bin/env python3
"""
Add has_moved column to wallets table
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.data.database import db
import structlog

logger = structlog.get_logger()


async def add_has_moved_column():
    """Add has_moved column to wallets table"""
    await db.initialize()
    
    async with db.get_session() as session:
        try:
            # Add the column
            await session.execute(text(
                "ALTER TABLE wallets ADD COLUMN has_moved BOOLEAN DEFAULT FALSE"
            ))
            await session.commit()
            logger.info("Successfully added has_moved column to wallets table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                logger.info("Column has_moved already exists")
            else:
                logger.error(f"Error adding column: {e}")
                raise
    
    await db.close()


if __name__ == "__main__":
    asyncio.run(add_has_moved_column())