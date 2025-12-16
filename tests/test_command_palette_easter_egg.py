import importlib
import sys
import types


def test_easter_egg_handler_invokes_dialog(monkeypatch):
    sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=object))

    class _DummyEncoding:
        def encode(self, text):
            return list(text)

    sys.modules.setdefault(
        "tiktoken",
        types.SimpleNamespace(
            get_encoding=lambda name: _DummyEncoding(),
            encoding_for_model=lambda name: _DummyEncoding(),
        ),
    )

    palette_module = importlib.import_module("ghostline.ui.command_palette")
    CommandPalette = palette_module.CommandPalette
    EASTER_EGG_QUERY = palette_module.EASTER_EGG_QUERY

    palette = CommandPalette.__new__(CommandPalette)
    called = {}

    def _fake_show_dialog():
        called["triggered"] = True

    palette._show_credits_dialog = _fake_show_dialog  # type: ignore[attr-defined]

    assert CommandPalette._handle_easter_egg(palette, EASTER_EGG_QUERY) is True
    assert called["triggered"] is True

    # Non-matching queries should not trigger the easter egg.
    assert CommandPalette._handle_easter_egg(palette, "open:ghosts") is False
