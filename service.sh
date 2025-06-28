#!/bin/bash

# SatoshisEndgame Service Management Script
# Manages the systemd service for the monitoring daemon

set -e

SERVICE_NAME="satoshis-endgame"
SERVICE_FILE="satoshis-endgame.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER=$(whoami)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[i]${NC} $1"
}

# Check if running as root when needed
check_sudo() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This command must be run with sudo"
        exit 1
    fi
}

# Install the service
install_service() {
    check_sudo
    
    print_info "Installing ${SERVICE_NAME} service..."
    
    # Check if template exists
    if [[ ! -f "${SCRIPT_DIR}/${SERVICE_FILE}.template" ]]; then
        print_error "Service template file not found: ${SERVICE_FILE}.template"
        exit 1
    fi
    
    # Check if venv exists
    if [[ ! -d "${SCRIPT_DIR}/venv" ]]; then
        print_error "Virtual environment not found. Please run ./quickstart.sh first"
        exit 1
    fi
    
    # Generate service file from template
    sed -e "s|{{INSTALL_DIR}}|${SCRIPT_DIR}|g" \
        -e "s|{{USER}}|${SUDO_USER:-$USER}|g" \
        "${SCRIPT_DIR}/${SERVICE_FILE}.template" > "/etc/systemd/system/${SERVICE_NAME}.service"
    
    systemctl daemon-reload
    print_status "Service installed successfully"
    print_info "You can now use: sudo service.sh start"
}

# Uninstall the service
uninstall_service() {
    check_sudo
    
    print_info "Uninstalling ${SERVICE_NAME} service..."
    
    # Stop service if running
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
    
    # Remove service file
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    
    print_status "Service uninstalled successfully"
}

# Start the service
start_service() {
    check_sudo
    
    print_info "Starting ${SERVICE_NAME} service..."
    systemctl start "${SERVICE_NAME}"
    print_status "Service started"
}

# Stop the service
stop_service() {
    check_sudo
    
    print_info "Stopping ${SERVICE_NAME} service..."
    systemctl stop "${SERVICE_NAME}"
    print_status "Service stopped"
}

# Restart the service
restart_service() {
    check_sudo
    
    print_info "Restarting ${SERVICE_NAME} service..."
    systemctl restart "${SERVICE_NAME}"
    print_status "Service restarted"
}

# Show service status
status_service() {
    systemctl status "${SERVICE_NAME}" --no-pager || true
}

# Show service logs
logs_service() {
    print_info "Showing logs for ${SERVICE_NAME} (Ctrl+C to exit)..."
    journalctl -u "${SERVICE_NAME}" -f
}

# Enable service to start on boot
enable_service() {
    check_sudo
    
    print_info "Enabling ${SERVICE_NAME} to start on boot..."
    systemctl enable "${SERVICE_NAME}"
    print_status "Service enabled"
}

# Disable service from starting on boot
disable_service() {
    check_sudo
    
    print_info "Disabling ${SERVICE_NAME} from starting on boot..."
    systemctl disable "${SERVICE_NAME}"
    print_status "Service disabled"
}

# Main command handling
case "$1" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        logs_service
        ;;
    enable)
        enable_service
        ;;
    disable)
        disable_service
        ;;
    *)
        echo "SatoshisEndgame Service Manager"
        echo ""
        echo "Usage: $0 {install|uninstall|start|stop|restart|status|logs|enable|disable}"
        echo ""
        echo "Commands:"
        echo "  install    - Install the systemd service"
        echo "  uninstall  - Remove the systemd service"
        echo "  start      - Start the monitoring service"
        echo "  stop       - Stop the monitoring service"
        echo "  restart    - Restart the monitoring service"
        echo "  status     - Show service status"
        echo "  logs       - Follow service logs (Ctrl+C to exit)"
        echo "  enable     - Enable service to start on boot"
        echo "  disable    - Disable service from starting on boot"
        echo ""
        echo "Note: install/uninstall/start/stop/restart/enable/disable require sudo"
        exit 1
        ;;
esac