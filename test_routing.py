"""
Unit tests for routing.py module.

Tests cover:
- Validation functions for group_type, amount, and source_id
- Source management (add, remove, get)
- Routing logic with available and unavailable sources
- Edge cases and error handling
"""

import unittest
import logging
from routing import (
    validate_group_type,
    validate_amount,
    validate_source_id,
    add_source,
    remove_source,
    get_sources,
    get_source_for_type,
    clear_sources,
    get_routing_stats,
    VALID_GROUP_TYPES,
)

# Configure logging for tests
logging.basicConfig(level=logging.WARNING)


class TestValidationFunctions(unittest.TestCase):
    """Test validation functions for inputs."""
    
    def test_validate_group_type_valid(self):
        """Test validation with valid group types."""
        for group_type in VALID_GROUP_TYPES:
            with self.subTest(group_type=group_type):
                self.assertTrue(validate_group_type(group_type))
    
    def test_validate_group_type_invalid(self):
        """Test validation with invalid group types."""
        invalid_types = ["", "invalid", "UNSAFE", "Safe_Fast", None, 123, []]
        for group_type in invalid_types:
            with self.subTest(group_type=group_type):
                self.assertFalse(validate_group_type(group_type))
    
    def test_validate_amount_valid(self):
        """Test validation with valid amounts."""
        valid_amounts = [1, 10, 100, 1000, 999999]
        for amount in valid_amounts:
            with self.subTest(amount=amount):
                self.assertTrue(validate_amount(amount))
    
    def test_validate_amount_invalid(self):
        """Test validation with invalid amounts."""
        invalid_amounts = [0, -1, -100, "100", 100.5, None, []]
        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                self.assertFalse(validate_amount(amount))
    
    def test_validate_source_id_valid(self):
        """Test validation with valid source IDs."""
        valid_ids = [1, 100, -100, 12345, -67890]
        for source_id in valid_ids:
            with self.subTest(source_id=source_id):
                self.assertTrue(validate_source_id(source_id))
    
    def test_validate_source_id_invalid(self):
        """Test validation with invalid source IDs."""
        invalid_ids = [0, "12345", 123.45, None, []]
        for source_id in invalid_ids:
            with self.subTest(source_id=source_id):
                self.assertFalse(validate_source_id(source_id))


