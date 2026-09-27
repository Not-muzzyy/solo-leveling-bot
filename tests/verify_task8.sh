#!/usr/bin/env bash
# Task 8 verification battery for callback in-place refresh plan.
set -e
cd "$(dirname "$0")/.."
python -m py_compile handlers/leaderboard.py handlers/guild.py handlers/inventory.py \
  handlers/forge.py handlers/tower.py handlers/quest.py handlers/guild_war.py
python -m game.rich_message
python -m game.rich_send
python -c "import handlers.leaderboard, handlers.guild, handlers.inventory, handlers.forge, handlers.tower, handlers.quest, handlers.guild_war; print('IMPORT SMOKE OK')"
python tests/audit_callback_refresh.py
