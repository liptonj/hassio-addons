#!/bin/bash
# SSH Tunnel Setup for Testing MariaDB from Mac
# Run this on your Mac

echo "🔧 Setting up SSH tunnel to Home Assistant MariaDB..."

# Configuration
HA_HOST="${HA_HOST:-192.168.14.50}"
LOCAL_PORT="${LOCAL_PORT:-3307}"
SSH_USER="${SSH_USER:-root}"

echo "  Home Assistant: $HA_HOST"
echo "  Local Port: $LOCAL_PORT"
echo "  SSH User: $SSH_USER"

# Check if tunnel already exists
if lsof -Pi :$LOCAL_PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port $LOCAL_PORT is already in use. Killing existing process..."
    kill $(lsof -t -i:$LOCAL_PORT)
    sleep 1
fi

echo ""
echo "📡 Creating SSH tunnel..."
echo "   Local: 127.0.0.1:$LOCAL_PORT → Remote: core-mariadb:3306"
echo ""
echo "   Press Ctrl+C to stop the tunnel"
echo "   Keep this terminal open while testing"
echo ""

# Create tunnel (runs in foreground so you can see it's working)
ssh -v -L ${LOCAL_PORT}:core-mariadb:3306 ${SSH_USER}@${HA_HOST} \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    "echo '✅ SSH tunnel established!'; echo ''; echo 'Connect to: mysql+pymysql://wpn-user:PASSWORD@127.0.0.1:${LOCAL_PORT}/wpn_radius'; echo ''; echo 'Press Ctrl+C to close tunnel'; cat"
