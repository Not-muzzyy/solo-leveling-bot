"""Visual smoke for the Mini App: mocks Telegram initData + /api/v1/*, screenshots all screens.

Run: python tests/miniapp_visual.py <output_dir>   (expects vite dev on 127.0.0.1:5173)
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT.mkdir(parents=True, exist_ok=True)

HUNTER = {
    "display_name": "Sung Jinwoo", "rank": "S", "level": 42,
    "xp": 2400, "xp_needed": 3000, "gold": 15420, "power": 486,
    "str_stat": 61, "agi": 54, "vit": 48, "int_stat": 57, "per": 52,
    "title": "Shadow Monarch", "last_claim_time": 0,
    "claim_remaining_seconds": 0, "guild_id": 1,
}
GUILD = {
    "id": 1, "name": "Ahjin Guild", "description": "The Shadow Monarch's own syndicate.",
    "owner_name": "Sung Jinwoo", "member_count": 3, "max_members": 15,
    "total_power": 1240, "average_level": 38.0, "total_gold": 90000,
    "war_score": 1200, "war_wins": 7, "war_losses": 2, "xp_bonus_percent": 5,
    "members": [
        {"display_name": "Sung Jinwoo", "role": "owner", "rank": "S", "level": 42, "power": 486},
        {"display_name": "Cha Hae-in", "role": "member", "rank": "S", "level": 40, "power": 470},
        {"display_name": "Yoo Jinho", "role": "member", "rank": "B", "level": 28, "power": 284},
    ],
}
ITEMS = [
    {"key": "k1", "name": "Demon King's Longsword", "type": "weapon", "rarity": "Legendary", "price": 5200, "stats": {"attack": 96, "defense": 0, "hp": 0, "speed": 8}},
    {"key": "k2", "name": "Knight Killer", "type": "weapon", "rarity": "Rare", "price": 1800, "stats": {"attack": 42, "defense": 0, "hp": 0, "speed": 3}},
    {"key": "k3", "name": "Hunter's Leather Armor", "type": "armor", "rarity": "Uncommon", "price": 900, "stats": {"attack": 0, "defense": 28, "hp": 60, "speed": 0}},
    {"key": "k4", "name": "Red Gate Ring", "type": "accessory", "rarity": "Epic", "price": 3400, "stats": {"attack": 12, "defense": 6, "hp": 40, "speed": 10}},
    {"key": "k5", "name": "Lesser Healing Potion", "type": "consumable", "rarity": "Common", "price": 120, "stats": {"attack": 0, "defense": 0, "hp": 150, "speed": 0}},
]
GUILDS = [
    GUILD,
    {**GUILD, "id": 2, "name": "Knights Guild", "owner_name": "Baek Yoonho", "total_power": 4100, "members": GUILD["members"][:1]},
    {**GUILD, "id": 3, "name": "White Tiger Guild", "owner_name": "Choi Jong-In", "total_power": 3650, "members": GUILD["members"][1:2]},
]
ME = {"hunter": HUNTER, "inventory_count": 7, "guild": GUILD}


def mock(route, request):
    url = request.url
    if "/api/v1/me" in url:
        body = ME
    elif "/shop/catalog" in url:
        body = {"categories": ["weapon", "armor", "accessory", "consumable", "material"], "items": ITEMS}
    elif "/shop/purchases" in url:
        body = {"item": {"id": 1, "name": "Demon King's Longsword", "type": "weapon", "rarity": "Legendary", "stats": ITEMS[0]["stats"]}, "price": ITEMS[0]["price"], "hunter": {**HUNTER, "gold": HUNTER["gold"] - ITEMS[0]["price"]}}
    elif re.search(r"/guilds/\d+", url):
        body = GUILDS[1]
    elif "/api/v1/guilds" in url:
        body = {"sort": "power", "guilds": GUILDS}
    elif "/api/v1/claim" in url:
        body = {"gold_reward": 470, "xp_reward": 365, "leveled_up": False, "new_rank": None,
                "hunter": {**HUNTER, "claim_remaining_seconds": 86400}}
    else:
        route.fulfill(status=404, json={"detail": {"code": "not_found", "message": "unmocked"}})
        return
    route.fulfill(status=200, headers={"content-type": "application/json"}, body=json.dumps(body))


errors = []
main_errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.add_init_script(
        "window.Telegram={WebApp:{initData:'mock-init-data',initDataUnsafe:{start_param:''},expand(){}}};"
    )
    # index.html loads telegram-web-app.js, which would replace the mock with initData:''.
    ctx.route(re.compile(r"telegram-web-app\.js"),
              lambda route: route.fulfill(status=200, content_type="application/javascript", body=""))
    api_route = re.compile(r"/api/v1/")
    ctx.route(api_route, lambda route: mock(route, route.request))
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto("http://localhost:5173")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / "01-profile.png"), full_page=True)

    page.get_by_role("button", name="Claim").click()
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "02-claim.png"), full_page=True)

    page.get_by_role("button", name="SYS:CLAIM").click()
    page.wait_for_timeout(350)
    page.screenshot(path=str(OUT / "03-claim-notice.png"), full_page=True)

    page.get_by_role("button", name="Shop").click()
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "04-shop.png"), full_page=True)

    page.get_by_role("button", name="Guilds").click()
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "05-guilds.png"), full_page=True)

    # Snapshot real-phase errors; the error-state 404s below are intentional.
    main_errors = list(errors)

    # Error state: every API call 404s (hunter not awakened)
    ctx.unroute(api_route)
    ctx.route(api_route, lambda route: route.fulfill(status=404, json={"detail": {"code": "hunter_not_found", "message": "Awaken as a Hunter in the bot before opening the Mini App."}}))
    page.reload()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "06-state-error.png"), full_page=True)

    browser.close()

print("SHOTS:", sorted(p.name for p in OUT.glob("*.png")))
print("CONSOLE ERRORS:", main_errors if main_errors else "none")
sys.exit(1 if main_errors else 0)
