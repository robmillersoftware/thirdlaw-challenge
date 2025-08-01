#!/usr/bin/env python3
"""
Auto-scaling service for PDF Scanner based on Prometheus metrics.
Monitors metrics and automatically scales Docker Swarm services.
"""

import time
import requests
import subprocess
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
import argparse

@dataclass
class ScalingDecision:
    """Represents a scaling decision."""
    action: str  # 'scale_up', 'scale_down', 'no_change'
    current_replicas: int
    target_replicas: int
    reason: str
    confidence: float

class AutoScaler:
    def __init__(self, prometheus_url: str = "http://localhost:9090", 
                 service_name: str = "pdf-scanner-stack_pdf-scanner",
                 min_replicas: int = 1, max_replicas: int = 10):
        self.prometheus_url = prometheus_url
        self.service_name = service_name
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        
        # Scaling thresholds
        self.cpu_scale_up_threshold = 70
        self.cpu_scale_down_threshold = 20
        self.memory_scale_up_threshold = 80
        self.memory_scale_down_threshold = 40
        self.request_rate_scale_up_threshold = 50
        self.request_rate_scale_down_threshold = 10
        self.response_time_scale_up_threshold = 2.0
        
        # Scaling cooldowns (seconds)
        self.scale_up_cooldown = 300  # 5 minutes
        self.scale_down_cooldown = 600  # 10 minutes
        self.last_scale_time = 0
        self.last_scale_action = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def query_prometheus(self, query: str) -> Optional[float]:
        """Query Prometheus and return the result value."""
        try:
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': query},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'success' and data['data']['result']:
                return float(data['data']['result'][0]['value'][1])
            return None
        except Exception as e:
            self.logger.error(f"Error querying Prometheus: {e}")
            return None

    def get_current_replicas(self) -> int:
        """Get current number of service replicas."""
        try:
            result = subprocess.run([
                'docker', 'service', 'inspect', self.service_name,
                '--format', '{{.Spec.Mode.Replicated.Replicas}}'
            ], capture_output=True, text=True, check=True)
            return int(result.stdout.strip())
        except Exception as e:
            self.logger.error(f"Error getting current replicas: {e}")
            return 1

    def get_metrics(self) -> Dict[str, Optional[float]]:
        """Collect current metrics from Prometheus."""
        metrics = {}
        
        # CPU usage (average across all replicas)
        metrics['cpu_usage'] = self.query_prometheus(
            'avg(rate(container_cpu_usage_seconds_total{name=~".*pdf-scanner.*"}[5m]) * 100)'
        )
        
        # Memory usage (average across all replicas)
        metrics['memory_usage'] = self.query_prometheus(
            'avg((container_memory_usage_bytes{name=~".*pdf-scanner.*"} / '
            'container_spec_memory_limit_bytes{name=~".*pdf-scanner.*"}) * 100)'
        )
        
        # Request rate (requests per second)
        metrics['request_rate'] = self.query_prometheus(
            'sum(rate(http_requests_total{job="pdf-scanner"}[5m]))'
        )
        
        # Response time (95th percentile)
        metrics['response_time_p95'] = self.query_prometheus(
            'histogram_quantile(0.95, '
            'sum(rate(http_request_duration_seconds_bucket{job="pdf-scanner"}[5m])) by (le))'
        )
        
        # Error rate
        metrics['error_rate'] = self.query_prometheus(
            'sum(rate(http_requests_total{job="pdf-scanner",status=~"5.."}[5m])) / '
            'sum(rate(http_requests_total{job="pdf-scanner"}[5m]))'
        )
        
        # Active replicas
        metrics['active_replicas'] = self.query_prometheus(
            'count(up{job="pdf-scanner"} == 1)'
        )
        
        return metrics

    def make_scaling_decision(self, metrics: Dict[str, Optional[float]], 
                            current_replicas: int) -> ScalingDecision:
        """Make scaling decision based on metrics."""
        scale_up_score = 0
        scale_down_score = 0
        reasons = []
        
        # CPU-based scaling
        if metrics['cpu_usage'] is not None:
            if metrics['cpu_usage'] > self.cpu_scale_up_threshold:
                scale_up_score += 3
                reasons.append(f"High CPU: {metrics['cpu_usage']:.1f}%")
            elif metrics['cpu_usage'] < self.cpu_scale_down_threshold:
                scale_down_score += 2
                reasons.append(f"Low CPU: {metrics['cpu_usage']:.1f}%")
        
        # Memory-based scaling
        if metrics['memory_usage'] is not None:
            if metrics['memory_usage'] > self.memory_scale_up_threshold:
                scale_up_score += 3
                reasons.append(f"High Memory: {metrics['memory_usage']:.1f}%")
            elif metrics['memory_usage'] < self.memory_scale_down_threshold:
                scale_down_score += 1
                reasons.append(f"Low Memory: {metrics['memory_usage']:.1f}%")
        
        # Request rate-based scaling
        if metrics['request_rate'] is not None:
            if metrics['request_rate'] > self.request_rate_scale_up_threshold:
                scale_up_score += 2
                reasons.append(f"High Request Rate: {metrics['request_rate']:.1f} req/s")
            elif metrics['request_rate'] < self.request_rate_scale_down_threshold:
                scale_down_score += 2
                reasons.append(f"Low Request Rate: {metrics['request_rate']:.1f} req/s")
        
        # Response time-based scaling
        if metrics['response_time_p95'] is not None:
            if metrics['response_time_p95'] > self.response_time_scale_up_threshold:
                scale_up_score += 2
                reasons.append(f"Slow Response: {metrics['response_time_p95']:.2f}s P95")
        
        # Error rate-based scaling
        if metrics['error_rate'] is not None and metrics['error_rate'] > 0.01:
            scale_up_score += 1
            reasons.append(f"High Error Rate: {metrics['error_rate']:.2%}")
        
        # Determine action
        if scale_up_score >= 3 and current_replicas < self.max_replicas:
            target_replicas = min(current_replicas + 1, self.max_replicas)
            # For high load, scale up more aggressively
            if scale_up_score >= 6:
                target_replicas = min(current_replicas + 2, self.max_replicas)
            
            return ScalingDecision(
                action='scale_up',
                current_replicas=current_replicas,
                target_replicas=target_replicas,
                reason='; '.join(reasons),
                confidence=min(scale_up_score / 10.0, 1.0)
            )
        
        elif scale_down_score >= 3 and current_replicas > self.min_replicas:
            target_replicas = max(current_replicas - 1, self.min_replicas)
            
            return ScalingDecision(
                action='scale_down',
                current_replicas=current_replicas,
                target_replicas=target_replicas,
                reason='; '.join(reasons),
                confidence=min(scale_down_score / 5.0, 1.0)
            )
        
        else:
            return ScalingDecision(
                action='no_change',
                current_replicas=current_replicas,
                target_replicas=current_replicas,
                reason='Metrics within acceptable ranges',
                confidence=1.0
            )

    def execute_scaling(self, decision: ScalingDecision) -> bool:
        """Execute the scaling decision."""
        if decision.action == 'no_change':
            return True
        
        # Check cooldown period
        current_time = time.time()
        if decision.action == 'scale_up':
            cooldown = self.scale_up_cooldown
        else:
            cooldown = self.scale_down_cooldown
        
        if (current_time - self.last_scale_time) < cooldown:
            remaining = cooldown - (current_time - self.last_scale_time)
            self.logger.info(f"Scaling {decision.action} requested but in cooldown period. "
                           f"Remaining: {remaining:.0f}s")
            return False
        
        try:
            # Execute Docker service scale command
            result = subprocess.run([
                'docker', 'service', 'scale', 
                f"{self.service_name}={decision.target_replicas}"
            ], capture_output=True, text=True, check=True)
            
            self.logger.info(f"Scaled service {decision.action}: "
                           f"{decision.current_replicas} → {decision.target_replicas} replicas")
            self.logger.info(f"Reason: {decision.reason}")
            
            # Update scaling state
            self.last_scale_time = current_time
            self.last_scale_action = decision.action
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to scale service: {e}")
            return False

    def run_scaling_cycle(self) -> ScalingDecision:
        """Run one scaling evaluation cycle."""
        self.logger.info("Running scaling evaluation...")
        
        # Get current metrics
        metrics = self.get_metrics()
        current_replicas = self.get_current_replicas()
        
        # Log current state
        self.logger.info(f"Current replicas: {current_replicas}")
        self.logger.info(f"Metrics: {json.dumps({k: f'{v:.2f}' if v else 'N/A' for k, v in metrics.items()})}")
        
        # Make scaling decision
        decision = self.make_scaling_decision(metrics, current_replicas)
        
        # Execute if needed
        if decision.action != 'no_change':
            self.execute_scaling(decision)
        else:
            self.logger.info("No scaling action required")
        
        return decision

    def run_daemon(self, interval: int = 60):
        """Run the auto-scaler as a daemon."""
        self.logger.info(f"Starting PDF Scanner Auto-scaler daemon (interval: {interval}s)")
        self.logger.info(f"Service: {self.service_name}")
        self.logger.info(f"Replicas range: {self.min_replicas}-{self.max_replicas}")
        
        while True:
            try:
                decision = self.run_scaling_cycle()
                time.sleep(interval)
            except KeyboardInterrupt:
                self.logger.info("Auto-scaler stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in scaling cycle: {e}")
                time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description='Auto-scaler for PDF Scanner service')
    parser.add_argument('--prometheus-url', default='http://localhost:9090',
                       help='Prometheus server URL')
    parser.add_argument('--service-name', default='pdf-scanner-stack_pdf-scanner',
                       help='Docker Swarm service name')
    parser.add_argument('--min-replicas', type=int, default=1,
                       help='Minimum number of replicas')
    parser.add_argument('--max-replicas', type=int, default=10,
                       help='Maximum number of replicas')
    parser.add_argument('--interval', type=int, default=60,
                       help='Evaluation interval in seconds')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit (for testing)')
    
    args = parser.parse_args()
    
    scaler = AutoScaler(
        prometheus_url=args.prometheus_url,
        service_name=args.service_name,
        min_replicas=args.min_replicas,
        max_replicas=args.max_replicas
    )
    
    if args.once:
        decision = scaler.run_scaling_cycle()
        print(f"Decision: {decision.action}")
        print(f"Replicas: {decision.current_replicas} → {decision.target_replicas}")
        print(f"Reason: {decision.reason}")
        print(f"Confidence: {decision.confidence:.2f}")
    else:
        scaler.run_daemon(args.interval)

if __name__ == '__main__':
    main()