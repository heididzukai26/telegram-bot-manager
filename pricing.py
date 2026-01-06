"""
Price list management module for Telegram bot.

Includes:
- Price list parsing with robust edge case handling
- Confirmation workflows for price updates
- Strict validation for database operations
- User-friendly message formatting
- Comprehensive logging for debugging
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, InvalidOperation
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


# ==================== CONSTANTS ====================

# Price list format patterns
PRICE_LINE_PATTERNS = [
    # Format: "Item: $10.50" or "Item: 10.50" (also handles negative: -10.50)
    r'^(.+?):\s*\$?(-?\d+(?:\.\d{1,2})?)\s*$',
    # Format: "Item - $10.50" or "Item - 10.50" (note: dash is separator, not negative sign)
    r'^(.+?)\s+-\s+\$?(\d+(?:\.\d{1,2})?)\s*$',
    # Format: "Item | $10.50" or "Item | 10.50"
    r'^(.+?)\s*\|\s*\$?(-?\d+(?:\.\d{1,2})?)\s*$',
    # Format: "Item $10.50" or "Item 10.50" (with explicit price at end)
    r'^(.+?)\s+\$?(-?\d+(?:\.\d{1,2})?)\s*$',
]

# Maximum price value for validation
MAX_PRICE_VALUE = Decimal('999999.99')
MIN_PRICE_VALUE = Decimal('0.00')

# Confirmation timeout in seconds
CONFIRMATION_TIMEOUT = 300  # 5 minutes


# ==================== PRICE LIST PARSING ====================

def parse_price_list(price_text: str) -> Tuple[Dict[str, Decimal], List[str]]:
    """
    Parse price list text with robust edge case handling.
    
    Handles various formats:
    - Item: $10.50
    - Item - $10.50
    - Item | $10.50
    - Item $10.50
    
    Edge cases handled:
    - Empty or whitespace-only input
    - Malformed lines (logged and skipped)
    - Invalid price values (negative, too large, non-numeric)
    - Duplicate items (last value wins, with warning)
    - Mixed formatting in the same list
    
    Args:
        price_text: Multi-line string containing price list
        
    Returns:
        Tuple of (price_dict, error_messages):
            - price_dict: Dict mapping item names to Decimal prices
            - error_messages: List of error messages for skipped/invalid lines
            
    Examples:
        >>> prices, errors = parse_price_list("Apple: $1.50\\nBanana: $0.75")
        >>> prices['Apple']
        Decimal('1.50')
        >>> len(errors)
        0
    """
    logger.info("Starting price list parsing")
    
    if not price_text or not isinstance(price_text, str):
        logger.warning("Empty or invalid price text provided")
        return {}, ["❌ Price list is empty or invalid"]
    
    price_text = price_text.strip()
    if not price_text:
        logger.warning("Price text contains only whitespace")
        return {}, ["❌ Price list contains only whitespace"]
    
    lines = price_text.split('\n')
    logger.info(f"Processing {len(lines)} lines from price list")
    
    prices: Dict[str, Decimal] = {}
    errors: List[str] = []
    line_number = 0
    
    for line in lines:
        line_number += 1
        line = line.strip()
        
        # Skip empty lines
        if not line:
            logger.debug(f"Skipping empty line {line_number}")
            continue
        
        # Skip comment lines (starting with # or //)
        if line.startswith('#') or line.startswith('//'):
            logger.debug(f"Skipping comment line {line_number}: {line}")
            continue
        
        # Try to parse the line with different patterns
        parsed = False
        for pattern in PRICE_LINE_PATTERNS:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(2).strip()
                
                # Validate item name
                if not item_name:
                    error_msg = f"Line {line_number}: Empty item name in '{line}'"
                    logger.warning(error_msg)
                    errors.append(f"❌ {error_msg}")
                    parsed = True
                    break
                
                # Validate and convert price
                try:
                    price = Decimal(price_str)
                    
                    # Check price bounds
                    if price < MIN_PRICE_VALUE:
                        error_msg = f"Line {line_number}: Negative price for '{item_name}': {price}"
                        logger.warning(error_msg)
                        errors.append(f"❌ {error_msg}")
                        parsed = True
                        break
                    
                    if price > MAX_PRICE_VALUE:
                        error_msg = f"Line {line_number}: Price too large for '{item_name}': {price}"
                        logger.warning(error_msg)
                        errors.append(f"❌ {error_msg}")
                        parsed = True
                        break
                    
                    # Check for duplicates
                    if item_name in prices:
                        old_price = prices[item_name]
                        logger.warning(f"Duplicate item '{item_name}' on line {line_number}. "
                                     f"Replacing ${old_price} with ${price}")
                        errors.append(f"⚠️ Line {line_number}: Duplicate item '{item_name}' "
                                    f"(${old_price} → ${price})")
                    
                    # Store the price
                    prices[item_name] = price
                    logger.debug(f"Parsed: '{item_name}' = ${price}")
                    parsed = True
                    break
                    
                except (InvalidOperation, ValueError) as e:
                    error_msg = f"Line {line_number}: Invalid price format '{price_str}' for '{item_name}'"
                    logger.error(f"{error_msg}: {e}")
                    errors.append(f"❌ {error_msg}")
                    parsed = True
                    break
        
        if not parsed:
            error_msg = f"Line {line_number}: Could not parse format: '{line}'"
            logger.warning(error_msg)
            errors.append(f"❌ {error_msg}")
    
    logger.info(f"Parsing complete: {len(prices)} items parsed, {len(errors)} errors")
    
    if not prices and errors:
        errors.append("\n❌ No valid price entries found. Please check the format.")
    
    return prices, errors


# ==================== CONFIRMATION WORKFLOWS ====================

def generate_confirmation_prompt(prices: Dict[str, Decimal], 
                                operation: str = "update") -> str:
    """
    Generate a user-friendly confirmation prompt for price updates.
    
    Args:
        prices: Dictionary of item names to prices
        operation: Type of operation ("update", "add", "delete")
        
    Returns:
        Formatted confirmation message
        
    Example:
        >>> prices = {"Apple": Decimal("1.50"), "Banana": Decimal("0.75")}
        >>> prompt = generate_confirmation_prompt(prices, "update")
        >>> "Apple" in prompt
        True
    """
    logger.info(f"Generating confirmation prompt for {operation} operation with {len(prices)} items")
    
    if not prices:
        logger.warning("Empty price dictionary provided for confirmation")
        return "⚠️ No items to confirm."
    
    # Build the header
    header = f"📋 **Confirm Price {operation.title()}**\n"
    header += "═" * 40 + "\n\n"
    
    # Build the item list
    items_text = ""
    total = Decimal('0.00')
    
    sorted_items = sorted(prices.items())
    for item_name, price in sorted_items:
        items_text += f"• **{item_name}**: ${price:.2f}\n"
        total += price
    
    # Build the footer
    footer = "\n" + "─" * 40 + "\n"
    footer += f"**Total value**: ${total:.2f}\n"
    footer += f"**Item count**: {len(prices)}\n\n"
    footer += "⚠️ **Important**: This operation will modify the database.\n"
    footer += "Please verify all prices carefully before confirming.\n\n"
    footer += "Reply with:\n"
    footer += "• ✅ **CONFIRM** - to proceed with the update\n"
    footer += "• ❌ **CANCEL** - to cancel the operation\n"
    footer += f"\n⏱️ This confirmation will expire in {CONFIRMATION_TIMEOUT // 60} minutes."
    
    confirmation_msg = header + items_text + footer
    
    logger.debug(f"Generated confirmation prompt: {len(confirmation_msg)} characters")
    return confirmation_msg


def validate_price_update_confirmation(user_response: str, 
                                      expected_operation: str = "update") -> Tuple[bool, str]:
    """
    Validate user's confirmation response to reduce errors.
    
    Args:
        user_response: User's response text
        expected_operation: Expected operation type for validation
        
    Returns:
        Tuple of (is_confirmed, message):
            - is_confirmed: True if user confirmed, False if cancelled or invalid
            - message: Response message to display to user
            
    Examples:
        >>> validate_price_update_confirmation("CONFIRM", "update")
        (True, '✅ Price update confirmed...')
        >>> validate_price_update_confirmation("CANCEL", "update")
        (False, '❌ Price update cancelled...')
    """
    logger.info(f"Validating confirmation response for {expected_operation}")
    
    if not user_response or not isinstance(user_response, str):
        logger.warning("Empty or invalid confirmation response")
        return False, "❌ Invalid response. Operation cancelled."
    
    response = user_response.strip().upper()
    
    # Check for confirmation
    if response in ["CONFIRM", "YES", "Y", "✅", "CONFIRMED"]:
        logger.info(f"User confirmed {expected_operation} operation")
        return True, f"✅ Price {expected_operation} confirmed. Processing..."
    
    # Check for cancellation
    if response in ["CANCEL", "NO", "N", "❌", "CANCELLED"]:
        logger.info(f"User cancelled {expected_operation} operation")
        return False, f"❌ Price {expected_operation} cancelled by user."
    
    # Invalid response
    logger.warning(f"Invalid confirmation response: {response}")
    return False, (
        "❌ Invalid response. Please reply with 'CONFIRM' or 'CANCEL'.\n"
        "Operation cancelled for safety."
    )


def check_confirmation_timeout(request_time: datetime, 
                              current_time: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Check if a confirmation request has timed out.
    
    Args:
        request_time: When the confirmation was requested
        current_time: Current time (defaults to now)
        
    Returns:
        Tuple of (is_expired, message):
            - is_expired: True if the confirmation has expired
            - message: Message explaining the timeout status
    """
    if current_time is None:
        current_time = datetime.now()
    
    elapsed = (current_time - request_time).total_seconds()
    
    if elapsed > CONFIRMATION_TIMEOUT:
        logger.warning(f"Confirmation timeout: {elapsed:.0f}s elapsed (limit: {CONFIRMATION_TIMEOUT}s)")
        return True, (
            f"⏱️ Confirmation expired after {elapsed/60:.1f} minutes.\n"
            f"Maximum wait time is {CONFIRMATION_TIMEOUT/60:.0f} minutes.\n"
            "Please submit the price update again."
        )
    
    logger.debug(f"Confirmation still valid: {elapsed:.0f}s elapsed")
    return False, f"⏱️ {(CONFIRMATION_TIMEOUT - elapsed)/60:.1f} minutes remaining"


