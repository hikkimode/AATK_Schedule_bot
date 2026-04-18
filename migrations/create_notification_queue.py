"""
Migration script to create notification_queue table.

Run this script to add the notification queue table to your database:
    python migrations/create_notification_queue.py

Or use Alembic if you have it configured.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from config import load_config


async def create_notification_queue_table():
    """Create notification_queue table if it doesn't exist."""
    config = load_config()
    engine = create_async_engine(config.database_url)
    
    async with engine.begin() as conn:
        # Check if table already exists
        check_query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'notification_queue'
            );
        """)
        result = await conn.execute(check_query)
        exists = result.scalar()
        
        if exists:
            print("Table 'notification_queue' already exists. Skipping creation.")
            return
        
        # Create the table
        create_table_sql = text("""
            CREATE TABLE notification_queue (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                message_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP NULL,
                error_message TEXT NULL,
                group_name TEXT NULL
            );
            
            -- Create indexes for efficient queries
            CREATE INDEX idx_notification_queue_user_id ON notification_queue(user_id);
            CREATE INDEX idx_notification_queue_status ON notification_queue(status);
            CREATE INDEX idx_notification_queue_created_at ON notification_queue(created_at);
            CREATE INDEX idx_notification_queue_group_name ON notification_queue(group_name);
            CREATE INDEX idx_notification_queue_status_created ON notification_queue(status, created_at);
            CREATE INDEX idx_notification_queue_user_status ON notification_queue(user_id, status);
        """)
        
        await conn.execute(create_table_sql)
        print("Table 'notification_queue' created successfully with indexes.")
    
    await engine.dispose()


async def main():
    print("Running migration: create_notification_queue")
    try:
        await create_notification_queue_table()
        print("Migration completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