class TestSourceManagement(unittest.TestCase):
    """Test add_source, remove_source, and get_sources functions."""
    
    def setUp(self):
        """Clear all sources before each test."""
        clear_sources()
    
    def tearDown(self):
        """Clear all sources after each test."""
        clear_sources()
    
    def test_add_source_success(self):
        """Test successfully adding a source."""
        result = add_source("unsafe", 12345)
        self.assertTrue(result)
        
        sources = get_sources("unsafe")
        self.assertEqual(sources, [12345])
    
    def test_add_source_multiple(self):
        """Test adding multiple sources to same group type."""
        self.assertTrue(add_source("unsafe", 12345))
        self.assertTrue(add_source("unsafe", 67890))
        self.assertTrue(add_source("unsafe", 11111))
        
        sources = get_sources("unsafe")
        self.assertEqual(len(sources), 3)
        self.assertIn(12345, sources)
        self.assertIn(67890, sources)
        self.assertIn(11111, sources)
    
    def test_add_source_duplicate(self):
        """Test that duplicate sources are rejected."""
        self.assertTrue(add_source("unsafe", 12345))
        self.assertFalse(add_source("unsafe", 12345))
        
        sources = get_sources("unsafe")
        self.assertEqual(sources, [12345])
    
    def test_add_source_invalid_group_type(self):
        """Test adding source with invalid group type."""
        self.assertFalse(add_source("invalid_type", 12345))
        self.assertFalse(add_source("", 12345))
        self.assertFalse(add_source(None, 12345))
    
    def test_add_source_invalid_source_id(self):
        """Test adding source with invalid source ID."""
        self.assertFalse(add_source("unsafe", 0))
        self.assertFalse(add_source("unsafe", "12345"))
        self.assertFalse(add_source("unsafe", None))
    
    def test_add_source_different_types(self):
        """Test adding sources to different group types."""
        self.assertTrue(add_source("unsafe", 12345))
        self.assertTrue(add_source("fund", 67890))
        self.assertTrue(add_source("safe_fast", 11111))
        self.assertTrue(add_source("safe_slow", 22222))
        
        self.assertEqual(get_sources("unsafe"), [12345])
        self.assertEqual(get_sources("fund"), [67890])
        self.assertEqual(get_sources("safe_fast"), [11111])
        self.assertEqual(get_sources("safe_slow"), [22222])
    
    def test_remove_source_success(self):
        """Test successfully removing a source."""
        add_source("unsafe", 12345)
        result = remove_source("unsafe", 12345)
        self.assertTrue(result)
        
        sources = get_sources("unsafe")
        self.assertEqual(sources, [])
    
    def test_remove_source_nonexistent(self):
        """Test removing a source that doesn't exist."""
        result = remove_source("unsafe", 99999)
        self.assertFalse(result)
    
    def test_remove_source_invalid_group_type(self):
        """Test removing source with invalid group type."""
        self.assertFalse(remove_source("invalid_type", 12345))
        self.assertFalse(remove_source("", 12345))
        self.assertFalse(remove_source(None, 12345))
    
    def test_remove_source_invalid_source_id(self):
        """Test removing source with invalid source ID."""
        self.assertFalse(remove_source("unsafe", 0))
        self.assertFalse(remove_source("unsafe", "12345"))
        self.assertFalse(remove_source("unsafe", None))
    
    def test_remove_source_multiple(self):
        """Test removing multiple sources."""
        add_source("unsafe", 12345)
        add_source("unsafe", 67890)
        add_source("unsafe", 11111)
        
        self.assertTrue(remove_source("unsafe", 67890))
        sources = get_sources("unsafe")
        self.assertEqual(len(sources), 2)
        self.assertNotIn(67890, sources)
    
    def test_get_sources_empty(self):
        """Test getting sources when none exist."""
        sources = get_sources("unsafe")
        self.assertEqual(sources, [])
    
    def test_get_sources_invalid_group_type(self):
        """Test getting sources with invalid group type."""
        sources = get_sources("invalid_type")
        self.assertEqual(sources, [])
    
    def test_get_sources_returns_copy(self):
        """Test that get_sources returns a copy, not reference."""
        add_source("unsafe", 12345)
        sources1 = get_sources("unsafe")
        sources2 = get_sources("unsafe")
        
        # Modify one list
        sources1.append(99999)
        
        # Original should be unchanged
        self.assertNotEqual(sources1, sources2)
        self.assertEqual(get_sources("unsafe"), [12345])


