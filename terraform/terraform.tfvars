# OCI Configuration - Copy this to terraform.tfvars and fill in your values

# Your OCI tenancy OCID (found in OCI Console -> Profile -> Tenancy)
tenancy_ocid = "ocid1.tenancy.oc1..aaaaaaaa2abdovpnbayulsjb6vo3huxutgrwiet4kl5hc2akkhk6ehjt5mka"

# Your user OCID (found in OCI Console -> Profile -> User Settings)
user_ocid = "ocid1.user.oc1..aaaaaaaavxocsxa3owvnsuskcuqgn2pqgua2ekol2dpjbpmge3pyl2jmkula"

# Your API key fingerprint (found in OCI Console -> Profile -> API Keys)
fingerprint = "25:84:48:b0:5d:53:62:a8:ea:71:f1:a8:a2:e4:62:5a"

# Path to your private API key file (download from OCI Console)
private_key_path = "~/.oci/oci_api_key.pem"

# OCI region (e.g., us-ashburn-1, us-phoenix-1, uk-london-1)
region = "us-ashburn-1"

# Your SSH public key content (cat ~/.ssh/id_rsa.pub)
ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIO25PUJpzmKEd0kNva5DL8+auCo+eXNVHBsY5scZq3Bm robmillersoftware@gmail.com"

# Compartment OCID (use tenancy_ocid for root compartment, or create a new compartment)
compartment_ocid = "ocid1.tenancy.oc1..aaaaaaaa2abdovpnbayulsjb6vo3huxutgrwiet4kl5hc2akkhk6ehjt5mka"  # Same as tenancy_ocid for root compartment