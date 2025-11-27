# Multi-server LSP Chains

Ghostline Studio supports chaining multiple LSP servers per language. Roles include:
- primary: completions, hover, navigation
- analyzers: diagnostics-only providers
- formatter: formatting entry point

Servers run independently so analyzer failures do not block editing.
