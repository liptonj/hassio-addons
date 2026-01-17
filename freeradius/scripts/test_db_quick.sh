#!/bin/bash
# Quick Database Connectivity Test
# Usage: ./test_db_quick.sh <ngrok-host> <ngrok-port>

NGROK_HOST="${1:-5.tcp.ngrok.io}"
NGROK_PORT="${2:-21829}"
DB_USER="wpn-user"
DB_PASS="C1sco5150!"
DB_NAME="wpn_radius"

echo "🔗 Testing MariaDB connectivity via ngrok..."
echo "   Host: $NGROK_HOST"
echo "   Port: $NGROK_PORT"
echo ""

# Test 1: Port reachability
echo "📡 Test 1: Port Reachability"
if timeout 5 nc -zv $NGROK_HOST $NGROK_PORT 2>&1 | grep -q "succeeded"; then
    echo "   ✅ Port is reachable"
else
    echo "   ❌ Port is NOT reachable"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check ngrok tunnel is running:"
    echo "     http://homeassistant.local:4040"
    echo "  2. Verify ngrok address:"
    echo "     docker logs addon_xxx_ngrok | grep tcp://"
    echo "  3. Check firewall/network settings"
    exit 1
fi

# Test 2: Database connection
echo ""
echo "🗄️  Test 2: Database Connection"
cd /Users/jolipton/Projects/hassio-addons-1/meraki-wpn-portal/backend
uv run python <<EOF
from sqlalchemy import create_engine, text

try:
    url = "mysql+pymysql://$DB_USER:$DB_PASS@$NGROK_HOST:$NGROK_PORT/$DB_NAME"
    engine = create_engine(url, connect_args={'connect_timeout': 10})
    
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        if result.scalar() == 1:
            print("   ✅ Database connection successful")
            
            # Quick schema check
            tables = conn.execute(text('SHOW TABLES'))
            table_list = [row[0] for row in tables]
            print(f"   ✅ Found {len(table_list)} tables")
            
            if 'radius_clients' in table_list and 'udn_assignments' in table_list:
                print("   ✅ Required tables exist")
            else:
                print("   ⚠️  Some required tables missing")
        else:
            print("   ❌ Query failed")
            exit(1)
except Exception as e:
    print(f"   ❌ Connection failed: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=" * 60
    echo "🎉 All connectivity tests PASSED!"
    echo "=" * 60
    echo ""
    echo "You can now run full validation:"
    echo "  DATABASE_URL=\"mysql+pymysql://$DB_USER:$DB_PASS@$NGROK_HOST:$NGROK_PORT/$DB_NAME\" \\"
    echo "    python3 scripts/validate_deployment.py"
else
    echo ""
    echo "❌ Database connectivity test FAILED"
    exit 1
fi
