#!/usr/bin/env python3
"""
Test runner script for PDF Scanner application.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and return success status."""
    if description:
        print(f"🧪 {description}")
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {cmd}")
        print(f"Error: {e.stderr}")
        return False, e.stderr

def check_dependencies():
    """Check if required dependencies are installed."""
    print("📦 Checking dependencies...")
    
    try:
        import pytest
        import httpx
        import reportlab
        print("✅ All test dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Run: pip install -r requirements.txt")
        return False

def check_clickhouse():
    """Check if ClickHouse is available."""
    print("🗄️  Checking ClickHouse availability...")
    
    success, _ = run_command("curl -s http://localhost:8123 > /dev/null")
    if success:
        print("✅ ClickHouse is running")
        return True
    else:
        print("⚠️  ClickHouse not available - integration tests will be skipped")
        return False

def run_unit_tests():
    """Run unit tests only."""
    print("\n🔬 Running Unit Tests")
    print("=" * 50)
    
    cmd = "python -m pytest tests/unit/ -v -m unit"
    success, output = run_command(cmd, "Running unit tests")
    
    if success:
        print("✅ Unit tests passed")
    else:
        print("❌ Unit tests failed")
    
    return success

def run_integration_tests(with_clickhouse=True):
    """Run integration tests."""
    print("\n🔗 Running Integration Tests")
    print("=" * 50)
    
    if not with_clickhouse:
        print("⚠️  Skipping database integration tests (ClickHouse not available)")
        return True
    
    cmd = "python -m pytest tests/integration/ -v -m integration"
    success, output = run_command(cmd, "Running integration tests")
    
    if success:
        print("✅ Integration tests passed")
    else:
        print("❌ Integration tests failed")
    
    return success

def run_e2e_tests():
    """Run end-to-end tests."""
    print("\n🌐 Running End-to-End Tests")
    print("=" * 50)
    
    # Check if TEST_WITH_SERVER is set
    if not os.getenv('TEST_WITH_SERVER'):
        print("⚠️  Skipping E2E tests (set TEST_WITH_SERVER=1 to enable)")
        return True
    
    cmd = "python -m pytest tests/e2e/ -v -m e2e"
    success, output = run_command(cmd, "Running end-to-end tests")
    
    if success:
        print("✅ E2E tests passed")
    else:
        print("❌ E2E tests failed")
    
    return success

def run_all_tests(with_clickhouse=True):
    """Run all tests."""
    print("\n🧪 Running All Tests")
    print("=" * 50)
    
    if with_clickhouse:
        if os.getenv('TEST_WITH_SERVER'):
            cmd = "python -m pytest tests/ -v"
        else:
            cmd = "python -m pytest tests/unit/ tests/integration/ -v"
    else:
        cmd = "python -m pytest tests/unit/ -v"
    
    success, output = run_command(cmd, "Running all tests")
    
    if success:
        print("✅ All tests passed")
    else:
        print("❌ Some tests failed")
    
    return success

def run_coverage():
    """Run tests with coverage report."""
    print("\n📊 Running Tests with Coverage")
    print("=" * 50)
    
    # Install coverage if not available
    try:
        import coverage
    except ImportError:
        print("📦 Installing coverage...")
        run_command("pip install coverage", "Installing coverage package")
    
    # Run tests with coverage
    success, _ = run_command(
        "python -m coverage run -m pytest tests/ --tb=short",
        "Running tests with coverage"
    )
    
    if success:
        print("\n📈 Coverage Report:")
        run_command("python -m coverage report -m", "Generating coverage report")
        run_command("python -m coverage html", "Generating HTML coverage report")
        print("📁 HTML coverage report generated in htmlcov/")
    
    return success

def run_performance_tests():
    """Run performance baseline tests."""
    print("\n⚡ Running Performance Tests")
    print("=" * 50)
    
    cmd = "python -m pytest tests/test_integration.py::TestIntegration::test_performance_baseline -v -s"
    success, output = run_command(cmd, "Running performance tests")
    
    return success

def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="PDF Scanner Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests only")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency checks")
    
    args = parser.parse_args()
    
    print("🧪 PDF Scanner Test Suite")
    print("=" * 50)
    
    # Check dependencies
    if not args.skip_deps:
        if not check_dependencies():
            sys.exit(1)
    
    # Check ClickHouse availability
    clickhouse_available = check_clickhouse()
    
    success = True
    
    try:
        if args.unit:
            success = run_unit_tests()
        elif args.integration:
            success = run_integration_tests(clickhouse_available)
        elif args.e2e:
            success = run_e2e_tests()
        elif args.coverage:
            success = run_coverage()
        elif args.performance:
            if not clickhouse_available:
                print("❌ Performance tests require ClickHouse")
                sys.exit(1)
            success = run_performance_tests()
        else:
            # Run all tests by default
            success = run_all_tests(clickhouse_available)
        
        # Final summary
        print("\n" + "=" * 50)
        if success:
            print("🎉 All tests completed successfully!")
            print("\n💡 Next steps:")
            print("   • Review test coverage: open htmlcov/index.html")
            print("   • Run specific tests: python -m pytest tests/test_*.py")
            print("   • Add more test cases as needed")
        else:
            print("❌ Some tests failed. Please review the output above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()