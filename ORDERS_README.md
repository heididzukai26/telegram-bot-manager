# Orders Module Documentation

## Overview

The `orders.py` module provides a comprehensive order management system for the Telegram bot, including:

- **Order handling** with edge case validation
- **Photo collection** with race condition prevention
- **Worker reply validation** to avoid false matches
- **Photo delivery** with network delay handling
- **Detailed logging** for debugging

## Key Features

### 1. Edge Case Handling

The `handle_order` function validates orders and handles edge cases:

- ✅ Missing CP values
- ✅ Missing order types
- ✅ Duplicate order IDs
- ✅ Invalid order formats
- ✅ Fallback order type detection

**Example:**
```python
from orders import order_manager

# Handle an order
success, message, order = await order_manager.handle_order(
    order_id="ORD001",
    order_text="user@example.com\n100 unsafe\nOrder details",
    validate=True
)

if success:
    print(f"Order created: {order.order_id}")
else:
    print(f"Error: {message}")
```

### 2. Worker Reply Validation

The `is_valid_worker_reply` function validates replies to prevent false matches:

- ✅ Checks reply is to correct message
- ✅ Filters out old messages (>24 hours)
- ✅ Rejects empty or very short messages
- ✅ Filters common false positives (e.g., "ok", "yes", "hi")
- ✅ Prevents duplicate processing

**Example:**
```python
from orders import WorkerReply

reply = WorkerReply(
    user_id=12345,
    message_id=67890,
    reply_to_message_id=order.reply_message_id,
    text="Here are the photos",
    photos=["photo1.jpg", "photo2.jpg"]
)

if order_manager.is_valid_worker_reply(reply, order):
    print("Valid reply!")
```

### 3. Photo Collection with Race Condition Prevention

The `collect_worker_photos` function safely collects photos:

- ✅ Uses async locks to prevent race conditions
- ✅ Implements retry logic for network delays
- ✅ Automatically deduplicates photos
- ✅ Tracks message processing to prevent duplicates

**Example:**
```python
success, photos = await order_manager.collect_worker_photos(
    order_id="ORD001",
    reply=reply,
    timeout=30.0,
    retry_delay=2.0,
    max_retries=3
)

if success:
    print(f"Collected {len(photos)} photos")
```

### 4. Photo Delivery with Network Delay Handling

The `deliver_photos` function delivers photos with retry logic:

- ✅ Handles network timeouts
- ✅ Retries failed deliveries
- ✅ Exponential backoff for retries
- ✅ Reports partial success

**Example:**
```python
async def send_photo(chat_id, photo):
    # Your photo sending logic here
    await bot.send_photo(chat_id, photo)

success, message = await order_manager.deliver_photos(
    order_id="ORD001",
    destination_chat_id=12345,
    send_photo_func=send_photo,
    network_timeout=60.0,
    retry_on_failure=True,
    max_retries=3
)

print(message)
```

### 5. Complete Order Processing

The `process_worker_reply` function handles the complete workflow:

- ✅ Validates the reply
- ✅ Assigns worker to order
- ✅ Collects photos if present
- ✅ Stores reply history

**Example:**
```python
success, message = await order_manager.process_worker_reply(
    order_id="ORD001",
    reply=reply
)

if success:
    print("Reply processed successfully")
```

## Data Structures

### Order

```python
@dataclass
class Order:
    order_id: str
    text: str
    cp_amount: int
    order_type: Optional[str]
    created_at: datetime
    worker_id: Optional[int]
    photos: List[str]
    status: str  # pending, assigned, completed, failed
    reply_message_id: Optional[int]
```

### WorkerReply

```python
@dataclass
class WorkerReply:
    user_id: int
    message_id: int
    reply_to_message_id: Optional[int]
    text: str
    timestamp: datetime
    photos: List[str]
```

## Logging

The module uses detailed logging at multiple levels:

- **INFO**: Major operations (order creation, photo collection, delivery)
- **WARNING**: Validation failures, timeouts, partial failures
- **ERROR**: Critical errors with full stack traces
- **DEBUG**: Detailed operation flow (locks, retries, validation steps)

