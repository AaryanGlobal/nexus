#!/usr/bin/env bash
#===============================================================================
# Hermes-Pi Bridge Self-Seeding Script
#===============================================================================
# Installs this bridge to both Hermes and pi agents from a single monorepo.
#
# Usage:
#   ./scripts/seed.sh           # Normal install
#   ./scripts/seed.sh --dev     # Development (symlinks)
#   ./scripts/seed.sh --uninstall # Remove from both agents
#   ./scripts/seed.sh --hermes-only # Hermes only
#   ./scripts/seed.sh --pi-only     # pi only
#   ./scripts/seed.sh --check   # Check installation status
#
# Exit codes:
#   0 - Success
#   1 - General error
#   2 - Hermes not found
#   3 - pi not found
#   4 - Hermes install failed
#   5 - pi install failed
#===============================================================================

set -euo pipefail

# Colors (disabled if not a terminal)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_PLUGINS_DIR="${HERMES_PLUGINS_DIR:-$HOME/.hermes/plugins}"
HERMES_CONFIG="${HERMES_CONFIG:-$HOME/.hermes/config.yaml}"
PI_SETTINGS="${PI_SETTINGS:-$HOME/.pi/agent/settings.json}"
PI_PACKAGES_DIR="${PI_PACKAGES_DIR:-$HOME/.pi/agent/npm}"

# Plugin name (must match plugin.yaml)
PLUGIN_NAME="hermes-pi-bridge"

#-------------------------------------------------------------------------------
# Utility Functions
#-------------------------------------------------------------------------------

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

die() {
    log_error "$*"
    exit "${2:-1}"
}

# Check if a command exists
has_command() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Hermes is installed
check_hermes() {
    if [[ -d "$HERMES_PLUGINS_DIR" ]] || has_command hermes; then
        return 0
    fi
    return 1
}

# Check if pi is installed
check_pi() {
    if [[ -d "$PI_SETTINGS" ]] || has_command pi; then
        return 0
    fi
    return 1
}

# Get Hermes version
get_hermes_version() {
    if has_command hermes; then
        hermes --version 2>/dev/null || echo "unknown"
    else
        echo "not found"
    fi
}

# Get pi version
get_pi_version() {
    if has_command pi; then
        pi --version 2>/dev/null || echo "unknown"
    else
        echo "not found"
    fi
}

#-------------------------------------------------------------------------------
# Hermes Installation
#-------------------------------------------------------------------------------

install_hermes_plugin() {
    log_info "Installing Hermes plugin..."

    # Check Hermes is available
    if ! check_hermes; then
        log_warn "Hermes not detected. Skipping Hermes plugin."
        return 0
    fi

    # Install core package first (required dependency)
    install_hermes_core

    # Create plugins directory if needed
    mkdir -p "$HERMES_PLUGINS_DIR"

    # Remove existing installation if present
    if [[ -d "$HERMES_PLUGINS_DIR/$PLUGIN_NAME" ]]; then
        if [[ "${DEV_MODE:-}" == "1" ]]; then
            log_info "Updating existing Hermes plugin (symlink mode)..."
        else
            log_info "Removing existing Hermes plugin..."
            rm -rf "$HERMES_PLUGINS_DIR/$PLUGIN_NAME"
        fi
    fi

    if [[ "${DEV_MODE:-}" == "1" ]]; then
        # Development: create symlink
        ln -sfn "$REPO_ROOT/packages/hermes-plugin" "$HERMES_PLUGINS_DIR/$PLUGIN_NAME"
        log_success "Hermes plugin symlinked to $HERMES_PLUGINS_DIR/$PLUGIN_NAME"
    else
        # Production: copy files
        cp -r "$REPO_ROOT/packages/hermes-plugin" "$HERMES_PLUGINS_DIR/$PLUGIN_NAME"
        log_success "Hermes plugin installed to $HERMES_PLUGINS_DIR/$PLUGIN_NAME"
    fi

    # Verify plugin was installed
    if [[ ! -d "$HERMES_PLUGINS_DIR/$PLUGIN_NAME" ]]; then
        log_error "Plugin directory not created"
        return 4
    fi
    
    if [[ ! -f "$HERMES_PLUGINS_DIR/$PLUGIN_NAME/plugin.yaml" ]]; then
        log_error "Plugin verification failed: plugin.yaml not found"
        return 4
    fi

    # Install hermes-plugin package (provides hermes_pi_bridge module)
    log_info "Installing hermes-pi-bridge Python package..."
    local python_cmd="python3"
    if [[ -x "$HOME/.hermes/hermes-agent/venv/bin/python3" ]]; then
        python_cmd="$HOME/.hermes/hermes-agent/venv/bin/python3"
    fi
    if ! $python_cmd -m pip install -e "$REPO_ROOT/packages/hermes-plugin" 2>&1 | tail -3; then
        log_warn "Plugin package install failed, continuing anyway..."
    fi

    # Update Hermes config if needed
    update_hermes_config

    return 0
}

