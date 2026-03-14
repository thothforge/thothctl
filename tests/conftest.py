"""Pytest configuration.

Force-load thothctl from src/ to prevent the root __init__.py
(project dir is named 'thothctl') from shadowing the real package.
"""
import thothctl.services  # noqa: F401 - primes correct package resolution
