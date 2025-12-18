#!/bin/bash
set -e

# Ghostline Studio Linux Installer
# Version: 1.0.0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_TYPE=""
INSTALL_DIR=""
PYTHON_CMD=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║          Ghostline Studio Linux Installer                ║"
    echo "║    AI-Augmented Development Environment                  ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

check_python() {
    print_info "Checking for Python 3.11 or higher..."

    # Try different Python commands
    for cmd in python3.14 python3.13 python3.12 python3.11 python3 python; do
        if command -v "$cmd" &> /dev/null; then
            version=$($cmd --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
            major=$(echo $version | cut -d. -f1)
            minor=$(echo $version | cut -d. -f2)

            if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
                PYTHON_CMD="$cmd"
                print_success "Found Python $version at $(command -v $cmd)"
                return 0
            fi
        fi
    done

    print_error "Python 3.11 or higher is required but not found."
    echo "Please install Python 3.11+ and try again."
    echo "Visit: https://www.python.org/downloads/"
    exit 1
}

check_pip() {
    print_info "Checking for pip..."

    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        print_error "pip is not available."
        echo "Installing pip..."
        $PYTHON_CMD -m ensurepip --default-pip || {
            print_error "Failed to install pip. Please install it manually."
            exit 1
        }
    fi

    print_success "pip is available"
}

select_install_type() {
    echo ""
    echo "Select installation type:"
    echo "  1) User installation (recommended) - Install to ~/.local"
    echo "  2) System installation - Install system-wide (requires sudo)"
    echo ""
    read -p "Enter choice [1-2]: " choice

    case $choice in
        1)
            INSTALL_TYPE="user"
            INSTALL_DIR="$HOME/.local"
            print_info "Installing for current user to $INSTALL_DIR"
            ;;
        2)
            INSTALL_TYPE="system"
            INSTALL_DIR="/usr/local"
            print_info "Installing system-wide to $INSTALL_DIR"

            if [ "$EUID" -ne 0 ]; then
                print_error "System installation requires sudo privileges."
                echo "Please run with sudo or choose user installation."
                exit 1
            fi
            ;;
        *)
            print_error "Invalid choice. Exiting."
            exit 1
            ;;
    esac
}

install_package() {
    print_info "Installing Ghostline Studio and dependencies..."

    cd "$SCRIPT_DIR"

    if [ "$INSTALL_TYPE" = "user" ]; then
        $PYTHON_CMD -m pip install --user . || {
            print_error "Installation failed."
            exit 1
        }
    else
        $PYTHON_CMD -m pip install . || {
            print_error "Installation failed."
            exit 1
        }
    fi

    print_success "Package installed successfully"
}

create_launcher() {
    print_info "Creating launcher script..."

    local bin_dir="$INSTALL_DIR/bin"
    local launcher_path="$bin_dir/ghostline"

    mkdir -p "$bin_dir"

    cat > "$launcher_path" << 'EOF'
#!/bin/bash
# Ghostline Studio Launcher

exec python3 -m ghostline.main "$@"
EOF

    chmod +x "$launcher_path"
    print_success "Launcher created at $launcher_path"

    # Add to PATH if user installation and not already in PATH
    if [ "$INSTALL_TYPE" = "user" ]; then
        if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
            print_info "Adding $bin_dir to PATH..."

            # Detect shell and add to appropriate rc file
            if [ -n "$BASH_VERSION" ]; then
                shell_rc="$HOME/.bashrc"
            elif [ -n "$ZSH_VERSION" ]; then
                shell_rc="$HOME/.zshrc"
            else
                shell_rc="$HOME/.profile"
            fi

            echo "" >> "$shell_rc"
            echo "# Added by Ghostline Studio installer" >> "$shell_rc"
            echo "export PATH=\"\$PATH:$bin_dir\"" >> "$shell_rc"

            print_success "Added to PATH in $shell_rc"
            print_info "Please run 'source $shell_rc' or restart your terminal"
        fi
    fi
}

create_desktop_entry() {
    print_info "Creating desktop entry..."

    local desktop_dir
    local icon_dir

    if [ "$INSTALL_TYPE" = "user" ]; then
        desktop_dir="$HOME/.local/share/applications"
        icon_dir="$HOME/.local/share/icons/hicolor/scalable/apps"
    else
        desktop_dir="/usr/share/applications"
        icon_dir="/usr/share/icons/hicolor/scalable/apps"
    fi

    mkdir -p "$desktop_dir"
    mkdir -p "$icon_dir"

    # Create desktop entry
    cat > "$desktop_dir/ghostline-studio.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Ghostline Studio
Comment=AI-Augmented Development Environment
Exec=$INSTALL_DIR/bin/ghostline %F
Icon=ghostline-studio
Terminal=false
Categories=Development;IDE;TextEditor;
MimeType=text/plain;text/x-python;application/x-python;
StartupNotify=true
EOF

    # Create a simple SVG icon if it doesn't exist
    if [ ! -f "$icon_dir/ghostline-studio.svg" ]; then
        cat > "$icon_dir/ghostline-studio.svg" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg width="64" height="64" xmlns="http://www.w3.org/2000/svg">
  <rect width="64" height="64" rx="8" fill="#2E3440"/>
  <text x="50%" y="50%" font-family="monospace" font-size="36" fill="#88C0D0" text-anchor="middle" dominant-baseline="central" font-weight="bold">G</text>
</svg>
EOF
    fi

    # Update desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$desktop_dir" 2>/dev/null || true
    fi

    print_success "Desktop entry created"
}

create_uninstaller() {
    print_info "Creating uninstaller..."

    local uninstall_script="$INSTALL_DIR/bin/ghostline-uninstall"

    cat > "$uninstall_script" << EOF
#!/bin/bash
# Ghostline Studio Uninstaller

set -e

echo "Uninstalling Ghostline Studio..."

# Uninstall Python package
if [ "$INSTALL_TYPE" = "user" ]; then
    python3 -m pip uninstall -y ghostline
else
    python3 -m pip uninstall -y ghostline
fi

# Remove launcher
rm -f "$INSTALL_DIR/bin/ghostline"
rm -f "$INSTALL_DIR/bin/ghostline-uninstall"

# Remove desktop entry
if [ "$INSTALL_TYPE" = "user" ]; then
    rm -f "$HOME/.local/share/applications/ghostline-studio.desktop"
    rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/ghostline-studio.svg"
else
    rm -f "/usr/share/applications/ghostline-studio.desktop"
    rm -f "/usr/share/icons/hicolor/scalable/apps/ghostline-studio.svg"
fi

echo "Ghostline Studio has been uninstalled."
echo "Note: Configuration files in ~/.config/ghostline have been preserved."
echo "To remove them, run: rm -rf ~/.config/ghostline"
EOF

    chmod +x "$uninstall_script"
    print_success "Uninstaller created at $uninstall_script"
}

print_completion() {
    echo ""
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║   Installation Complete!                                  ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "To launch Ghostline Studio:"
    echo "  • From terminal: ghostline"
    echo "  • From application menu: Search for 'Ghostline Studio'"
    echo ""
    echo "Configuration directory: ~/.config/ghostline"
    echo ""
    echo "To uninstall, run: ghostline-uninstall"
    echo ""
    if [ "$INSTALL_TYPE" = "user" ]; then
        echo "Note: You may need to restart your terminal or run:"
        echo "  source ~/.bashrc  (or ~/.zshrc)"
        echo ""
    fi
}

# Main installation flow
main() {
    print_header
    check_python
    check_pip
    select_install_type
    install_package
    create_launcher
    create_desktop_entry
    create_uninstaller
    print_completion
}

# Run main function
main
