#!/usr/bin/env python3
"""
Test script for oversized and corrupt PDF handling.
"""
import os
import sys
import requests
import time
import subprocess
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from pdf_scanner import PDFScanner

def test_pdf_scanner_direct():
    """Test PDF scanner directly with problematic files."""
    print("🔬 Testing PDF Scanner directly...")
    
    scanner = PDFScanner()
    test_dir = "problematic_test_pdfs"
    
    if not os.path.exists(test_dir):
        print(f"❌ Test directory {test_dir} not found. Run test_oversized_corrupt_pdfs.py first.")
        return
    
    test_results = {}
    
    for filename in os.listdir(test_dir):
        if filename.endswith('.pdf'):
            filepath = os.path.join(test_dir, filename)
            print(f"\n📄 Testing: {filename}")
            
            start_time = time.time()
            try:
                result = scanner.scan_pdf(filepath)
                elapsed = time.time() - start_time
                
                print(f"  Status: {result['status']}")
                if result['status'] == 'success':
                    print(f"  Findings: {result.get('findings_count', 0)}")
                    print(f"  Pages: {result.get('total_pages', 0)}")
                    print(f"  Processing time: {elapsed:.2f}s")
                else:
                    print(f"  Error: {result.get('error', 'Unknown error')}")
                    print(f"  Error type: {result.get('error_type', 'Unknown')}")
                    print(f"  Processing time: {elapsed:.2f}s")
                
                test_results[filename] = {
                    'status': result['status'],
                    'processing_time': elapsed,
                    'error': result.get('error'),
                    'error_type': result.get('error_type'),
                    'findings_count': result.get('findings_count', 0)
                }
                
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  Exception: {str(e)}")
                print(f"  Processing time: {elapsed:.2f}s")
                test_results[filename] = {
                    'status': 'exception',
                    'processing_time': elapsed,
                    'error': str(e),
                    'error_type': 'exception'
                }
    
    return test_results

def test_api_endpoints():
    """Test API endpoints with problematic files."""
    print("\n🌐 Testing API endpoints...")
    
    base_url = "http://localhost:8000"
    test_dir = "problematic_test_pdfs"
    
    # Test health endpoint first
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server not running or unhealthy. Start server first.")
            return None
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to server. Start server first.")
        return None
    
    print("✅ Server is running")
    
    api_results = {}
    
    for filename in os.listdir(test_dir):
        if filename.endswith('.pdf'):
            filepath = os.path.join(test_dir, filename)
            print(f"\n📡 API Testing: {filename}")
            
            # Test upload endpoint
            start_time = time.time()
            try:
                with open(filepath, 'rb') as f:
                    files = {'file': (filename, f, 'application/pdf')}
                    response = requests.post(f"{base_url}/upload", files=files, timeout=300)  # 5 min timeout
                
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"  Status: {result['status']}")
                    print(f"  Processing time: {elapsed:.2f}s")
                    if result['status'] == 'success':
                        print(f"  Findings: {result.get('findings_count', 0)}")
                        print(f"  Pages: {result.get('total_pages', 0)}")
                else:
                    print(f"  HTTP Error: {response.status_code}")
                    print(f"  Response: {response.text[:200]}...")
                    print(f"  Processing time: {elapsed:.2f}s")
                
                api_results[filename] = {
                    'status_code': response.status_code,
                    'processing_time': elapsed,
                    'response': response.json() if response.status_code == 200 else response.text[:500]
                }
                
            except requests.exceptions.Timeout:
                elapsed = time.time() - start_time
                print(f"  Timeout after {elapsed:.2f}s")
                api_results[filename] = {
                    'status_code': 'timeout',
                    'processing_time': elapsed,
                    'response': 'Request timed out'
                }
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  Exception: {str(e)}")
                api_results[filename] = {
                    'status_code': 'exception',
                    'processing_time': elapsed,
                    'response': str(e)
                }
    
    return api_results

def generate_test_report(scanner_results, api_results):
    """Generate a comprehensive test report."""
    print("\n📊 Test Report")
    print("=" * 50)
    
    # Summary statistics
    total_tests = len(scanner_results) if scanner_results else 0
    
    if scanner_results:
        scanner_success = sum(1 for r in scanner_results.values() if r['status'] == 'success')
        scanner_errors = sum(1 for r in scanner_results.values() if r['status'] == 'error')
        scanner_exceptions = sum(1 for r in scanner_results.values() if r['status'] == 'exception')
        
        print(f"\n🔬 Direct Scanner Results:")
        print(f"  Total tests: {total_tests}")
        print(f"  Successful: {scanner_success}")
        print(f"  Handled errors: {scanner_errors}")
        print(f"  Exceptions: {scanner_exceptions}")
        
        # Performance analysis
        processing_times = [r['processing_time'] for r in scanner_results.values()]
        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
            max_time = max(processing_times)
            print(f"  Average processing time: {avg_time:.2f}s")
            print(f"  Maximum processing time: {max_time:.2f}s")
    
    if api_results:
        api_success = sum(1 for r in api_results.values() if r['status_code'] == 200)
        api_errors = sum(1 for r in api_results.values() if isinstance(r['status_code'], int) and r['status_code'] != 200)
        api_timeouts = sum(1 for r in api_results.values() if r['status_code'] == 'timeout')
        
        print(f"\n🌐 API Results:")
        print(f"  Total tests: {len(api_results)}")
        print(f"  Successful (200): {api_success}")
        print(f"  HTTP errors: {api_errors}")  
        print(f"  Timeouts: {api_timeouts}")
        
        # Performance analysis
        api_times = [r['processing_time'] for r in api_results.values() if isinstance(r['processing_time'], (int, float))]
        if api_times:
            avg_time = sum(api_times) / len(api_times)
            max_time = max(api_times)
            print(f"  Average processing time: {avg_time:.2f}s")
            print(f"  Maximum processing time: {max_time:.2f}s")
    
    # Detailed results
    print(f"\n📝 Detailed Results:")
    if scanner_results:
        for filename, result in scanner_results.items():
            status_emoji = "✅" if result['status'] == 'success' else "⚠️" if result['status'] == 'error' else "❌"
            print(f"  {status_emoji} {filename}: {result['status']} ({result['processing_time']:.2f}s)")
            if result.get('error'):
                print(f"    Error: {result['error'][:100]}...")
    
    # Save detailed report to file
    report_data = {
        'timestamp': time.time(),
        'scanner_results': scanner_results,
        'api_results': api_results
    }
    
    with open('pdf_handling_test_report.json', 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n💾 Detailed report saved to: pdf_handling_test_report.json")

def main():
    """Main test function."""
    print("🧪 PDF Handling Test Suite")
    print("Testing oversized and corrupt PDF handling...")
    
    # Generate test files if they don't exist
    test_dir = "problematic_test_pdfs"
    if not os.path.exists(test_dir):
        print(f"\n📁 Creating test files in {test_dir}...")
        try:
            subprocess.run([sys.executable, "test_oversized_corrupt_pdfs.py"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to generate test files: {e}")
            return
    
    # Run tests
    scanner_results = test_pdf_scanner_direct()
    api_results = test_api_endpoints()
    
    # Generate report
    generate_test_report(scanner_results, api_results)
    
    print("\n🎉 Testing complete!")

if __name__ == "__main__":
    main()