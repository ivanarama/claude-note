#!/bin/bash
# claude-note uninstaller
# Removes service and uv-installed tool
# Does NOT remove vault data or config (user decides)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Claude Note Uninstaller"
echo "======================="
echo ""

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Darwin) OS_TYPE="macos" ;;
    Linux)  OS_TYPE="linux" ;;
    *)      echo -e "${RED}Unsupported OS: $OS${NC}"; exit 1 ;;
esac

echo "Detected: $OS_TYPE"
echo ""

# ============================================================================
# Step 1: Stop and remove service
# ============================================================================
echo "Step 1: Stopping and removing service..."

if [ "$OS_TYPE" = "macos" ]; then
    PLIST="$HOME/Library/LaunchAgents/com.claude-note.worker.plist"
    if [ -f "$PLIST" ]; then
        echo "  Stopping launchd service..."
        launchctl unload "$PLIST" 2>/dev/null || true
        rm "$PLIST"
        echo -e "  ${GREEN}✓ Removed launchd service${NC}"
    else
        echo "  No launchd service found"
    fi
else
    SERVICE="$HOME/.config/systemd/user/claude-note.service"
    if [ -f "$SERVICE" ]; then
        echo "  Stopping systemd service..."
        systemctl --user stop claude-note 2>/dev/null || true
        systemctl --user disable claude-note 2>/dev/null || true
        rm "$SERVICE"
        systemctl --user daemon-reload
        echo -e "  ${GREEN}✓ Removed systemd service${NC}"
    else
        echo "  No systemd service found"
    fi
fi

# ============================================================================
# Step 2: Uninstall with uv
# ============================================================================
echo ""
echo "Step 2: Removing claude-note..."

if command -v uv &>/dev/null; then
    if uv tool list 2>/dev/null | grep -q "claude-note"; then
        uv tool uninstall claude-note
        echo -e "  ${GREEN}✓ Uninstalled claude-note via uv${NC}"
    else
        echo "  claude-note not found in uv tools"
        # Check for legacy CLI shim
        CLI_PATH="$HOME/.local/bin/claude-note"
        if [ -f "$CLI_PATH" ]; then
            rm "$CLI_PATH"
            echo -e "  ${GREEN}✓ Removed legacy CLI at $CLI_PATH${NC}"
        fi
    fi
else
    echo -e "  ${YELLOW}uv not found, checking for legacy installation...${NC}"
    # Remove legacy CLI shim if it exists
    CLI_PATH="$HOME/.local/bin/claude-note"
    if [ -f "$CLI_PATH" ]; then
        rm "$CLI_PATH"
        echo -e "  ${GREEN}✓ Removed $CLI_PATH${NC}"
    else
        echo "  No CLI found at $CLI_PATH"
    fi
fi

# ============================================================================
# Step 3: Remove legacy source directory (if exists from old installation)
# ============================================================================
echo ""
echo "Step 3: Cleaning up legacy files..."

SRC_DIR="$HOME/.local/share/claude-note"
if [ -d "$SRC_DIR" ]; then
    rm -rf "$SRC_DIR"
    echo -e "  ${GREEN}✓ Removed legacy source directory $SRC_DIR${NC}"
else
    echo "  No legacy source directory found"
fi

# ============================================================================
# Step 4: Ask about config
# ============================================================================
echo ""
echo "Step 4: Configuration cleanup..."

CONFIG_DIR="$HOME/.config/claude-note"
if [ -d "$CONFIG_DIR" ]; then
    echo -e "${YELLOW}Config directory found: $CONFIG_DIR${NC}"
    read -p "Remove config directory? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo -e "  ${GREEN}✓ Removed config${NC}"
    else
        echo "  Keeping config"
    fi
else
    echo "  No config directory found"
fi

# ============================================================================
# Done
# ============================================================================
echo ""
echo -e "${GREEN}Uninstall complete!${NC}"
echo ""
echo "Note: Your vault data was NOT removed."
echo "If you want to remove claude-note data from your vault, manually delete:"
echo "  - .claude-note/ directory in your vault"
echo "  - claude-session-*.md files (session logs)"
echo "  - claude-note-inbox.md (if you want to remove synthesized content)"
echo ""
