"""
Comprehensive metrics collection for PDF scanner application.
Provides performance monitoring, throughput tracking, and operational insights.
"""

import time
import psutil
import threading
from collections import deque, defaultdict
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import statistics
import os


@dataclass
class ProcessingMetrics:
    """Individual processing operation metrics."""
    timestamp: float
    operation_type: str  # 'scan', 'redact', 'scan_and_redact'
    file_size_bytes: int
    processing_time_ms: float
    findings_count: int
    success: bool
    error_type: Optional[str] = None
    pages_processed: int = 0
    redacted_instances: int = 0


@dataclass
class SystemMetrics:
    """System resource metrics."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    active_connections: int


@dataclass
class ThroughputMetrics:
    """Throughput and performance metrics."""
    requests_per_minute: float
    documents_per_hour: float
    avg_processing_time_ms: float
    p50_processing_time_ms: float
    p95_processing_time_ms: float
    p99_processing_time_ms: float
    success_rate_percent: float
    error_rate_percent: float
    total_documents_processed: int
    total_bytes_processed: int


class MetricsCollector:
    """Centralized metrics collection and analysis."""
    
    def __init__(self, retention_minutes: int = 60):
        self.retention_minutes = retention_minutes
        self.processing_metrics = deque(maxlen=10000)  # Last 10k operations
        self.system_metrics = deque(maxlen=3600)  # Last hour of system metrics
        self.error_counts = defaultdict(int)
        self.active_operations = {}
        self.start_time = time.time()
        
        # Thread-safe locks
        self.processing_lock = threading.Lock()
        self.system_lock = threading.Lock()
        self.error_lock = threading.Lock()
        
        # System monitoring
        self.process = psutil.Process()
        try:
            self.last_disk_io = self.process.io_counters()
        except (AttributeError, psutil.AccessDenied):
            # Fallback for systems without io_counters access
            self.last_disk_io = type('obj', (object,), {'read_bytes': 0, 'write_bytes': 0})()
        
        # Start background system monitoring
        self._start_system_monitoring()
    
    def _start_system_monitoring(self):
        """Start background thread for system metrics collection."""
        def collect_system_metrics():
            while True:
                try:
                    self._collect_system_metrics()
                    time.sleep(10)  # Collect every 10 seconds
                except Exception as e:
                    print(f"Error collecting system metrics: {e}")
                    time.sleep(30)  # Back off on error
        
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()
    
    def _collect_system_metrics(self):
        """Collect current system metrics."""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Process-specific memory
            process_memory = self.process.memory_info()
            
            # Disk I/O
            try:
                current_io = self.process.io_counters()
                disk_read_mb = (current_io.read_bytes - self.last_disk_io.read_bytes) / (1024 * 1024)
                disk_write_mb = (current_io.write_bytes - self.last_disk_io.write_bytes) / (1024 * 1024)
                self.last_disk_io = current_io
            except (AttributeError, psutil.AccessDenied):
                disk_read_mb = 0
                disk_write_mb = 0
            
            # Network connections (approximate)
            try:
                active_connections = len(psutil.net_connections(kind='tcp'))
            except (psutil.AccessDenied, OSError):
                active_connections = 0
            
            metrics = SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=process_memory.rss / (1024 * 1024),
                disk_io_read_mb=max(0, disk_read_mb),
                disk_io_write_mb=max(0, disk_write_mb),
                active_connections=active_connections
            )
            
            with self.system_lock:
                self.system_metrics.append(metrics)
                self._cleanup_old_system_metrics()
                
        except Exception as e:
            print(f"Error in system metrics collection: {e}")
    
    def start_operation(self, operation_id: str, operation_type: str, file_size: int) -> str:
        """Start tracking an operation."""
        operation_data = {
            'operation_type': operation_type,
            'file_size': file_size,
            'start_time': time.time(),
            'pages_processed': 0
        }
        
        self.active_operations[operation_id] = operation_data
        return operation_id
    
    def end_operation(self, operation_id: str, success: bool, findings_count: int = 0, 
                     pages_processed: int = 0, redacted_instances: int = 0, 
                     error_type: Optional[str] = None):
        """End tracking an operation and record metrics."""
        if operation_id not in self.active_operations:
            return
        
        operation_data = self.active_operations.pop(operation_id)
        processing_time_ms = (time.time() - operation_data['start_time']) * 1000
        
        metrics = ProcessingMetrics(
            timestamp=time.time(),
            operation_type=operation_data['operation_type'],
            file_size_bytes=operation_data['file_size'],
            processing_time_ms=processing_time_ms,
            findings_count=findings_count,
            success=success,
            error_type=error_type,
            pages_processed=pages_processed,
            redacted_instances=redacted_instances
        )
        
        with self.processing_lock:
            self.processing_metrics.append(metrics)
            self._cleanup_old_processing_metrics()
        
        if error_type:
            with self.error_lock:
                self.error_counts[error_type] += 1
    
    def record_error(self, error_type: str, operation_type: str = "unknown"):
        """Record an error occurrence."""
        with self.error_lock:
            self.error_counts[f"{operation_type}:{error_type}"] += 1
    
    def get_processing_metrics(self, minutes: int = 60) -> List[ProcessingMetrics]:
        """Get processing metrics for the last N minutes."""
        cutoff_time = time.time() - (minutes * 60)
        
        with self.processing_lock:
            return [m for m in self.processing_metrics if m.timestamp >= cutoff_time]
    
    def get_system_metrics(self, minutes: int = 60) -> List[SystemMetrics]:
        """Get system metrics for the last N minutes."""
        cutoff_time = time.time() - (minutes * 60)
        
        with self.system_lock:
            return [m for m in self.system_metrics if m.timestamp >= cutoff_time]
    
    def get_throughput_metrics(self, minutes: int = 60) -> ThroughputMetrics:
        """Calculate comprehensive throughput metrics."""
        recent_metrics = self.get_processing_metrics(minutes)
        
        if not recent_metrics:
            return ThroughputMetrics(
                requests_per_minute=0,
                documents_per_hour=0,
                avg_processing_time_ms=0,
                p50_processing_time_ms=0,
                p95_processing_time_ms=0,
                p99_processing_time_ms=0,
                success_rate_percent=0,
                error_rate_percent=0,
                total_documents_processed=0,
                total_bytes_processed=0
            )
        
        # Basic counts
        total_operations = len(recent_metrics)
        successful_operations = sum(1 for m in recent_metrics if m.success)
        failed_operations = total_operations - successful_operations
        
        # Time-based calculations using actual operation timespan
        if len(recent_metrics) >= 2:
            # Calculate actual time span between first and last operations
            timestamps = [m.timestamp for m in recent_metrics]
            actual_time_span_seconds = max(timestamps) - min(timestamps)
            # Add a small buffer for single-second operations to avoid division by zero
            actual_time_span_seconds = max(actual_time_span_seconds, 1.0)
            actual_time_span_minutes = actual_time_span_seconds / 60
            requests_per_minute = total_operations / actual_time_span_minutes
        elif len(recent_metrics) == 1:
            # For single operation, estimate based on processing time
            processing_time_seconds = recent_metrics[0].processing_time_ms / 1000
            # Estimate potential throughput based on processing speed
            requests_per_minute = 60 / max(processing_time_seconds, 0.1)
        else:
            requests_per_minute = 0
        
        documents_per_hour = requests_per_minute * 60
        
        # Processing time statistics
        processing_times = [m.processing_time_ms for m in recent_metrics]
        avg_processing_time = statistics.mean(processing_times)
        
        # Percentiles
        sorted_times = sorted(processing_times)
        p50 = self._percentile(sorted_times, 50)
        p95 = self._percentile(sorted_times, 95)
        p99 = self._percentile(sorted_times, 99)
        
        # Success rates
        success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
        error_rate = 100 - success_rate
        
        # Volume statistics
        total_bytes = sum(m.file_size_bytes for m in recent_metrics)
        
        return ThroughputMetrics(
            requests_per_minute=round(requests_per_minute, 2),
            documents_per_hour=round(documents_per_hour, 2),
            avg_processing_time_ms=round(avg_processing_time, 2),
            p50_processing_time_ms=round(p50, 2),
            p95_processing_time_ms=round(p95, 2),
            p99_processing_time_ms=round(p99, 2),
            success_rate_percent=round(success_rate, 2),
            error_rate_percent=round(error_rate, 2),
            total_documents_processed=total_operations,
            total_bytes_processed=total_bytes
        )
    
    def get_error_summary(self, minutes: int = 60) -> Dict[str, int]:
        """Get error counts for the specified time period."""
        with self.error_lock:
            return dict(self.error_counts)
    
    def get_performance_insights(self, minutes: int = 60) -> Dict[str, Any]:
        """Get actionable performance insights."""
        recent_metrics = self.get_processing_metrics(minutes)
        system_metrics = self.get_system_metrics(minutes)
        throughput = self.get_throughput_metrics(minutes)
        
        insights = {
            'performance_score': self._calculate_performance_score(throughput, system_metrics),
            'bottlenecks': self._identify_bottlenecks(recent_metrics, system_metrics),
            'recommendations': self._generate_recommendations(throughput, system_metrics),
            'capacity_utilization': self._calculate_capacity_utilization(system_metrics),
            'uptime_seconds': time.time() - self.start_time
        }
        
        return insights
    
    def get_comprehensive_report(self, minutes: int = 60) -> Dict[str, Any]:
        """Get comprehensive metrics report."""
        return {
            'timestamp': datetime.now().isoformat(),
            'time_window_minutes': minutes,
            'throughput': asdict(self.get_throughput_metrics(minutes)),
            'system_metrics': {
                'current': asdict(self.get_system_metrics(1)[-1]) if self.get_system_metrics(1) else None,
                'average': self._get_average_system_metrics(minutes)
            },
            'errors': self.get_error_summary(minutes),
            'insights': self.get_performance_insights(minutes),
            'scaling': self.get_scaling_recommendations(minutes),
            'health_status': self._get_health_status()
        }
    
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
    
    def _cleanup_old_processing_metrics(self):
        """Remove old processing metrics beyond retention period."""
        cutoff_time = time.time() - (self.retention_minutes * 60)
        while self.processing_metrics and self.processing_metrics[0].timestamp < cutoff_time:
            self.processing_metrics.popleft()
    
    def _cleanup_old_system_metrics(self):
        """Remove old system metrics beyond retention period."""
        cutoff_time = time.time() - (self.retention_minutes * 60)
        while self.system_metrics and self.system_metrics[0].timestamp < cutoff_time:
            self.system_metrics.popleft()
    
    def _calculate_performance_score(self, throughput: ThroughputMetrics, 
                                   system_metrics: List[SystemMetrics]) -> float:
        """Calculate overall performance score (0-100)."""
        if not system_metrics:
            return 50.0
        
        # Factors contributing to performance score
        success_rate_score = throughput.success_rate_percent
        
        # Processing time score (lower is better)
        processing_time_score = max(0, 100 - (throughput.p95_processing_time_ms / 50))  # 5s = 0 points
        
        # System resource score
        avg_cpu = statistics.mean([m.cpu_percent for m in system_metrics])
        avg_memory = statistics.mean([m.memory_percent for m in system_metrics])
        resource_score = max(0, 100 - max(avg_cpu, avg_memory))
        
        # Weighted average
        performance_score = (
            success_rate_score * 0.4 +
            processing_time_score * 0.3 +
            resource_score * 0.3
        )
        
        return round(performance_score, 1)
    
    def _identify_bottlenecks(self, processing_metrics: List[ProcessingMetrics],
                            system_metrics: List[SystemMetrics]) -> List[str]:
        """Identify performance bottlenecks."""
        bottlenecks = []
        
        if processing_metrics:
            # High processing times
            avg_processing_time = statistics.mean([m.processing_time_ms for m in processing_metrics])
            if avg_processing_time > 5000:  # 5 seconds
                bottlenecks.append("High average processing time")
            
            # High error rate
            error_rate = sum(1 for m in processing_metrics if not m.success) / len(processing_metrics) * 100
            if error_rate > 10:
                bottlenecks.append("High error rate")
        
        if system_metrics:
            # Resource constraints
            avg_cpu = statistics.mean([m.cpu_percent for m in system_metrics])
            avg_memory = statistics.mean([m.memory_percent for m in system_metrics])
            
            if avg_cpu > 80:
                bottlenecks.append("High CPU utilization")
            if avg_memory > 85:
                bottlenecks.append("High memory utilization")
        
        return bottlenecks
    
    def _generate_recommendations(self, throughput: ThroughputMetrics,
                                system_metrics: List[SystemMetrics]) -> List[str]:
        """Generate performance recommendations with auto-scaling triggers."""
        recommendations = []
        
        if throughput.p95_processing_time_ms > 3000:
            recommendations.append("Consider optimizing PDF processing algorithms")
        
        if throughput.error_rate_percent > 5:
            recommendations.append("Investigate and fix error sources")
        
        if system_metrics:
            avg_cpu = statistics.mean([m.cpu_percent for m in system_metrics])
            avg_memory = statistics.mean([m.memory_percent for m in system_metrics])
            
            # Memory recommendations
            if avg_memory > 85:
                recommendations.append("🚨 CRITICAL: Scale up memory immediately (>85% usage)")
            elif avg_memory > 80:
                recommendations.append("⚠️ Consider increasing memory allocation (>80% usage)")
            
            # CPU recommendations
            if avg_cpu > 85:
                recommendations.append("🚨 CRITICAL: Scale up CPU immediately (>85% usage)")
            elif avg_cpu > 75:
                recommendations.append("⚠️ Consider adding CPU cores (>75% usage)")
            
            # Auto-scaling triggers
            if self.should_scale_up(system_metrics, throughput):
                recommendations.append("🔄 AUTO-SCALE: Add horizontal replicas now")
            elif self.should_enable_async_processing(throughput):
                recommendations.append("⚡ Enable async processing for better throughput")
        
        # Throughput-based scaling
        if throughput.requests_per_minute > 50:
            recommendations.append("📈 High load detected: Consider horizontal scaling")
        elif throughput.requests_per_minute > 30:
            recommendations.append("📊 Moderate load: Prepare for scaling")
        
        return recommendations
    
    def should_scale_up(self, system_metrics: List[SystemMetrics] = None, 
                       throughput: ThroughputMetrics = None) -> bool:
        """Determine if the system should scale up based on resource usage."""
        if not system_metrics:
            system_metrics = self.get_system_metrics(5)  # Last 5 minutes
        
        if not system_metrics:
            return False
        
        avg_cpu = statistics.mean([m.cpu_percent for m in system_metrics])
        avg_memory = statistics.mean([m.memory_percent for m in system_metrics])
        
        # Scale up triggers
        resource_pressure = avg_cpu > 80 or avg_memory > 80
        high_load = throughput and throughput.requests_per_minute > 40
        degraded_performance = throughput and throughput.p95_processing_time_ms > 5000
        
        return resource_pressure or (high_load and degraded_performance)
    
    def should_scale_down(self, system_metrics: List[SystemMetrics] = None,
                         throughput: ThroughputMetrics = None) -> bool:
        """Determine if the system can scale down to save resources."""
        if not system_metrics:
            system_metrics = self.get_system_metrics(15)  # Last 15 minutes
        
        if not system_metrics:
            return False
        
        avg_cpu = statistics.mean([m.cpu_percent for m in system_metrics])
        avg_memory = statistics.mean([m.memory_percent for m in system_metrics])
        
        # Scale down triggers (conservative)
        low_resource_usage = avg_cpu < 25 and avg_memory < 40
        low_load = throughput and throughput.requests_per_minute < 10
        good_performance = throughput and throughput.p95_processing_time_ms < 2000
        
        return low_resource_usage and low_load and good_performance
    
    def should_enable_async_processing(self, throughput: ThroughputMetrics) -> bool:
        """Determine if async processing should be enabled for better throughput."""
        if not throughput:
            return False
        
        # Enable async processing if we have moderate load and good performance
        # This allows handling more concurrent requests
        moderate_load = 20 <= throughput.requests_per_minute <= 40
        acceptable_performance = throughput.p95_processing_time_ms < 3000
        good_success_rate = throughput.success_rate_percent > 95
        
        return moderate_load and acceptable_performance and good_success_rate
    
    def get_scaling_recommendations(self, minutes: int = 10) -> Dict[str, Any]:
        """Get comprehensive scaling recommendations."""
        system_metrics = self.get_system_metrics(minutes)
        throughput = self.get_throughput_metrics(minutes)
        
        return {
            'timestamp': time.time(),
            'time_window_minutes': minutes,
            'scaling_actions': {
                'scale_up': self.should_scale_up(system_metrics, throughput),
                'scale_down': self.should_scale_down(system_metrics, throughput),
                'enable_async': self.should_enable_async_processing(throughput)
            },
            'resource_pressure': {
                'cpu_pressure': statistics.mean([m.cpu_percent for m in system_metrics]) > 75 if system_metrics else False,
                'memory_pressure': statistics.mean([m.memory_percent for m in system_metrics]) > 75 if system_metrics else False
            },
            'load_characteristics': {
                'current_rpm': throughput.requests_per_minute,
                'load_level': self._classify_load_level(throughput.requests_per_minute),
                'performance_tier': self._classify_performance_tier(throughput.p95_processing_time_ms)
            },
            'recommended_actions': self._get_scaling_actions(system_metrics, throughput)
        }
    
    def _classify_load_level(self, requests_per_minute: float) -> str:
        """Classify current load level."""
        if requests_per_minute >= 50:
            return 'high'
        elif requests_per_minute >= 25:
            return 'moderate'
        elif requests_per_minute >= 10:
            return 'low'
        else:
            return 'minimal'
    
    def _classify_performance_tier(self, p95_processing_time_ms: float) -> str:
        """Classify current performance tier."""
        if p95_processing_time_ms <= 1000:
            return 'excellent'
        elif p95_processing_time_ms <= 2000:
            return 'good'
        elif p95_processing_time_ms <= 5000:
            return 'acceptable'
        else:
            return 'poor'
    
    def _get_scaling_actions(self, system_metrics: List[SystemMetrics], 
                           throughput: ThroughputMetrics) -> List[Dict[str, Any]]:
        """Get specific scaling actions with priorities."""
        actions = []
        
        if self.should_scale_up(system_metrics, throughput):
            avg_cpu = statistics.mean([m.cpu_percent for m in system_metrics]) if system_metrics else 0
            avg_memory = statistics.mean([m.memory_percent for m in system_metrics]) if system_metrics else 0
            
            if avg_cpu > 85 or avg_memory > 85:
                actions.append({
                    'action': 'immediate_scale_up',
                    'priority': 'critical',
                    'reason': f'Resource usage critical (CPU: {avg_cpu:.1f}%, Memory: {avg_memory:.1f}%)',
                    'target_replicas': 'double_current'
                })
            else:
                actions.append({
                    'action': 'gradual_scale_up',
                    'priority': 'high',
                    'reason': 'Resource pressure detected',
                    'target_replicas': 'add_1_replica'
                })
        
        if self.should_enable_async_processing(throughput):
            actions.append({
                'action': 'enable_async_processing',
                'priority': 'medium',
                'reason': 'Moderate load with good performance - async processing can improve throughput',
                'implementation': 'start_celery_workers'
            })
        
        if self.should_scale_down(system_metrics, throughput):
            actions.append({
                'action': 'scale_down',
                'priority': 'low',
                'reason': 'Low resource usage and load - can reduce costs',
                'target_replicas': 'remove_1_replica'
            })
        
        return actions
    
    def _calculate_capacity_utilization(self, system_metrics: List[SystemMetrics]) -> Dict[str, float]:
        """Calculate current capacity utilization."""
        if not system_metrics:
            return {'cpu': 0, 'memory': 0, 'overall': 0}
        
        avg_cpu = statistics.mean([m.cpu_percent for m in system_metrics])
        avg_memory = statistics.mean([m.memory_percent for m in system_metrics])
        overall = max(avg_cpu, avg_memory)
        
        return {
            'cpu': round(avg_cpu, 1),
            'memory': round(avg_memory, 1),
            'overall': round(overall, 1)
        }
    
    def _get_average_system_metrics(self, minutes: int) -> Dict[str, float]:
        """Get average system metrics for time period."""
        metrics = self.get_system_metrics(minutes)
        
        if not metrics:
            return {}
        
        return {
            'cpu_percent': round(statistics.mean([m.cpu_percent for m in metrics]), 1),
            'memory_percent': round(statistics.mean([m.memory_percent for m in metrics]), 1),
            'memory_used_mb': round(statistics.mean([m.memory_used_mb for m in metrics]), 1),
            'active_connections': round(statistics.mean([m.active_connections for m in metrics]), 1)
        }
    
    def _get_health_status(self) -> str:
        """Get overall system health status."""
        recent_system_metrics = self.get_system_metrics(5)  # Last 5 minutes
        recent_processing_metrics = self.get_processing_metrics(5)
        
        if not recent_system_metrics:
            return "unknown"
        
        # Check system resources
        avg_cpu = statistics.mean([m.cpu_percent for m in recent_system_metrics])
        avg_memory = statistics.mean([m.memory_percent for m in recent_system_metrics])
        
        # Check error rate
        error_rate = 0
        if recent_processing_metrics:
            errors = sum(1 for m in recent_processing_metrics if not m.success)
            error_rate = errors / len(recent_processing_metrics) * 100
        
        # Determine health status
        if avg_cpu > 90 or avg_memory > 95 or error_rate > 20:
            return "critical"
        elif avg_cpu > 75 or avg_memory > 85 or error_rate > 10:
            return "warning"
        else:
            return "healthy"


# Global metrics collector instance
metrics_collector = MetricsCollector()