#!/bin/bash
#
# Ghostline Studio Linux Installer
# This script installs Ghostline Studio to your system and creates menu entries
# Can be run from terminal or double-clicked in file manager
#

set -e

APP_NAME="Ghostline Studio"
EXECUTABLE_NAME="ghostline-studio"
VERSION="0.1.0"

# Detect if running in a GUI environment
HAS_GUI=false
if [ -n "$DISPLAY" ] && command -v zenity &> /dev/null; then
    HAS_GUI=true
fi

# Function to show messages in GUI or terminal
msg_info() {
    if [ "$HAS_GUI" = true ]; then
        zenity --info --title="$APP_NAME Installer" --text="$1" --width=400 2>/dev/null || true
    else
        echo -e "\033[0;32m$1\033[0m"
    fi
}

msg_error() {
    if [ "$HAS_GUI" = true ]; then
        zenity --error --title="$APP_NAME Installer" --text="$1" --width=400 2>/dev/null || true
    else
        echo -e "\033[0;31mError: $1\033[0m"
    fi
}

msg_question() {
    if [ "$HAS_GUI" = true ]; then
        zenity --question --title="$APP_NAME Installer" --text="$1" --width=400 2>/dev/null
        return $?
    else
        echo -e "\033[1;33m$1 (y/n)\033[0m"
        read -r response
        [[ "$response" =~ ^[Yy]$ ]]
        return $?
    fi
}

# Show welcome message
if [ "$HAS_GUI" = true ]; then
    if ! zenity --question --title="$APP_NAME Installer" \
        --text="Welcome to Ghostline Studio Installer!\n\nVersion: $VERSION\n\nThis will install Ghostline Studio on your system.\n\nDo you want to continue?" \
        --width=400 2>/dev/null; then
        exit 0
    fi
else
    echo -e "\033[0;32m======================================\033[0m"
    echo -e "\033[0;32m  Ghostline Studio Installer\033[0m"
    echo -e "\033[0;32m  Version: ${VERSION}\033[0m"
    echo -e "\033[0;32m======================================\033[0m"
    echo
fi

# Ask user for installation type
INSTALL_TYPE="user"
if [ "$EUID" -eq 0 ]; then
    # Running as root - install system-wide
    INSTALL_DIR="/usr/local/bin"
    DESKTOP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
    INSTALL_TYPE="system"
    msg_info "Installing system-wide for all users"
else
    # Not running as root - ask if user wants to try sudo
    if msg_question "Do you want to install system-wide for all users?\n\n• Yes: Install to /usr/local/bin (requires sudo password)\n• No: Install for current user only to ~/.local/bin"; then
        # Re-run with sudo
        if command -v sudo &> /dev/null; then
            exec sudo bash "$0" "$@"
        else
            msg_error "sudo is not available. Installing for current user only."
            INSTALL_DIR="$HOME/.local/bin"
            DESKTOP_DIR="$HOME/.local/share/applications"
            ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
        fi
    else
        INSTALL_DIR="$HOME/.local/bin"
        DESKTOP_DIR="$HOME/.local/share/applications"
        ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
        msg_info "Installing for current user only"
    fi
fi

# Create directories if they don't exist
mkdir -p "$INSTALL_DIR" 2>/dev/null || true
mkdir -p "$DESKTOP_DIR" 2>/dev/null || true
mkdir -p "$ICON_DIR" 2>/dev/null || true

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if executable exists
if [ ! -f "$SCRIPT_DIR/$EXECUTABLE_NAME" ]; then
    msg_error "$EXECUTABLE_NAME not found in $SCRIPT_DIR\n\nMake sure the executable is in the same directory as this installer."
    exit 1
fi

# Show progress
if [ "$HAS_GUI" = true ]; then
    (
        echo "10" ; echo "# Installing executable..."
        cp "$SCRIPT_DIR/$EXECUTABLE_NAME" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/$EXECUTABLE_NAME"
        sleep 0.5

        echo "40" ; echo "# Creating application menu entry..."
        cat > "$DESKTOP_DIR/ghostline-studio.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Ghostline Studio
Comment=Advanced code editor with AI integration
Exec=$INSTALL_DIR/$EXECUTABLE_NAME %F
Icon=ghostline-studio
Terminal=false
Categories=Development;TextEditor;IDE;
MimeType=text/plain;text/x-python;application/x-python;
Keywords=editor;development;programming;code;ai;
StartupNotify=true
EOF
        chmod +x "$DESKTOP_DIR/ghostline-studio.desktop"
        sleep 0.5

        echo "60" ; echo "# Installing application icon..."
        if [ -f "$SCRIPT_DIR/ghostline-studio.png" ]; then
            cp "$SCRIPT_DIR/ghostline-studio.png" "$ICON_DIR/ghostline-studio.png"
        fi
        sleep 0.5

        echo "80" ; echo "# Updating desktop database..."
        if command -v update-desktop-database &> /dev/null; then
            if [ "$INSTALL_TYPE" = "system" ]; then
                update-desktop-database /usr/share/applications 2>/dev/null || true
            else
                update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
            fi
        fi

        if command -v gtk-update-icon-cache &> /dev/null; then
            if [ "$INSTALL_TYPE" = "system" ]; then
                gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
            else
                gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
            fi
        fi
        sleep 0.5

        echo "100" ; echo "# Installation complete!"
    ) | zenity --progress --title="Installing $APP_NAME" --text="Starting installation..." --percentage=0 --auto-close --width=400 2>/dev/null || true
