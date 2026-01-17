#!/bin/bash
# Test Database Connectivity Through SSH Tunnel
# Usage: ./test_with_tunnel.sh

echo "🧪 Testing MariaDB Connectivity Through SSH Tunnel"
echo ""

# Check if tunnel is running
if ! lsof -Pi :3307 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "❌ SSH tunnel not running on port 3307"
    echo ""
    echo "Start the tunnel first:"
    echo "  ./scripts/ssh_tunnel.sh"
    echo ""
    exit 1
fi

echo "✅ SSH tunnel detected on port 3307"
echo ""

# Set database URL to use tunnel
export DATABASE_URL="mysql+pymysql://wpn-user:C1sco5150!@127.0.0.1:3307/wpn_radius"
export API_AUTH_TOKEN="test-token-for-validation"
export CERT_PASSWORD="test-cert-password"

echo "📊 Running validation..."
echo ""

# Run validation
python3 scripts/validate_deployment.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "🎉 Database connectivity test PASSED!"
    echo ""
    echo "You can now test with:"
    echo "  mysql -h 127.0.0.1 -P 3307 -u wpn-user -p wpn_radius"
else
    echo ""
    echo "❌ Validation failed. Check the output above."
fi

exit $exit_code