install_hermes_core() {
    log_info "Installing hermes-pi-bridge-core..."
    
    # Find Python executable (prefer Hermes venv)
    local python_cmd="python3"
    if [[ -x "$HOME/.hermes/hermes-agent/venv/bin/python3" ]]; then
        python_cmd="$HOME/.hermes/hermes-agent/venv/bin/python3"
    fi
    
    if [[ "${DEV_MODE:-}" == "1" ]]; then
        # Development: install in editable mode
        if ! $python_cmd -m pip install -e "$REPO_ROOT/packages/core" 2>&1 | tail -3; then
            log_warn "Editable install failed, trying regular install..."
            if ! $python_cmd -m pip install "$REPO_ROOT/packages/core" 2>&1 | tail -3; then
                log_error "Failed to install hermes-pi-bridge-core"
                return 1
            fi
        fi
    else
        # Production: build and install
        if ! $python_cmd -m pip install "$REPO_ROOT/packages/core" 2>&1 | tail -3; then
            log_error "Failed to install hermes-pi-bridge-core"
            return 1
        fi
    fi
    
    # Verify installation (package name is hermes_pi_bridge_core)
    if ! $python_cmd -c "import hermes_pi_bridge_core" 2>/dev/null; then
        log_error "Verification failed: hermes_pi_bridge_core not importable"
        return 1
    fi
    
    log_success "hermes-pi-bridge-core installed"
    return 0
}

update_hermes_config() {
    local config_line="  - $PLUGIN_NAME"
    local settings_content="hermes_pi_bridge:
  # pi HTTP server URL
  pi_url: \"http://localhost:2719\"
  # Authentication token (optional)
  auth_token: \"\"
  # Max concurrent tasks
  max_concurrent: 2
  # Default timeout (seconds)
  timeout_seconds: 300"

    # Check if plugin is already in config
    if [[ -f "$HERMES_CONFIG" ]]; then
        if grep -q "^  - $PLUGIN_NAME$" "$HERMES_CONFIG" 2>/dev/null; then
            log_info "Hermes plugin already in config"
        else
            log_info "Adding plugin to $HERMES_CONFIG..."
            # Add to plugins list (before first non-comment/non-empty line or at end)
            if grep -q "^plugins:" "$HERMES_CONFIG"; then
                # Insert after plugins: line
                sed -i "/^plugins:/a$config_line" "$HERMES_CONFIG"
            else
                echo -e "\nplugins:\n$config_line" >> "$HERMES_CONFIG"
            fi
        fi

        # Add bridge settings if not present
        if grep -q "^hermes_pi_bridge:" "$HERMES_CONFIG"; then
            log_info "Bridge settings already in config"
        else
            echo -e "\n$settings_content" >> "$HERMES_CONFIG"
        fi
    else
        log_info "Creating new Hermes config at $HERMES_CONFIG..."
        cat > "$HERMES_CONFIG" <<EOF
plugins:
$config_line

$settings_content
EOF
    fi

    log_success "Hermes config updated"
}

uninstall_hermes_plugin() {
    log_info "Uninstalling Hermes plugin..."

    if [[ -d "$HERMES_PLUGINS_DIR/$PLUGIN_NAME" ]]; then
        rm -rf "$HERMES_PLUGINS_DIR/$PLUGIN_NAME"
        log_success "Hermes plugin removed"
    else
        log_warn "Hermes plugin not found at $HERMES_PLUGINS_DIR/$PLUGIN_NAME"
    fi

    # Remove from config
    if [[ -f "$HERMES_CONFIG" ]]; then
        sed -i "/^  - $PLUGIN_NAME$/d" "$HERMES_CONFIG" 2>/dev/null || true
        sed -i "/^hermes_pi_bridge:/,/^[^ ]/{ /^hermes_pi_bridge:/d; /^  - /!{ /^[^ ]/q; d; }; }" "$HERMES_CONFIG" 2>/dev/null || true
        log_success "Hermes config updated"
    fi
}

#-------------------------------------------------------------------------------
# pi Installation
#-------------------------------------------------------------------------------

