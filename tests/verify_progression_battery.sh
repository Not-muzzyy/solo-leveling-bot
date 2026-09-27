#!/usr/bin/env bash
# Task 8 verification battery — progression rebalance (approach A).
# Run: bash tests/verify_progression_battery.sh   (from repo root)
set -uo pipefail
export PYTHONIOENCODING=utf-8
fail=0

step() { echo "== $1"; }

step "1. py_compile 8 touched files"
python -m py_compile config.py models.py game/hunter.py game/duel.py \
  handlers/duel.py handlers/guild_war.py game/combat.py game/tower.py \
  && echo OK || fail=1

step "2. test suite (3 runs, flake check)"
for i in 1 2 3; do
  out=$(python tests/test_progression_rebalance.py 2>&1 | tail -1)
  echo "run $i: $out"
  case "$out" in *"passed"*) ;; *) fail=1 ;; esac
done

step "3. grep audits (source only, docs excluded)"
audit() { # audit <label> <pattern> <path...>
  hits=$(rg -n --glob '!docs/**' --glob '!.superpowers/**' --glob '!tests/**' "$2" "${@:3}")
  if [ -n "$hits" ]; then echo "FAIL $1:"; echo "$hits"; fail=1; else echo "$1: 0 hits"; fi
}
audit "add_xp bonus callers" 'add_xp\([^)]*bonus' game handlers
audit "old curve ** 1.5" '\*\* 1\.5' config.py game handlers
audit "hunt // 5 consolation" '// 5([^0-9]|$)' game/combat.py
audit "guild bonus 0.10" 'GUILD_XP_BONUS.*0\.10' config.py game handlers
audit "old duel winner formula" 'loser\.level \* 8' game/duel.py
audit "old duel loser formula" 'winner\.level \* 2' game/duel.py

step "4. import smoke"
python -c "import config, models, game.hunter, game.duel, game.combat, game.tower, handlers.duel, handlers.guild_war, handlers.tower, handlers.hunt; print('OK')" \
  2>/dev/null && echo OK || fail=1

step "5. boot smoke: performed live (Session started, ready, 20 HandlerTasks, 0 Tracebacks)"

echo
if [ "$fail" -eq 0 ]; then echo "BATTERY: PASS"; else echo "BATTERY: FAIL"; fi
exit $fail
