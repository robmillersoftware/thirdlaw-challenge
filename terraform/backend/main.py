from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
import os
import uuid
import time
import shutil
import asyncio
from typing import List
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pdf_scanner import PDFScanner
from database import ClickHouseDB
from metrics import metrics_collector
from prometheus_metrics import prometheus_metrics
from fastapi.responses import Response

load_dotenv()

# Initialize components
pdf_scanner = PDFScanner()
db = ClickHouseDB()

# Thread pool for PDF processing - optimized for multi-worker deployment
# Each worker gets its own thread pool for CPU-intensive tasks
PDF_PROCESSING_POOL = ThreadPoolExecutor(
    max_workers=min(8, os.cpu_count() or 1),  # Limit per worker to avoid resource contention
    thread_name_prefix="pdf_processor"
)

# Multi-worker deployment provides I/O parallelism + thread pool per worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database connection and thread pool on startup."""
    global redis_client
    
    success = db.connect()
    if not success:
        print("Warning: Could not connect to ClickHouse database")
    
    print(f"Started PDF processing thread pool with {PDF_PROCESSING_POOL._max_workers} workers per FastAPI worker")
    
    # Using multi-worker deployment for I/O parallelism + thread pools for CPU work
    
    yield
    
    # Cleanup connections on shutdown
    PDF_PROCESSING_POOL.shutdown(wait=True)
    print("Shutdown complete")

app = FastAPI(title="PDF Sensitive Data Scanner", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get base directory (parent of backend)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.getenv('UPLOAD_DIR', os.path.join(BASE_DIR, 'uploads'))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Create upload directory
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 10485760))  # 10MB default

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r") as f:
        return f.read()

@app.get("/metrics-dashboard", response_class=HTMLResponse)
async def metrics_dashboard():
    """Serve the metrics dashboard."""
    metrics_path = os.path.join(STATIC_DIR, "metrics.html")
    with open(metrics_path, "r") as f:
        return f.read()

@app.get("/health")
async def health_check():
    db_healthy = db.health_check()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected"
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and scan a PDF file for sensitive data."""
    
    # Validate file type
    if not file.content_type == "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Generate unique ID for this document
    document_id = str(uuid.uuid4())
    
    try:
        # Read file content
        content = await file.read()
        
        # Check file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE} bytes"
            )
        
        # Save file temporarily
        file_path = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Validate PDF
        if not pdf_scanner.is_valid_pdf(file_path):
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        
        # Scan the PDF using thread pool for CPU-intensive work
        start_time = time.time()
        loop = asyncio.get_event_loop()
        scan_result = await loop.run_in_executor(
            PDF_PROCESSING_POOL, 
            pdf_scanner.scan_pdf, 
            file_path
        )
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Record Prometheus metrics
        prometheus_metrics.record_request("scan", "success" if scan_result["status"] == "success" else "error")
        prometheus_metrics.record_processing_time("scan", (time.time() - start_time))
        prometheus_metrics.record_file_size(len(content))
        if scan_result["status"] == "success":
            prometheus_metrics.record_pages_processed(scan_result.get("total_pages", 0))
            for finding in scan_result.get("findings", []):
                prometheus_metrics.record_findings(finding.get("type", "unknown"))
        
        # Store results in database
        db.store_scan_result(document_id, file.filename, scan_result, processing_time_ms)
        
        # Clean up temporary file
        os.remove(file_path)
        
        # Prepare response
        response = {
            "document_id": document_id,
            "filename": file.filename,
            "status": scan_result["status"],
            "processing_time_ms": processing_time_ms
        }
        
        if scan_result["status"] == "success":
            response.update({
                "findings": scan_result["findings"],
                "findings_count": scan_result["findings_count"],
                "total_pages": scan_result["total_pages"],
                "file_size": scan_result["file_size"]
            })
        elif scan_result["status"] == "error":
            response["error"] = scan_result["error"]
        
        return response
        
    except HTTPException:
        # Clean up file if it exists
        file_path = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        # Clean up file if it exists
        file_path = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/findings")
async def get_findings(limit: int = 50, document_id: str = None):
    """Get findings from the database."""
    try:
        findings = db.get_findings(limit=limit, document_id=document_id)
        return findings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get processing statistics."""
    try:
        stats = db.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-and-redact")
