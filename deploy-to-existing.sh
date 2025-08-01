#!/bin/bash

# Deploy PDF Scanner to an existing OCI instance
# Use this when you've manually created a VM to bypass capacity issues

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if IP address is provided
if [ -z "$1" ]; then
    print_error "Usage: $0 <server-ip-address>"
    echo ""
    echo "Example: $0 123.456.789.012"
    echo ""
    echo "Steps to get your server IP:"
    echo "1. Go to OCI Console → Compute → Instances"
    echo "2. Find your instance's Public IP"
    echo "3. Run: $0 <that-ip-address>"
    exit 1
fi

SERVER_IP="$1"

print_status "Deploying PDF Scanner to existing server: $SERVER_IP"

# Test SSH connectivity
print_status "Testing SSH connectivity..."
if ! ssh -i ~/.ssh/id_ed25519 -o ConnectTimeout=10 -o BatchMode=yes opc@$SERVER_IP "echo 'SSH connection successful'" 2>/dev/null; then
    print_error "Cannot SSH to $SERVER_IP"
    echo ""
    echo "Troubleshooting:"
    echo "1. Make sure the instance is running"
    echo "2. Check security group allows SSH (port 22)"
    echo "3. Verify your SSH key is added to the instance"
    echo "4. Try: ssh -i ~/.ssh/id_ed25519 opc@$SERVER_IP"
    exit 1
fi

print_success "SSH connection successful"

# Create deployment package
print_status "Creating deployment package..."
tar -czf deploy-package.tar.gz \
    backend/ \
    static/ \
    requirements.txt \
    docker-compose.simple.yml \
    prometheus.yml \
    Dockerfile

print_success "Deployment package created"

# Copy files to server
print_status "Copying files to server..."
scp -i ~/.ssh/id_ed25519 deploy-package.tar.gz opc@$SERVER_IP:/home/opc/
print_success "Files copied"

# Deploy on server
print_status "Deploying application on server..."
ssh -i ~/.ssh/id_ed25519 opc@$SERVER_IP << 'EOF'
set -e

echo "🔧 Setting up server..."

# Extract deployment package
cd /home/opc
tar -xzf deploy-package.tar.gz
rm deploy-package.tar.gz

# Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo dnf update -y
    sudo dnf install -y docker docker-compose
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker opc
    newgrp docker
fi

# Configure firewall
echo "Configuring firewall..."
sudo firewall-cmd --permanent --add-port=22/tcp
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=9090/tcp
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=8123/tcp
sudo firewall-cmd --reload

# Create prometheus config if missing
if [ ! -f prometheus.yml ]; then
    cat > prometheus.yml << 'PROMETHEUS_EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'pdf-scanner'
    static_configs:
      - targets: ['pdf-scanner:8000']
    metrics_path: '/metrics/prometheus'
    scrape_interval: 5s
PROMETHEUS_EOF
fi

# Start the application
echo "Starting PDF Scanner application..."
docker-compose -f docker-compose.simple.yml down || true
docker-compose -f docker-compose.simple.yml up -d --build

echo "✅ Deployment complete!"
echo ""
echo "Application starting up... (takes 1-2 minutes)"
echo ""
echo "URLs:"
echo "  📱 PDF Scanner:  http://$(curl -s ifconfig.me):8000"
echo "  📊 Prometheus:   http://$(curl -s ifconfig.me):9090"
echo "  📈 Grafana:      http://$(curl -s ifconfig.me):3000 (admin/demo123)"
echo ""
echo "Check status with: docker-compose -f docker-compose.simple.yml ps"
EOF

print_success "Application deployed successfully!"

# Clean up local deployment package
rm -f deploy-package.tar.gz

# Get final status
print_status "Getting deployment status..."
echo ""
echo "=================================================================================="
echo "🎯 PDF SCANNER DEPLOYED TO EXISTING SERVER"  
echo "=================================================================================="
echo ""
echo "📍 Server IP: $SERVER_IP"
echo ""
echo "🔗 Application URLs (wait 1-2 minutes for startup):"
echo "   • PDF Scanner:  http://$SERVER_IP:8000"
echo "   • Prometheus:   http://$SERVER_IP:9090"
echo "   • Grafana:      http://$SERVER_IP:3000 (admin/demo123)"
echo ""
echo "🔧 SSH Access:"
echo "   ssh -i ~/.ssh/id_ed25519 opc@$SERVER_IP"
echo ""
echo "📊 Check Status:"
echo "   ssh -i ~/.ssh/id_ed25519 opc@$SERVER_IP 'docker-compose -f docker-compose.simple.yml ps'"
echo ""
echo "🔄 Restart Services:"
echo "   ssh -i ~/.ssh/id_ed25519 opc@$SERVER_IP 'docker-compose -f docker-compose.simple.yml restart'"
echo "=================================================================================="