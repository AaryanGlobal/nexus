#!/bin/bash
# Nexus Management Script - Start, stop, and manage Nexus daemon
# Usage: ./nexus.sh start|stop|restart|status|logs

COMMAND="$1"
NEXUS_PORT="${NEXUS_PORT:-8080}"
NEXUS_HOME="${HOME}/.nexus"
PID_FILE="${NEXUS_HOME}/nexus.pid"
LOG_FILE="${NEXUS_HOME}/nexus.log"

ensure_dir() {
    mkdir -p "${NEXUS_HOME}"
}

get_pid() {
    if [ -f "${PID_FILE}" ]; then
        cat "${PID_FILE}"
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
        return 0
    fi
    return 1
}

do_start() {
    ensure_dir
    
    if is_running; then
        echo "Nexus is already running (PID: $(get_pid))"
        return 1
    fi
    
    echo "Starting Nexus on port ${NEXUS_PORT}..."
    
    # Start in background
    PYTHONPATH="${HOME}/nexus/packages/core/src" \
        python3 "${HOME}/nexus/nexus_server.py" --port "${NEXUS_PORT}" \
        >> "${LOG_FILE}" 2>&1 &
    
    local pid=$!
    echo "${pid}" > "${PID_FILE}"
    
    # Wait for server to start
    sleep 2
    
    if is_running; then
        echo "Nexus started successfully (PID: ${pid})"
        return 0
    else
        echo "Failed to start Nexus"
        rm -f "${PID_FILE}"
        return 1
    fi
}

do_stop() {
    if ! is_running; then
        echo "Nexus is not running"
        return 1
    fi
    
    local pid=$(get_pid)
    echo "Stopping Nexus (PID: ${pid})..."
    
    kill "${pid}" 2>/dev/null
    sleep 1
    
    # Force kill if still running
    if kill -0 "${pid}" 2>/dev/null; then
        echo "Forcing shutdown..."
        kill -9 "${pid}" 2>/dev/null
    fi
    
    rm -f "${PID_FILE}"
    echo "Nexus stopped"
    return 0
}

do_status() {
    if is_running; then
        local pid=$(get_pid)
        echo "Nexus is running (PID: ${pid})"
        
        # Try to get health
        if command -v curl &>/dev/null; then
            local health=$(curl -s "http://localhost:${NEXUS_PORT}/health" 2>/dev/null)
            if [ -n "${health}" ]; then
                echo "Health: ${health}"
            fi
        fi
        return 0
    else
        echo "Nexus is not running"
        return 1
    fi
}

do_logs() {
    if [ -f "${LOG_FILE}" ]; then
        tail -n 50 "${LOG_FILE}"
    else
        echo "No log file found"
        return 1
    fi
}

do_restart() {
    do_stop
    sleep 1
    do_start
}

case "${COMMAND}" in
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_restart
        ;;
    status)
        do_status
        ;;
    logs)
        do_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start Nexus server"
        echo "  stop    - Stop Nexus server"
        echo "  restart - Restart Nexus server"
        echo "  status  - Show Nexus status"
        echo "  logs    - Show recent logs"
        exit 1
        ;;
esac