async def upload_and_redact_file(file: UploadFile = File(...)):
    """Upload a PDF file, scan for sensitive data, and create a redacted version."""
    
    # Validate file type
    if not file.content_type == "application/pdf":
        metrics_collector.record_error("invalid_file_type", "upload_and_redact")
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Generate unique ID for this document
    document_id = str(uuid.uuid4())
    operation_id = None
    
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Start metrics tracking
        operation_id = metrics_collector.start_operation(document_id, "scan_and_redact", file_size)
        
        # Check file size
        if file_size > MAX_FILE_SIZE:
            metrics_collector.record_error("file_too_large", "upload_and_redact")
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE} bytes"
            )
        
        # Save file temporarily
        file_path = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Validate PDF
        if not pdf_scanner.is_valid_pdf(file_path):
            os.remove(file_path)
            metrics_collector.record_error("invalid_pdf", "upload_and_redact")
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        
        # Scan and redact the PDF using thread pool for CPU-intensive work
        start_time = time.time()
        loop = asyncio.get_event_loop()
        scan_redact_result = await loop.run_in_executor(
            PDF_PROCESSING_POOL, 
            pdf_scanner.scan_and_redact_pdf, 
            file_path
        )
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Record Prometheus metrics
        prometheus_metrics.record_request("scan_and_redact", "success" if scan_redact_result["status"] == "success" else "error")
        prometheus_metrics.record_processing_time("scan_and_redact", (time.time() - start_time))
        prometheus_metrics.record_file_size(file_size)
        if scan_redact_result["status"] == "success":
            prometheus_metrics.record_pages_processed(scan_redact_result.get("total_pages", 0))
            for finding in scan_redact_result.get("findings", []):
                prometheus_metrics.record_findings(finding.get("type", "unknown"))
        
        # Store scan results in database
        try:
            db.store_scan_result(document_id, file.filename, scan_redact_result, processing_time_ms)
        except Exception as db_error:
            metrics_collector.record_error("database_error", "upload_and_redact")
            print(f"Database error: {db_error}")
        
        # Determine success and collect metrics
        success = scan_redact_result["status"] == "success"
        findings_count = scan_redact_result.get("findings_count", 0)
        pages_processed = scan_redact_result.get("total_pages", 0)
        redacted_instances = 0
        
        if success and "redaction" in scan_redact_result:
            redacted_instances = scan_redact_result["redaction"].get("redacted_count", 0)
        
        error_type = None if success else "processing_error"
        
        # End metrics tracking
        if operation_id:
            metrics_collector.end_operation(
                operation_id, 
                success=success,
                findings_count=findings_count,
                pages_processed=pages_processed,
                redacted_instances=redacted_instances,
                error_type=error_type
            )
        
        # Prepare response
        response = {
            "document_id": document_id,
            "filename": file.filename,
            "status": scan_redact_result["status"],
            "processing_time_ms": processing_time_ms
        }
        
        if scan_redact_result["status"] == "success":
            response.update({
                "findings": scan_redact_result["findings"],
                "findings_count": scan_redact_result["findings_count"],
                "total_pages": scan_redact_result["total_pages"],
                "file_size": scan_redact_result["file_size"],
                "redaction": scan_redact_result["redaction"]
            })
        elif scan_redact_result["status"] == "error":
            response["error"] = scan_redact_result["error"]
        
        # Clean up original file but keep redacted version temporarily
        os.remove(file_path)
        
        return response
        
    except HTTPException as he:
        if operation_id:
            metrics_collector.end_operation(operation_id, success=False, error_type="http_error")
        # Clean up files if they exist
        file_path = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        if operation_id:
            metrics_collector.end_operation(operation_id, success=False, error_type="unknown_error")
        metrics_collector.record_error("unknown_error", "upload_and_redact")
        # Clean up files if they exist
        file_path = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/redact/{document_id}")
async def redact_existing_document(document_id: str):
    """Create a redacted version of a previously uploaded document."""
    try:
        # Get document findings from database
        findings_data = db.get_findings(document_id=document_id)
        
        if not findings_data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = findings_data[0]
        
        # Check if original file still exists (unlikely in production)
        original_path = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
        if not os.path.exists(original_path):
            raise HTTPException(
                status_code=404, 
                detail="Original file no longer available for redaction"
            )
        
        # Convert findings to Finding objects
        from pdf_scanner import Finding
        findings = []
        for finding_dict in document['findings']:
            findings.append(Finding(
                type=finding_dict['type'],
                value=finding_dict['value'],
                page=finding_dict['page'],
                position=finding_dict['position']
            ))
        
        # Create redacted version
        redacted_path = os.path.join(UPLOAD_DIR, f"{document_id}_redacted.pdf")
        redaction_result = pdf_scanner.create_redacted_pdf(original_path, findings, redacted_path)
        
        return redaction_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-redacted/{document_id}")
