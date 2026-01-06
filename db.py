"""
Database module for Telegram bot manager.

Handles:
- Database initialization and schema management
- Migration system for schema updates
- Backup and restore functionality
- Order and user data management
- Async database operations with proper error handling
"""

import os
import asyncio
import logging
import aiosqlite
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

DB_PATH = os.getenv("DB_PATH", "telegram_bot.db")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "10"))

# Database schema version
SCHEMA_VERSION = 1

# ==================== SCHEMA DEFINITIONS ====================

SCHEMA_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    order_type TEXT NOT NULL CHECK(order_type IN ('unsafe', 'fund', 'safe_slow', 'safe_fast')),
    cp_amount INTEGER NOT NULL CHECK(cp_amount > 0),
    email TEXT NOT NULL,
    order_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'cancelled')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Migrations table to track applied migrations
CREATE TABLE IF NOT EXISTS migrations (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
"""

# ==================== MIGRATION DEFINITIONS ====================

# Format: {version: {"name": "migration_name", "sql": "SQL statements"}}
MIGRATIONS = {
    1: {
        "name": "initial_schema",
        "sql": SCHEMA_SQL
    },
    # Future migrations can be added here with incremented version numbers
    # 2: {
    #     "name": "add_payment_info",
    #     "sql": "ALTER TABLE orders ADD COLUMN payment_info TEXT;"
    # }
}

# ==================== DATABASE INITIALIZATION ====================

async def init_db(db_path: Optional[str] = None) -> bool:
    """
    Initialize the database with schema and indexes.
    
    Args:
        db_path: Path to the database file. If None, uses DB_PATH from env.
    
    Returns:
        True if initialization successful, False otherwise.
    
    Raises:
        Exception: If database initialization fails critically.
    """
    if db_path is None:
        db_path = DB_PATH
    
    logger.info(f"🔧 Initializing database at: {db_path}")
    
    try:
        # Ensure parent directory exists
        db_dir = Path(db_path).parent
        if db_dir and not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Created database directory: {db_dir}")
        
        # Connect to database
        async with aiosqlite.connect(db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Apply initial schema
            logger.info("📋 Creating database schema...")
            await db.executescript(SCHEMA_SQL)
            await db.commit()
            
            logger.info("✅ Database initialized successfully")
            return True
            
    except aiosqlite.Error as e:
        logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error during database initialization: {e}", exc_info=True)
        raise

# ==================== MIGRATION SYSTEM ====================

async def get_current_version(db: aiosqlite.Connection) -> int:
    """
    Get the current schema version from the database.
    
    Args:
        db: Database connection.
    
    Returns:
        Current schema version, or 0 if no migrations applied yet.
    """
    try:
        async with db.execute(
            "SELECT MAX(version) FROM migrations"
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result and result[0] is not None else 0
    except aiosqlite.OperationalError:
        # Migrations table doesn't exist yet
        return 0

async def apply_migrations(db_path: Optional[str] = None) -> bool:
    """
    Apply pending database migrations.
    
    This function:
    1. Checks current schema version
    2. Applies all migrations newer than current version
    3. Records each migration in migrations table
    4. Rolls back on failure
    
    Args:
        db_path: Path to the database file. If None, uses DB_PATH from env.
    
    Returns:
        True if all migrations applied successfully, False otherwise.
    """
    if db_path is None:
        db_path = DB_PATH
    
    logger.info("🔄 Checking for pending migrations...")
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Get current version
            current_version = await get_current_version(db)
            logger.info(f"📊 Current schema version: {current_version}")
            
            # Find pending migrations
            pending_migrations = [
                (version, migration) 
                for version, migration in sorted(MIGRATIONS.items())
                if version > current_version
            ]
            
            if not pending_migrations:
                logger.info("✅ No pending migrations")
                return True
            
            logger.info(f"📦 Found {len(pending_migrations)} pending migration(s)")
            
            # Apply each pending migration
            for version, migration in pending_migrations:
                logger.info(f"⚙️  Applying migration {version}: {migration['name']}")
                
                try:
                    # Execute migration SQL
                    await db.executescript(migration['sql'])
                    
                    # Record migration
                    await db.execute(
                        "INSERT INTO migrations (version, name) VALUES (?, ?)",
                        (version, migration['name'])
                    )
                    
                    await db.commit()
                    logger.info(f"✅ Migration {version} applied successfully")
                    
                except Exception as e:
                    logger.error(f"❌ Migration {version} failed: {e}", exc_info=True)
                    await db.rollback()
                    raise
            
            logger.info("✅ All migrations applied successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration process failed: {e}", exc_info=True)
        return False

# ==================== BACKUP FUNCTIONALITY ====================

async def backup_db(db_path: Optional[str] = None, backup_dir: Optional[str] = None) -> Optional[str]:
    """
    Create a backup of the database with timestamp and rotation.
    
    Features:
    - Creates timestamped backup files
    - Maintains only MAX_BACKUPS most recent backups
    - Logs backup operations
    
    Args:
        db_path: Path to the database file to backup. If None, uses DB_PATH from env.
        backup_dir: Directory to store backups. If None, uses BACKUP_DIR from env.
    
    Returns:
        Path to the backup file if successful, None otherwise.
    """
    if db_path is None:
        db_path = DB_PATH
    
    if backup_dir is None:
        backup_dir = BACKUP_DIR
    
    logger.info(f"💾 Starting database backup...")
    
    try:
        # Check if database exists
        if not Path(db_path).exists():
            logger.error(f"❌ Database file not found: {db_path}")
            return None
        
        # Create backup directory if it doesn't exist
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Backup directory: {backup_path}")
        
        # Generate backup filename with timestamp (including microseconds for uniqueness)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        db_name = Path(db_path).stem
        backup_file = backup_path / f"{db_name}_backup_{timestamp}.db"
        
        # Copy database file
        shutil.copy2(db_path, backup_file)
        
        # Verify backup file was created
        if not backup_file.exists():
            logger.error(f"❌ Backup file was not created: {backup_file}")
            return None
        
        backup_size = backup_file.stat().st_size
        logger.info(f"✅ Backup created: {backup_file} ({backup_size} bytes)")
        
        # Rotate old backups (keep only MAX_BACKUPS most recent)
        await _rotate_backups(backup_path, db_name)
        
        return str(backup_file)
        
    except PermissionError as e:
        logger.error(f"❌ Permission denied during backup: {e}", exc_info=True)
        return None
    except OSError as e:
        logger.error(f"❌ OS error during backup: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error during backup: {e}", exc_info=True)
        return None

async def _rotate_backups(backup_dir: Path, db_name: str) -> None:
    """
    Remove old backups, keeping only MAX_BACKUPS most recent files.
    
    Args:
        backup_dir: Directory containing backup files.
        db_name: Base name of the database (used to identify backup files).
    """
    try:
        # Find all backup files for this database
        backup_pattern = f"{db_name}_backup_*.db"
        backup_files = sorted(
            backup_dir.glob(backup_pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Remove old backups beyond MAX_BACKUPS
        if len(backup_files) > MAX_BACKUPS:
            files_to_remove = backup_files[MAX_BACKUPS:]
            logger.info(f"🗑️  Removing {len(files_to_remove)} old backup(s)")
            
            for old_backup in files_to_remove:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")
                
            logger.info(f"✅ Backup rotation complete (kept {MAX_BACKUPS} most recent)")
        else:
            logger.debug(f"No backup rotation needed ({len(backup_files)}/{MAX_BACKUPS})")
            
    except Exception as e:
        logger.error(f"⚠️  Error during backup rotation: {e}", exc_info=True)
        # Don't raise - rotation failure shouldn't prevent backup

# ==================== DATABASE OPERATIONS ====================

async def create_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    is_admin: bool = False,
    db_path: Optional[str] = None
) -> bool:
    """
    Create or update a user in the database.
    
    Args:
        user_id: Telegram user ID.
        username: Telegram username.
        first_name: User's first name.
        last_name: User's last name.
        is_admin: Whether user is an admin.
        db_path: Path to the database file. If None, uses DB_PATH from env.
    
    Returns:
        True if user created/updated successfully, False otherwise.
    """
    if db_path is None:
        db_path = DB_PATH
    
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            
            await db.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name, is_admin, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    is_admin = excluded.is_admin,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, username, first_name, last_name, int(is_admin))
            )
            
            await db.commit()
            logger.debug(f"✅ User {user_id} created/updated successfully")
            return True
            
    except aiosqlite.Error as e:
        logger.error(f"❌ Failed to create/update user {user_id}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error creating/updating user {user_id}: {e}", exc_info=True)
        return False

async def create_order(
    user_id: int,
    order_type: str,
    cp_amount: int,
    email: str,
    order_text: str,
    db_path: Optional[str] = None
) -> Optional[int]:
    """
    Create a new order in the database.
    
    Args:
        user_id: Telegram user ID who placed the order.
        order_type: Type of order (unsafe, fund, safe_slow, safe_fast).
        cp_amount: CP amount for the order.
        email: Email address for the order.
        order_text: Full order text.
        db_path: Path to the database file. If None, uses DB_PATH from env.
    
    Returns:
        Order ID if created successfully, None otherwise.
    """
    if db_path is None:
        db_path = DB_PATH
    
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            
            cursor = await db.execute(
                """
                INSERT INTO orders (user_id, order_type, cp_amount, email, order_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, order_type, cp_amount, email, order_text)
            )
            
            await db.commit()
            order_id = cursor.lastrowid
            logger.info(f"✅ Order {order_id} created successfully for user {user_id}")
            return order_id
            
    except aiosqlite.IntegrityError as e:
        logger.error(f"❌ Integrity error creating order: {e}", exc_info=True)
        return None
    except aiosqlite.Error as e:
        logger.error(f"❌ Database error creating order: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error creating order: {e}", exc_info=True)
        return None

