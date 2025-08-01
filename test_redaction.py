#!/usr/bin/env python3
"""
Test redaction functionality specifically.
"""
import os
import sys
import requests
import time

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from pdf_scanner import PDFScanner

def test_redaction_direct():
    """Test redaction directly with PDF scanner."""
    print("🔍 Testing redaction functionality directly...")
    
    scanner = PDFScanner()
    test_file = "problematic_test_pdfs/normal_with_sensitive_data.pdf"
    
    if not os.path.exists(test_file):
        print(f"❌ Test file {test_file} not found.")
        return False
    
    print(f"📄 Testing redaction with: {test_file}")
    
    try:
        # First scan the file
        scan_result = scanner.scan_pdf(test_file)
        print(f"✅ Scan successful: {scan_result['findings_count']} findings")
        
        # Test scan and redact
        redact_result = scanner.scan_and_redact_pdf(test_file, "test_redacted_output.pdf")
        print(f"✅ Scan and redact result: {redact_result['status']}")
        
        if redact_result['status'] == 'success':
            print(f"   Redaction status: {redact_result['redaction']['status']}")
            if 'redacted_count' in redact_result['redaction']:
                print(f"   Items redacted: {redact_result['redaction']['redacted_count']}")
            if 'output_path' in redact_result['redaction']:
                print(f"   Output file: {redact_result['redaction']['output_path']}")
                if os.path.exists(redact_result['redaction']['output_path']):
                    print(f"   ✅ Redacted file created successfully")
                    return True
        else:
            print(f"   ❌ Redaction failed: {redact_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Exception during redaction test: {e}")
        return False
    
    return False

def test_redaction_api():
    """Test redaction through API."""
    print("\n🌐 Testing redaction through API...")
    
    base_url = "http://localhost:8000"
    test_file = "problematic_test_pdfs/normal_with_sensitive_data.pdf"
    
    # Test health endpoint first
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server not running or unhealthy.")
            return False
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to server.")
        return False
    
    print("✅ Server is running")
    
    try:
        with open(test_file, 'rb') as f:
            files = {'file': ('test.pdf', f, 'application/pdf')}
            response = requests.post(f"{base_url}/upload-and-redact", files=files, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload and redact successful")
            print(f"   Status: {result['status']}")
            print(f"   Findings: {result.get('findings_count', 0)}")
            
            if 'redaction' in result:
                redaction = result['redaction']
                print(f"   Redaction status: {redaction['status']}")
                if 'redacted_count' in redaction:
                    print(f"   Items redacted: {redaction['redacted_count']}")
                
                # Try to download the redacted file if available
                if result.get('document_id'):
                    download_url = f"{base_url}/download-redacted/{result['document_id']}"
                    download_response = requests.get(download_url, timeout=30)
                    if download_response.status_code == 200:
                        print(f"   ✅ Redacted file download successful")
                        return True
                    else:
                        print(f"   ⚠️ Download failed: {download_response.status_code}")
            
            return True
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ API Exception: {e}")
        return False

def main():
    """Main test function."""
    print("🧪 Redaction Test Suite")
    print("Testing PDF redaction functionality...")
    
    # Test direct redaction
    direct_success = test_redaction_direct()
    
    # Test API redaction
    api_success = test_redaction_api()
    
    print(f"\n📊 Test Results:")
    print(f"   Direct redaction: {'✅ PASSED' if direct_success else '❌ FAILED'}")
    print(f"   API redaction: {'✅ PASSED' if api_success else '❌ FAILED'}")
    
    if direct_success and api_success:
        print("\n🎉 All redaction tests passed!")
        return True
    else:
        print("\n❌ Some redaction tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)