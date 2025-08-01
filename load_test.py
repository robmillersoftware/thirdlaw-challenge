#!/usr/bin/env python3
"""
Load testing script for PDF Scanner & Redactor with comprehensive metrics.
"""

import os
import time
import random
import asyncio
import aiohttp
import aiofiles
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import statistics
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import argparse


@dataclass
class TestResult:
    """Individual test result."""
    timestamp: float
    filename: str
    file_size: int
    response_time_ms: float
    status_code: int
    success: bool
    findings_count: int = 0
    redacted_count: int = 0
    processing_time_ms: float = 0
    error: str = None


@dataclass
class LoadTestMetrics:
    """Comprehensive load test metrics."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate_percent: float
    total_duration_seconds: float
    requests_per_second: float
    
    # Response time metrics
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    
    # Processing metrics
    avg_processing_time_ms: float
    total_findings: int
    total_redactions: int
    avg_findings_per_doc: float
    
    # Throughput metrics
    total_bytes_processed: int
    mb_per_second: float
    
    # Error breakdown
    error_types: Dict[str, int]


class LoadTester:
    """Asynchronous load tester for PDF scanner."""
    
    def __init__(self, base_url: str = "http://localhost:8000", 
                 pdf_directory: str = "test_pdfs"):
        self.base_url = base_url
        self.pdf_directory = Path(pdf_directory)
        self.results: List[TestResult] = []
        
        # Get list of test PDFs
        self.pdf_files = list(self.pdf_directory.glob("*.pdf"))
        if not self.pdf_files:
            raise ValueError(f"No PDF files found in {pdf_directory}")
        
        print(f"🔍 Found {len(self.pdf_files)} test PDFs")
    
    async def upload_pdf(self, session: aiohttp.ClientSession, pdf_path: Path) -> TestResult:
        """Upload a single PDF and measure performance."""
        start_time = time.time()
        
        try:
            # Read file
            async with aiofiles.open(pdf_path, 'rb') as f:
                file_data = await f.read()
            
            file_size = len(file_data)
            
            # Prepare multipart form data
            form_data = aiohttp.FormData()
            form_data.add_field('file', file_data, 
                              filename=pdf_path.name, 
                              content_type='application/pdf')
            
            # Make request
            async with session.post(f"{self.base_url}/upload-and-redact", 
                                  data=form_data) as response:
                
                response_time_ms = (time.time() - start_time) * 1000
                
                result = TestResult(
                    timestamp=start_time,
                    filename=pdf_path.name,
                    file_size=file_size,
                    response_time_ms=response_time_ms,
                    status_code=response.status,
                    success=response.status == 200
                )
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        result.findings_count = data.get('findings_count', 0)
                        result.processing_time_ms = data.get('processing_time_ms', 0)
                        
                        # Get redaction count
                        redaction = data.get('redaction', {})
                        if isinstance(redaction, dict):
                            result.redacted_count = redaction.get('redacted_count', 0)
                        
                    except Exception as e:
                        result.error = f"JSON parse error: {e}"
                        result.success = False
                else:
                    try:
                        error_data = await response.text()
                        result.error = f"HTTP {response.status}: {error_data[:200]}"
                    except:
                        result.error = f"HTTP {response.status}"
                
                return result
                
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return TestResult(
                timestamp=start_time,
                filename=pdf_path.name,
                file_size=0,
                response_time_ms=response_time_ms,
                status_code=0,
                success=False,
                error=str(e)
            )
    
    async def run_concurrent_test(self, concurrent_users: int, 
                                total_requests: int, 
                                duration_seconds: int = None) -> LoadTestMetrics:
        """Run concurrent load test."""
        
        print(f"🚀 Starting load test:")
        print(f"   • Concurrent users: {concurrent_users}")
        print(f"   • Total requests: {total_requests}")
        if duration_seconds:
            print(f"   • Max duration: {duration_seconds} seconds")
        print(f"   • Test PDFs: {len(self.pdf_files)}")
        
        start_time = time.time()
        completed_requests = 0
        
        # Create aiohttp session with appropriate limits
        connector = aiohttp.TCPConnector(
            limit=concurrent_users * 2,
            limit_per_host=concurrent_users * 2
        )
        
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout
        
        async with aiohttp.ClientSession(
            connector=connector, 
            timeout=timeout
        ) as session:
            
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(concurrent_users)
            
            async def limited_upload(pdf_path: Path) -> TestResult:
                async with semaphore:
                    return await self.upload_pdf(session, pdf_path)
            
            # Generate request queue
            request_queue = []
            for i in range(total_requests):
                pdf_path = random.choice(self.pdf_files)
                request_queue.append(pdf_path)
            
            # Execute requests with progress tracking
            tasks = []
            for pdf_path in request_queue:
                # Check duration limit
                if duration_seconds and (time.time() - start_time) > duration_seconds:
                    break
                
                task = asyncio.create_task(limited_upload(pdf_path))
                tasks.append(task)
            
            # Process completed tasks with progress reporting
            self.results = []
            for i, task in enumerate(asyncio.as_completed(tasks)):
                try:
                    result = await task
                    self.results.append(result)
                    completed_requests += 1
                    
                    # Progress reporting
                    if completed_requests % 50 == 0 or completed_requests == len(tasks):
                        elapsed = time.time() - start_time
                        rate = completed_requests / elapsed if elapsed > 0 else 0
                        success_rate = sum(1 for r in self.results if r.success) / len(self.results) * 100
                        
                        print(f"📊 Progress: {completed_requests}/{len(tasks)} "
                              f"({completed_requests/len(tasks)*100:.1f}%) "
                              f"- Rate: {rate:.1f} req/sec "
                              f"- Success: {success_rate:.1f}%")
                        
                except Exception as e:
                    print(f"❌ Task error: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n✅ Load test completed in {duration:.1f} seconds")
        
        return self._calculate_metrics(duration)
    
    def _calculate_metrics(self, duration_seconds: float) -> LoadTestMetrics:
        """Calculate comprehensive test metrics."""
        
        if not self.results:
            raise ValueError("No results to analyze")
        
        # Basic counts
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.success)
        failed_requests = total_requests - successful_requests
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Response time metrics
        response_times = [r.response_time_ms for r in self.results]
        successful_response_times = [r.response_time_ms for r in self.results if r.success]
        
        if successful_response_times:
            avg_response_time = statistics.mean(successful_response_times)
            min_response_time = min(successful_response_times)
            max_response_time = max(successful_response_times)
            
            sorted_times = sorted(successful_response_times)
            p50 = self._percentile(sorted_times, 50)
            p95 = self._percentile(sorted_times, 95)
            p99 = self._percentile(sorted_times, 99)
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p50 = p95 = p99 = 0
        
        # Processing time metrics
        processing_times = [r.processing_time_ms for r in self.results if r.success and r.processing_time_ms > 0]
        avg_processing_time = statistics.mean(processing_times) if processing_times else 0
        
        # Business metrics
        total_findings = sum(r.findings_count for r in self.results if r.success)
        total_redactions = sum(r.redacted_count for r in self.results if r.success)
        avg_findings = total_findings / successful_requests if successful_requests > 0 else 0
        
        # Throughput metrics
        total_bytes = sum(r.file_size for r in self.results if r.success)
        mb_per_second = (total_bytes / (1024 * 1024)) / duration_seconds if duration_seconds > 0 else 0
        requests_per_second = total_requests / duration_seconds if duration_seconds > 0 else 0
        
        # Error analysis
        error_types = {}
        for result in self.results:
            if not result.success and result.error:
                error_key = self._categorize_error(result.error)
                error_types[error_key] = error_types.get(error_key, 0) + 1
        
        return LoadTestMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            success_rate_percent=round(success_rate, 2),
            total_duration_seconds=round(duration_seconds, 2),
            requests_per_second=round(requests_per_second, 2),
            
            avg_response_time_ms=round(avg_response_time, 2),
            min_response_time_ms=round(min_response_time, 2),
            max_response_time_ms=round(max_response_time, 2),
            p50_response_time_ms=round(p50, 2),
            p95_response_time_ms=round(p95, 2),
            p99_response_time_ms=round(p99, 2),
            
            avg_processing_time_ms=round(avg_processing_time, 2),
            total_findings=total_findings,
            total_redactions=total_redactions,
            avg_findings_per_doc=round(avg_findings, 2),
            
            total_bytes_processed=total_bytes,
            mb_per_second=round(mb_per_second, 2),
            
            error_types=error_types
        )
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile from sorted data."""
        if not data:
            return 0
        
        k = (len(data) - 1) * (percentile / 100)
        f = int(k)
        c = k - f
        
        if f == len(data) - 1:
            return data[f]
        
        return data[f] + c * (data[f + 1] - data[f])
    
    def _categorize_error(self, error: str) -> str:
        """Categorize errors for analysis."""
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            return "timeout"
        elif "connection" in error_lower:
            return "connection_error"
        elif "http 400" in error_lower:
            return "bad_request"
        elif "http 413" in error_lower:
            return "file_too_large"
        elif "http 500" in error_lower:
            return "server_error"
        elif "json" in error_lower:
            return "json_parse_error"
        else:
            return "other"
    
    def print_results(self, metrics: LoadTestMetrics):
        """Print comprehensive test results."""
        
        print("\n" + "="*80)
        print("🎯 LOAD TEST RESULTS")
        print("="*80)
        
        # Overall metrics
        print(f"\n📊 OVERALL PERFORMANCE:")
        print(f"   • Total Requests: {metrics.total_requests:,}")
        print(f"   • Successful: {metrics.successful_requests:,} ({metrics.success_rate_percent}%)")
        print(f"   • Failed: {metrics.failed_requests:,}")
        print(f"   • Duration: {metrics.total_duration_seconds:.1f} seconds")
        print(f"   • Throughput: {metrics.requests_per_second:.1f} requests/second")
        
        # Response time metrics
        print(f"\n⏱️  RESPONSE TIME METRICS (ms):")
        print(f"   • Average: {metrics.avg_response_time_ms:.1f} ms")
        print(f"   • Minimum: {metrics.min_response_time_ms:.1f} ms")
        print(f"   • Maximum: {metrics.max_response_time_ms:.1f} ms")
        print(f"   • 50th percentile (median): {metrics.p50_response_time_ms:.1f} ms")
        print(f"   • 95th percentile: {metrics.p95_response_time_ms:.1f} ms")
        print(f"   • 99th percentile: {metrics.p99_response_time_ms:.1f} ms")
        
        # Processing metrics
        print(f"\n🔍 PROCESSING METRICS:")
        print(f"   • Average processing time: {metrics.avg_processing_time_ms:.1f} ms")
        print(f"   • Total sensitive data found: {metrics.total_findings:,}")
        print(f"   • Total redactions made: {metrics.total_redactions:,}")
        print(f"   • Average findings per document: {metrics.avg_findings_per_doc:.1f}")
        
        # Data throughput
        print(f"\n📈 DATA THROUGHPUT:")
        print(f"   • Total data processed: {metrics.total_bytes_processed / (1024*1024):.1f} MB")
        print(f"   • Data throughput: {metrics.mb_per_second:.1f} MB/second")
        
        # Error analysis
        if metrics.error_types:
            print(f"\n❌ ERROR BREAKDOWN:")
            for error_type, count in sorted(metrics.error_types.items(), 
                                          key=lambda x: x[1], reverse=True):
                print(f"   • {error_type}: {count} occurrences")
        else:
            print(f"\n✅ NO ERRORS DETECTED")
        
        # Performance assessment
        print(f"\n🎭 PERFORMANCE ASSESSMENT:")
        
        if metrics.success_rate_percent >= 99:
            reliability = "🟢 Excellent"
        elif metrics.success_rate_percent >= 95:
            reliability = "🟡 Good"
        elif metrics.success_rate_percent >= 90:
            reliability = "🟠 Fair"
        else:
            reliability = "🔴 Poor"
        
        if metrics.p95_response_time_ms <= 3000:
            performance = "🟢 Excellent"
        elif metrics.p95_response_time_ms <= 5000:
            performance = "🟡 Good"
        elif metrics.p95_response_time_ms <= 10000:
            performance = "🟠 Fair"
        else:
            performance = "🔴 Poor"
        
        print(f"   • Reliability: {reliability} ({metrics.success_rate_percent}% success rate)")
        print(f"   • Performance: {performance} (P95: {metrics.p95_response_time_ms:.0f}ms)")
        print(f"   • Throughput: {metrics.requests_per_second:.1f} req/sec")
        
        print("\n" + "="*80)
    
    def save_results(self, metrics: LoadTestMetrics, filename: str = "load_test_results.json"):
        """Save detailed results to JSON file."""
        
        results_data = {
            "test_metadata": {
                "timestamp": time.time(),
                "test_duration": metrics.total_duration_seconds,
                "pdf_directory": str(self.pdf_directory),
                "base_url": self.base_url
            },
            "metrics": asdict(metrics),
            "detailed_results": [
                {
                    "filename": r.filename,
                    "response_time_ms": r.response_time_ms,
                    "processing_time_ms": r.processing_time_ms,
                    "success": r.success,
                    "findings_count": r.findings_count,
                    "redacted_count": r.redacted_count,
                    "file_size": r.file_size,
                    "error": r.error
                } for r in self.results
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"📁 Detailed results saved to: {filename}")


async def main():
    parser = argparse.ArgumentParser(description="Load test PDF Scanner & Redactor")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL of the service")
    parser.add_argument("--pdfs", default="test_pdfs", 
                       help="Directory containing test PDFs")
    parser.add_argument("--requests", "-r", type=int, default=100,
                       help="Total number of requests")
    parser.add_argument("--concurrent", "-c", type=int, default=10,
                       help="Number of concurrent users")
    parser.add_argument("--duration", "-d", type=int, 
                       help="Max test duration in seconds")
    parser.add_argument("--output", "-o", default="load_test_results.json",
                       help="Output file for detailed results")
    
    args = parser.parse_args()
    
    # Create load tester
    tester = LoadTester(args.url, args.pdfs)
    
    # Run test
    try:
        metrics = await tester.run_concurrent_test(
            concurrent_users=args.concurrent,
            total_requests=args.requests,
            duration_seconds=args.duration
        )
        
        # Display results
        tester.print_results(metrics)
        
        # Save results
        tester.save_results(metrics, args.output)
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")


if __name__ == "__main__":
    # Install required packages if not available
    try:
        import aiohttp
        import aiofiles
    except ImportError:
        print("📦 Installing required packages...")
        import subprocess
        subprocess.check_call(["pip", "install", "aiohttp", "aiofiles"])
    
    asyncio.run(main())