"""
Albert OS — Test fixtures
Spek: 41_TESTING_AND_QUALITY_BIBLE.md
"""
import os
import sys
import pytest

# Lisa backend root sys.path-i et importimine toimiks
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Testi ajal kasuta mälu DB-d, mitte toodangu andmebaasi
os.environ.setdefault("ALBERT_DB_PATH", ":memory:")
os.environ.setdefault("OPENAI_API_KEY", "test-key-placeholder")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-placeholder")
os.environ.setdefault("DEVICE_ID", "test-device-001")
