# Database Module Documentation

## Overview

The `db.py` module provides comprehensive database handling for the Telegram bot manager, including:

- Schema management with optimized indexes
- Version-based migration system
- Automatic backup with rotation
- Full CRUD operations for users and orders
- Async operations with proper error handling

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
import asyncio
import db

async def main():
    # Initialize database
    await db.init_db()
    
    # Apply any pending migrations
    await db.apply_migrations()
    
    # Create a backup
    backup_file = await db.backup_db()
    print(f"Backup created: {backup_file}")
    
    # Create a user
    await db.create_user(
        user_id=12345,
        username="johndoe",
        first_name="John",
        last_name="Doe",
        is_admin=False
    )
    
    # Create an order
    order_id = await db.create_order(
        user_id=12345,
        order_type="safe_fast",
        cp_amount=100,
        email="john@example.com",
        order_text="Full order details here..."
    )
    
    # Retrieve order
    order = await db.get_order(order_id)
    print(f"Order: {order}")
    
    # Update order status
    await db.update_order_status(order_id, "completed")
    
    # Get all user orders
    orders = await db.get_user_orders(12345)
    for order in orders:
        print(f"Order {order['order_id']}: {order['status']}")

asyncio.run(main())
```

## Configuration

The module uses environment variables for configuration:

- `DB_PATH`: Path to the SQLite database file (default: `telegram_bot.db`)
- `BACKUP_DIR`: Directory for storing backups (default: `backups`)
- `MAX_BACKUPS`: Maximum number of backups to keep (default: `10`)

Example:

```bash
export DB_PATH="/var/lib/telegram-bot/bot.db"
export BACKUP_DIR="/var/backups/telegram-bot"
export MAX_BACKUPS="20"
```

## Database Schema

### Users Table

| Column | Type | Constraints |
|--------|------|-------------|
| user_id | INTEGER | PRIMARY KEY, NOT NULL |
| username | TEXT | |
| first_name | TEXT | |
| last_name | TEXT | |
| is_admin | INTEGER | NOT NULL, DEFAULT 0 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP |

### Orders Table

| Column | Type | Constraints |
|--------|------|-------------|
| order_id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| user_id | INTEGER | NOT NULL, FOREIGN KEY |
| order_type | TEXT | NOT NULL, CHECK (unsafe, fund, safe_slow, safe_fast) |
| cp_amount | INTEGER | NOT NULL, CHECK (> 0) |
| email | TEXT | NOT NULL |
| order_text | TEXT | NOT NULL |
| status | TEXT | NOT NULL, DEFAULT 'pending', CHECK (pending, processing, completed, cancelled) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP |
| completed_at | TIMESTAMP | |

### Migrations Table

| Column | Type | Constraints |
|--------|------|-------------|
| migration_id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| version | INTEGER | NOT NULL, UNIQUE |
| name | TEXT | NOT NULL |
| applied_at | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP |

## API Reference

### Database Initialization

#### `init_db(db_path: Optional[str] = None) -> bool`

Initialize the database with schema and indexes.

**Parameters:**
- `db_path`: Path to the database file (optional, defaults to `DB_PATH` env var)

**Returns:** `True` if initialization successful, `False` otherwise

**Example:**
```python
success = await db.init_db("/path/to/database.db")
```

### Migration System

#### `apply_migrations(db_path: Optional[str] = None) -> bool`

Apply all pending database migrations.

**Parameters:**
- `db_path`: Path to the database file (optional)

**Returns:** `True` if all migrations applied successfully

**Example:**
```python
success = await db.apply_migrations()
```

### Backup Functionality

#### `backup_db(db_path: Optional[str] = None, backup_dir: Optional[str] = None) -> Optional[str]`

Create a timestamped backup of the database.

**Parameters:**
- `db_path`: Path to the database file (optional)
- `backup_dir`: Directory to store backups (optional)

**Returns:** Path to the backup file if successful, `None` otherwise

**Example:**
```python
backup_file = await db.backup_db()
if backup_file:
    print(f"Backup saved to: {backup_file}")