async def get_order(order_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve an order by ID.
    
    Args:
        order_id: Order ID to retrieve.
        db_path: Path to the database file. If None, uses DB_PATH from env.
    
    Returns:
        Order data as dictionary if found, None otherwise.
    """
    if db_path is None:
        db_path = DB_PATH
    
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON")
            
            async with db.execute(
                "SELECT * FROM orders WHERE order_id = ?",
                (order_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    return dict(row)
                else:
                    logger.debug(f"Order {order_id} not found")
                    return None
                    
    except aiosqlite.Error as e:
        logger.error(f"❌ Database error retrieving order {order_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error retrieving order {order_id}: {e}", exc_info=True)
        return None

async def update_order_status(
    order_id: int,
    status: str,
    db_path: Optional[str] = None
) -> bool:
    """
    Update the status of an order.
    
    Args:
        order_id: Order ID to update.
        status: New status (pending, processing, completed, cancelled).
        db_path: Path to the database file. If None, uses DB_PATH from env.
    
    Returns:
        True if updated successfully, False otherwise.
    """
    if db_path is None:
        db_path = DB_PATH
    
    if status not in ('pending', 'processing', 'completed', 'cancelled'):
        logger.error(f"❌ Invalid status: {status}")
        return False
    
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            
            # If status is completed, set completed_at timestamp
            if status == 'completed':
                await db.execute(
                    """
                    UPDATE orders 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?
                    """,
                    (status, order_id)
                )
            else:
                await db.execute(
                    """
                    UPDATE orders 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?
                    """,
                    (status, order_id)
                )
            
            await db.commit()
            
            if db.total_changes > 0:
                logger.info(f"✅ Order {order_id} status updated to: {status}")
                return True
            else:
                logger.warning(f"⚠️  Order {order_id} not found or status unchanged")
                return False
                
    except aiosqlite.Error as e:
        logger.error(f"❌ Database error updating order {order_id}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error updating order {order_id}: {e}", exc_info=True)
        return False

async def get_user_orders(
    user_id: int,
    status: Optional[str] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all orders for a specific user.
    
    Args:
        user_id: User ID to get orders for.
        status: Optional status filter (pending, processing, completed, cancelled).
        db_path: Path to the database file. If None, uses DB_PATH from env.
    
    Returns:
        List of order dictionaries, empty list if none found or on error.
    """
    if db_path is None:
        db_path = DB_PATH
    
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON")
            
            if status:
                query = "SELECT * FROM orders WHERE user_id = ? AND status = ? ORDER BY created_at DESC"
                params = (user_id, status)
            else:
                query = "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC"
                params = (user_id,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
    except aiosqlite.Error as e:
        logger.error(f"❌ Database error getting orders for user {user_id}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"❌ Unexpected error getting orders for user {user_id}: {e}", exc_info=True)
        return []

async def get_all_orders(
    status: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all orders with optional status filter.
    
    Args:
        status: Optional status filter (pending, processing, completed, cancelled).
        limit: Maximum number of orders to return.
        db_path: Path to the database file. If None, uses DB_PATH from env.
    
    Returns:
        List of order dictionaries, empty list if none found or on error.
    """
    if db_path is None:
        db_path = DB_PATH
    
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON")
            
            if status:
                query = "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?"
                params = (status, limit)
            else:
                query = "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?"
                params = (limit,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
    except aiosqlite.Error as e:
        logger.error(f"❌ Database error getting all orders: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"❌ Unexpected error getting all orders: {e}", exc_info=True)
        return []