# ==================== DATABASE VALIDATION ====================

def validate_price_data(prices: Dict[str, Decimal], 
                       operation: str = "update") -> Tuple[bool, List[str]]:
    """
    Strict validation of price data before database operations.
    
    Checks:
    - Non-empty price dictionary
    - All item names are non-empty strings
    - All prices are valid Decimal values
    - All prices are within acceptable bounds
    - Item name length limits
    - No SQL injection patterns in item names
    
    Args:
        prices: Dictionary of item names to prices
        operation: Type of operation for context in errors
        
    Returns:
        Tuple of (is_valid, error_messages):
            - is_valid: True if all validations pass
            - error_messages: List of validation errors (empty if valid)
    """
    logger.info(f"Validating price data for {operation} operation: {len(prices)} items")
    
    errors: List[str] = []
    
    # Check for empty dictionary
    if not prices:
        error = "❌ Cannot proceed: No price data provided"
        logger.error(error)
        errors.append(error)
        return False, errors
    
    # Check for too many items (potential DoS)
    if len(prices) > 1000:
        error = f"❌ Too many items ({len(prices)}). Maximum is 1000 items per operation."
        logger.error(error)
        errors.append(error)
        return False, errors
    
    # Validate each item
    for item_name, price in prices.items():
        # Validate item name type and content
        if not isinstance(item_name, str):
            error = f"❌ Invalid item name type: {type(item_name)}"
            logger.error(error)
            errors.append(error)
            continue
        
        if not item_name or not item_name.strip():
            error = "❌ Empty item name found"
            logger.error(error)
            errors.append(error)
            continue
        
        # Check item name length
        if len(item_name) > 200:
            error = f"❌ Item name too long (>200 chars): '{item_name[:50]}...'"
            logger.error(error)
            errors.append(error)
            continue
        
        # Check for SQL injection patterns (basic check)
        suspicious_patterns = [';', '--', '/*', '*/', 'DROP', 'DELETE', 'INSERT', 'UPDATE']
        if any(pattern in item_name.upper() for pattern in suspicious_patterns):
            error = f"⚠️ Suspicious pattern in item name: '{item_name}'"
            logger.warning(error)
            errors.append(error)
            continue
        
        # Validate price type
        if not isinstance(price, Decimal):
            try:
                price = Decimal(str(price))
            except (InvalidOperation, ValueError):
                error = f"❌ Invalid price type for '{item_name}': {type(price)}"
                logger.error(error)
                errors.append(error)
                continue
        
        # Validate price bounds
        if price < MIN_PRICE_VALUE:
            error = f"❌ Price below minimum for '{item_name}': ${price}"
            logger.error(error)
            errors.append(error)
            continue
        
        if price > MAX_PRICE_VALUE:
            error = f"❌ Price exceeds maximum for '{item_name}': ${price}"
            logger.error(error)
            errors.append(error)
            continue
    
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info(f"✅ Price data validation passed for {len(prices)} items")
    else:
        logger.error(f"❌ Price data validation failed with {len(errors)} errors")
    
    return is_valid, errors


