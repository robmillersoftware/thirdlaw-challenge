# PDF Scanner - Minimal OCI Deployment for Demo

This guide provides the **absolute minimum** setup to deploy your PDF scanner application to Oracle Cloud Infrastructure for a job interview demonstration.

## 🎯 What This Deploys

- **1 Always Free ARM instance** (VM.Standard.A1.Flex)
- **Single-node deployment** with all services on one machine
- **Automatic setup** via cloud-init
- **Public access** to demonstrate functionality

## 📋 Prerequisites

1. **OCI Account** (free tier is sufficient)
2. **Terraform installed** locally
3. **Basic OCI setup** (API keys, etc.)

## 🚀 Quick Deployment (5 minutes)

### Step 1: Get OCI Credentials

1. Log into OCI Console
2. Go to **Profile → User Settings**
3. Note your **User OCID**
4. Go to **Profile → Tenancy** 
5. Note your **Tenancy OCID**
6. Create API Key:
   - **Profile → API Keys → Add API Key**
   - Download the private key file
   - Note the **fingerprint**

### Step 2: Configure Deployment

```bash
# Copy and edit configuration
cp terraform/terraform.tfvars.example terraform/terraform.tfvars

# Edit terraform/terraform.tfvars with your OCI details:
# - tenancy_ocid
# - user_ocid  
# - fingerprint
# - private_key_path (path to downloaded .pem file)
# - region (e.g., "us-ashburn-1")
# - compartment_ocid (same as tenancy_ocid for root)
```

### Step 3: Deploy

```bash
# One command deployment
./deploy-oci.sh deploy
```

That's it! The script will:
- ✅ Generate SSH keys if needed
- ✅ Deploy infrastructure via Terraform
- ✅ Configure firewall rules
- ✅ Install Docker and start services
- ✅ Provide access URLs

## 🔗 Access Your Demo

After deployment (2-3 minutes for full startup):

```bash
# Your deployment info will show:
PDF Scanner:  http://YOUR_IP:8000
Prometheus:   http://YOUR_IP:9090  
Grafana:      http://YOUR_IP:3000 (admin/demo123)
```

## 🎤 For the Interview

### Key Points to Highlight:

1. **Infrastructure as Code**: Complete Terraform setup
2. **Cloud-Native**: Leverages OCI Always Free tier
3. **Production-Ready**: Monitoring, metrics, proper security
4. **Scalable Architecture**: Easy to extend to multi-node
5. **Cost-Effective**: Uses free resources only

### Demo Flow Suggestion:

1. **Show the application** - Upload a test PDF
2. **Show monitoring** - Prometheus metrics, Grafana dashboard
3. **Show the code** - Terraform infrastructure, Docker setup
4. **Explain scaling** - How this extends to production with Swarm

### Technical Discussion Points:

- **Why single-node**: Minimal for demo, but architecture supports scaling
- **Security**: Proper VCN, security groups, minimal attack surface
- **Monitoring**: Production-ready observability from day one
- **Automation**: Complete IaC approach, no manual steps

## 🗑️ Cleanup

```bash
# Destroy everything (saves costs)
./deploy-oci.sh destroy
```

## 📁 Architecture Overview

```
Internet → OCI Load Balancer → Single VM:
                                ├── PDF Scanner (Docker)
                                ├── ClickHouse (Docker)  
                                ├── Prometheus (Docker)
                                └── Grafana (Docker)
```

## 💰 Cost

- **$0/month** using Always Free tier
- 1 ARM VM (1 OCPU, 6GB RAM)
- 47GB boot volume
- Always Free tier includes this permanently

## 🔧 Troubleshooting

### If deployment fails:
```bash
# Check status
./deploy-oci.sh status

# SSH to investigate
ssh opc@YOUR_IP
sudo docker logs pdf-scanner_pdf-scanner_1
```

### Common issues:
- **Service limits**: OCI may have regional limits on Always Free
- **Startup time**: Allow 2-3 minutes for Docker services to start
- **Firewall**: Cloud-init configures this automatically

## 🏆 Why This Approach

**For Interview Context:**
- Demonstrates cloud expertise
- Shows infrastructure automation skills  
- Proves understanding of production concerns
- Minimal cost/complexity while remaining professional
- Easy to explain and modify during discussion

This setup gives you a live, publicly accessible demo running on enterprise cloud infrastructure - perfect for impressing interviewers while staying within free tier limits!