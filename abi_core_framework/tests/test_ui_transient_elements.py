"""A saved chat does not bring back what was on screen only for a moment.
Deletes are soft, so "Preparing" stays in the database; reopening a chat
showed its spinner forever (found live, 2026-11-06)."""

from abi_core.ui.secure_data_layer import _without_transient


def test_preparing_and_its_message_leave_the_saved_chat():
    thread = {"id": "t", "name": "Chat",
              "steps": [{"id": "m1", "output": ""}, {"id": "m2", "output": ""}, {"id": "m3", "output": "hola"}],
              "elements": [{"id": "e1", "name": "Preparing", "forId": "m1"}, {"id": "e2", "name": "Welcome", "forId": "m2"}]}
    assert _without_transient(thread) == {"id": "t", "name": "Chat",
                                          "steps": [{"id": "m2", "output": ""}, {"id": "m3", "output": "hola"}],
                                          "elements": [{"id": "e2", "name": "Welcome", "forId": "m2"}]}


def test_a_chat_without_it_is_untouched():
    thread = {"id": "t", "steps": [{"id": "m1"}], "elements": [{"id": "e1", "name": "Welcome", "forId": "m1"}]}
    assert _without_transient(thread) is thread
    empty = {"id": "t", "steps": [], "elements": None}
    assert _without_transient(empty) is empty
    assert _without_transient(None) is None