def apply_price_list_to_db(prices: Dict[str, Decimal], 
                          db_connection: Any,
                          operation: str = "update") -> Tuple[bool, str]:
    """
    Apply validated price list to database with transaction safety.
    
    This is a template function that shows the pattern for safe database operations.
    Actual implementation depends on the specific database being used.
    
    Features:
    - Transaction-based updates (all-or-nothing)
    - Rollback on any error
    - Detailed logging of operations
    - Pre-operation validation
    
    Args:
        prices: Validated dictionary of item names to prices
        db_connection: Database connection object
        operation: Type of operation ("update", "insert", "upsert")
        
    Returns:
        Tuple of (success, message):
            - success: True if operation completed successfully
            - message: Success or error message
            
    Note:
        This is a template. Implement actual database logic based on your DB system.
    """
    logger.info(f"Starting database {operation} operation for {len(prices)} items")
    
    # Pre-operation validation
    is_valid, validation_errors = validate_price_data(prices, operation)
    if not is_valid:
        error_msg = f"❌ Validation failed:\n" + "\n".join(validation_errors)
        logger.error(f"Pre-operation validation failed: {len(validation_errors)} errors")
        return False, error_msg
    
    # Check database connection
    if db_connection is None:
        error_msg = "❌ No database connection provided"
        logger.error(error_msg)
        return False, error_msg
    
    try:
        # Start transaction (pseudo-code - adapt to your DB)
        logger.info("Starting database transaction")
        # db_connection.begin_transaction()
        
        items_processed = 0
        
        for item_name, price in prices.items():
            logger.debug(f"Processing: '{item_name}' = ${price}")
            
            # Perform database operation based on type
            if operation == "update":
                # Example: db_connection.execute(
                #     "UPDATE prices SET price = ? WHERE item_name = ?",
                #     (float(price), item_name)
                # )
                pass
            elif operation == "insert":
                # Example: db_connection.execute(
                #     "INSERT INTO prices (item_name, price) VALUES (?, ?)",
                #     (item_name, float(price))
                # )
                pass
            elif operation == "upsert":
                # Example: db_connection.execute(
                #     "INSERT INTO prices (item_name, price) VALUES (?, ?) "
                #     "ON CONFLICT(item_name) DO UPDATE SET price = ?",
                #     (item_name, float(price), float(price))
                # )
                pass
            
            items_processed += 1
        
        # Commit transaction (pseudo-code)
        logger.info(f"Committing transaction: {items_processed} items processed")
        # db_connection.commit()
        
        success_msg = (
            f"✅ Successfully {operation}d {items_processed} price(s) in database.\n"
            f"Total value: ${sum(prices.values()):.2f}"
        )
        logger.info(success_msg)
        return True, success_msg
        
    except Exception as e:
        # Rollback on any error (pseudo-code)
        logger.error(f"Database operation failed: {e}")
        # db_connection.rollback()
        
        error_msg = (
            f"❌ Database {operation} failed: {str(e)}\n"
            "All changes have been rolled back."
        )
        logger.error(error_msg)
        return False, error_msg