install_pi_extension() {
    log_info "Installing pi extension..."

    # Check pi is available
    if ! check_pi; then
        log_warn "pi not detected. Skipping pi extension."
        return 0
    fi

    # Ensure packages directory exists
    mkdir -p "$PI_PACKAGES_DIR"

    # Remove existing installation first to fix "cannot overwrite directory" error
    if [[ -L "$PI_PACKAGES_DIR/$PLUGIN_NAME" ]] || [[ -d "$PI_PACKAGES_DIR/$PLUGIN_NAME" ]]; then
        rm -rf "$PI_PACKAGES_DIR/$PLUGIN_NAME"
    fi
    
    if [[ "${DEV_MODE:-}" == "1" ]]; then
        # Development: create symlink
        ln -sfn "$REPO_ROOT/packages/pi-extension" "$PI_PACKAGES_DIR/$PLUGIN_NAME"
        log_success "pi extension symlinked to $PI_PACKAGES_DIR/$PLUGIN_NAME"
    else
        # Production: npm pack and install
        cd "$REPO_ROOT/packages/pi-extension"
        
        # Build if needed
        if [[ ! -d "dist" ]]; then
            log_info "Building pi extension..."
            if ! npm install 2>&1 | tail -5; then
                log_error "npm install failed"
                return 5
            fi
            if ! npm run build 2>&1 | tail -5; then
                log_error "npm build failed"
                return 5
            fi
        fi
        
        # Install to pi packages dir
        cp -r "$REPO_ROOT/packages/pi-extension" "$PI_PACKAGES_DIR/$PLUGIN_NAME"
        log_success "pi extension installed to $PI_PACKAGES_DIR/$PLUGIN_NAME"
        
        cd "$REPO_ROOT"
    fi

    # Verify TypeScript extension can be loaded
    if [[ -f "$PI_PACKAGES_DIR/$PLUGIN_NAME/dist/index.js" ]]; then
        log_success "pi extension verified"
    else
        log_error "pi extension verification failed: dist/index.js not found"
        return 5
    fi

    # Update pi settings
    update_pi_settings

    return 0
}

update_pi_settings() {
    local package_entry="\"$PLUGIN_NAME\""
    
    # Create settings file if it doesn't exist
    if [[ ! -f "$PI_SETTINGS" ]]; then
        mkdir -p "$(dirname "$PI_SETTINGS")"
        cat > "$PI_SETTINGS" <<EOF
{
  "packages": []
}
EOF
    fi

    # Check if package is already in settings
    if grep -q "\"$PLUGIN_NAME\"" "$PI_SETTINGS" 2>/dev/null; then
        log_info "pi extension already in settings"
    else
        log_info "Adding extension to $PI_SETTINGS..."
        # Add to packages array using Python for reliable JSON manipulation
        python3 -c "
import json
import sys

try:
    with open('$PI_SETTINGS', 'r') as f:
        settings = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    settings = {'packages': []}

if 'packages' not in settings:
    settings['packages'] = []
    
if '$PLUGIN_NAME' not in settings['packages']:
    settings['packages'].append('$PLUGIN_NAME')

with open('$PI_SETTINGS', 'w') as f:
    json.dump(settings, f, indent=2)
"
        log_success "pi settings updated"
    fi

    # Add bridge config if not present
    if ! grep -q "\"hermesBridge\"" "$PI_SETTINGS" 2>/dev/null; then
        python3 -c "
import json

try:
    with open('$PI_SETTINGS', 'r') as f:
        settings = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    settings = {}

settings['hermesBridge'] = {
    'hermesUrl': 'http://localhost:8080',
    'authToken': ''
}

with open('$PI_SETTINGS', 'w') as f:
    json.dump(settings, f, indent=2)
"
        log_success "pi bridge config added"
    fi
}

uninstall_pi_extension() {
    log_info "Uninstalling pi extension..."

    if [[ -d "$PI_PACKAGES_DIR/$PLUGIN_NAME" ]]; then
        rm -rf "$PI_PACKAGES_DIR/$PLUGIN_NAME"
        log_success "pi extension removed"
    else
        log_warn "pi extension not found at $PI_PACKAGES_DIR/$PLUGIN_NAME"
    fi

    # Remove from settings
    if [[ -f "$PI_SETTINGS" ]]; then
        python3 -c "
import json

try:
    with open('$PI_SETTINGS', 'r') as f:
        settings = json.load(f)
    
    if 'packages' in settings and '$PLUGIN_NAME' in settings['packages']:
        settings['packages'].remove('$PLUGIN_NAME')
    
    with open('$PI_SETTINGS', 'w') as f:
        json.dump(settings, f, indent=2)
except Exception as e:
    pass
"
        log_success "pi settings updated"
    fi
}

#-------------------------------------------------------------------------------
# Status Check
#-------------------------------------------------------------------------------

