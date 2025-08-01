#!/bin/bash

# PDF Scanner Docker Startup Script
# Provides easy commands to manage the containerized application

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

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    mkdir -p uploads logs problematic_test_pdfs
    print_success "Directories created"
}

# Function to build the application
build_app() {
    print_status "Building PDF Scanner application..."
    docker-compose build pdf-scanner
    print_success "Application built successfully"
}

# Function to start all services
start_services() {
    print_status "Starting all services..."
    docker-compose up -d
    
    print_status "Waiting for services to be healthy..."
    sleep 10
    
    # Check service health
    if docker-compose ps | grep -q "Up (healthy)"; then
        print_success "Services started successfully!"
        echo ""
        print_status "Service URLs:"
        echo "  📊 Application:      http://localhost:8000"
        echo "  📈 Metrics Dashboard: http://localhost:8000/metrics-dashboard"
        echo "  🔍 Prometheus:       http://localhost:9090"
        echo "  📊 Grafana:          http://localhost:3000 (admin/admin123)"
        echo "  🗄️  ClickHouse:       http://localhost:8123"
        echo ""
        print_status "Health check: curl http://localhost:8000/health"
    else
        print_warning "Some services may still be starting. Check status with: docker-compose ps"
    fi
}

# Function to stop all services
stop_services() {
    print_status "Stopping all services..."
    docker-compose down
    print_success "Services stopped"
}

# Function to restart services
restart_services() {
    print_status "Restarting services..."
    docker-compose down
    docker-compose up -d
    print_success "Services restarted"
}

# Function to view logs
view_logs() {
    local service=${1:-pdf-scanner}
    print_status "Showing logs for $service..."
    if [ "$service" = "all" ]; then
        docker-compose logs -f
    else
        docker-compose logs -f "$service"
    fi
}

# Function to run shell inside container
exec_shell() {
    local service=${1:-pdf-scanner}
    print_status "Opening shell in $service container..."
    docker-compose exec "$service" /bin/bash
}

# Function to run tests
run_tests() {
    print_status "Running PDF handling tests..."
    if ! docker-compose ps pdf-scanner | grep -q "Up"; then
        print_error "PDF Scanner service is not running. Start it first with: $0 start"
        exit 1
    fi
    
    # Generate test files if they don't exist
    if [ ! -f "problematic_test_pdfs/normal_with_sensitive_data.pdf" ]; then
        print_status "Generating test PDFs..."
        python test_oversized_corrupt_pdfs.py
    fi
    
    # Run redaction tests
    print_status "Testing redaction functionality..."
    python test_redaction.py
    
    # Run comprehensive PDF handling tests
    print_status "Running comprehensive PDF tests..."
    python test_pdf_handling.py
    
    print_success "Tests completed!"
}

# Function to load test data
load_test() {
    local count=${1:-100}
    print_status "Running load test with $count requests..."
    
    if ! docker-compose ps pdf-scanner | grep -q "Up"; then
        print_error "PDF Scanner service is not running. Start it first with: $0 start"
        exit 1
    fi
    
    # Generate test PDFs if needed
    if [ ! -d "test_pdfs" ] || [ $(ls test_pdfs/*.pdf 2>/dev/null | wc -l) -lt 10 ]; then
        print_status "Generating test PDFs for load testing..."
        python generate_test_pdfs.py --count 50 --workers 4
    fi
    
    # Run load test
    python load_test.py
    print_success "Load test completed!"
}

# Function to clean up
cleanup() {
    print_status "Cleaning up containers and volumes..."
    docker-compose down -v
    docker system prune -f
    print_success "Cleanup completed"
}

# Function to show status
show_status() {
    print_status "Service Status:"
    docker-compose ps
    echo ""
    
    print_status "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
}

# Function to show help
show_help() {
    echo "PDF Scanner Docker Management Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start                 Start all services"
    echo "  stop                  Stop all services"
    echo "  restart               Restart all services"
    echo "  build                 Build the application"
    echo "  logs [service]        View logs (default: pdf-scanner, use 'all' for all services)"
    echo "  shell [service]       Open shell in container (default: pdf-scanner)"
    echo "  status                Show service status and resource usage"
    echo "  test                  Run comprehensive tests"
    echo "  load-test [count]     Run load test (default: 100 requests)"
    echo "  cleanup               Remove all containers and volumes"
    echo "  help                  Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start all services"
    echo "  $0 logs               # View PDF scanner logs"
    echo "  $0 logs all           # View all service logs"
    echo "  $0 shell              # Open shell in PDF scanner container"
    echo "  $0 test               # Run all tests"
    echo "  $0 load-test 200      # Run load test with 200 requests"
}

# Main command handling
case "${1:-help}" in
    "start")
        check_docker
        create_directories
        build_app
        start_services
        ;;
    "stop")
        check_docker
        stop_services
        ;;
    "restart")
        check_docker
        restart_services
        ;;
    "build")
        check_docker
        build_app
        ;;
    "logs")
        check_docker
        view_logs "$2"
        ;;
    "shell")
        check_docker
        exec_shell "$2"
        ;;
    "status")
        check_docker
        show_status
        ;;
    "test")
        run_tests
        ;;
    "load-test")
        load_test "$2"
        ;;
    "cleanup")
        check_docker
        cleanup
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