# ==================== MESSAGE FORMATTING ====================

def format_pricelist_message(prices: Dict[str, Decimal], 
                            title: str = "Price List",
                            format_style: str = "table") -> str:
    """
    Format price list for better user readability.
    
    Supports multiple display formats:
    - "table": Formatted table with alignment
    - "list": Simple bullet list
    - "compact": Minimal formatting for space-constrained displays
    
    Args:
        prices: Dictionary of item names to prices
        title: Header title for the price list
        format_style: Display format ("table", "list", "compact")
        
    Returns:
        Formatted price list message
        
    Examples:
        >>> prices = {"Apple": Decimal("1.50"), "Banana": Decimal("0.75")}
        >>> msg = format_pricelist_message(prices, "Fruit Prices")
        >>> "Apple" in msg
        True
    """
    logger.info(f"Formatting price list: {len(prices)} items, style: {format_style}")
    
    if not prices:
        logger.warning("Empty price dictionary provided for formatting")
        return f"📋 **{title}**\n\n_No items available._"
    
    # Sort items alphabetically
    sorted_items = sorted(prices.items())
    
    if format_style == "table":
        return _format_as_table(sorted_items, title)
    elif format_style == "list":
        return _format_as_list(sorted_items, title)
    elif format_style == "compact":
        return _format_as_compact(sorted_items, title)
    else:
        logger.warning(f"Unknown format style: {format_style}, defaulting to table")
        return _format_as_table(sorted_items, title)


