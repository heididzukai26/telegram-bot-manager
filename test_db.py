"""
Unit tests for the database module.

Tests cover:
- Database initialization
- Migration system
- Backup functionality
- CRUD operations for users and orders
- Error handling and edge cases
"""

import pytest
import pytest_asyncio
import asyncio
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import db


class TestDatabaseInitialization:
    """Tests for database initialization."""
    
    @pytest_asyncio.fixture
    async def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        if Path(db_path).exists():
            Path(db_path).unlink()
    
    @pytest.mark.asyncio
    async def test_init_db_creates_database(self, temp_db):
        """Test that init_db creates a database file."""
        result = await db.init_db(temp_db)
        
        assert result is True
        assert Path(temp_db).exists()
    
    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, temp_db):
        """Test that init_db creates all required tables."""
        await db.init_db(temp_db)
        
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            # Check users table exists
            async with conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            ) as cursor:
                result = await cursor.fetchone()
                assert result is not None
            
            # Check orders table exists
            async with conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
            ) as cursor:
                result = await cursor.fetchone()
                assert result is not None
            
            # Check migrations table exists
            async with conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
            ) as cursor:
                result = await cursor.fetchone()
                assert result is not None
    
    @pytest.mark.asyncio
    async def test_init_db_creates_indexes(self, temp_db):
        """Test that init_db creates indexes."""
        await db.init_db(temp_db)
        
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            async with conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ) as cursor:
                indexes = await cursor.fetchall()
                index_names = [idx[0] for idx in indexes]
                
                assert 'idx_orders_user_id' in index_names
                assert 'idx_orders_status' in index_names
                assert 'idx_orders_created_at' in index_names
                assert 'idx_users_username' in index_names
    
    @pytest.mark.asyncio
    async def test_init_db_with_nonexistent_directory(self):
        """Test that init_db creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "subdir" / "test.db"
            
            result = await db.init_db(str(db_path))
            
            assert result is True
            assert db_path.exists()


class TestMigrationSystem:
    """Tests for database migration system."""
    
    @pytest_asyncio.fixture
    async def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            db_path = f.name
        
        await db.init_db(db_path)
        
        yield db_path
        
        # Cleanup
        if Path(db_path).exists():
            Path(db_path).unlink()
    
    @pytest.mark.asyncio
    async def test_get_current_version_new_db(self, temp_db):
        """Test getting version from a new database."""
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            version = await db.get_current_version(conn)
            assert version == 0
    
    @pytest.mark.asyncio
    async def test_apply_migrations_creates_records(self, temp_db):
        """Test that apply_migrations records applied migrations."""
        result = await db.apply_migrations(temp_db)
        
        assert result is True
        
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            async with conn.execute("SELECT version, name FROM migrations") as cursor:
                migrations = await cursor.fetchall()
                
                assert len(migrations) > 0
                assert migrations[0][0] == 1  # Version 1
                assert "initial_schema" in migrations[0][1]
    
    @pytest.mark.asyncio
    async def test_apply_migrations_idempotent(self, temp_db):
        """Test that applying migrations multiple times is safe."""
        # Apply migrations first time
        result1 = await db.apply_migrations(temp_db)
        assert result1 is True
        
        # Apply migrations second time
        result2 = await db.apply_migrations(temp_db)
        assert result2 is True
        
        # Check that migration was only recorded once
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            async with conn.execute("SELECT COUNT(*) FROM migrations WHERE version = 1") as cursor:
                count = await cursor.fetchone()
                assert count[0] == 1
    
    @pytest.mark.asyncio
    async def test_get_current_version_after_migration(self, temp_db):
        """Test getting version after applying migrations."""
        await db.apply_migrations(temp_db)
        
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            version = await db.get_current_version(conn)
            assert version >= 1


class TestBackupFunctionality:
    """Tests for database backup functionality."""
    
    @pytest_asyncio.fixture
    async def temp_db_with_backup_dir(self):
        """Create a temporary database and backup directory."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"
        backup_dir = Path(temp_dir) / "backups"
        
        # Initialize database
        await db.init_db(str(db_path))
        
        yield str(db_path), str(backup_dir)
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_backup_db_creates_backup(self, temp_db_with_backup_dir):
        """Test that backup_db creates a backup file."""
        db_path, backup_dir = temp_db_with_backup_dir
        
        backup_file = await db.backup_db(db_path, backup_dir)
        
        assert backup_file is not None
        assert Path(backup_file).exists()
        assert "backup_" in backup_file
    
    @pytest.mark.asyncio
    async def test_backup_db_creates_directory(self, temp_db_with_backup_dir):
        """Test that backup_db creates backup directory if it doesn't exist."""
        db_path, backup_dir = temp_db_with_backup_dir
        
        # Ensure backup dir doesn't exist
        if Path(backup_dir).exists():
            shutil.rmtree(backup_dir)
        
        backup_file = await db.backup_db(db_path, backup_dir)
        
        assert backup_file is not None
        assert Path(backup_dir).exists()
    
    @pytest.mark.asyncio
    async def test_backup_db_rotation(self, temp_db_with_backup_dir):
        """Test that old backups are rotated out."""
        db_path, backup_dir = temp_db_with_backup_dir
        
        # Create more backups than MAX_BACKUPS
        original_max = db.MAX_BACKUPS
        db.MAX_BACKUPS = 3  # Set low for testing
        
        backup_files = []
        for i in range(5):
            backup_file = await db.backup_db(db_path, backup_dir)
            backup_files.append(backup_file)
            await asyncio.sleep(0.01)  # Small delay to ensure different microsecond timestamps
        
        # Check that only MAX_BACKUPS files remain
        remaining_backups = list(Path(backup_dir).glob("*.db"))
        assert len(remaining_backups) == db.MAX_BACKUPS
        
        # Restore original MAX_BACKUPS
        db.MAX_BACKUPS = original_max
    
    @pytest.mark.asyncio
    async def test_backup_db_nonexistent_file(self):
        """Test that backup_db handles nonexistent database gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "nonexistent.db"
            backup_dir = Path(temp_dir) / "backups"
            
            backup_file = await db.backup_db(str(db_path), str(backup_dir))
            
            assert backup_file is None


class TestUserOperations:
    """Tests for user CRUD operations."""
    
    @pytest_asyncio.fixture
    async def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            db_path = f.name
        
        await db.init_db(db_path)
        
        yield db_path
        
        # Cleanup
        if Path(db_path).exists():
            Path(db_path).unlink()
    
    @pytest.mark.asyncio
    async def test_create_user(self, temp_db):
        """Test creating a new user."""
        result = await db.create_user(
            user_id=12345,
            username="testuser",
            first_name="Test",
            last_name="User",
            is_admin=False,
            db_path=temp_db
        )
        
        assert result is True
        
        # Verify user was created
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            async with conn.execute("SELECT * FROM users WHERE user_id = ?", (12345,)) as cursor:
                user = await cursor.fetchone()
                assert user is not None
                assert user[1] == "testuser"
    
    @pytest.mark.asyncio
    async def test_create_user_update_existing(self, temp_db):
        """Test updating an existing user."""
        # Create user
        await db.create_user(
            user_id=12345,
            username="oldname",
            first_name="Old",
            db_path=temp_db
        )
        
        # Update user
        await db.create_user(
            user_id=12345,
            username="newname",
            first_name="New",
            db_path=temp_db
        )
        
        # Verify user was updated
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            async with conn.execute("SELECT username, first_name FROM users WHERE user_id = ?", (12345,)) as cursor:
                user = await cursor.fetchone()
                assert user[0] == "newname"
                assert user[1] == "New"
    
    @pytest.mark.asyncio
    async def test_create_user_with_admin_flag(self, temp_db):
        """Test creating a user with admin flag."""
        await db.create_user(
            user_id=99999,
            username="admin",
            is_admin=True,
            db_path=temp_db
        )
        
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            async with conn.execute("SELECT is_admin FROM users WHERE user_id = ?", (99999,)) as cursor:
                user = await cursor.fetchone()
                assert user[0] == 1  # True is stored as 1


class TestOrderOperations:
    """Tests for order CRUD operations."""
    
    @pytest_asyncio.fixture
    async def temp_db(self):
        """Create a temporary database with a test user."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            db_path = f.name
        
        await db.init_db(db_path)
        await db.create_user(12345, "testuser", db_path=db_path)
        
        yield db_path
        
        # Cleanup
        if Path(db_path).exists():
            Path(db_path).unlink()
    
    @pytest.mark.asyncio
    async def test_create_order(self, temp_db):
        """Test creating a new order."""
        order_id = await db.create_order(
            user_id=12345,
            order_type="safe_fast",
            cp_amount=100,
            email="test@example.com",
            order_text="Test order text",
            db_path=temp_db
        )
        
        assert order_id is not None
        assert order_id > 0
    
    @pytest.mark.asyncio
    async def test_create_order_with_invalid_type(self, temp_db):
        """Test that creating an order with invalid type fails."""
        order_id = await db.create_order(
            user_id=12345,
            order_type="invalid_type",
            cp_amount=100,
            email="test@example.com",
            order_text="Test order",
            db_path=temp_db
        )
        
        # Should fail due to CHECK constraint
        assert order_id is None
    
    @pytest.mark.asyncio
    async def test_create_order_with_invalid_cp_amount(self, temp_db):
        """Test that creating an order with invalid CP amount fails."""
        order_id = await db.create_order(
            user_id=12345,
            order_type="safe_fast",
            cp_amount=0,  # Invalid: must be > 0
            email="test@example.com",
            order_text="Test order",
            db_path=temp_db
        )
        
        # Should fail due to CHECK constraint
        assert order_id is None
    
    @pytest.mark.asyncio
    async def test_get_order(self, temp_db):
        """Test retrieving an order by ID."""
        # Create order
        order_id = await db.create_order(
            user_id=12345,
            order_type="unsafe",
            cp_amount=200,
            email="test@example.com",
            order_text="Test order text",
            db_path=temp_db
        )
        
        # Retrieve order
        order = await db.get_order(order_id, temp_db)
        
        assert order is not None
        assert order['order_id'] == order_id
        assert order['user_id'] == 12345
        assert order['order_type'] == "unsafe"
        assert order['cp_amount'] == 200
        assert order['status'] == "pending"
    
    @pytest.mark.asyncio
    async def test_get_order_nonexistent(self, temp_db):
        """Test retrieving a nonexistent order."""
        order = await db.get_order(99999, temp_db)
        assert order is None
    
    @pytest.mark.asyncio
    async def test_update_order_status(self, temp_db):
        """Test updating order status."""
        # Create order
        order_id = await db.create_order(
            user_id=12345,
            order_type="fund",
            cp_amount=150,
            email="test@example.com",
            order_text="Test order",
            db_path=temp_db
        )
        
        # Update status
        result = await db.update_order_status(order_id, "processing", temp_db)
        assert result is True
        
        # Verify status changed
        order = await db.get_order(order_id, temp_db)
        assert order['status'] == "processing"
    
    @pytest.mark.asyncio
    async def test_update_order_status_to_completed(self, temp_db):
        """Test updating order status to completed sets timestamp."""
        # Create order
        order_id = await db.create_order(
            user_id=12345,
            order_type="safe_slow",
            cp_amount=100,
            email="test@example.com",
            order_text="Test order",
            db_path=temp_db
        )
        
        # Update to completed
        await db.update_order_status(order_id, "completed", temp_db)
        
        # Verify completed_at is set
        order = await db.get_order(order_id, temp_db)
        assert order['completed_at'] is not None
    
    @pytest.mark.asyncio
    async def test_update_order_status_invalid_status(self, temp_db):
        """Test updating order with invalid status."""
        # Create order
        order_id = await db.create_order(
            user_id=12345,
            order_type="safe_fast",
            cp_amount=100,
            email="test@example.com",
            order_text="Test order",
            db_path=temp_db
        )
        
        # Try invalid status
        result = await db.update_order_status(order_id, "invalid_status", temp_db)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_user_orders(self, temp_db):
        """Test getting all orders for a user."""
        # Create multiple orders
        await db.create_order(12345, "safe_fast", 100, "test1@example.com", "Order 1", temp_db)
        await db.create_order(12345, "unsafe", 200, "test2@example.com", "Order 2", temp_db)
        await db.create_order(12345, "fund", 300, "test3@example.com", "Order 3", temp_db)
        
        # Get all orders
        orders = await db.get_user_orders(12345, db_path=temp_db)
        
        assert len(orders) == 3
        assert all(order['user_id'] == 12345 for order in orders)
    
    @pytest.mark.asyncio
    async def test_get_user_orders_with_status_filter(self, temp_db):
        """Test getting user orders filtered by status."""
        # Create orders with different statuses
        order1_id = await db.create_order(12345, "safe_fast", 100, "test1@example.com", "Order 1", temp_db)
        order2_id = await db.create_order(12345, "unsafe", 200, "test2@example.com", "Order 2", temp_db)
        
        await db.update_order_status(order1_id, "completed", temp_db)
        
        # Get only pending orders
        pending_orders = await db.get_user_orders(12345, status="pending", db_path=temp_db)
        assert len(pending_orders) == 1
        assert pending_orders[0]['order_id'] == order2_id
        
        # Get only completed orders
        completed_orders = await db.get_user_orders(12345, status="completed", db_path=temp_db)
        assert len(completed_orders) == 1
        assert completed_orders[0]['order_id'] == order1_id
    
    @pytest.mark.asyncio
    async def test_get_all_orders(self, temp_db):
        """Test getting all orders."""
        # Create user and orders
        await db.create_user(67890, "user2", db_path=temp_db)
        await db.create_order(12345, "safe_fast", 100, "test1@example.com", "Order 1", temp_db)
        await db.create_order(67890, "unsafe", 200, "test2@example.com", "Order 2", temp_db)
        
        # Get all orders
        orders = await db.get_all_orders(db_path=temp_db)
        
        assert len(orders) >= 2
    
    @pytest.mark.asyncio
    async def test_get_all_orders_with_status_filter(self, temp_db):
        """Test getting all orders filtered by status."""
        # Create orders
        order1_id = await db.create_order(12345, "safe_fast", 100, "test1@example.com", "Order 1", temp_db)
        order2_id = await db.create_order(12345, "unsafe", 200, "test2@example.com", "Order 2", temp_db)
        
        await db.update_order_status(order1_id, "cancelled", temp_db)
        
        # Get only pending orders
        pending_orders = await db.get_all_orders(status="pending", db_path=temp_db)
        assert all(order['status'] == "pending" for order in pending_orders)
        
        # Get only cancelled orders
        cancelled_orders = await db.get_all_orders(status="cancelled", db_path=temp_db)
        assert len(cancelled_orders) >= 1
        assert cancelled_orders[0]['order_id'] == order1_id
    
    @pytest.mark.asyncio
    async def test_get_all_orders_with_limit(self, temp_db):
        """Test getting all orders with a limit."""
        # Create multiple orders
        for i in range(5):
            await db.create_order(12345, "safe_fast", 100, f"test{i}@example.com", f"Order {i}", temp_db)
        
        # Get orders with limit
        orders = await db.get_all_orders(limit=3, db_path=temp_db)
        
        assert len(orders) == 3


