#!/bin/bash
# Nexus Installation Script

set -e

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                        NEXUS INSTALLATION                                    ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"

# Check Python version
echo "Checking Python version..."
python3 --version

# Install Python package
echo ""
echo "Installing Python package..."
cd packages/core
pip install -e .

# Install Node package (optional)
echo ""
echo "Installing Node package..."
cd ../pi-extension
npm install

# Go back to root
cd ../..

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                        INSTALLATION COMPLETE                                  ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"

echo ""
echo "Run tests:"
echo "  python -m pytest packages/core/tests"
echo ""
echo "Run CLI:"
echo "  ./nexus status"