"""
Tests for the code agent TDD (abi_core.common.code_tdd).
Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/01-code-agent-tdd.md
"""

import textwrap

from abi_core.common.code_tdd import (
    TDD_MARKER,
    build_tdd,
    extract_assumes,
    extract_exposes,
    extract_resources,
    extract_role,
    parse_model_fields,
    tdd_summary,
)


def _d(s):
    return textwrap.dedent(s).lstrip()


PLAYER = _d("""
    class Player:
        def __init__(self, x):
            self.x = x
        def shoot(self):
            pass
""")

GAME = _d("""
    import pygame
    from player import Player
    from assets import load_all

    class Game:
        def __init__(self):
            self.p = Player(1)
            self.p.shoot(5)
            self.p.jump()
            self.img = pygame.image.load('ship.png')
            self.font = pygame.font.Font(None, 30)
""")


def test_exposes_matches_contract_shape():
    exp = extract_exposes(PLAYER)
    assert exp == {"classes": [{"name": "Player", "methods": ["__init__(self, x)", "shoot(self)"]}],
                   "functions": []}


def test_assumes_imports_calls_and_missing_modules():
    a = extract_assumes(GAME, ["player"])
    assert a["imports"] == {"player": ["Player"]}
    assert a["calls"] == ["Player(1)", "Player.jump/0", "Player.shoot/1"]
    assert a["missing_modules"] == ["assets"]          # not delivered, not stdlib, not in the sandbox
    assert "pygame" not in a["missing_modules"]         # provided by the sandbox image


def test_resources_skip_default_font():
    assert extract_resources(GAME) == ["load(ship.png)"]


def test_role_flags_and_import_time_work():
    src = _d("""
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((800, 600))
        while True:
            for e in pygame.event.get():
                pass
            pygame.display.flip()
    """)
    role = extract_role(src)
    assert set(role["flags"]) == {"creates_window", "initializes_pygame", "handles_events", "render_loop"}
    assert any("set_mode" in r for r in role["runs_at_import"])
    assert extract_role(PLAYER) == {"flags": [], "runs_at_import": []}


def test_model_fields_present_and_missing():
    # Spec before the code: the section opens the answer and the code follows it.
    answer = (f"{TDD_MARKER}\nPurpose and data model: Game owns the score.\nNeeded but not found: none\n\n"
              "Writing game.py now.\nDone.")
    assert parse_model_fields(answer) == {"purpose_data_model": "Game owns the score.",
                                          "needed_not_found": "none"}
    assert parse_model_fields("Done, no section.") == {"purpose_data_model": None, "needed_not_found": None}


def test_build_tdd_early_findings_and_missing_model_fields():
    tdd = build_tdd("game.py", {"game.py": GAME, "player.py": PLAYER}, "no TDD section")
    msgs = " | ".join(tdd["early_findings"])
    assert "self.p.shoot(...)" in msgs and "no tiene el método `jump`" in msgs
    assert tdd["model_fields_missing"] == ["purpose_data_model", "needed_not_found"]
    assert tdd["resources"] == ["load(ship.png)"]


def test_early_findings_only_for_this_file():
    # player.py is fine; its TDD must not carry game.py's errors
    tdd = build_tdd("player.py", {"game.py": GAME, "player.py": PLAYER})
    assert tdd["early_findings"] == []


def test_summary_for_dependents():
    tdd = build_tdd("game.py", {"game.py": GAME, "player.py": PLAYER},
                    f"{TDD_MARKER}\nPurpose and data model: Game owns the score.\nNeeded but not found: none")
    s = tdd_summary(tdd)
    assert "Game owns the score." in s and "ship.png" in s
