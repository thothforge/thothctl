# src/thothctl/core/__init__.py
import sys
from pathlib import Path
from typing import Optional


class ThothCore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._src_path: Optional[Path] = None
        self._setup_paths()

    def _setup_paths(self) -> None:
        """Setup essential paths for the application"""
        current_file = Path(__file__).resolve()
        self._src_path = current_file.parent.parent

        if str(self._src_path) not in sys.path:
            sys.path.insert(0, str(self._src_path))

    @property
    def src_path(self) -> Path:
        """Get the source path"""
        return self._src_path

    @classmethod
    def get_instance(cls) -> "ThothCore":
        """Get singleton instance"""
        return cls()
