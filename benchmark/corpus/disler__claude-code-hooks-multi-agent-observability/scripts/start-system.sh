#!/bin/bash

echo "🚀 Starting Multi-Agent Observability System"
echo "==========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the project root directory (parent of scripts)
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Read ports from environment variables or use defaults
SERVER_PORT=${SERVER_PORT:-4000}
CLIENT_PORT=${CLIENT_PORT:-5173}

echo -e "${BLUE}Configuration:${NC}"
echo -e "  Server Port: ${GREEN}$SERVER_PORT${NC}"
echo -e "  Client Port: ${GREEN}$CLIENT_PORT${NC}"

# Function to kill processes on a port
kill_port() {
    local port=$1
    local name=$2

    echo -e "\n${YELLOW}Checking for existing $name on port $port...${NC}"

    # Find PIDs using the port
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        PIDS=$(lsof -ti :$port 2>/dev/null)
    else
        # Linux
        PIDS=$(lsof -ti :$port 2>/dev/null || fuser -n tcp $port 2>/dev/null | awk '{print $2}')
    fi

    if [ -n "$PIDS" ]; then
        echo -e "${RED}Found existing processes on port $port: $PIDS${NC}"
        for PID in $PIDS; do
            kill -9 $PID 2>/dev/null && echo -e "${GREEN}✅ Killed process $PID${NC}" || echo -e "${RED}❌ Failed to kill process $PID${NC}"
        done
        sleep 1
    else
        echo -e "${GREEN}✅ Port $port is available${NC}"
    fi
}

# Kill any existing processes on our ports
kill_port $SERVER_PORT "server"
kill_port $CLIENT_PORT "client"

# Start server
echo -e "\n${GREEN}Starting server on port $SERVER_PORT...${NC}"
cd "$PROJECT_ROOT/apps/server"
SERVER_PORT=$SERVER_PORT bun run dev &
SERVER_PID=$!

# Wait for server to be ready
echo -e "${YELLOW}Waiting for server to start...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:$SERVER_PORT/health >/dev/null 2>&1 || curl -s http://localhost:$SERVER_PORT/events/filter-options >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Server is ready!${NC}"
        break
    fi
    sleep 1
done

# Start client
echo -e "\n${GREEN}Starting client on port $CLIENT_PORT...${NC}"
cd "$PROJECT_ROOT/apps/client"
VITE_PORT=$CLIENT_PORT bun run dev &
CLIENT_PID=$!

# Wait for client to be ready
echo -e "${YELLOW}Waiting for client to start...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:$CLIENT_PORT >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Client is ready!${NC}"
        break
    fi
    sleep 1
done

# Display status
echo -e "\n${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Multi-Agent Observability System Started${NC}"
echo -e "${BLUE}============================================${NC}"
echo
echo -e "🖥️  Client URL: ${GREEN}http://localhost:$CLIENT_PORT${NC}"
echo -e "🔌 Server API: ${GREEN}http://localhost:$SERVER_PORT${NC}"
echo -e "📡 WebSocket: ${GREEN}ws://localhost:$SERVER_PORT/stream${NC}"
echo
echo -e "📝 Process IDs:"
echo -e "   Server PID: ${YELLOW}$SERVER_PID${NC}"
echo -e "   Client PID: ${YELLOW}$CLIENT_PID${NC}"
echo
echo -e "To stop the system, run: ${YELLOW}./scripts/reset-system.sh${NC}"
echo -e "To test the system, run: ${YELLOW}./scripts/test-system.sh${NC}"
echo
echo -e "${BLUE}Press Ctrl+C to stop both processes${NC}"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill $SERVER_PID 2>/dev/null
    kill $CLIENT_PID 2>/dev/null
    echo -e "${GREEN}✅ Stopped all processes${NC}"
    exit 0
}

# Set up trap to cleanup on Ctrl+C
trap cleanup INT

# Wait for both processes
wait $SERVER_PID $CLIENT_PID