class TestErrorHandling:
    """Tests for error handling in database operations."""
    
    @pytest.mark.asyncio
    async def test_init_db_with_invalid_path(self):
        """Test init_db with an invalid path."""
        # Try to initialize database in a path that cannot be created
        invalid_path = "/root/forbidden/path/test.db"
        
        with pytest.raises((PermissionError, OSError)):
            await db.init_db(invalid_path)
    
    @pytest.mark.asyncio
    async def test_create_order_without_user(self):
        """Test creating an order for a nonexistent user (should fail due to foreign key)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            await db.init_db(db_path)
            
            # Try to create order for nonexistent user
            order_id = await db.create_order(
                user_id=99999,  # User doesn't exist
                order_type="safe_fast",
                cp_amount=100,
                email="test@example.com",
                order_text="Test order",
                db_path=db_path
            )
            
            # Should fail due to foreign key constraint
            assert order_id is None
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()
    
    @pytest.mark.asyncio
    async def test_operations_on_nonexistent_database(self):
        """Test that operations on nonexistent database handle errors gracefully."""
        # Use a temporary path that doesn't exist (cross-platform)
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_db = str(Path(temp_dir) / "nonexistent_subdir" / "nonexistent_db.db")
            
            # These should not crash, but return None/False/empty list
            user_result = await db.create_user(12345, "test", db_path=nonexistent_db)
            assert user_result is False
            
            order = await db.get_order(1, nonexistent_db)
            assert order is None
            
            orders = await db.get_user_orders(12345, db_path=nonexistent_db)
            assert orders == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