check_status() {
    echo ""
    echo "=============================================="
    echo "        Hermes-Pi Bridge Installation         "
    echo "=============================================="
    echo ""
    
    echo "Repository: $REPO_ROOT"
    echo "Version: 1.0.0"
    echo ""
    
    echo "┌─────────────────────────────────────────────┐"
    echo "│ Hermes                                      │"
    echo "├─────────────────────────────────────────────┤"
    echo -e "│ Version:     $(get_hermes_version)" | sed 's/ *$//'
    echo -e "│ Plugins Dir: $HERMES_PLUGINS_DIR"
    
    if [[ -d "$HERMES_PLUGINS_DIR/$PLUGIN_NAME" ]]; then
        echo -e "│ Status:      ${GREEN}INSTALLED${NC} ✓"
    else
        echo -e "│ Status:      ${RED}NOT INSTALLED${NC}"
    fi
    echo "└─────────────────────────────────────────────┘"
    
    echo ""
    echo "┌─────────────────────────────────────────────┐"
    echo "│ pi                                          │"
    echo "├─────────────────────────────────────────────┤"
    echo -e "│ Version:     $(get_pi_version)" | sed 's/ *$//'
    echo -e "│ Packages:    $PI_PACKAGES_DIR"
    
    if [[ -d "$PI_PACKAGES_DIR/$PLUGIN_NAME" ]]; then
        echo -e "│ Status:      ${GREEN}INSTALLED${NC} ✓"
    else
        echo -e "│ Status:      ${RED}NOT INSTALLED${NC}"
    fi
    echo "└─────────────────────────────────────────────┘"
    echo ""
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------

usage() {
    cat <<EOF
Hermes-Pi Bridge Self-Seeding Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --check         Check installation status
    --dev           Development mode (symlinks instead of copies)
    --hermes-only   Install Hermes plugin only
    --pi-only       Install pi extension only
    --uninstall     Remove from both agents
    -h, --help      Show this help

EXAMPLES:
    $0               # Normal install to both agents
    $0 --dev         # Development install (symlinks)
    $0 --check       # Check what's installed
    $0 --uninstall   # Remove from both agents

EXIT CODES:
    0 - Success
    1 - General error
    2 - Hermes not found (warning only)
    3 - pi not found (warning only)
EOF
}

main() {
    local hermes_only=false
    local pi_only=false
    local uninstall=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --check)
                check_status
                exit 0
                ;;
            --dev)
                DEV_MODE=1
                log_info "Development mode: using symlinks"
                shift
                ;;
            --hermes-only)
                hermes_only=true
                shift
                ;;
            --pi-only)
                pi_only=true
                shift
                ;;
            --uninstall)
                uninstall=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # Verify we're in the right directory
    if [[ ! -f "$REPO_ROOT/SPEC.md" ]]; then
        die "Not a hermes-pi-bridge repository. Run from the repository root."
    fi

    if [[ "$uninstall" == "true" ]]; then
        echo ""
        log_warn "Uninstalling Hermes-Pi Bridge..."
        echo ""
        uninstall_hermes_plugin 2>/dev/null || true
        uninstall_pi_extension 2>/dev/null || true
        echo ""
        log_success "Uninstallation complete"
        exit 0
    fi

    echo ""
    echo "=============================================="
    echo "      Hermes-Pi Bridge Installation          "
    echo "=============================================="
    echo ""
    log_info "Repository: $REPO_ROOT"
    
    # Validate prerequisites
    local hermes_ok=false
    local pi_ok=false
    
    if check_hermes; then
        hermes_ok=true
        log_success "Hermes detected: $(get_hermes_version)"
    else
        log_warn "Hermes not detected. Will install Hermes plugin anyway (may fail)."
    fi
    
    if check_pi; then
        pi_ok=true
        log_success "pi detected: $(get_pi_version)"
    else
        log_warn "pi not detected. Will install pi extension anyway (may fail)."
    fi

    echo ""
    
    # Install
    local exit_code=0
    
    if [[ "$pi_only" != "true" ]]; then
        install_hermes_plugin || exit_code=4
    fi
    
    if [[ "$hermes_only" != "true" ]]; then
        install_pi_extension || exit_code=5
    fi

    echo ""
    echo "=============================================="
    echo "           Installation Complete              "
    echo "=============================================="
    echo ""
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "Hermes-Pi Bridge installed successfully!"
    else
        log_warn "Installation completed with some errors"
    fi
    
    echo ""
    log_info "Next steps:"
    echo "  1. Edit config: nano ~/.hermes/config.yaml"
    echo "  2. Restart Hermes: hermes"
    echo "  3. Restart pi: pi"
    echo ""
    
    exit $exit_code
}

main "$@"
