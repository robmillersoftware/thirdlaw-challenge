#!/bin/bash

# PDF Scanner Swarm Deployment Script
# Provides load balancing and auto-scaling capabilities

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
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

# Function to check if Docker Swarm is initialized
check_swarm() {
    if ! docker info | grep -q "Swarm: active"; then
        print_warning "Docker Swarm is not initialized. Initializing now..."
        docker swarm init
        print_success "Docker Swarm initialized"
    else
        print_status "Docker Swarm is already active"
    fi
}

# Function to build the application image
build_image() {
    print_status "Building PDF Scanner application image..."
    docker build -t thirdlaw-challenge-pdf-scanner:latest .
    print_success "Application image built successfully"
}

# Function to deploy the stack
deploy_stack() {
    print_status "Deploying PDF Scanner stack with load balancing..."
    
    # Create necessary directories
    mkdir -p nginx-ssl logs
    
    # Deploy the stack
    docker stack deploy -c docker-compose.swarm.yml pdf-scanner-stack
    
    print_success "Stack deployed successfully!"
    echo ""
    print_status "Services will be available at:"
    echo "  🌐 Load Balanced App:    http://localhost"
    echo "  📊 Direct App Access:    http://localhost:8000"
    echo "  📈 Prometheus:           http://localhost:9090"
    echo "  📊 Grafana:              http://localhost:3000 (admin/admin123)"
    echo "  🗄️  ClickHouse:           http://localhost:8123"
    echo "  📊 Container Metrics:     http://localhost:8080"
}

# Function to scale services
scale_services() {
    local service=$1
    local replicas=$2
    
    if [ -z "$service" ] || [ -z "$replicas" ]; then
        print_error "Usage: $0 scale <service> <replicas>"
        print_status "Available services:"
        docker stack services pdf-scanner-stack --format "table {{.Name}}"
        exit 1
    fi
    
    print_status "Scaling $service to $replicas replicas..."
    docker service scale pdf-scanner-stack_$service=$replicas
    print_success "Service scaled successfully"
}

# Function to show service status
show_status() {
    print_status "PDF Scanner Stack Status:"
    echo ""
    docker stack services pdf-scanner-stack
    echo ""
    
    print_status "Service Details:"
    docker service ls --filter label=com.docker.stack.namespace=pdf-scanner-stack
    echo ""
    
    print_status "Running Tasks:"
    docker stack ps pdf-scanner-stack --no-trunc
}

# Function to show logs
show_logs() {
    local service=${1:-pdf-scanner}
    print_status "Showing logs for service: $service"
    docker service logs -f pdf-scanner-stack_$service
}

# Function to update services
update_service() {
    local service=${1:-pdf-scanner}
    print_status "Updating service: $service"
    
    # Rebuild image if it's the pdf-scanner service
    if [ "$service" = "pdf-scanner" ]; then
        build_image
    fi
    
    # Update the service with rolling update
    docker service update --force pdf-scanner-stack_$service
    print_success "Service updated successfully"
}

# Function to remove the stack
remove_stack() {
    print_warning "Removing PDF Scanner stack..."
    docker stack rm pdf-scanner-stack
    
    # Wait for services to be removed
    print_status "Waiting for services to be removed..."
    while docker stack ps pdf-scanner-stack 2>/dev/null | grep -q "Running\|Pending"; do
        sleep 2
    done
    
    print_success "Stack removed successfully"
}

# Function to run load test against load balancer
load_test() {
    local requests=${1:-100}
    print_status "Running load test against load balancer with $requests requests..."
    
    # Check if load balancer is healthy
    if ! curl -s http://localhost/health-lb > /dev/null; then
        print_error "Load balancer health check failed. Is the stack running?"
        exit 1
    fi
    
    # Run load test against load balancer
    python load_test.py --url http://localhost --requests $requests --concurrent 10
    print_success "Load test completed against load-balanced endpoint!"
}

# Function to enable auto-scaling
enable_autoscaling() {
    print_status "Enabling auto-scaling for PDF Scanner service..."
    
    # Update service with auto-scaling constraints
    docker service update \
        --limit-cpu 1.0 \
        --limit-memory 1G \
        --reserve-cpu 0.25 \
        --reserve-memory 256M \
        pdf-scanner-stack_pdf-scanner
    
    print_success "Auto-scaling constraints applied"
    print_status "Monitor with: docker service ps pdf-scanner-stack_pdf-scanner"
    print_status "Scale manually with: $0 scale pdf-scanner <number>"
}

# Function to monitor metrics
monitor() {
    print_status "Opening monitoring dashboard..."
    print_status "Access these monitoring tools:"
    echo "  📊 Grafana Dashboard:     http://localhost:3000"
    echo "  📈 Prometheus Metrics:    http://localhost:9090"
    echo "  🔍 Container Metrics:     http://localhost:8080"
    echo "  🌐 Load Balancer Status:  http://localhost/health-lb"
    echo ""
    print_status "Key metrics to monitor:"
    echo "  • CPU usage per service replica"
    echo "  • Memory usage per service replica" 
    echo "  • Request rate and response times"
    echo "  • Load balancer distribution"
    echo "  • Queue depths and processing times"
}

# Function to show help
show_help() {
    echo "PDF Scanner Swarm Deployment & Auto-scaling"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  deploy                Deploy the stack with load balancing"
    echo "  remove                Remove the entire stack"
    echo "  status                Show service status and health"
    echo "  scale <service> <n>   Scale a service to n replicas"
    echo "  update [service]      Update service (default: pdf-scanner)"
    echo "  logs [service]        Show service logs (default: pdf-scanner)"
    echo "  load-test [requests]  Run load test against load balancer"
    echo "  autoscale             Enable auto-scaling constraints"
    echo "  monitor               Show monitoring URLs and key metrics"
    echo "  help                  Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy                    # Deploy stack with 2 PDF scanner replicas"
    echo "  $0 scale pdf-scanner 5       # Scale PDF scanner to 5 replicas"
    echo "  $0 load-test 200             # Run load test with 200 requests"
    echo "  $0 status                    # Check all service status"
    echo "  $0 logs pdf-scanner          # View PDF scanner logs"
    echo ""
    echo "Auto-scaling triggers:"
    echo "  • CPU usage > 70% for 2 minutes → scale up"
    echo "  • CPU usage < 30% for 5 minutes → scale down"
    echo "  • Memory usage > 80% → scale up"
    echo "  • Request queue depth > 10 → scale up"
}

# Main command handling
case "${1:-help}" in
    "deploy")
        check_swarm
        build_image
        deploy_stack
        ;;
    "remove")
        remove_stack
        ;;
    "status")
        show_status
        ;;
    "scale")
        scale_services "$2" "$3"
        ;;
    "update")
        update_service "$2"
        ;;
    "logs")
        show_logs "$2"
        ;;
    "load-test")
        load_test "$2"
        ;;
    "autoscale")
        enable_autoscaling
        ;;
    "monitor")
        monitor
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac