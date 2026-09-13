"""
game/hunt_gif.py — Backward compatibility shim for game/hunt_image.py.

Redirects render_hunt_gif to game.hunt_image.render_hunt_image.
"""

from __future__ import annotations

from game.hunt_image import (
    render_hunt_image,
    render_hunt_image as render_hunt_gif,
    WIDTH,
    HEIGHT,
)

__all__ = ["render_hunt_image", "render_hunt_gif", "WIDTH", "HEIGHT"]