def _format_as_table(items: List[Tuple[str, Decimal]], title: str) -> str:
    """Format prices as an aligned table."""
    logger.debug(f"Formatting {len(items)} items as table")
    
    # Calculate column widths
    max_name_length = max(len(name) for name, _ in items)
    max_name_length = min(max_name_length, 50)  # Cap at 50 chars
    
    # Build header
    result = f"📋 **{title}**\n"
    result += "═" * (max_name_length + 15) + "\n\n"
    
    # Add items
    for name, price in items:
        # Truncate long names
        display_name = name if len(name) <= max_name_length else name[:max_name_length-3] + "..."
        padding = " " * (max_name_length - len(display_name))
        result += f"  {display_name}{padding}  →  ${price:>8.2f}\n"
    
    # Add footer with statistics
    total = sum(price for _, price in items)
    avg = total / len(items) if items else Decimal('0')
    
    result += "\n" + "─" * (max_name_length + 15) + "\n"
    result += f"  **Total**: ${total:.2f}  |  **Count**: {len(items)}  |  **Avg**: ${avg:.2f}\n"
    
    logger.debug(f"Table formatted: {len(result)} characters")
    return result


def _format_as_list(items: List[Tuple[str, Decimal]], title: str) -> str:
    """Format prices as a simple bullet list."""
    logger.debug(f"Formatting {len(items)} items as list")
    
    result = f"📋 **{title}**\n\n"
    
    for name, price in items:
        result += f"• **{name}**: ${price:.2f}\n"
    
    # Add summary
    total = sum(price for _, price in items)
    result += f"\n_Total: ${total:.2f} ({len(items)} items)_\n"
    
    logger.debug(f"List formatted: {len(result)} characters")
    return result


def _format_as_compact(items: List[Tuple[str, Decimal]], title: str) -> str:
    """Format prices in compact format for space-constrained displays."""
    logger.debug(f"Formatting {len(items)} items as compact")
    
    result = f"📋 {title}\n"
    
    for name, price in items:
        # Truncate long names more aggressively
        display_name = name if len(name) <= 30 else name[:27] + "..."
        result += f"{display_name}: ${price:.2f}\n"
    
    total = sum(price for _, price in items)
    result += f"Total: ${total:.2f}\n"
    
    logger.debug(f"Compact format: {len(result)} characters")
    return result


# ==================== UTILITY FUNCTIONS ====================

def get_price_statistics(prices: Dict[str, Decimal]) -> Dict[str, Any]:
    """
    Calculate statistics for a price list.
    
    Args:
        prices: Dictionary of item names to prices
        
    Returns:
        Dictionary containing:
            - count: Number of items
            - total: Sum of all prices
            - average: Average price
            - min: Minimum price and item
            - max: Maximum price and item
    """
    logger.info(f"Calculating statistics for {len(prices)} items")
    
    if not prices:
        return {
            "count": 0,
            "total": Decimal('0'),
            "average": Decimal('0'),
            "min": None,
            "max": None
        }
    
    total = sum(prices.values())
    average = total / len(prices)
    
    min_item = min(prices.items(), key=lambda x: x[1])
    max_item = max(prices.items(), key=lambda x: x[1])
    
    stats = {
        "count": len(prices),
        "total": total,
        "average": average,
        "min": {"item": min_item[0], "price": min_item[1]},
        "max": {"item": max_item[0], "price": max_item[1]}
    }
    
    logger.debug(f"Statistics: {stats}")
    return stats


def validate_price_format(price_str: str) -> Tuple[bool, Optional[Decimal], str]:
    """
    Validate a single price string format.
    
    Args:
        price_str: String representation of price
        
    Returns:
        Tuple of (is_valid, price_value, error_message):
            - is_valid: True if price is valid
            - price_value: Decimal value (None if invalid)
            - error_message: Error description (empty if valid)
    """
    if not price_str:
        return False, None, "Empty price string"
    
    # Remove currency symbols and whitespace
    cleaned = price_str.strip().replace('$', '').replace(',', '')
    
    try:
        price = Decimal(cleaned)
        
        if price < MIN_PRICE_VALUE:
            return False, None, f"Price below minimum: ${price}"
        
        if price > MAX_PRICE_VALUE:
            return False, None, f"Price exceeds maximum: ${price}"
        
        return True, price, ""
        
    except (InvalidOperation, ValueError) as e:
        return False, None, f"Invalid price format: {str(e)}"
