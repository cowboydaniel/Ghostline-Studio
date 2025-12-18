#!/bin/bash
#
# Ghostline Studio Linux Installer
# This script installs Ghostline Studio to your system and creates menu entries
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

APP_NAME="Ghostline Studio"
EXECUTABLE_NAME="ghostline-studio"
VERSION="0.1.0"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Ghostline Studio Installer${NC}"
echo -e "${GREEN}  Version: ${VERSION}${NC}"
echo -e "${GREEN}======================================${NC}"
echo

# Detect if running as root
if [ "$EUID" -eq 0 ]; then
    INSTALL_DIR="/usr/local/bin"
    DESKTOP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
    INSTALL_TYPE="system"
    echo -e "${YELLOW}Installing system-wide (requires root)${NC}"
else
    INSTALL_DIR="$HOME/.local/bin"
    DESKTOP_DIR="$HOME/.local/share/applications"
    ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
    INSTALL_TYPE="user"
    echo -e "${YELLOW}Installing for current user only${NC}"
fi

echo

# Create directories if they don't exist
echo "Creating installation directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DIR"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if executable exists
if [ ! -f "$SCRIPT_DIR/$EXECUTABLE_NAME" ]; then
    echo -e "${RED}Error: $EXECUTABLE_NAME not found in $SCRIPT_DIR${NC}"
    echo "Make sure the executable is in the same directory as this installer."
    exit 1
fi

# Install executable
echo "Installing executable to $INSTALL_DIR..."
cp "$SCRIPT_DIR/$EXECUTABLE_NAME" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/$EXECUTABLE_NAME"

# Create .desktop file
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

# Install icon if available
if [ -f "$SCRIPT_DIR/app-icon.png" ]; then
    echo "Installing application icon..."
    cp "$SCRIPT_DIR/app-icon.png" "$ICON_DIR/ghostline-studio.png"
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    echo "Updating desktop database..."
    if [ "$INSTALL_TYPE" = "system" ]; then
        update-desktop-database /usr/share/applications 2>/dev/null || true
    else
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
fi

# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    echo "Updating icon cache..."
    if [ "$INSTALL_TYPE" = "system" ]; then
        gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    else
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
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

# Add to PATH if needed (for user installation)
if [ "$INSTALL_TYPE" = "user" ]; then
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo
        echo -e "${YELLOW}Note: $HOME/.local/bin is not in your PATH.${NC}"
        echo "Add this line to your ~/.bashrc or ~/.zshrc:"
        echo -e "${GREEN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
        echo
    fi
fi

echo
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo
echo "Ghostline Studio has been installed to: $INSTALL_DIR"
echo "Desktop entry created at: $DESKTOP_DIR/ghostline-studio.desktop"
echo
echo "You can now:"
echo "  1. Launch from your application menu (search for 'Ghostline Studio')"
echo "  2. Run from terminal: $EXECUTABLE_NAME"
echo
echo "To uninstall, run: $([ "$INSTALL_TYPE" = "system" ] && echo "sudo ")$UNINSTALL_SCRIPT"
echo
