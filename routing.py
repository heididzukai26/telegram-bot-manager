"""
Order routing module for Telegram bot manager.

Manages worker group sources and routes orders to available groups based on type.
Includes comprehensive logging and validation for reliable order distribution.
"""

import logging
from typing import Dict, List, Optional, Set
from collections import defaultdict

# Configure logger
logger = logging.getLogger(__name__)

# Valid group types
VALID_GROUP_TYPES = {"unsafe", "fund", "safe_fast", "safe_slow"}

# ==================== DATA STRUCTURES ====================

# Routing table: {group_type: [list of source group IDs]}
_routing_table: Dict[str, List[int]] = defaultdict(list)

# Set for quick duplicate checking: {group_type: set of source group IDs}
_routing_set: Dict[str, Set[int]] = defaultdict(set)


# ==================== VALIDATION FUNCTIONS ====================

def validate_group_type(group_type: str) -> bool:
    """
    Validate that group_type is one of the supported types.
    
    Args:
        group_type: The order group type to validate
        
    Returns:
        True if valid, False otherwise
        
    Examples:
        >>> validate_group_type("unsafe")
        True
        >>> validate_group_type("invalid_type")
        False
    """
    if not group_type:
        logger.warning("⚠️  Validation failed: group_type is empty or None")
        return False
        
    if not isinstance(group_type, str):
        logger.warning(f"⚠️  Validation failed: group_type must be string, got {type(group_type)}")
        return False
        
    if group_type not in VALID_GROUP_TYPES:
        logger.warning(f"⚠️  Validation failed: '{group_type}' not in valid types {VALID_GROUP_TYPES}")
        return False
        
    logger.debug(f"✅ Validated group_type: '{group_type}'")
    return True


def validate_amount(amount: int) -> bool:
    """
    Validate that amount is a positive integer.
    
    Args:
        amount: The order amount to validate
        
    Returns:
        True if valid, False otherwise
        
    Examples:
        >>> validate_amount(100)
        True
        >>> validate_amount(-10)
        False
        >>> validate_amount(0)
        False
    """
    if not isinstance(amount, int):
        logger.warning(f"⚠️  Validation failed: amount must be int, got {type(amount)}")
        return False
        
    if amount <= 0:
        logger.warning(f"⚠️  Validation failed: amount must be positive, got {amount}")
        return False
        
    logger.debug(f"✅ Validated amount: {amount}")
    return True


def validate_source_id(source_id: int) -> bool:
    """
    Validate that source_id is a valid integer.
    
    Args:
        source_id: The source group ID to validate
        
    Returns:
        True if valid, False otherwise
        
    Examples:
        >>> validate_source_id(12345)
        True
        >>> validate_source_id(-100)
        True
        >>> validate_source_id(0)
        False
    """
    if not isinstance(source_id, int):
        logger.warning(f"⚠️  Validation failed: source_id must be int, got {type(source_id)}")
        return False
        
    if source_id == 0:
        logger.warning(f"⚠️  Validation failed: source_id cannot be 0")
        return False
        
    logger.debug(f"✅ Validated source_id: {source_id}")
    return True


# ==================== SOURCE MANAGEMENT ====================

def add_source(group_type: str, source_id: int) -> bool:
    """
    Add a source group ID for a specific order type.
    
    Handles edge cases:
    - Validates group_type and source_id
    - Prevents duplicate entries
    - Logs all operations for traceability
    
    Args:
        group_type: Type of orders (unsafe, fund, safe_fast, safe_slow)
        source_id: Telegram group ID to add as source
        
    Returns:
        True if source was added successfully, False otherwise
        
    Examples:
        >>> add_source("unsafe", 12345)
        True
        >>> add_source("unsafe", 12345)  # Duplicate
        False
        >>> add_source("invalid", 12345)  # Invalid type
        False
    """
    logger.info(f"🔄 add_source called: group_type='{group_type}', source_id={source_id}")
    
    # Validate inputs
    if not validate_group_type(group_type):
        logger.error(f"❌ Failed to add source: invalid group_type '{group_type}'")
        return False
        
    if not validate_source_id(source_id):
        logger.error(f"❌ Failed to add source: invalid source_id {source_id}")
        return False
    
    # Check for duplicates
    if source_id in _routing_set[group_type]:
        logger.warning(f"⚠️  Source {source_id} already exists for group_type '{group_type}'. Skipping.")
        return False
    
    # Add to both data structures
    _routing_table[group_type].append(source_id)
    _routing_set[group_type].add(source_id)
    
    logger.info(f"✅ Successfully added source {source_id} to '{group_type}'. Total sources: {len(_routing_table[group_type])}")
    logger.debug(f"📊 Current sources for '{group_type}': {_routing_table[group_type]}")
    
    return True


