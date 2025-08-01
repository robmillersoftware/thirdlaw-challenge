#!/usr/bin/env python3
"""
Simple test script to verify the PDF scanner application is working.
"""

import requests
import time
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_test_pdf(filename="test_sample.pdf"):
    """Create a test PDF with sensitive data for testing."""
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Add some text with sensitive information
    c.drawString(100, height - 100, "Test Document - PDF Scanner")
    c.drawString(100, height - 140, "Contact Information:")
    c.drawString(120, height - 160, "Email: john.doe@example.com")
    c.drawString(120, height - 180, "Email: support@testcompany.org")
    c.drawString(120, height - 200, "SSN: 123-45-6789")
    c.drawString(120, height - 220, "SSN: 987 65 4321")
    c.drawString(120, height - 240, "Phone: (555) 123-4567")
    
    # Add content on second page
    c.showPage()
    c.drawString(100, height - 100, "Page 2 - Additional Information")
    c.drawString(120, height - 140, "Alternative contact: jane.smith@company.com")
    c.drawString(120, height - 160, "Social Security: 555444333")
    
    c.save()
    return filename

def test_health_endpoint(base_url="http://localhost:8000"):
    """Test the health endpoint."""
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✅ Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_upload_pdf(base_url="http://localhost:8000", pdf_file="test_sample.pdf"):
    """Test PDF upload and scanning."""
    try:
        with open(pdf_file, 'rb') as f:
            files = {'file': (pdf_file, f, 'application/pdf')}
            response = requests.post(f"{base_url}/upload", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload successful: {result['filename']}")
            print(f"   📊 Processing time: {result['processing_time_ms']}ms")
            print(f"   📄 Pages: {result.get('total_pages', 'N/A')}")
            print(f"   🔍 Findings: {result.get('findings_count', 0)}")
            
            if result.get('findings'):
                print("   📋 Detected sensitive data:")
                for finding in result['findings']:
                    print(f"      {finding['type']}: {finding['value']} (page {finding['page']})")
            
            return True, result['document_id']
        else:
            print(f"❌ Upload failed: {response.status_code} - {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ Upload test failed: {e}")
        return False, None

def test_findings_endpoint(base_url="http://localhost:8000", document_id=None):
    """Test the findings endpoint."""
    try:
        url = f"{base_url}/findings"
        if document_id:
            url += f"?document_id={document_id}"
        
        response = requests.get(url)
        
        if response.status_code == 200:
            findings = response.json()
            print(f"✅ Findings retrieved: {len(findings)} documents")
            
            if findings:
                latest = findings[0]
                print(f"   📄 Latest: {latest['filename']} ({latest['findings_count']} findings)")
            
            return True
        else:
            print(f"❌ Findings request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Findings test failed: {e}")
        return False

def test_stats_endpoint(base_url="http://localhost:8000"):
    """Test the stats endpoint."""
    try:
        response = requests.get(f"{base_url}/stats")
        
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Stats retrieved:")
            print(f"   📊 Total documents: {stats.get('total_documents', 0)}")
            print(f"   🔍 Total findings: {stats.get('total_findings', 0)}")
            print(f"   ⏱️  Avg processing time: {stats.get('avg_processing_time_ms', 0):.1f}ms")
            return True
        else:
            print(f"❌ Stats request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Stats test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 PDF Scanner Application Tests")
    print("=" * 40)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    if not test_health_endpoint(base_url):
        print("❌ Application is not running. Please start the server first:")
        print("   ./start.sh")
        return
    
    # Test 2: Create and upload test PDF
    print("\n2. Creating test PDF...")
    test_pdf = create_test_pdf()
    print(f"✅ Created test PDF: {test_pdf}")
    
    print("\n3. Testing PDF upload and scanning...")
    success, document_id = test_upload_pdf(base_url, test_pdf)
    
    if success:
        # Test 3: Check findings
        print("\n4. Testing findings endpoint...")
        test_findings_endpoint(base_url, document_id)
        
        # Test 4: Check stats
        print("\n5. Testing stats endpoint...")
        test_stats_endpoint(base_url)
        
        print("\n🎉 All tests completed successfully!")
        print(f"🌐 Visit {base_url} to try the web interface")
    else:
        print("\n❌ Upload test failed, skipping remaining tests")
    
    # Cleanup
    if os.path.exists(test_pdf):
        os.remove(test_pdf)
        print(f"🧹 Cleaned up test file: {test_pdf}")

if __name__ == "__main__":
    main()