class TestRoutingLogic(unittest.TestCase):
    """Test get_source_for_type routing function."""
    
    def setUp(self):
        """Clear all sources before each test."""
        clear_sources()
    
    def tearDown(self):
        """Clear all sources after each test."""
        clear_sources()
    
    def test_get_source_with_available_source(self):
        """Test routing when sources are available."""
        add_source("unsafe", 12345)
        source = get_source_for_type("unsafe", 100)
        self.assertEqual(source, 12345)
    
    def test_get_source_with_unavailable_source(self):
        """Test routing when no sources are available."""
        source = get_source_for_type("fund", 100)
        self.assertIsNone(source)
    
    def test_get_source_invalid_group_type(self):
        """Test routing with invalid group type."""
        source = get_source_for_type("invalid_type", 100)
        self.assertIsNone(source)
    
    def test_get_source_invalid_amount(self):
        """Test routing with invalid amount."""
        add_source("unsafe", 12345)
        source = get_source_for_type("unsafe", -100)
        self.assertIsNone(source)
    
    def test_get_source_no_amount(self):
        """Test routing without specifying amount (None)."""
        add_source("unsafe", 12345)
        source = get_source_for_type("unsafe")
        self.assertEqual(source, 12345)
    
    def test_get_source_zero_amount(self):
        """Test routing with zero amount (should be rejected)."""
        add_source("unsafe", 12345)
        source = get_source_for_type("unsafe", 0)
        self.assertIsNone(source)
    
    def test_get_source_multiple_sources(self):
        """Test routing when multiple sources exist (round-robin)."""
        add_source("unsafe", 12345)
        add_source("unsafe", 67890)
        add_source("unsafe", 11111)
        
        # Should return first source (basic implementation)
        source = get_source_for_type("unsafe", 100)
        self.assertIn(source, [12345, 67890, 11111])
    
    def test_get_source_different_types(self):
        """Test routing for different group types."""
        add_source("unsafe", 12345)
        add_source("fund", 67890)
        add_source("safe_fast", 11111)
        
        self.assertEqual(get_source_for_type("unsafe", 100), 12345)
        self.assertEqual(get_source_for_type("fund", 200), 67890)
        self.assertEqual(get_source_for_type("safe_fast", 300), 11111)
        self.assertIsNone(get_source_for_type("safe_slow", 400))


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions like clear_sources and get_routing_stats."""
    
    def setUp(self):
        """Clear all sources before each test."""
        clear_sources()
    
    def tearDown(self):
        """Clear all sources after each test."""
        clear_sources()
    
    def test_clear_sources_specific_type(self):
        """Test clearing sources for specific group type."""
        add_source("unsafe", 12345)
        add_source("fund", 67890)
        
        result = clear_sources("unsafe")
        self.assertTrue(result)
        
        self.assertEqual(get_sources("unsafe"), [])
        self.assertEqual(get_sources("fund"), [67890])
    
    def test_clear_sources_all_types(self):
        """Test clearing all sources."""
        add_source("unsafe", 12345)
        add_source("fund", 67890)
        add_source("safe_fast", 11111)
        
        result = clear_sources()
        self.assertTrue(result)
        
        for group_type in VALID_GROUP_TYPES:
            self.assertEqual(get_sources(group_type), [])
    
    def test_clear_sources_invalid_type(self):
        """Test clearing with invalid group type."""
        result = clear_sources("invalid_type")
        self.assertFalse(result)
    
    def test_get_routing_stats_empty(self):
        """Test getting stats when no sources exist."""
        stats = get_routing_stats()
        
        for group_type in VALID_GROUP_TYPES:
            self.assertEqual(stats[group_type], 0)
    
    def test_get_routing_stats_with_sources(self):
        """Test getting stats with various sources."""
        add_source("unsafe", 12345)
        add_source("unsafe", 67890)
        add_source("fund", 11111)
        add_source("safe_fast", 22222)
        
        stats = get_routing_stats()
        
        self.assertEqual(stats["unsafe"], 2)
        self.assertEqual(stats["fund"], 1)
        self.assertEqual(stats["safe_fast"], 1)
        self.assertEqual(stats["safe_slow"], 0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def setUp(self):
        """Clear all sources before each test."""
        clear_sources()
    
    def tearDown(self):
        """Clear all sources after each test."""
        clear_sources()
    
    def test_negative_source_id(self):
        """Test that negative source IDs are allowed."""
        result = add_source("unsafe", -12345)
        self.assertTrue(result)
        
        sources = get_sources("unsafe")
        self.assertEqual(sources, [-12345])
    
    def test_large_source_id(self):
        """Test with very large source ID."""
        large_id = 999999999999
        result = add_source("unsafe", large_id)
        self.assertTrue(result)
        
        source = get_source_for_type("unsafe", 100)
        self.assertEqual(source, large_id)
    
    def test_add_remove_add_sequence(self):
        """Test adding, removing, and re-adding same source."""
        self.assertTrue(add_source("unsafe", 12345))
        self.assertTrue(remove_source("unsafe", 12345))
        self.assertTrue(add_source("unsafe", 12345))
        
        sources = get_sources("unsafe")
        self.assertEqual(sources, [12345])
    
    def test_multiple_operations_same_type(self):
        """Test multiple operations on same group type."""
        # Add multiple sources
        add_source("unsafe", 111)
        add_source("unsafe", 222)
        add_source("unsafe", 333)
        
        # Remove one
        remove_source("unsafe", 222)
        
        # Add another
        add_source("unsafe", 444)
        
        sources = get_sources("unsafe")
        self.assertEqual(len(sources), 3)
        self.assertIn(111, sources)
        self.assertNotIn(222, sources)
        self.assertIn(333, sources)
        self.assertIn(444, sources)
    
    def test_concurrent_types(self):
        """Test operations on all group types simultaneously."""
        for i, group_type in enumerate(VALID_GROUP_TYPES, start=1):
            add_source(group_type, i * 1000)
            add_source(group_type, i * 1000 + 1)
        
        stats = get_routing_stats()
        for group_type in VALID_GROUP_TYPES:
            self.assertEqual(stats[group_type], 2)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
