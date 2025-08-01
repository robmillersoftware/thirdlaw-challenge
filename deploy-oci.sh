#!/bin/bash

# Minimal OCI Deployment Script for PDF Scanner Demo
# For job interview demonstration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check requirements
check_requirements() {
    print_status "Checking requirements..."
    
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform not found. Please install Terraform first."
        echo "Visit: https://developer.hashicorp.com/terraform/downloads"
        exit 1
    fi
    
    if ! command -v ssh-keygen &> /dev/null; then
        print_error "ssh-keygen not found. Please install OpenSSH."
        exit 1
    fi
    
    print_success "Requirements check passed"
}

# Setup SSH key if it doesn't exist
setup_ssh_key() {
    if [ ! -f ~/.ssh/id_rsa ]; then
        print_status "Generating SSH key pair..."
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -C "pdf-scanner-demo"
        print_success "SSH key pair generated"
    fi
    
    SSH_PUBLIC_KEY=$(cat ~/.ssh/id_rsa.pub)
    print_status "SSH public key ready"
}

# Setup Terraform variables
setup_terraform_vars() {
    if [ ! -f terraform/terraform.tfvars ]; then
        print_warning "terraform.tfvars not found. Please create it from terraform.tfvars.example"
        print_status "Required steps:"
        echo "1. Copy terraform/terraform.tfvars.example to terraform/terraform.tfvars"
        echo "2. Fill in your OCI credentials and settings"
        echo "3. Run this script again"
        exit 1
    fi
    
    # Add SSH key to terraform.tfvars if not already there
    if ! grep -q "ssh_public_key" terraform/terraform.tfvars; then
        echo "" >> terraform/terraform.tfvars
        echo "# Auto-generated SSH public key" >> terraform/terraform.tfvars
        echo "ssh_public_key = \"$SSH_PUBLIC_KEY\"" >> terraform/terraform.tfvars
        print_status "SSH public key added to terraform.tfvars"
    fi
}

# Copy application files
copy_app_files() {
    print_status "Copying application files to terraform directory..."
    
    # Copy necessary files
    cp -r backend terraform/
    cp -r static terraform/
    cp requirements.txt terraform/
    cp prometheus.yml terraform/ 2>/dev/null || echo "global:" > terraform/prometheus.yml
    
    print_success "Application files copied"
}

# Deploy infrastructure
deploy_infrastructure() {
    print_status "Deploying infrastructure to OCI..."
    
    cd terraform
    
    # Initialize Terraform
    terraform init
    
    # Plan deployment
    print_status "Planning Terraform deployment..."
    terraform plan
    
    # Apply deployment
    print_status "Applying Terraform deployment..."
    terraform apply -auto-approve
    
    cd ..
    print_success "Infrastructure deployed successfully"
}

# Get deployment info
get_deployment_info() {
    print_status "Getting deployment information..."
    
    cd terraform
    PUBLIC_IP=$(terraform output -raw instance_public_ip)
    cd ..
    
    print_success "Deployment completed successfully!"
    echo ""
    echo "===================================================================================="
    echo "🎯 PDF SCANNER DEMO DEPLOYMENT"
    echo "===================================================================================="
    echo ""
    echo "📍 Instance Public IP: $PUBLIC_IP"
    echo ""
    echo "🔗 Application URLs:"
    echo "   • PDF Scanner:  http://$PUBLIC_IP:8000"
    echo "   • Prometheus:   http://$PUBLIC_IP:9090"
    echo "   • Grafana:      http://$PUBLIC_IP:3000 (admin/demo123)"
    echo ""
    echo "🔧 SSH Access:"
    echo "   ssh opc@$PUBLIC_IP"
    echo ""
    echo "⏱️  Note: The application may take 2-3 minutes to fully start up after the instance boots."
    echo "         You can monitor the startup process by SSHing to the instance and running:"
    echo "         docker logs pdf-scanner_pdf-scanner_1 -f"
    echo ""
    echo "🗑️  To destroy this demo environment:"
    echo "   cd terraform && terraform destroy -auto-approve"
    echo "===================================================================================="
}

# Main deployment flow
main() {
    echo "===================================================================================="
    echo "🚀 PDF SCANNER - MINIMAL OCI DEPLOYMENT FOR DEMO"
    echo "===================================================================================="
    echo ""
    
    check_requirements
    setup_ssh_key
    setup_terraform_vars
    copy_app_files
    deploy_infrastructure
    get_deployment_info
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "destroy")
        print_warning "Destroying infrastructure..."
        cd terraform
        terraform destroy -auto-approve
        cd ..
        print_success "Infrastructure destroyed"
        ;;
    "status")
        if [ -f terraform/terraform.tfstate ]; then
            cd terraform
            terraform output
            cd ..
        else
            print_error "No deployment found. Run './deploy-oci.sh deploy' first."
        fi
        ;;
    "help"|"--help"|"-h")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  deploy    Deploy the PDF scanner to OCI (default)"
        echo "  destroy   Destroy the OCI deployment"
        echo "  status    Show deployment status and URLs"
        echo "  help      Show this help message"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac