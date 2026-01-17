#!/bin/bash
# Quick start script for local Docker Compose testing

set -e

echo "=============================================="
echo "Meraki WPN Portal - Local Test Environment"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Stop and remove existing containers
echo "Stopping existing containers..."
docker-compose down

# Build and start services
echo ""
echo "Building and starting services..."
docker-compose up --build -d

# Wait for services to start
echo ""
echo "Waiting for services to become healthy..."
sleep 5

# Check MariaDB health
echo ""
echo "Checking MariaDB..."
for i in {1..30}; do
    if docker exec wpn-mariadb mariadb -uwpn-user -pC1sco5150! wpn_radius -e "SELECT 1;" > /dev/null 2>&1; then
        print_status "MariaDB is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "MariaDB failed to start"
        exit 1
    fi
    sleep 1
done

# Check Portal health
echo "Checking Portal..."
for i in {1..30}; do
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        print_status "Portal is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Portal failed to start"
        exit 1
    fi
    sleep 1
done

# Check FreeRADIUS health
echo "Checking FreeRADIUS..."
for i in {1..30}; do
    if docker exec freeradius-server radtest healthcheck healthcheck localhost 1812 testing123 > /dev/null 2>&1; then
        print_status "FreeRADIUS is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        print_warning "FreeRADIUS health check inconclusive (may still be starting)"
        break
    fi
    sleep 1
done

# Verify database tables
echo ""
echo "Verifying database tables..."
TABLES=$(docker exec wpn-mariadb mariadb -uwpn-user -pC1sco5150! wpn_radius -e "SHOW TABLES;" 2>/dev/null | tail -n +2)
TABLE_COUNT=$(echo "$TABLES" | wc -l | tr -d ' ')

if [ "$TABLE_COUNT" -ge 8 ]; then
    print_status "Database has $TABLE_COUNT tables"
    echo "$TABLES" | sed 's/^/  - /'
else
    print_error "Database missing tables (found $TABLE_COUNT, expected 8+)"
    exit 1
fi

# Check deployment mode
echo ""
echo "Checking deployment mode..."
DEPLOYMENT_MODE=$(docker-compose logs portal 2>/dev/null | grep "Deployment mode:" | tail -n 1)
if echo "$DEPLOYMENT_MODE" | grep -q "Standalone"; then
    print_status "Deployment mode: Standalone"
else
    print_error "Deployment mode incorrect: $DEPLOYMENT_MODE"
fi

# Check database type
DATABASE_TYPE=$(docker-compose logs portal 2>/dev/null | grep "📊 Database:" | tail -n 1)
if echo "$DATABASE_TYPE" | grep -q "MySQL/MariaDB"; then
    print_status "Database type: MySQL/MariaDB"
else
    print_error "Database type incorrect: $DATABASE_TYPE"
fi

# Show container status
echo ""
echo "Container status:"
docker-compose ps

echo ""
echo "=============================================="
print_status "All services are up and running!"
echo "=============================================="
echo ""
echo "Access points:"
echo "  Portal:     http://localhost:8080"
echo "  Health:     http://localhost:8080/health"
echo "  RADIUS API: http://localhost:8000"
echo ""
echo "Database access:"
echo "  docker exec wpn-mariadb mariadb -uwpn-user -pC1sco5150! wpn_radius"
echo ""
echo "View logs:"
echo "  docker-compose logs -f portal"
echo "  docker-compose logs -f freeradius"
echo "  docker-compose logs -f mariadb"
echo ""
echo "Stop services:"
echo "  docker-compose down"
echo ""
