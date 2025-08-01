#!/usr/bin/env python3

import asyncio
import aiohttp
import time
import json
import argparse
from pathlib import Path
import statistics

async def upload_pdf(session, pdf_path, base_url="http://localhost:8000"):
    """Upload a single PDF file"""
    with open(pdf_path, 'rb') as f:
        data = aiohttp.FormData()
        data.add_field('file', f, filename=pdf_path.name, content_type='application/pdf')
        
        start_time = time.time()
        try:
            async with session.post(f"{base_url}/upload", data=data) as response:
                end_time = time.time()
                return {
                    'status': response.status,
                    'time': end_time - start_time,
                    'success': response.status == 200,
                    'file': pdf_path.name
                }
        except Exception as e:
            end_time = time.time()
            return {
                'status': 0,
                'time': end_time - start_time,
                'success': False,
                'error': str(e),
                'file': pdf_path.name
            }

async def run_load_test(concurrent_requests, total_requests, base_url, pdf_files):
    """Run load test with specified parameters"""
    print(f"Starting load test:")
    print(f"  Base URL: {base_url}")
    print(f"  Concurrent requests: {concurrent_requests}")
    print(f"  Total requests: {total_requests}")
    print(f"  PDF files available: {len(pdf_files)}")
    print()
    
    connector = aiohttp.TCPConnector(limit=concurrent_requests)
    timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        async def bounded_upload(pdf_path):
            async with semaphore:
                return await upload_pdf(session, pdf_path, base_url)
        
        start_time = time.time()
        
        # For large request counts, use a queue-based approach to limit memory
        if total_requests > 2000:
            print("Using queue-based approach for large request count...")
            results = []
            
            # Create a queue of work items
            queue = asyncio.Queue(maxsize=concurrent_requests * 2)  # Small buffer
            
            # Producer: Add work to queue
            async def producer():
                for i in range(total_requests):
                    pdf_file = pdf_files[i % len(pdf_files)]
                    await queue.put((i, pdf_file))
                # Signal completion
                for _ in range(concurrent_requests):
                    await queue.put(None)
            
            # Consumer: Process work from queue
            async def consumer():
                while True:
                    item = await queue.get()
                    if item is None:  # Shutdown signal
                        break
                    i, pdf_file = item
                    result = await upload_pdf(session, pdf_file, base_url)
                    results.append(result)
                    
                    if (i + 1) % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = (i + 1) / elapsed if elapsed > 0 else 0
                        print(f"Completed {i + 1}/{total_requests} requests ({rate:.1f} req/sec)")
            
            # Start producer and consumers
            producer_task = asyncio.create_task(producer())
            consumer_tasks = [asyncio.create_task(consumer()) for _ in range(concurrent_requests)]
            
            await producer_task
            await asyncio.gather(*consumer_tasks)
            
        else:
            # For smaller request counts, use the original approach
            tasks = []
            for i in range(total_requests):
                pdf_file = pdf_files[i % len(pdf_files)]
                tasks.append(bounded_upload(pdf_file))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
    
    # Process results
    successful_results = []
    failed_results = []
    
    for result in results:
        if isinstance(result, Exception):
            failed_results.append({'error': str(result), 'success': False})
        elif result['success']:
            successful_results.append(result)
        else:
            failed_results.append(result)
    
    # Calculate statistics
    success_count = len(successful_results)
    failure_count = len(failed_results)
    success_rate = (success_count / total_requests) * 100
    
    if successful_results:
        response_times = [r['time'] for r in successful_results]
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        median_response_time = statistics.median(response_times)
        requests_per_second = success_count / total_time
    else:
        avg_response_time = 0
        min_response_time = 0
        max_response_time = 0
        median_response_time = 0
        requests_per_second = 0
    
    # Print results
    print("=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)
    print(f"Total requests: {total_requests}")
    print(f"Successful requests: {success_count}")
    print(f"Failed requests: {failure_count}")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"Total test time: {total_time:.2f} seconds")
    print(f"Requests per second: {requests_per_second:.2f}")
    print()
    
    if successful_results:
        print("Response Time Statistics:")
        print(f"  Average: {avg_response_time:.3f}s")
        print(f"  Median: {median_response_time:.3f}s")
        print(f"  Min: {min_response_time:.3f}s")
        print(f"  Max: {max_response_time:.3f}s")
    
    if failed_results:
        print()
        print("Sample failures:")
        for i, failure in enumerate(failed_results[:5]):  # Show first 5 failures
            if 'error' in failure:
                print(f"  {i+1}. Error: {failure['error']}")
            else:
                print(f"  {i+1}. Status {failure.get('status', 'unknown')}: {failure.get('file', 'unknown')}")
    
    # Save detailed results to JSON
    results_data = {
        'test_parameters': {
            'concurrent_requests': concurrent_requests,
            'total_requests': total_requests,
            'base_url': base_url,
            'pdf_files_count': len(pdf_files)
        },
        'summary': {
            'total_requests': total_requests,
            'successful_requests': success_count,
            'failed_requests': failure_count,
            'success_rate': success_rate,
            'total_time': total_time,
            'requests_per_second': requests_per_second,
            'avg_response_time': avg_response_time,
            'median_response_time': median_response_time,
            'min_response_time': min_response_time,
            'max_response_time': max_response_time
        },
        'detailed_results': {
            'successful': successful_results,
            'failed': failed_results
        }
    }
    
    with open('load_test_results.json', 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\nDetailed results saved to: load_test_results.json")
    return results_data

def find_pdf_files():
    """Find available PDF files for testing"""
    pdf_paths = []
    
    # Look for test PDFs in common locations
    test_dirs = [
        Path('test_pdfs'),
        Path('problematic_test_pdfs'),
        Path('.')  # Current directory
    ]
    
    for test_dir in test_dirs:
        if test_dir.exists():
            pdf_files = list(test_dir.glob('*.pdf'))
            pdf_paths.extend(pdf_files)
    
    if not pdf_paths:
        print("Error: No PDF files found for testing!")
        print("Please ensure you have PDF files in one of these directories:")
        for test_dir in test_dirs:
            print(f"  - {test_dir}")
        return []
    
    return pdf_paths

async def main():
    parser = argparse.ArgumentParser(description='Load test the PDF scanner service')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='Base URL of the PDF scanner service')
    parser.add_argument('--concurrent', '-c', type=int, default=10,
                       help='Number of concurrent requests')
    parser.add_argument('--requests', '-r', type=int, default=100,
                       help='Total number of requests to make')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test: 5 concurrent, 20 total requests')
    
    args = parser.parse_args()
    
    if args.quick:
        args.concurrent = 5
        args.requests = 20
        print("Quick test mode enabled")
        print()
    
    # Find PDF files
    pdf_files = find_pdf_files()
    if not pdf_files:
        return
    
    print(f"Found {len(pdf_files)} PDF files for testing")
    
    # Run the load test
    await run_load_test(args.concurrent, args.requests, args.url, pdf_files)

if __name__ == "__main__":
    asyncio.run(main())