```

### User Operations

#### `create_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None, last_name: Optional[str] = None, is_admin: bool = False, db_path: Optional[str] = None) -> bool`

Create or update a user in the database.

**Parameters:**
- `user_id`: Telegram user ID (required)
- `username`: Telegram username
- `first_name`: User's first name
- `last_name`: User's last name
- `is_admin`: Whether user is an admin
- `db_path`: Path to the database file

**Returns:** `True` if user created/updated successfully

**Example:**
```python
await db.create_user(
    user_id=12345,
    username="alice",
    first_name="Alice",
    is_admin=True
)
```

### Order Operations

#### `create_order(user_id: int, order_type: str, cp_amount: int, email: str, order_text: str, db_path: Optional[str] = None) -> Optional[int]`

Create a new order in the database.

**Parameters:**
- `user_id`: Telegram user ID
- `order_type`: Type of order (`unsafe`, `fund`, `safe_slow`, `safe_fast`)
- `cp_amount`: CP amount (must be > 0)
- `email`: Email address
- `order_text`: Full order text
- `db_path`: Path to the database file

**Returns:** Order ID if created successfully, `None` otherwise

**Example:**
```python
order_id = await db.create_order(
    user_id=12345,
    order_type="safe_fast",
    cp_amount=150,
    email="user@example.com",
    order_text="Full order details..."
)
```

#### `get_order(order_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]`

Retrieve an order by ID.

**Returns:** Order data as dictionary if found, `None` otherwise

#### `update_order_status(order_id: int, status: str, db_path: Optional[str] = None) -> bool`

Update the status of an order.

**Parameters:**
- `order_id`: Order ID
- `status`: New status (`pending`, `processing`, `completed`, `cancelled`)

**Returns:** `True` if updated successfully

#### `get_user_orders(user_id: int, status: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]`

Get all orders for a specific user.

**Parameters:**
- `user_id`: User ID
- `status`: Optional status filter

**Returns:** List of order dictionaries

#### `get_all_orders(status: Optional[str] = None, limit: int = 100, db_path: Optional[str] = None) -> List[Dict[str, Any]]`

Get all orders with optional status filter.

**Parameters:**
- `status`: Optional status filter
- `limit`: Maximum number of orders to return

**Returns:** List of order dictionaries

## Error Handling

All database operations include comprehensive error handling and logging:

- **Database errors**: Logged with full context and return appropriate default values
- **Foreign key violations**: Handled gracefully with meaningful error messages
- **Check constraint violations**: Validated before database operations when possible
- **File system errors**: Caught and logged during initialization and backup operations

Example error handling:

```python
order_id = await db.create_order(
    user_id=99999,  # User doesn't exist
    order_type="safe_fast",
    cp_amount=100,
    email="test@example.com",
    order_text="Test"
)

if order_id is None:
    print("Failed to create order - check logs for details")
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest test_db.py -v

# Run specific test class
pytest test_db.py::TestOrderOperations -v

# Run with coverage
pytest test_db.py --cov=db --cov-report=html
```

The test suite includes:
- Database initialization tests
- Migration system tests
- Backup functionality tests
- CRUD operation tests
- Error handling tests

## Migration System

The module includes a version-based migration system for schema updates:

1. Migrations are defined in the `MIGRATIONS` dictionary in `db.py`
2. Each migration has a version number and SQL statements
3. Applied migrations are tracked in the `migrations` table
4. Migrations are applied automatically in version order
5. Failed migrations trigger a rollback

### Adding a New Migration

To add a new migration:

```python
# In db.py, add to MIGRATIONS dictionary:
MIGRATIONS = {
    1: {
        "name": "initial_schema",
        "sql": SCHEMA_SQL
    },
    2: {
        "name": "add_payment_info",
        "sql": "ALTER TABLE orders ADD COLUMN payment_info TEXT;"
    }
}
```

Then run:

```python
await db.apply_migrations()
```

## Best Practices

1. **Always initialize the database before use:**
   ```python
   await db.init_db()
   ```

2. **Apply migrations after initialization:**
   ```python
   await db.apply_migrations()
   ```

3. **Create regular backups:**
   ```python
   # In your scheduled task
   await db.backup_db()
   ```

4. **Check return values:**
   ```python
   success = await db.create_user(...)
   if not success:
       # Handle error
       pass
   ```

5. **Use try-except for critical operations:**
   ```python
   try:
       order_id = await db.create_order(...)
       if order_id:
           await process_order(order_id)
   except Exception as e:
       logger.error(f"Failed to process order: {e}")
   ```

## Performance Considerations

- **Indexes**: The schema includes indexes on frequently queried fields
- **Foreign Keys**: Enabled for referential integrity
- **Connection Pooling**: Use connection pooling for high-throughput scenarios
- **Batch Operations**: For bulk inserts, consider using transactions

## Security

- **SQL Injection**: All queries use parameterized statements
- **Input Validation**: CHECK constraints enforce data integrity
- **Error Handling**: Sensitive information is not exposed in error messages
- **Permissions**: Database files should have appropriate file permissions

## License

See project LICENSE file.
