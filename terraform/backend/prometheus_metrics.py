"""
Prometheus-based metrics collection for multi-worker PDF scanner deployment.
Replaces in-memory metrics with shared Prometheus metrics.
"""

import time
import psutil
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from typing import Optional
import threading

class PrometheusMetrics:
    """Prometheus-based metrics collector for multi-worker deployments."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self.start_time = time.time()
        
        # Processing metrics
        self.pdf_requests_total = Counter(
            'pdf_requests_total',
            'Total number of PDF processing requests',
            ['operation_type', 'status'],
            registry=self.registry
        )
        
        self.processing_duration_seconds = Histogram(
            'pdf_processing_duration_seconds',
            'Time spent processing PDFs',
            ['operation_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        self.findings_total = Counter(
            'pdf_findings_total',
            'Total number of sensitive data findings',
            ['finding_type'],
            registry=self.registry
        )
        
        self.file_size_bytes = Histogram(
            'pdf_file_size_bytes',
            'Size of processed PDF files',
            buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],  # 1KB to 100MB
            registry=self.registry
        )
        
        self.pages_processed_total = Counter(
            'pdf_pages_processed_total',
            'Total number of PDF pages processed',
            registry=self.registry
        )
        
        # System metrics
        self.cpu_usage_percent = Gauge(
            'system_cpu_usage_percent',
            'Current CPU usage percentage',
            registry=self.registry
        )
        
        self.memory_usage_percent = Gauge(
            'system_memory_usage_percent',
            'Current memory usage percentage',
            registry=self.registry
        )
        
        self.memory_used_bytes = Gauge(
            'process_memory_used_bytes',
            'Process memory usage in bytes',
            registry=self.registry
        )
        
        self.active_threads = Gauge(
            'pdf_processor_active_threads',
            'Number of active PDF processing threads',
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            'pdf_errors_total',
            'Total number of processing errors',
            ['error_type', 'operation'],
            registry=self.registry
        )
        
        # Uptime
        self.uptime_seconds = Gauge(
            'pdf_scanner_uptime_seconds',
            'Application uptime in seconds',
            registry=self.registry
        )
        
        # Start background system metrics collection
        self._start_system_monitoring()
    
    def record_request(self, operation_type: str, status: str):
        """Record a PDF processing request."""
        self.pdf_requests_total.labels(
            operation_type=operation_type,
            status=status
        ).inc()
    
    def record_processing_time(self, operation_type: str, duration_seconds: float):
        """Record PDF processing duration."""
        self.processing_duration_seconds.labels(
            operation_type=operation_type
        ).observe(duration_seconds)
    
    def record_findings(self, finding_type: str, count: int = 1):
        """Record sensitive data findings."""
        self.findings_total.labels(finding_type=finding_type).inc(count)
    
    def record_file_size(self, size_bytes: int):
        """Record processed file size."""
        self.file_size_bytes.observe(size_bytes)
    
    def record_pages_processed(self, pages: int):
        """Record number of pages processed."""
        self.pages_processed_total.inc(pages)
    
    def record_error(self, error_type: str, operation: str):
        """Record an error occurrence."""
        self.errors_total.labels(
            error_type=error_type,
            operation=operation
        ).inc()
    
    def update_active_threads(self, count: int):
        """Update active thread count."""
        self.active_threads.set(count)
    
    def _start_system_monitoring(self):
        """Start background thread for system metrics collection."""
        def collect_system_metrics():
            while True:
                try:
                    # CPU and Memory
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    
                    # Process-specific memory
                    process = psutil.Process()
                    process_memory = process.memory_info()
                    
                    # Update metrics
                    self.cpu_usage_percent.set(cpu_percent)
                    self.memory_usage_percent.set(memory.percent)
                    self.memory_used_bytes.set(process_memory.rss)
                    self.uptime_seconds.set(time.time() - self.start_time)
                    
                    time.sleep(10)  # Collect every 10 seconds
                except Exception as e:
                    print(f"Error collecting system metrics: {e}")
                    time.sleep(30)  # Back off on error
        
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_content_type(self) -> str:
        """Get the content type for metrics response."""
        return CONTENT_TYPE_LATEST

# Global Prometheus metrics instance
prometheus_metrics = PrometheusMetrics()