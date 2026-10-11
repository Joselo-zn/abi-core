"""
Tests for the one-call integration repair (abi_core.common.integration_repair):
prompt, output parsing and the deterministic missing-import fixer.
The model call itself is exercised live, not here.
"""

from abi_core.common.integration_repair import (
    build_repair_prompt,
    fix_missing_imports,
    parse_repaired_files,
)


class TestParse:
    def test_only_delivered_names_and_trailing_newline(self):
        text = (
            "noise\n=== FILE: a.py ===\nx = 1\n=== END FILE ===\n"
            "=== FILE: evil.py ===\nimport os\n=== END FILE ===\n"
        )
        assert parse_repaired_files(text, {"a.py", "b.py"}) == {"a.py": "x = 1\n"}

    def test_nothing_parsable(self):
        assert parse_repaired_files("I could not do it", {"a.py"}) == {}


class TestPrompt:
    def test_includes_files_report_and_dependency_direction(self):
        p = build_repair_prompt({"a.py": "x = 1\n"}, "a.py", "REPORT",
                                {"a.py": ["b.py"], "b.py": []})
        assert "REPORT" in p and "=== FILE: a.py ===" in p
        assert "- a.py may import: b.py" in p and "- b.py may import: none of the other files" in p

    def test_without_dependency_direction(self):
        p = build_repair_prompt({"a.py": "x = 1\n"}, "a.py", "R")
        assert "may import" not in p

    def test_rules_live_in_the_reviewer_role_not_in_the_message(self):
        # per-call-prompts-rewrite B7 (measured): the repair rules are in
        # REVIEWER_ROLE, the system prompt of the only caller (the reviewer).
        from abi_core.common.prompts.reviewer import REVIEWER_ROLE
        p = build_repair_prompt({"a.py": "x = 1\n"}, "a.py", "R", {"a.py": [], "b.py": ["a.py"]})
        for rule in ("No circular imports", "Wire the main loop", "must match the callee's real signature"):
            assert rule in REVIEWER_ROLE and rule not in p


class TestFixMissingImports:
    def test_adds_import_for_name_defined_in_one_other_file(self):
        files = {"player.py": "class Player:\n    pass\n",
                 "game.py": "import pygame\n\nclass Game:\n    def __init__(self):\n        self.p = Player()\n"}
        fixed, notes = fix_missing_imports(files)
        assert "from player import Player\n" in fixed["game.py"]
        assert fixed["game.py"].index("from player import Player") > fixed["game.py"].index("import pygame")
        assert fixed["player.py"] == files["player.py"]
        compile(fixed["game.py"], "game.py", "exec")

    def test_skips_circular(self):
        files = {"player.py": "import game\n\nclass Player:\n    pass\n",
                 "game.py": "class Game:\n    def f(self):\n        return Player()\n"}
        fixed, notes = fix_missing_imports(files)
        assert fixed == files and any("circular" in n for n in notes)

    def test_skips_ambiguous_and_already_bound(self):
        files = {"a.py": "class Thing:\n    pass\n", "b.py": "class Thing:\n    pass\n",
                 "c.py": "def f():\n    return Thing()\n",
                 "d.py": "Thing = 1\nprint(Thing)\n"}
        fixed, _ = fix_missing_imports(files)
        assert fixed == files

    def test_ignores_builtins_and_syntax_errors(self):
        files = {"a.py": "print(len([1]))\n", "b.py": "def broken(:\n"}
        fixed, notes = fix_missing_imports(files)
        assert fixed == files and notes == []
