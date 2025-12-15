"""Resource helpers for Ghostline Studio."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon


_ICONS_DIR = Path(__file__).resolve().parent.parent / "resources" / "icons"


def icons_dir() -> Path:
    """Return the absolute path to the bundled icons directory."""

    return _ICONS_DIR


@lru_cache(maxsize=None)
def _existing_icon_path(name: str) -> Path | None:
    path = _ICONS_DIR / name
    if path.exists():
        return path
    return None


def icon_path(name: str, *, fallback: str | None = None) -> Path | None:
    """Resolve an icon path, optionally falling back to another name."""

    for candidate in (name, fallback):
        if not candidate:
            continue
        path = _existing_icon_path(candidate)
        if path:
            return path
    return None


def load_icon(name: str, *, fallback: str | None = None) -> QIcon:
    """Load an icon from disk, returning an empty icon if missing."""

    path = icon_path(name, fallback=fallback)
    return QIcon(str(path)) if path else QIcon()


# File extension to icon name mapping
_FILE_EXTENSION_ICONS = {
    # Programming languages
    ".py": "file_python.svg",
    ".js": "file_javascript.svg",
    ".jsx": "file_react.svg",
    ".ts": "file_typescript.svg",
    ".tsx": "file_react-ts.svg",
    ".rb": "file_ruby.svg",
    ".rs": "file_rust.svg",
    ".go": "file_go.svg",
    ".java": "file_java.svg",
    ".php": "file_php.svg",
    ".c": "file_c.svg",
    ".cpp": "file_cpp.svg",
    ".cc": "file_cpp.svg",
    ".cxx": "file_cpp.svg",
    ".h": "file_c.svg",
    ".hpp": "file_cpp.svg",
    ".cs": "file_csharp.svg",
    ".swift": "file_swift.svg",
    ".kt": "file_kotlin.svg",
    ".kts": "file_kotlin.svg",
    ".dart": "file_dart.svg",
    ".lua": "file_lua.svg",
    ".clj": "file_clojure.svg",
    ".cljs": "file_clojure.svg",
    ".coffee": "file_coffeescript.svg",
    ".ex": "file_elixir.svg",
    ".exs": "file_elixir.svg",
    ".erl": "file_erlang.svg",
    ".hrl": "file_erlang.svg",
    ".hs": "file_haskell.svg",
    ".jl": "file_julia.svg",
    ".scala": "file_scala.svg",
    ".sc": "file_scala.svg",
    ".cr": "file_crystal.svg",
    ".sol": "file_solidity.svg",
    ".zig": "file_zig.svg",

    # Markup and config
    ".md": "file_markdown.svg",
    ".markdown": "file_markdown.svg",
    ".mdx": "file_mdx.svg",
    ".html": "file_html.svg",
    ".htm": "file_html.svg",
    ".xml": "file_xml.svg",
    ".yaml": "file_yaml.svg",
    ".yml": "file_yaml.svg",
    ".json": "file_json.svg",
    ".toml": "file_toml.svg",
    ".ini": "file_config.svg",
    ".conf": "file_config.svg",
    ".cfg": "file_config.svg",
    ".csv": "file_csv.svg",
    ".txt": "file_text.svg",
    ".log": "file_text.svg",

    # Stylesheets
    ".css": "file_css.svg",
    ".scss": "file_sass.svg",
    ".sass": "file_sass.svg",
    ".less": "file_css.svg",
    ".stylus": "file_css.svg",
    ".styl": "file_css.svg",

    # Templates
    ".vue": "file_vue.svg",
    ".svelte": "file_svelte.svg",
    ".pug": "file_pug.svg",
    ".jade": "file_pug.svg",
    ".haml": "file_haml.svg",
    ".liquid": "file_liquid.svg",
    ".twig": "file_twig.svg",
    ".njk": "file_nunjucks.svg",
    ".hbs": "file_html.svg",
    ".handlebars": "file_html.svg",

    # Shell scripts
    ".sh": "file_shell.svg",
    ".bash": "file_shell.svg",
    ".zsh": "file_shell.svg",
    ".fish": "file_shell.svg",
    ".ps1": "file_shell.svg",
    ".bat": "file_shell.svg",
    ".cmd": "file_shell.svg",

    # Build and config files
    ".dockerfile": "file_docker.svg",
    ".graphql": "file_graphql.svg",
    ".gql": "file_graphql.svg",
    ".proto": "file_proto.svg",
    ".tf": "file_terraform.svg",
    ".tfvars": "file_terraform.svg",
    ".prisma": "file_prisma.svg",
    ".astro": "file_astro.svg",

    # Media files
    ".png": "file_image.svg",
    ".jpg": "file_image.svg",
    ".jpeg": "file_image.svg",
    ".gif": "file_image.svg",
    ".webp": "file_image.svg",
    ".svg": "file_svg.svg",
    ".ico": "file_image.svg",
    ".bmp": "file_image.svg",
    ".pdf": "file_pdf.svg",
    ".mp3": "file_audio.svg",
    ".wav": "file_audio.svg",
    ".ogg": "file_audio.svg",
    ".flac": "file_audio.svg",
    ".mp4": "file_video.svg",
    ".avi": "file_video.svg",
    ".mkv": "file_video.svg",
    ".mov": "file_video.svg",
    ".webm": "file_video.svg",

    # Font files
    ".ttf": "file_font.svg",
    ".otf": "file_font.svg",
    ".woff": "file_font.svg",
    ".woff2": "file_font.svg",
    ".eot": "file_font.svg",

    # Special files
    ".sql": "file_sql.svg",
    ".db": "file_database.svg",
    ".sqlite": "file_database.svg",
    ".sqlite3": "file_database.svg",
    ".exe": "file_exe.svg",
    ".dll": "file_exe.svg",
    ".so": "file_exe.svg",
    ".ipynb": "file_notebook.svg",
    ".tex": "file_tex.svg",
    ".http": "file_http.svg",
    ".rest": "file_http.svg",
}

# Special filename to icon mapping (exact matches)
_SPECIAL_FILE_ICONS = {
    "dockerfile": "file_docker.svg",
    "docker-compose.yml": "file_docker.svg",
    "docker-compose.yaml": "file_docker.svg",
    ".gitignore": "file_ignore.svg",
    ".dockerignore": "file_ignore.svg",
    ".npmignore": "file_ignore.svg",
    ".eslintignore": "file_ignore.svg",
    "license": "file_license.svg",
    "license.md": "file_license.svg",
    "license.txt": "file_license.svg",
    "package.json": "file_node.svg",
    "package-lock.json": "file_npm.svg",
    "yarn.lock": "file_yarn.svg",
    "pnpm-lock.yaml": "file_pnpm.svg",
    "tsconfig.json": "file_tsconfig.svg",
    ".editorconfig": "file_editorconfig.svg",
    ".eslintrc": "file_eslint.svg",
    ".eslintrc.js": "file_eslint.svg",
    ".eslintrc.json": "file_eslint.svg",
    ".prettierrc": "file_prettier.svg",
    ".prettierrc.js": "file_prettier.svg",
    ".prettierrc.json": "file_prettier.svg",
    "jest.config.js": "file_jest.svg",
    "jest.config.ts": "file_jest.svg",
    "babel.config.js": "file_babel.svg",
    ".babelrc": "file_babel.svg",
    "webpack.config.js": "file_webpack.svg",
    "vite.config.js": "file_vite.svg",
    "vite.config.ts": "file_vite.svg",
    "postcss.config.js": "file_postcss.svg",
    "tailwind.config.js": "file_tailwind.svg",
    "tailwind.config.ts": "file_tailwind.svg",
    "next.config.js": "file_next.svg",
    "next.config.ts": "file_next.svg",
    "nuxt.config.js": "file_nuxt.svg",
    "nuxt.config.ts": "file_nuxt.svg",
    "astro.config.mjs": "file_astro.svg",
    "gradle.properties": "file_gradle.svg",
    "build.gradle": "file_gradle.svg",
    "build.gradle.kts": "file_gradle.svg",
    ".gitattributes": "file_git.svg",
    ".gitmodules": "file_git.svg",
    "cmakelists.txt": "file_cmake.svg",
    "makefile": "file_config.svg",
    ".env": "file_config.svg",
    ".env.example": "file_config.svg",
    ".env.local": "file_config.svg",
}


@lru_cache(maxsize=256)
def get_file_icon_name(filename: str) -> str:
    """Get the icon name for a file based on its name and extension."""

    filename_lower = filename.lower()

    # Check special filenames first (exact match)
    if filename_lower in _SPECIAL_FILE_ICONS:
        return _SPECIAL_FILE_ICONS[filename_lower]

    # Check file extension
    for ext, icon_name in _FILE_EXTENSION_ICONS.items():
        if filename_lower.endswith(ext):
            return icon_name

    # Default to generic file icon
    return "file_generic.svg"


def load_file_icon(filename: str) -> QIcon:
    """Load the appropriate icon for a file based on its name and extension."""

    icon_name = get_file_icon_name(filename)
    return load_icon(icon_name, fallback="file_generic.svg")
