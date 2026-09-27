"""AST audit: callback handlers must refresh in place, not reply with a new message.

Root cause this guards: `if <msg>.photo:` used as the edit-in-place
discriminator. Rich-origin cards (InputRichMessage) have .photo = None and
fell into a reply-new or no-op branch. After the fix, a photo-tested If may
only *select* the classic fallback lambda -- never call edit_rich/reply_rich.

Rules (each violation = file:line: rule):
  R1  photo-If body contains reply_rich(...)           -> replies instead of editing
  R2  photo-If body has edit_rich AND else has reply_rich -> new message on non-photo origin
  R3  photo-If body has edit_rich AND empty else        -> silent no-op on non-photo origin
  R4  reply_rich(query.message / target.message, ...) outside allowlist
                                                        -> unconditional new-message refresh

Allowlist for R4: duel.py (action-result cards; classic parity: challenge is
edited at :254, the result is intentionally a fresh reply card).

Run:  python tests\audit_callback_refresh.py [file ...]     (default: all handlers/*.py)
Exit: 0 = clean, 1 = violations found.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "handlers"
ALLOWED_REPLY_FILES = {"duel.py"}


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    """All calls to a plain function name (e.g. edit_rich) inside node."""
    out: list[ast.Call] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == name:
            out.append(sub)
    return out


def _has_photo_test(node: ast.If) -> bool:
    src = ast.dump(node.test)
    return ".photo" in src or "photo" in src and "Attribute" in src and "value" in src


def _first_arg_is_msg_attr(call: ast.Call) -> bool:
    if not call.args:
        return False
    a0 = call.args[0]
    if isinstance(a0, ast.Attribute) and isinstance(a0.value, ast.Name):
        return a0.value.id in {"query", "target"} and a0.attr == "message"
    return False


def audit_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    rel = path.relative_to(ROOT).as_posix()

    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _has_photo_test(node):
            body_edit = bool(_calls_named(ast.Module(body=node.body, type_ignores=[]), "edit_rich"))
            body_reply = bool(_calls_named(ast.Module(body=node.body, type_ignores=[]), "reply_rich"))
            else_reply = bool(_calls_named(ast.Module(body=node.orelse, type_ignores=[]), "reply_rich"))
            if body_reply:
                violations.append(f"{rel}:{node.lineno}: R1 photo branch replies instead of editing")
            elif body_edit and else_reply:
                violations.append(f"{rel}:{node.lineno}: R2 else branch sends a new message")
            elif body_edit and not node.orelse:
                violations.append(f"{rel}:{node.lineno}: R3 photo guard makes edit a no-op on rich cards")

    if path.name not in ALLOWED_REPLY_FILES:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "reply_rich"
                and _first_arg_is_msg_attr(node)
            ):
                violations.append(
                    f"{rel}:{node.lineno}: R4 unconditional reply_rich(query.message, ...) refresh"
                )

    return violations


def main(argv: list[str]) -> int:
    if argv:
        files = [Path(a).resolve() for a in argv]
    else:
        files = sorted(HANDLERS.glob("*.py"))
    violations: list[str] = []
    for f in files:
        violations.extend(audit_file(f))
    if violations:
        print(f"AUDIT FAIL — {len(violations)} violation(s):")
        for v in violations:
            print(f"  {v}")
        return 1
    print(f"AUDIT OK — {len(files)} file(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
