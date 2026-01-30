#!/usr/bin/env bash
#
# Claude Note Installer
#
# Installs claude-note for session logging with Claude Code.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/YOU/claude-note/main/install.sh | bash
#   # or
#   ./install.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation paths
INSTALL_DIR="${HOME}/.local/share/claude-note"
BIN_DIR="${HOME}/.local/bin"
CONFIG_DIR="${HOME}/.config/claude-note"
REPO_URL="https://github.com/YOU/claude-note.git"  # Update with actual repo

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)     OS_TYPE=linux;;
    Darwin*)    OS_TYPE=macos;;
    *)          OS_TYPE=unknown;;
esac

# ASCII Art Banner
echo
echo -e "${RED}  ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗${NC}"
echo -e "${RED} ██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝${NC}"
echo -e "${RED} ██║     ██║     ███████║██║   ██║██║  ██║█████╗  ${NC}"
echo -e "${RED} ██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝  ${NC}"
echo -e "${RED} ╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗${NC}"
echo -e "${RED}  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝${NC}"
echo -e "${GREEN} ███╗   ██╗ ██████╗ ████████╗███████╗${NC}"
echo -e "${GREEN} ████╗  ██║██╔═══██╗╚══██╔══╝██╔════╝${NC}"
echo -e "${GREEN} ██╔██╗ ██║██║   ██║   ██║   █████╗  ${NC}"
echo -e "${GREEN} ██║╚██╗██║██║   ██║   ██║   ██╔══╝  ${NC}"
echo -e "${GREEN} ██║ ╚████║╚██████╔╝   ██║   ███████╗${NC}"
echo -e "${GREEN} ╚═╝  ╚═══╝ ╚═════╝    ╚═╝   ╚══════╝${NC}"
echo
echo -e "  ${BLUE}>${NC} ${GREEN}\$ ./install.sh${NC} ... ${GREEN}OK${NC}"
echo

# =============================================================================
# Preflight Checks
# =============================================================================

echo -e "${BLUE}[1/7]${NC} Checking requirements..."

# Find Python 3.11+ (check versioned commands first, then generic python3)
PYTHON_CMD=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 11 ]]; then
            PYTHON_CMD="$cmd"
            PYTHON_VERSION="$version"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo -e "${RED}Error: Python 3.11+ required${NC}"
    echo "Please install Python 3.11 or newer."
    echo
    if [[ "$OS_TYPE" == "macos" ]]; then
        echo "On macOS: brew install python@3.11"
    else
        echo "On Linux: Check your package manager or https://python.org"
    fi
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION ($PYTHON_CMD)"

# Check Claude CLI (warn but continue)
if command -v claude &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Claude CLI found"
    CLAUDE_AVAILABLE=true
else
    echo -e "  ${YELLOW}!${NC} Claude CLI not found (synthesis will be disabled)"
    echo "    Install from: https://claude.ai/download"
    CLAUDE_AVAILABLE=false
fi

# Check git
if ! command -v git &>/dev/null; then
    echo -e "${RED}Error: git is required${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} git found"

# Check qmd (optional but recommended)
if command -v qmd &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} qmd found (semantic search enabled)"
    QMD_AVAILABLE=true
else
    echo -e "  ${YELLOW}!${NC} qmd not found (semantic search disabled)"
    echo "    Synthesis will work but without vault context."
    echo "    Install qmd for better results: https://github.com/tobi/qmd"
    echo
    read -p "    Continue without qmd? [Y/n] " CONTINUE_NO_QMD
    if [[ "$CONTINUE_NO_QMD" =~ ^[Nn] ]]; then
        echo "Install qmd first, then re-run this installer."
        exit 0
    fi
    QMD_AVAILABLE=false
fi

# =============================================================================
# Get Vault Path
# =============================================================================

echo
echo -e "${BLUE}[2/7]${NC} Configuring vault..."

# Check for existing config
if [[ -f "${CONFIG_DIR}/config.toml" ]]; then
    EXISTING_VAULT=$(grep -E '^vault_root\s*=' "${CONFIG_DIR}/config.toml" 2>/dev/null | sed 's/.*=\s*"\?\([^"]*\)"\?/\1/' || true)
    if [[ -n "$EXISTING_VAULT" ]]; then
        echo -e "  Found existing config: ${EXISTING_VAULT}"
        read -p "  Use this vault? [Y/n] " USE_EXISTING
        if [[ -z "$USE_EXISTING" || "$USE_EXISTING" =~ ^[Yy] ]]; then
            VAULT_PATH="$EXISTING_VAULT"
        fi
    fi
fi