else
    # Terminal mode - simple output
    echo "Installing executable..."
    cp "$SCRIPT_DIR/$EXECUTABLE_NAME" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/$EXECUTABLE_NAME"

    echo "Creating application menu entry..."
    cat > "$DESKTOP_DIR/ghostline-studio.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Ghostline Studio
Comment=Advanced code editor with AI integration
Exec=$INSTALL_DIR/$EXECUTABLE_NAME %F
Icon=ghostline-studio
Terminal=false
Categories=Development;TextEditor;IDE;
MimeType=text/plain;text/x-python;application/x-python;
Keywords=editor;development;programming;code;ai;
StartupNotify=true
EOF
    chmod +x "$DESKTOP_DIR/ghostline-studio.desktop"

    if [ -f "$SCRIPT_DIR/ghostline-studio.png" ]; then
        echo "Installing application icon..."
        cp "$SCRIPT_DIR/ghostline-studio.png" "$ICON_DIR/ghostline-studio.png"
    fi

    echo "Updating desktop database..."
    if command -v update-desktop-database &> /dev/null; then
        if [ "$INSTALL_TYPE" = "system" ]; then
            update-desktop-database /usr/share/applications 2>/dev/null || true
        else
            update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        fi
    fi

    if command -v gtk-update-icon-cache &> /dev/null; then
        if [ "$INSTALL_TYPE" = "system" ]; then
            gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
        else
            gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
        fi
    fi
fi

# Create uninstaller
UNINSTALL_SCRIPT="$INSTALL_DIR/ghostline-studio-uninstall"
cat > "$UNINSTALL_SCRIPT" << 'UNINSTALL_EOF'
#!/bin/bash
#
# Ghostline Studio Uninstaller
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Uninstalling Ghostline Studio...${NC}"

# Detect installation type
if [ "$EUID" -eq 0 ]; then
    INSTALL_DIR="/usr/local/bin"
    DESKTOP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
else
    INSTALL_DIR="$HOME/.local/bin"
    DESKTOP_DIR="$HOME/.local/share/applications"
    ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
fi

# Remove executable
if [ -f "$INSTALL_DIR/ghostline-studio" ]; then
    rm "$INSTALL_DIR/ghostline-studio"
    echo "Removed executable"
fi

# Remove desktop file
if [ -f "$DESKTOP_DIR/ghostline-studio.desktop" ]; then
    rm "$DESKTOP_DIR/ghostline-studio.desktop"
    echo "Removed desktop entry"
fi

# Remove icon
if [ -f "$ICON_DIR/ghostline-studio.png" ]; then
    rm "$ICON_DIR/ghostline-studio.png"
    echo "Removed icon"
fi

# Remove uninstaller
if [ -f "$INSTALL_DIR/ghostline-studio-uninstall" ]; then
    rm "$INSTALL_DIR/ghostline-studio-uninstall"
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    if [ "$EUID" -eq 0 ]; then
        update-desktop-database /usr/share/applications 2>/dev/null || true
    else
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
fi

echo -e "${GREEN}Ghostline Studio has been uninstalled.${NC}"
echo -e "${YELLOW}Note: User configuration files in ~/.config/ghostline/ were preserved.${NC}"
echo -e "${YELLOW}Remove them manually if desired: rm -rf ~/.config/ghostline/${NC}"
UNINSTALL_EOF

chmod +x "$UNINSTALL_SCRIPT"

# Build success message
SUCCESS_MSG="Installation Complete!\n\nGhostline Studio has been installed successfully.\n\n"
SUCCESS_MSG+="Installed to: $INSTALL_DIR\n\n"
SUCCESS_MSG+="You can now:\n"
SUCCESS_MSG+="• Launch from your application menu (search for 'Ghostline Studio')\n"
SUCCESS_MSG+="• Run from terminal: $EXECUTABLE_NAME\n\n"

if [ "$INSTALL_TYPE" = "user" ]; then
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        SUCCESS_MSG+="\nNote: Add ~/.local/bin to your PATH:\n"
        SUCCESS_MSG+="export PATH=\"\$HOME/.local/bin:\$PATH\"\n"
    fi
    SUCCESS_MSG+="\nTo uninstall, run: $UNINSTALL_SCRIPT"
else
    SUCCESS_MSG+="\nTo uninstall, run: sudo $UNINSTALL_SCRIPT"
fi

# Show success message
if [ "$HAS_GUI" = true ]; then
    zenity --info --title="$APP_NAME - Installation Complete" \
        --text="$SUCCESS_MSG" --width=500 2>/dev/null || true
else
    echo
    echo "======================================"
    echo "  Installation Complete!"
    echo "======================================"
    echo
    echo "Ghostline Studio has been installed to: $INSTALL_DIR"
    echo "Desktop entry created at: $DESKTOP_DIR/ghostline-studio.desktop"
    echo
    echo "You can now:"
    echo "  1. Launch from your application menu (search for 'Ghostline Studio')"
    echo "  2. Run from terminal: $EXECUTABLE_NAME"
    echo
    if [ "$INSTALL_TYPE" = "user" ]; then
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo "Note: $HOME/.local/bin is not in your PATH."
            echo "Add this line to your ~/.bashrc or ~/.zshrc:"
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo
        fi
        echo "To uninstall, run: $UNINSTALL_SCRIPT"
    else
        echo "To uninstall, run: sudo $UNINSTALL_SCRIPT"
    fi
    echo
fi
