# Plugins

Ghostline Studio supports lightweight plugins discovered from two locations:

- Built-ins bundled with the application.
- User plugins placed under `~/.config/ghostline/plugins`.

Each plugin exposes a `register(context)` function. The context gives access to:

| Method | Description |
| --- | --- |
| `register_command(id, label, callback)` | Adds a command to the Command Palette. |
| `register_menu(path, callback)` | Creates a menu item at the given path (e.g. `Tools/My Plugin`). |
| `register_dock(id, widget_factory)` | Adds a dock widget created from the factory. |
| `listen(event_name, callback)` | Receives core events: `file.opened`, `file.saved`, `workspace.opened`. |

## Write your first plugin

Create `~/.config/ghostline/plugins/hello.py`:

```python
def register(context):
    def greet():
        print("Hello from Ghostline plugin!")

    context.register_command("hello.say", "Say Hello", greet)
    context.register_menu("Tools/Hello", greet)
```

Start Ghostline Studio and open **Tools → Plugins** to enable or disable the plugin. Commands registered by plugins appear in the Command Palette.