**Example log output:**
```
INFO     orders:orders.py:93 📝 Processing order ORD001
DEBUG    orders:orders.py:95 Order text preview: user@example.com...
INFO     orders:orders.py:133 ✅ Order ORD001 created successfully: 100 CP, type: unsafe
INFO     orders:orders.py:222 📸 Collecting photos for order ORD001 from user 12345
DEBUG    orders:orders.py:229 🔒 Lock acquired for order ORD001
INFO     orders:orders.py:246 ✅ Added 2 new photos to order ORD001 (total: 2)
```

## Testing

The module includes comprehensive tests covering all functionality:

- **27 test cases** covering:
  - Edge cases (missing CP, missing order type, duplicates)
  - Worker reply validation
  - Photo collection and race conditions
  - Photo delivery with network issues
  - Complete order processing

**Run tests:**
```bash
pytest test_orders.py -v
```

## Best Practices

1. **Always validate orders** unless you're certain the format is correct:
   ```python
   await order_manager.handle_order(order_id, text, validate=True)
   ```

2. **Use appropriate timeouts** for your network conditions:
   ```python
   await order_manager.deliver_photos(
       order_id,
       chat_id,
       send_func,
       network_timeout=60.0  # Adjust based on network
   )
   ```

3. **Check return values** to handle errors gracefully:
   ```python
   success, message, order = await order_manager.handle_order(...)
   if not success:
       # Handle error
       logger.error(f"Failed to create order: {message}")
   ```

4. **Monitor logs** for debugging issues:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)  # For detailed logs
   ```

## Error Handling

All functions return meaningful error messages and status codes:

```python
# Order creation
success, message, order = await handle_order(...)
# success: bool - True if successful
# message: str - Human-readable status message
# order: Order | None - Order object if successful

# Photo operations
success, photos = await collect_worker_photos(...)
# success: bool - True if photos collected
# photos: List[str] - List of collected photos

success, message = await deliver_photos(...)
# success: bool - True if all or some photos delivered
# message: str - Detailed delivery status
```

## Integration Example

Here's a complete example of integrating the orders module with a Telegram bot:

```python
from telegram import Update
from telegram.ext import ContextTypes
from orders import order_manager, WorkerReply

async def handle_new_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming order from admin."""
    order_id = f"ORD{update.message.message_id}"
    order_text = update.message.text
    
    success, message, order = await order_manager.handle_order(
        order_id,
        order_text,
        validate=True
    )
    
    await update.message.reply_text(message)
    
    if success:
        # Forward to workers group
        sent_message = await context.bot.send_message(
            chat_id=WORKERS_GROUP_ID,
            text=f"New Order {order_id}:\n{order_text}"
        )
        order.reply_message_id = sent_message.message_id

async def handle_worker_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle worker reply to order."""
    if not update.message.reply_to_message:
        return
    
    # Find order by reply message ID
    order_id = find_order_by_message_id(update.message.reply_to_message.message_id)
    if not order_id:
        return
    
    reply = WorkerReply(
        user_id=update.message.from_user.id,
        message_id=update.message.message_id,
        reply_to_message_id=update.message.reply_to_message.message_id,
        text=update.message.text or "",
        photos=[photo.file_id for photo in update.message.photo]
    )
    
    success, message = await order_manager.process_worker_reply(order_id, reply)
    
    if success:
        # Deliver photos to admin
        async def send_photo(chat_id, photo):
            await context.bot.send_photo(chat_id, photo)
        
        await order_manager.deliver_photos(
            order_id,
            ADMIN_CHAT_ID,
            send_photo
        )
```

## Performance Considerations

- **Async locks** prevent race conditions without blocking
- **Exponential backoff** reduces server load during retries
- **Photo deduplication** saves storage and bandwidth
- **Message processing tracking** prevents duplicate work

## Future Enhancements

Potential improvements for the module:

1. Persistent storage (database integration)
2. Order priority queue
3. Worker load balancing
4. Photo compression/optimization
5. Analytics and reporting
6. Order cancellation and refunds
7. Notification system for status updates