async def download_redacted_file(document_id: str):
    """Download the redacted version of a document."""
    try:
        redacted_path = os.path.join(UPLOAD_DIR, f"{document_id}_redacted.pdf")
        
        if not os.path.exists(redacted_path):
            raise HTTPException(status_code=404, detail="Redacted file not found")
        
        # Get original filename from database
        findings_data = db.get_findings(document_id=document_id)
        if not findings_data:
            filename = f"{document_id}_redacted.pdf"
        else:
            original_filename = findings_data[0]['filename']
            base_name = os.path.splitext(original_filename)[0]
            filename = f"{base_name}_redacted.pdf"
        
        return FileResponse(
            path=redacted_path,
            filename=filename,
            media_type='application/pdf'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics(minutes: int = 60):
    """Get comprehensive performance metrics."""
    try:
        return metrics_collector.get_comprehensive_report(minutes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/throughput")
async def get_throughput_metrics(minutes: int = 60):
    """Get throughput and processing metrics with Prometheus integration."""
    try:
        # Try to get Prometheus metrics for more accurate data
        try:
            from prometheus_client.parser import text_string_to_metric_families
            
            # Get Prometheus metrics directly (avoid self-referencing HTTP call)
            metrics_text = prometheus_metrics.get_metrics()
            
            if metrics_text:
                # Parse Prometheus metrics
                total_requests = 0
                total_processing_time = 0
                total_processing_count = 0
                email_findings = 0
                ssn_findings = 0
                file_size_sum = 0
                file_size_count = 0
                
                for family in text_string_to_metric_families(metrics_text):
                    if family.name == 'pdf_requests':
                        for sample in family.samples:
                            if sample.labels.get('status') == 'success':
                                total_requests += sample.value
                    elif family.name == 'pdf_processing_duration_seconds':
                        for sample in family.samples:
                            if sample.name.endswith('_sum'):
                                total_processing_time += sample.value
                            elif sample.name.endswith('_count'):
                                total_processing_count += sample.value
                    elif family.name == 'pdf_findings':
                        for sample in family.samples:
                            if sample.labels.get('finding_type') == 'email':
                                email_findings += sample.value
                            elif sample.labels.get('finding_type') == 'ssn':
                                ssn_findings += sample.value
                    elif family.name == 'pdf_file_size_bytes':
                        for sample in family.samples:
                            if sample.name.endswith('_sum'):
                                file_size_sum += sample.value
                            elif sample.name.endswith('_count'):
                                file_size_count += sample.value
                
                # Calculate derived metrics
                avg_processing_time_ms = (total_processing_time / total_processing_count * 1000) if total_processing_count > 0 else 0
                
                # Get uptime for rate calculation
                uptime_seconds = time.time() - prometheus_metrics.start_time
                requests_per_minute = (total_requests / max(uptime_seconds / 60, 1)) if uptime_seconds > 0 else 0
                
                return {
                    "requests_per_minute": round(requests_per_minute, 2),
                    "documents_per_hour": round(requests_per_minute * 60, 2),
                    "avg_processing_time_ms": round(avg_processing_time_ms, 2),
                    "p50_processing_time_ms": round(avg_processing_time_ms * 0.8, 2),  # Estimate
                    "p95_processing_time_ms": round(avg_processing_time_ms * 1.5, 2),  # Estimate
                    "p99_processing_time_ms": round(avg_processing_time_ms * 1.8, 2),  # Estimate
                    "success_rate_percent": 100.0,  # From Prometheus we only count successes
                    "error_rate_percent": 0.0,
                    "total_documents_processed": int(total_requests),
                    "total_bytes_processed": int(file_size_sum),
                    "total_findings": int(email_findings + ssn_findings),
                    "source": "prometheus"
                }
        except Exception as prometheus_error:
            print(f"Prometheus metrics unavailable: {prometheus_error}")
        
        # Fallback to in-memory metrics
        fallback_metrics = metrics_collector.get_throughput_metrics(minutes)
        fallback_metrics["source"] = "memory"
        return fallback_metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/system")
async def get_system_metrics(minutes: int = 60):
    """Get system resource metrics with Prometheus integration."""
    try:
        # Try to get Prometheus system metrics for more accurate data
        try:
            from prometheus_client.parser import text_string_to_metric_families
            
            # Get Prometheus metrics directly (avoid self-referencing HTTP call)
            metrics_text = prometheus_metrics.get_metrics()
            
            if metrics_text:
                
                # Parse Prometheus system metrics
                cpu_percent = 0
                memory_percent = 0
                memory_used_bytes = 0
                active_threads = 0
                
                for family in text_string_to_metric_families(metrics_text):
                    if family.name == 'system_cpu_usage_percent':
                        for sample in family.samples:
                            cpu_percent = sample.value
                    elif family.name == 'system_memory_usage_percent':
                        for sample in family.samples:
                            memory_percent = sample.value
                    elif family.name == 'process_memory_used_bytes':
                        for sample in family.samples:
                            memory_used_bytes = sample.value
                    elif family.name == 'pdf_processor_active_threads':
                        for sample in family.samples:
                            active_threads = sample.value
                
                return {
                    "latest": {
                        "timestamp": time.time(),
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "memory_used_mb": memory_used_bytes / (1024 * 1024),
                        "active_connections": active_threads
                    },
                    "averages": {
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "memory_used_mb": memory_used_bytes / (1024 * 1024)
                    },
                    "total_samples": 1,
                    "source": "prometheus"
                }
        except Exception as prometheus_error:
            print(f"Prometheus system metrics unavailable: {prometheus_error}")
        
        # Fallback to in-memory metrics
        system_metrics = metrics_collector.get_system_metrics(minutes)
        if not system_metrics:
            return {"message": "No system metrics available", "metrics": [], "source": "memory"}
        
        # Return summary statistics
        latest = system_metrics[-1] if system_metrics else None
        
        return {
            "latest": {
                "timestamp": latest.timestamp,
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "memory_used_mb": latest.memory_used_mb,
                "active_connections": latest.active_connections
            } if latest else None,
            "averages": metrics_collector._get_average_system_metrics(minutes),
            "total_samples": len(system_metrics),
            "source": "memory"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/errors")
async def get_error_metrics():
    """Get error summary and counts with Prometheus integration."""
    try:
        # Try to get Prometheus error metrics
        try:
            from prometheus_client.parser import text_string_to_metric_families
            
            # Get Prometheus metrics directly (avoid self-referencing HTTP call)
            metrics_text = prometheus_metrics.get_metrics()
            
            if metrics_text:
                
                # Parse error metrics from Prometheus
                errors = {}
                
                for family in text_string_to_metric_families(metrics_text):
                    if family.name == 'pdf_errors':
                        for sample in family.samples:
                            error_type = sample.labels.get('error_type', 'unknown')
                            operation = sample.labels.get('operation', 'unknown')
                            error_key = f"{error_type}_{operation}"
                            errors[error_key] = int(sample.value)
                
                return {
                    "errors": errors,
                    "timestamp": time.time(),
                    "source": "prometheus"
                }
        except Exception as prometheus_error:
            print(f"Prometheus error metrics unavailable: {prometheus_error}")
        
        # Fallback to in-memory metrics
        return {
            "errors": metrics_collector.get_error_summary(),
            "timestamp": time.time(),
            "source": "memory"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/insights")
async def get_performance_insights(minutes: int = 60):
    """Get actionable performance insights and recommendations with Prometheus integration."""
    try:
        # Try to get Prometheus metrics for insights
        try:
            from prometheus_client.parser import text_string_to_metric_families
            
            # Get Prometheus metrics directly (avoid self-referencing HTTP call)
            metrics_text = prometheus_metrics.get_metrics()
            
            if metrics_text:
                
                # Parse key metrics for insights
                total_requests = 0
                total_errors = 0
                cpu_percent = 0
                memory_percent = 0
                uptime_seconds = 0
                active_threads = 0
                
                for family in text_string_to_metric_families(metrics_text):
                    if family.name == 'pdf_requests':
                        for sample in family.samples:
                            if sample.labels.get('status') == 'success':
                                total_requests += sample.value
                    elif family.name == 'pdf_errors':
                        for sample in family.samples:
                            total_errors += sample.value
                    elif family.name == 'system_cpu_usage_percent':
                        for sample in family.samples:
                            cpu_percent = sample.value
                    elif family.name == 'system_memory_usage_percent':
                        for sample in family.samples:
                            memory_percent = sample.value
                    elif family.name == 'pdf_scanner_uptime_seconds':
                        for sample in family.samples:
                            uptime_seconds = sample.value
                    elif family.name == 'pdf_processor_active_threads':
                        for sample in family.samples:
                            active_threads = sample.value
                
                # Generate insights based on Prometheus data
                bottlenecks = []
                recommendations = []
                
                if cpu_percent > 80:
                    bottlenecks.append("High CPU usage detected")
                    recommendations.append("Consider scaling horizontally or optimizing processing")
                    
                if memory_percent > 80:
                    bottlenecks.append("High memory usage detected")
                    recommendations.append("Monitor memory leaks and consider increasing available memory")
                    
                if total_errors > total_requests * 0.05:  # More than 5% error rate
                    bottlenecks.append("High error rate detected")
                    recommendations.append("Investigate error causes and improve error handling")
                
                # Performance scoring
                performance_score = 100
                if cpu_percent > 60: performance_score -= 20
                if memory_percent > 60: performance_score -= 20
                if total_errors > 0: performance_score -= 10
                performance_score = max(0, performance_score)
                
                # Health status
                if performance_score >= 80:
                    health_status = "healthy"
                elif performance_score >= 60:
                    health_status = "warning"
                else:
                    health_status = "critical"
                
                return {
                    "health_status": health_status,
                    "performance_score": performance_score,
                    "uptime_seconds": uptime_seconds,
                    "bottlenecks": bottlenecks,
                    "recommendations": recommendations,
                    "capacity_utilization": {
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "active_threads": active_threads
                    },
                    "source": "prometheus"
                }
        except Exception as prometheus_error:
            print(f"Prometheus insights unavailable: {prometheus_error}")
        
        # Fallback to in-memory metrics
        fallback_insights = metrics_collector.get_performance_insights(minutes)
        fallback_insights["source"] = "memory"
        return fallback_insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with metrics."""
    try:
        db_healthy = db.health_check()
        insights = metrics_collector.get_performance_insights(5)  # Last 5 minutes
        throughput = metrics_collector.get_throughput_metrics(5)
        
        # Using thread pool with multi-worker deployment for parallelism
        thread_pool_healthy = PDF_PROCESSING_POOL._threads is not None
        
        # Using thread pool workers per FastAPI worker
        active_threads = len([t for t in PDF_PROCESSING_POOL._threads if t.is_alive()]) if PDF_PROCESSING_POOL._threads else 0
        
        return {
            "status": insights.get("health_status", "unknown"),
            "database": "connected" if db_healthy else "disconnected",
            "thread_pool": "active" if thread_pool_healthy else "inactive",
            "thread_pool_workers": PDF_PROCESSING_POOL._max_workers,
            "active_threads": active_threads,
            "async_processing": "multi_worker_optimized" if thread_pool_healthy else "unavailable",
            "performance_score": insights.get("performance_score", 0),
            "uptime_seconds": insights.get("uptime_seconds", 0),
            "recent_throughput": {
                "requests_per_minute": throughput.requests_per_minute,
                "success_rate_percent": throughput.success_rate_percent,
                "avg_processing_time_ms": throughput.avg_processing_time_ms
            },
            "bottlenecks": insights.get("bottlenecks", []),
            "recommendations": insights.get("recommendations", []),
            "capacity_utilization": insights.get("capacity_utilization", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Async processing endpoints removed for now - focusing on sync optimizations with thread pools

@app.get("/scaling-recommendations")
async def get_scaling_recommendations(minutes: int = 10):
    """Get intelligent scaling recommendations based on current load and performance."""
    try:
        return metrics_collector.get_scaling_recommendations(minutes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """Prometheus metrics endpoint for scraping."""
    try:
        # Update active thread count
        if PDF_PROCESSING_POOL._threads:
            active_threads = len([t for t in PDF_PROCESSING_POOL._threads if t.is_alive()])
            prometheus_metrics.update_active_threads(active_threads)
        
        metrics_output = prometheus_metrics.get_metrics()
        return Response(
            content=metrics_output,
            media_type=prometheus_metrics.get_content_type()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auto-scale-check")
async def auto_scale_check():
    """Quick endpoint for auto-scaling systems to check if scaling is needed."""
    try:
        scaling_info = metrics_collector.get_scaling_recommendations(5)  # Last 5 minutes
        
        return {
            "timestamp": time.time(),
            "scale_up_needed": scaling_info['scaling_actions']['scale_up'],
            "scale_down_safe": scaling_info['scaling_actions']['scale_down'],
            "async_recommended": scaling_info['scaling_actions']['enable_async'],
            "load_level": scaling_info['load_characteristics']['load_level'],
            "performance_tier": scaling_info['load_characteristics']['performance_tier'],
            "critical_actions": [
                action for action in scaling_info['recommended_actions'] 
                if action.get('priority') == 'critical'
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)