"""Core package - Configuration, inventory, and template management."""

from .config import ConfigBuilder, TemplateConfig, TemplateManager
from .inventory import Inventory, InventoryGroup, InventoryManager

__all__ = [
    "TemplateManager", "ConfigBuilder", "TemplateConfig",
    "Inventory", "InventoryManager", "InventoryGroup",
]