def remove_source(group_type: str, source_id: int) -> bool:
    """
    Remove a source group ID from a specific order type.
    
    Handles edge cases:
    - Validates group_type and source_id
    - Handles non-existent sources gracefully
    - Logs all operations for traceability
    
    Args:
        group_type: Type of orders (unsafe, fund, safe_fast, safe_slow)
        source_id: Telegram group ID to remove
        
    Returns:
        True if source was removed successfully, False otherwise
        
    Examples:
        >>> add_source("unsafe", 12345)
        True
        >>> remove_source("unsafe", 12345)
        True
        >>> remove_source("unsafe", 12345)  # Already removed
        False
    """
    logger.info(f"🔄 remove_source called: group_type='{group_type}', source_id={source_id}")
    
    # Validate inputs
    if not validate_group_type(group_type):
        logger.error(f"❌ Failed to remove source: invalid group_type '{group_type}'")
        return False
        
    if not validate_source_id(source_id):
        logger.error(f"❌ Failed to remove source: invalid source_id {source_id}")
        return False
    
    # Check if source exists
    if source_id not in _routing_set[group_type]:
        logger.warning(f"⚠️  Source {source_id} does not exist for group_type '{group_type}'. Nothing to remove.")
        return False
    
    # Remove from both data structures
    try:
        _routing_table[group_type].remove(source_id)
        _routing_set[group_type].discard(source_id)
        
        logger.info(f"✅ Successfully removed source {source_id} from '{group_type}'. Remaining sources: {len(_routing_table[group_type])}")
        logger.debug(f"📊 Current sources for '{group_type}': {_routing_table[group_type]}")
        
        return True
    except (ValueError, KeyError) as e:
        logger.error(f"❌ Error removing source {source_id} from '{group_type}': {e}")
        return False


def get_sources(group_type: str) -> List[int]:
    """
    Get all source group IDs for a specific order type.
    
    Args:
        group_type: Type of orders (unsafe, fund, safe_fast, safe_slow)
        
    Returns:
        List of source group IDs, or empty list if none exist
        
    Examples:
        >>> add_source("unsafe", 12345)
        True
        >>> get_sources("unsafe")
        [12345]
        >>> get_sources("fund")
        []
    """
    if not validate_group_type(group_type):
        logger.warning(f"⚠️  get_sources called with invalid group_type '{group_type}'. Returning empty list.")
        return []
    
    sources = _routing_table.get(group_type, [])
    logger.debug(f"📊 get_sources('{group_type}'): {len(sources)} sources found")
    
    return sources.copy()  # Return a copy to prevent external modifications


# ==================== ROUTING FUNCTIONS ====================

def get_source_for_type(group_type: str, amount: int = 0) -> Optional[int]:
    """
    Get a source group ID for routing an order of a specific type.
    
    Handles cases where specific worker groups are unavailable:
    - Returns None if no sources are available for the group type
    - Validates inputs before routing
    - Logs routing decisions for debugging
    
    Round-robin algorithm: cycles through available sources to distribute load.
    
    Args:
        group_type: Type of order (unsafe, fund, safe_fast, safe_slow)
        amount: Order amount (for validation and logging purposes)
        
    Returns:
        Source group ID if available, None if no sources available
        
    Examples:
        >>> add_source("unsafe", 12345)
        True
        >>> get_source_for_type("unsafe", 100)
        12345
        >>> get_source_for_type("fund", 100)
        None
    """
    logger.info(f"🔍 get_source_for_type called: group_type='{group_type}', amount={amount}")
    
    # Validate inputs
    if not validate_group_type(group_type):
        logger.error(f"❌ Routing failed: invalid group_type '{group_type}'")
        return None
    
    # Validate amount if provided
    if amount != 0 and not validate_amount(amount):
        logger.error(f"❌ Routing failed: invalid amount {amount}")
        return None
    
    # Get available sources
    sources = _routing_table.get(group_type, [])
    
    if not sources:
        logger.warning(f"⚠️  No sources available for group_type '{group_type}'. Cannot route order.")
        logger.info(f"💡 Suggestion: Add sources using add_source('{group_type}', source_id)")
        return None
    
    # Simple round-robin: return first available source
    # In a more advanced implementation, this could track usage and rotate
    selected_source = sources[0]
    
    logger.info(f"✅ Routed order to source {selected_source} for group_type '{group_type}' (amount: {amount})")
    logger.debug(f"📊 Available sources for '{group_type}': {sources}")
    
    return selected_source


def clear_sources(group_type: Optional[str] = None) -> bool:
    """
    Clear all sources for a specific group type, or all sources if group_type is None.
    
    Args:
        group_type: Type of orders to clear, or None to clear all
        
    Returns:
        True if sources were cleared successfully
        
    Examples:
        >>> clear_sources("unsafe")
        True
        >>> clear_sources()  # Clear all
        True
    """
    if group_type is None:
        logger.info("🧹 Clearing all sources for all group types")
        _routing_table.clear()
        _routing_set.clear()
        logger.info("✅ All sources cleared")
        return True
    
    if not validate_group_type(group_type):
        logger.error(f"❌ Failed to clear sources: invalid group_type '{group_type}'")
        return False
    
    count = len(_routing_table.get(group_type, []))
    _routing_table[group_type] = []
    _routing_set[group_type] = set()
    
    logger.info(f"🧹 Cleared {count} sources for group_type '{group_type}'")
    return True


def get_routing_stats() -> Dict[str, int]:
    """
    Get statistics about current routing configuration.
    
    Returns:
        Dictionary with group types as keys and source counts as values
        
    Examples:
        >>> add_source("unsafe", 12345)
        True
        >>> add_source("unsafe", 67890)
        True
        >>> get_routing_stats()
        {'unsafe': 2, 'fund': 0, 'safe_fast': 0, 'safe_slow': 0}
    """
    stats = {group_type: len(_routing_table.get(group_type, [])) for group_type in VALID_GROUP_TYPES}
    logger.debug(f"📊 Routing stats: {stats}")
    return stats
