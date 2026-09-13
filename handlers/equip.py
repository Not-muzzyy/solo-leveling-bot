"""
handlers/equip.py — Backward-compatible wrapper.

Equipment is now directly managed inside /inventory.
This module delegates to handlers.inventory for backwards compatibility.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes
from handlers.inventory import handle, equip_callback as button_callback

__all__ = ["handle", "button_callback"]
