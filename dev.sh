#!/usr/bin/env bash
################################################################################
# Development Server Script
################################################################################
# This script starts the Django development server and Tailwind CSS compiler
# for local development. The server binds to 0.0.0.0 to allow access through
# VPN connections.
#
# Usage:
#   ./dev.sh [PORT]
#
# Arguments:
#   PORT    Optional. Port number for Django server (default: 8000)
#
# Examples:
#   ./dev.sh           # Start on default port 8000
#   ./dev.sh 8080      # Start on port 8080
#   ./dev.sh --help    # Show this help message
#
# What it does:
#   1. Activates the Python virtual environment (.venv or venv)
#   2. Starts Tailwind CSS compiler in the background
#   3. Starts Django development server on 0.0.0.0:[PORT]
#   4. Handles graceful shutdown of both processes on Ctrl+C
#
# Access:
#   From local machine: http://localhost:8000
#   From VPN/network:   http://YOUR_MACHINE_IP:8000
################################################################################

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Show help message
show_help() {
    echo -e "${BLUE}Development Server Script${NC}"
    echo ""
    echo "Usage: ./dev.sh [PORT]"
    echo ""
    echo "Arguments:"
    echo "  PORT    Optional. Port number for Django server (default: 8000)"
    echo ""
    echo "Examples:"
    echo "  ./dev.sh           # Start on default port 8000"
    echo "  ./dev.sh 8080      # Start on port 8080"
    echo ""
    echo "What it does:"
    echo "  1. Activates the Python virtual environment"
    echo "  2. Starts Tailwind CSS compiler in the background"
    echo "  3. Starts Django development server on 0.0.0.0:[PORT]"
    echo "  4. Handles graceful shutdown with Ctrl+C"
    echo ""
    echo "Access:"
    echo "  Local:   http://localhost:8000"
    echo "  Network: http://YOUR_MACHINE_IP:8000"
    exit 0
}

# Check for help flag
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    show_help
fi

# Activate virtual environment
if [ -d ".venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source venv/bin/activate
else
    echo -e "${RED}Error: No virtual environment found (.venv or venv)${NC}"
    exit 1
fi

# Default port
PORT="${1:-8000}"

echo -e "${GREEN}Starting development servers...${NC}"
echo -e "${YELLOW}Django will be accessible at: http://0.0.0.0:${PORT}${NC}"
echo ""

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $(jobs -p) 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Start Tailwind compiler in background
echo -e "${GREEN}Starting Tailwind CSS compiler...${NC}"
python manage.py tailwind start &
TAILWIND_PID=$!

# Give Tailwind a moment to start
sleep 2

# Start Django development server
echo -e "${GREEN}Starting Django development server on 0.0.0.0:${PORT}...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""
python manage.py runserver 0.0.0.0:${PORT}

# Cleanup will be called by trap on exit
