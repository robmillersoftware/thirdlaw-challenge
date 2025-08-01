# Minimal OCI setup for PDF Scanner demo
# Uses Always Free tier resources only

terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
      version = "~> 4.0"
    }
  }
}

# Variables
variable "tenancy_ocid" {
  description = "Your OCI tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "Your OCI user OCID"
  type        = string
}

variable "fingerprint" {
  description = "Your API key fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to your private API key file"
  type        = string
}

variable "region" {
  description = "OCI region"
  type        = string
  default     = "us-ashburn-1"
}

variable "ssh_public_key" {
  description = "Your SSH public key"
  type        = string
}

variable "compartment_ocid" {
  description = "Compartment OCID (use tenancy_ocid for root compartment)"
  type        = string
}

# Provider configuration
provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

# Get availability domain
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# VCN
resource "oci_core_vcn" "pdf_scanner_vcn" {
  compartment_id = var.compartment_ocid
  display_name   = "pdf-scanner-vcn"
  cidr_block     = "10.1.0.0/16"
}

# Internet Gateway
resource "oci_core_internet_gateway" "pdf_scanner_ig" {
  compartment_id = var.compartment_ocid
  display_name   = "pdf-scanner-ig"
  vcn_id         = oci_core_vcn.pdf_scanner_vcn.id
}

# Route Table
resource "oci_core_default_route_table" "pdf_scanner_rt" {
  manage_default_resource_id = oci_core_vcn.pdf_scanner_vcn.default_route_table_id
  display_name               = "pdf-scanner-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.pdf_scanner_ig.id
  }
}

# Security List
resource "oci_core_default_security_list" "pdf_scanner_sl" {
  manage_default_resource_id = oci_core_vcn.pdf_scanner_vcn.default_security_list_id
  display_name               = "pdf-scanner-sl"

  # SSH
  ingress_security_rules {
    protocol  = "6"
    source    = "0.0.0.0/0"
    stateless = false

    tcp_options {
      max = "22"
      min = "22"
    }
  }

  # HTTP
  ingress_security_rules {
    protocol  = "6"
    source    = "0.0.0.0/0"
    stateless = false

    tcp_options {
      max = "80"
      min = "80"
    }
  }

  # HTTPS
  ingress_security_rules {
    protocol  = "6"
    source    = "0.0.0.0/0"
    stateless = false

    tcp_options {
      max = "443"
      min = "443"
    }
  }

  # PDF Scanner App
  ingress_security_rules {
    protocol  = "6"
    source    = "0.0.0.0/0"
    stateless = false

    tcp_options {
      max = "8000"
      min = "8000"
    }
  }

  # Prometheus
  ingress_security_rules {
    protocol  = "6"
    source    = "0.0.0.0/0"
    stateless = false

    tcp_options {
      max = "9090"
      min = "9090"
    }
  }

  # Grafana
  ingress_security_rules {
    protocol  = "6"
    source    = "0.0.0.0/0"
    stateless = false

    tcp_options {
      max = "3000"
      min = "3000"
    }
  }

  # Allow all outbound
  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
    stateless   = false
  }
}

# Subnet
resource "oci_core_subnet" "pdf_scanner_subnet" {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  cidr_block          = "10.1.20.0/24"
  display_name        = "pdf-scanner-subnet"
  compartment_id      = var.compartment_ocid
  vcn_id              = oci_core_vcn.pdf_scanner_vcn.id
  route_table_id      = oci_core_vcn.pdf_scanner_vcn.default_route_table_id
  security_list_ids   = [oci_core_vcn.pdf_scanner_vcn.default_security_list_id]
}

# Get the latest Oracle Linux image
data "oci_core_images" "oracle_linux" {
  compartment_id   = var.compartment_ocid
  operating_system = "Oracle Linux"
  
  filter {
    name   = "display_name"
    values = ["^.*-aarch64-.*$"]
    regex  = true
  }
}

# Compute Instance (Always Free ARM)
resource "oci_core_instance" "pdf_scanner" {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  compartment_id      = var.compartment_ocid
  display_name        = "pdf-scanner-demo"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = 1
    memory_in_gbs = 6
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.pdf_scanner_subnet.id
    display_name     = "pdf-scanner-vnic"
    assign_public_ip = true
  }

  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.oracle_linux.images[0].id
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      docker_compose_content = base64encode(file("${path.module}/../docker-compose.simple.yml"))
    }))
  }

  timeouts {
    create = "60m"
  }
}

# Outputs
output "instance_public_ip" {
  description = "Public IP of the PDF Scanner instance"
  value       = oci_core_instance.pdf_scanner.public_ip
}

output "ssh_connection" {
  description = "SSH connection command"
  value       = "ssh opc@${oci_core_instance.pdf_scanner.public_ip}"
}

output "application_urls" {
  description = "Application access URLs"
  value = {
    pdf_scanner = "http://${oci_core_instance.pdf_scanner.public_ip}"
    prometheus  = "http://${oci_core_instance.pdf_scanner.public_ip}:9090"
    grafana     = "http://${oci_core_instance.pdf_scanner.public_ip}:3000"
  }
}