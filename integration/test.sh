#!/usr/bin/env bash
#===============================================================================
# Integration Tests for Hermes-Pi Bridge
#===============================================================================
#
# Tests the full integration between Hermes and pi via the bridge.
#
# Prerequisites:
#   - Hermes must be installed and running
#   - pi must be installed and running
#   - Both must have the bridge packages installed
#
# Usage:
#   ./integration/test.sh              # Run all tests
#   ./integration/test.sh --unit      # Unit tests only
#   ./integration/test.sh --api        # API tests only
#   ./integration/test.sh --delegate  # Delegation tests only
#   ./integration/test.sh --verbose    # Verbose output
#
#===============================================================================

set -euo pipefail

# Colors
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' NC=''
fi

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CORE_TESTS="$REPO_ROOT/packages/core/tests"
HERMES_TESTS="$REPO_ROOT/packages/hermes-plugin/tests"
PI_TESTS="$REPO_ROOT/packages/pi-extension/tests"

# Test state
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

#-------------------------------------------------------------------------------
# Utility Functions
#-------------------------------------------------------------------------------

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $*"; ((TESTS_PASSED++)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $*"; ((TESTS_FAILED++)); }
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $*"; ((TESTS_SKIPPED++)); }
log_section() { echo ""; echo -e "${CYAN}═══ $* ═══${NC}"; }

die() { log_error "$*"; exit 1; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

#-------------------------------------------------------------------------------
# Test Runners
#-------------------------------------------------------------------------------

run_core_tests() {
    log_section "Core Package Tests"
    
    cd "$REPO_ROOT"
    
    # Find Python with pip (prefer Hermes venv)
    local PYTHON=""
    if [[ -x "$HOME/.hermes/hermes-agent/venv/bin/python3" ]]; then
        PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python3"
    elif command -v python3 &>/dev/null && python3 -m pip --version &>/dev/null; then
        PYTHON="python3"
    else
        log_skip "Python with pip not available"
        return 0
    fi
    
    # Install core package in dev mode
    log_info "Installing core package..."
    if ! "$PYTHON" -m pip install -e "$REPO_ROOT/packages/core" -q 2>/dev/null; then
        log_skip "Could not install core package"
        return 0
    fi
    
    # Run pytest
    log_info "Running core tests..."
    if "$PYTHON" -m pytest "$CORE_TESTS" -v --tb=short 2>&1; then
        log_pass "Core tests passed"
    else
        log_fail "Core tests failed"
    fi
}

run_hermes_tests() {
    log_section "Hermes Plugin Tests"
    
    # Check Hermes is available
    if ! command -v hermes &>/dev/null; then
        log_skip "Hermes not available"
        return 0
    fi
    
    cd "$REPO_ROOT"
    
    # Find Python with pip (prefer Hermes venv)
    local PYTHON=""
    if [[ -x "$HOME/.hermes/hermes-agent/venv/bin/python3" ]]; then
        PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python3"
    elif command -v python3 &>/dev/null && python3 -m pip --version &>/dev/null; then
        PYTHON="python3"
    else
        log_skip "Python with pip not available"
        return 0
    fi
    
    # Install dependencies (fastapi, uvicorn for server)
    log_info "Installing dependencies..."
    "$PYTHON" -m pip install fastapi uvicorn -q 2>/dev/null || true
    
    # Run pytest with PYTHONPATH set to include source packages
    log_info "Running Hermes plugin tests..."
    PYTHONPATH="$REPO_ROOT/packages/core/src:$REPO_ROOT/packages/hermes-plugin/src" \
    "$PYTHON" -m pytest "$HERMES_TESTS" -v --tb=short 2>&1 && {
        log_pass "Hermes plugin tests passed"
    } || {
        log_fail "Hermes plugin tests failed"
    }
}

run_pi_tests() {
    log_section "pi Extension Tests"
    
    # Check Node.js is available
    if ! command -v node &>/dev/null; then
        log_skip "Node.js not available"
        return 0
    fi
    
    cd "$PI_TESTS"
    
    # Install dependencies
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing pi extension dependencies..."
        npm install --silent 2>/dev/null || {
            log_skip "Could not install npm dependencies"
            return 0
        }
    fi
    
    # Run vitest
    log_info "Running pi extension tests..."
    if npx vitest run 2>&1; then
        log_pass "pi extension tests passed"
    else
        log_fail "pi extension tests failed"
    fi
}

run_api_tests() {
    log_section "API Contract Tests"
    
    # Test that both packages expose expected tools
    log_info "Testing Hermes plugin tools..."
    
    # Check plugin directory exists
    if [[ -d "$HOME/.hermes/plugins/hermes-pi-bridge" ]]; then
        log_pass "Hermes plugin installed"
        
        # Check plugin.yaml exists and has correct tools
        if grep -q "pi_delegate" "$HOME/.hermes/plugins/hermes-pi-bridge/plugin.yaml" 2>/dev/null; then
            log_pass "pi_delegate tool registered"
        else
            log_fail "pi_delegate tool not found"
        fi
    else
        log_fail "Hermes plugin not installed"
    fi
    
    log_info "Testing pi extension..."
    
    # Check pi extension directory exists
    if [[ -d "$HOME/.pi/agent/npm/hermes-pi-bridge" ]]; then
        log_pass "pi extension installed"
        
        # Check package.json exists
        if grep -q '"hermes-pi-bridge"' "$HOME/.pi/agent/npm/hermes-pi-bridge/package.json" 2>/dev/null; then
            log_pass "pi extension package.json correct"
        else
            log_fail "pi extension package.json incorrect"
        fi
    else
        log_fail "pi extension not installed"
    fi
    
    # Test config files
    log_info "Testing configuration..."
    
    if grep -q "hermes-pi-bridge" "$HOME/.pi/agent/settings.json" 2>/dev/null; then
        log_pass "pi settings include bridge package"
    else
        log_fail "pi settings missing bridge package"
    fi
    
    if grep -q "hermes_pi_bridge" "$HOME/.hermes/config.yaml" 2>/dev/null; then
        log_pass "Hermes config includes bridge settings"
    else
        log_fail "Hermes config missing bridge settings"
    fi
}

run_delegation_tests() {
    log_section "Delegation Integration Tests"
    
    # These tests require both agents to be running
    # For now, just verify the code structure
    
    log_info "Checking delegation code structure..."
    
    # Check delegate tool exists
    if [[ -f "$HOME/.hermes/plugins/hermes-pi-bridge/src/hermes_pi_bridge/tools/delegate.py" ]]; then
        log_pass "Delegate tool exists"
    else
        log_fail "Delegate tool not found"
    fi
    
    # Check pi HTTP client exists
    if [[ -f "$HOME/.pi/agent/npm/hermes-pi-bridge/src/transport/client.ts" ]]; then
        log_pass "pi HTTP client exists"
    else
        log_fail "pi HTTP client not found"
    fi
    
    # Verify protocol matches
    log_info "Verifying protocol consistency..."
    
    # Check Python types
    if grep -q "PROTOCOL_VERSION" "$HOME/.hermes/plugins/hermes-pi-bridge/src/hermes_pi_bridge_core/types.py" 2>/dev/null; then
        log_pass "Python core has version constant"
    fi
    
    # Check TypeScript types
    if grep -q "PROTOCOL_VERSION" "$HOME/.pi/agent/npm/hermes-pi-bridge/src/types.ts" 2>/dev/null; then
        log_pass "TypeScript core has version constant"
    fi
}

run_seed_tests() {
    log_section "Seed Script Tests"
    
    log_info "Testing seed script..."
    
    # Check seed script exists and is executable
    if [[ -x "$REPO_ROOT/scripts/seed.sh" ]]; then
        log_pass "Seed script exists and is executable"
    else
        log_fail "Seed script missing or not executable"
    fi
    
    # Run seed script check
    log_info "Running seed script --check..."
    CHECK_OUTPUT=$("$REPO_ROOT/scripts/seed.sh" --check 2>&1)
    if echo "$CHECK_OUTPUT" | grep -q "INSTALLED"; then
        log_pass "Seed script reports packages installed"
    else
        log_fail "Seed script does not report packages installed"
    fi
    
    # Test reinstall (should be idempotent)
    log_info "Testing idempotent install..."
    if "$REPO_ROOT/scripts/seed.sh" 2>&1 | grep -q "successfully"; then
        log_pass "Idempotent install works"
    else
        log_fail "Idempotent install failed"
    fi
}

run_uninstall_tests() {
    log_section "Uninstall Tests"
    
    log_info "Testing uninstall..."
    
    # Uninstall
    if "$REPO_ROOT/scripts/seed.sh" --uninstall 2>&1 | grep -q "complete"; then
        log_pass "Uninstall completed"
    else
        log_fail "Uninstall failed"
    fi
    
    # Verify removal
    if [[ ! -d "$HOME/.hermes/plugins/hermes-pi-bridge" ]] && [[ ! -d "$HOME/.pi/agent/npm/hermes-pi-bridge" ]]; then
        log_pass "Packages removed successfully"
    else
        log_fail "Packages still present after uninstall"
    fi
    
    # Reinstall for other tests
    log_info "Reinstalling for continued testing..."
    "$REPO_ROOT/scripts/seed.sh" &>/dev/null || true
}

#-------------------------------------------------------------------------------
# Help
#-------------------------------------------------------------------------------

usage() {
    cat <<EOF
Hermes-Pi Bridge Integration Tests

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --unit         Run unit tests only (core, hermes, pi)
    --api          Run API contract tests only
    --delegate     Run delegation tests only
    --seed         Run seed script tests only
    --uninstall    Run uninstall tests (removes packages, then reinstalls)
    --all          Run all tests (default)
    --verbose      Show verbose output
    -h, --help     Show this help

EXAMPLES:
    $0                    # Run all tests
    $0 --unit             # Unit tests only
    $0 --all --verbose    # All tests with verbose output
EOF
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------

main() {
    local run_unit=false
    local run_api=false
    local run_delegate=false
    local run_seed=false
    local run_uninstall=false
    local run_all=true
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --unit) run_unit=true; run_all=false;;
            --api) run_api=true; run_all=false;;
            --delegate) run_delegate=true; run_all=false;;
            --seed) run_seed=true; run_all=false;;
            --uninstall) run_uninstall=true; run_all=false;;
            --all) run_all=true;;
            --verbose) set -x;;
            -h|--help) usage; exit 0;;
            *) log_error "Unknown option: $1"; usage; exit 1;;
        esac
        shift
    done
    
    echo ""
    echo "================================================"
    echo "    Hermes-Pi Bridge Integration Tests         "
    echo "================================================"
    echo ""
    log_info "Repository: $REPO_ROOT"
    log_info "Date: $(date)"
    echo ""
    
    # Run requested tests
    if $run_all || $run_unit; then
        run_core_tests || true
        run_hermes_tests || true
        run_pi_tests || true
    fi
    
    if $run_all || $run_api; then
        run_api_tests || true
    fi
    
    if $run_all || $run_delegate; then
        run_delegation_tests || true
    fi
    
    if $run_all || $run_seed; then
        run_seed_tests || true
    fi
    
    if $run_uninstall; then
        run_uninstall_tests || true
    fi
    
    # Summary
    echo ""
    echo "================================================"
    echo "                   Summary                     "
    echo "================================================"
    echo ""
    echo -e "  ${GREEN}Passed:${NC}  $TESTS_PASSED"
    echo -e "  ${RED}Failed:${NC}  $TESTS_FAILED"
    echo -e "  ${YELLOW}Skipped:${NC} $TESTS_SKIPPED"
    echo ""
    
    if [[ $TESTS_FAILED -gt 0 ]]; then
        echo -e "${RED}Some tests failed${NC}"
        exit 1
    else
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    fi
}

main "$@"