# Prompt for vault path if not set
if [[ -z "$VAULT_PATH" ]]; then
    echo "  Enter the path to your Obsidian vault (or notes directory):"
    read -p "  Vault path: " VAULT_PATH

    # Expand ~ to home directory
    VAULT_PATH="${VAULT_PATH/#\~/$HOME}"

    if [[ ! -d "$VAULT_PATH" ]]; then
        read -p "  Directory doesn't exist. Create it? [Y/n] " CREATE_DIR
        if [[ -z "$CREATE_DIR" || "$CREATE_DIR" =~ ^[Yy] ]]; then
            mkdir -p "$VAULT_PATH"
            echo -e "  ${GREEN}✓${NC} Created $VAULT_PATH"
        else
            echo -e "${RED}Error: Vault directory required${NC}"
            exit 1
        fi
    fi
fi

echo -e "  ${GREEN}✓${NC} Vault: $VAULT_PATH"

# =============================================================================
# Install Source Code
# =============================================================================

echo
echo -e "${BLUE}[3/7]${NC} Installing claude-note..."

# Create install directory
mkdir -p "$INSTALL_DIR"

# Clone or update repo
if [[ -d "${INSTALL_DIR}/.git" ]]; then
    echo "  Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet
else
    # Check if we're running from the repo itself
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "${SCRIPT_DIR}/src/claude_note/cli.py" ]]; then
        echo "  Copying from local directory..."
        cp -r "${SCRIPT_DIR}"/* "$INSTALL_DIR/"
    else
        echo "  Cloning repository..."
        git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    fi
fi

echo -e "  ${GREEN}✓${NC} Installed to $INSTALL_DIR"

# =============================================================================
# Create CLI Shim
# =============================================================================

echo
echo -e "${BLUE}[4/7]${NC} Creating CLI shim..."

mkdir -p "$BIN_DIR"

# Get full path to Python for launchd/systemd compatibility
PYTHON_FULL_PATH=$(command -v "$PYTHON_CMD")

cat > "${BIN_DIR}/claude-note" << SHIM
#!/usr/bin/env bash
# Claude Note CLI shim
INSTALL_DIR="\${HOME}/.local/share/claude-note"
export PYTHONPATH="\${INSTALL_DIR}/src"

# Only read stdin if it's piped (not a terminal)
if [ -t 0 ]; then
    exec ${PYTHON_FULL_PATH} -m claude_note.cli "\$@"
else
    exec ${PYTHON_FULL_PATH} -m claude_note.cli "\$@" <<< "\$(cat)"
fi
SHIM

# Make it executable
chmod +x "${BIN_DIR}/claude-note"

# Create Python-importable entry point
cat > "${INSTALL_DIR}/src/claude_note/__main__.py" << 'MAIN'
#!/usr/bin/env python3
"""Entry point for python -m claude_note."""
from .cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
MAIN

echo -e "  ${GREEN}✓${NC} CLI at ${BIN_DIR}/claude-note"

# Check if BIN_DIR is in PATH
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    echo -e "  ${YELLOW}!${NC} Add ${BIN_DIR} to your PATH:"
    echo "    export PATH=\"\$PATH:${BIN_DIR}\""
fi

# =============================================================================
# Write Configuration
# =============================================================================

echo
echo -e "${BLUE}[5/7]${NC} Writing configuration..."

mkdir -p "$CONFIG_DIR"

# Determine synthesis mode
if [[ "$CLAUDE_AVAILABLE" == true ]]; then
    SYNTH_MODE="route"
else
    SYNTH_MODE="log"
fi

cat > "${CONFIG_DIR}/config.toml" << EOF
# Claude Note Configuration
# See docs/configuration.md for all options

vault_root = "${VAULT_PATH}"

# Synthesis mode: log | inbox | route
# - log: Session logging only, no synthesis
# - inbox: Synthesize and append to inbox
# - route: Full synthesis with note creation/updates
[synthesis]
mode = "${SYNTH_MODE}"
model = "claude-sonnet-4-5-20250929"

# QMD semantic search (optional, requires qmd tool)
[qmd]
enabled = ${QMD_AVAILABLE}
synth_max_notes = 5
EOF

echo -e "  ${GREEN}✓${NC} Config at ${CONFIG_DIR}/config.toml"

# =============================================================================
# Initialize Vault Structure
# =============================================================================

echo
echo -e "${BLUE}[6/7]${NC} Initializing vault structure..."

# Create .claude-note directories
mkdir -p "${VAULT_PATH}/.claude-note/queue"
mkdir -p "${VAULT_PATH}/.claude-note/state"
mkdir -p "${VAULT_PATH}/.claude-note/logs"

echo -e "  ${GREEN}✓${NC} Created .claude-note/ directories"

# Optionally copy template files
TEMPLATE_DIR="${INSTALL_DIR}/vault-template"
if [[ -d "$TEMPLATE_DIR" ]]; then
    read -p "  Copy starter templates to vault? [Y/n] " COPY_TEMPLATES
    if [[ -z "$COPY_TEMPLATES" || "$COPY_TEMPLATES" =~ ^[Yy] ]]; then
        # Copy CLAUDE.md if it doesn't exist
        if [[ ! -f "${VAULT_PATH}/CLAUDE.md" ]]; then
            cp "${TEMPLATE_DIR}/CLAUDE.md" "${VAULT_PATH}/"
            echo -e "  ${GREEN}✓${NC} Created CLAUDE.md"
        fi

        # Copy inbox if it doesn't exist
        if [[ ! -f "${VAULT_PATH}/claude-note-inbox.md" ]]; then
            cp "${TEMPLATE_DIR}/claude-note-inbox.md" "${VAULT_PATH}/"
            echo -e "  ${GREEN}✓${NC} Created claude-note-inbox.md"
        fi

        # Copy open-questions.md if it doesn't exist
        if [[ ! -f "${VAULT_PATH}/open-questions.md" ]]; then
            cp "${TEMPLATE_DIR}/open-questions.md" "${VAULT_PATH}/"
            echo -e "  ${GREEN}✓${NC} Created open-questions.md"
        fi

        # Copy templates directory
        if [[ ! -d "${VAULT_PATH}/templates" ]]; then
            cp -r "${TEMPLATE_DIR}/templates" "${VAULT_PATH}/"
            echo -e "  ${GREEN}✓${NC} Created templates/"
        fi
    fi
fi

# =============================================================================
# Setup Service
# =============================================================================

echo
echo -e "${BLUE}[7/7]${NC} Setting up background worker..."

SERVICE_DIR="${INSTALL_DIR}/service"

if [[ "$OS_TYPE" == "macos" ]]; then
    # macOS launchd setup
    PLIST_NAME="com.claude-note.worker"
    PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_NAME}.plist"

    mkdir -p "${HOME}/Library/LaunchAgents"

    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${BIN_DIR}/claude-note</string>
        <string>worker</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${VAULT_PATH}/.claude-note/logs/worker-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${VAULT_PATH}/.claude-note/logs/worker-stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${INSTALL_DIR}/src</string>
        <key>PATH</key>
        <string>${BIN_DIR}:${HOME}/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

    # Load the service
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load "$PLIST_PATH"

    echo -e "  ${GREEN}✓${NC} Service installed and started"
    echo "  Commands:"
    echo "    launchctl stop ${PLIST_NAME}   # Stop worker"
    echo "    launchctl start ${PLIST_NAME}  # Start worker"

elif [[ "$OS_TYPE" == "linux" ]]; then
    # Linux systemd setup
    SERVICE_PATH="${HOME}/.config/systemd/user/claude-note.service"

    mkdir -p "${HOME}/.config/systemd/user"

    cat > "$SERVICE_PATH" << EOF
[Unit]
Description=Claude Note Background Worker
After=network.target

[Service]
Type=simple
ExecStart=${BIN_DIR}/claude-note worker
Restart=always
RestartSec=5
Environment=PYTHONPATH=${INSTALL_DIR}/src

[Install]
WantedBy=default.target
EOF

    # Reload and start the service
    systemctl --user daemon-reload
    systemctl --user enable claude-note.service
    systemctl --user start claude-note.service

    echo -e "  ${GREEN}✓${NC} Service installed and started"
    echo "  Commands:"
    echo "    systemctl --user stop claude-note    # Stop worker"
    echo "    systemctl --user start claude-note   # Start worker"
    echo "    systemctl --user status claude-note  # Check status"
else
    echo -e "  ${YELLOW}!${NC} Unknown OS - skipping service setup"
    echo "  Run manually: claude-note worker"
fi

# =============================================================================
# Final Instructions
# =============================================================================

echo
echo -e "${GREEN}"
cat << 'BANNER'
  ╔═══════════════════════════════════════════╗
  ║  ✓ INSTALLATION COMPLETE                  ║
  ║    claude-note is ready to capture        ║
  ║    knowledge from your sessions  ✎        ║
  ╚═══════════════════════════════════════════╝
BANNER
echo -e "${NC}"
echo -e "${BLUE}> Next steps:${NC}"
echo
echo "1. Add hooks to Claude Code (~/.claude/settings.json):"
echo
echo '   "hooks": {'
echo '     "PostToolUse": [{ "hooks": [{ "type": "command", "command": "claude-note enqueue", "timeout": 5000 }] }],'
echo '     "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "claude-note enqueue", "timeout": 5000 }] }],'
echo '     "Stop": [{ "hooks": [{ "type": "command", "command": "claude-note enqueue", "timeout": 5000 }] }]'
echo '   }'
echo
echo "2. Check status:"
echo "   claude-note status"
echo
echo "3. View logs:"
echo "   tail -f ${VAULT_PATH}/.claude-note/logs/worker-*.log"
echo
echo "Documentation: ${INSTALL_DIR}/docs/"
echo
