"""Comprehensive monitoring service with metrics, health checks, and APM."""

import asyncio
import time
import psutil
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import structlog
from collections import defaultdict, deque

from .redis_client import redis_client
from .database import db_manager
from .exceptions import ValidationError

logger = structlog.get_logger()

class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

class HealthStatus(Enum):
    """Health check statuses."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class Metric:
    """Metric data structure."""
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "type": self.type.value
        }

@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    response_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value
        }

class MonitoringService:
    """Comprehensive monitoring service."""
    
    def __init__(self):
        self.initialized = False
        self.metrics_buffer = deque(maxlen=10000)
        self.health_checks = {}
        self.alert_rules = {}
        self.metric_collectors = {}
        
        # Performance tracking
        self.request_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.active_requests = defaultdict(int)
        
        # System metrics
        self.system_metrics = {}
        
    async def initialize(self):
        """Initialize the monitoring service."""
        if self.initialized:
            return
            
        try:
            # Register default health checks
            await self._register_default_health_checks()
            
            # Register default metric collectors
            await self._register_default_collectors()
            
            # Start background tasks
            asyncio.create_task(self._metrics_collection_loop())
            asyncio.create_task(self._health_check_loop())
            asyncio.create_task(self._alert_evaluation_loop())
            
            self.initialized = True
            logger.info("Monitoring Service initialized successfully")
            
        except Exception as e:
            logger.error("Monitoring Service initialization failed", error=str(e))
            raise
    
    async def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Optional[Dict[str, str]] = None
    ):
        """Record a metric."""
        
        metric = Metric(
            name=name,
            type=metric_type,
            value=value,
            labels=labels or {},
            timestamp=datetime.utcnow()
        )
        
        # Add to buffer
        self.metrics_buffer.append(metric)
        
        # Store in Redis for real-time access
        await self._store_metric_in_redis(metric)
        
        # Check alert rules
        await self._check_alert_rules(metric)
    
    async def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric."""
        
        # Get current value from Redis
        key = self._get_metric_key(name, labels)
        current = await redis_client.get(key)
        current_value = float(current) if current else 0.0
        
        new_value = current_value + value
        
        await self.record_metric(name, new_value, MetricType.COUNTER, labels)
    
    async def record_timer(
        self,
        name: str,
        duration: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Record a timer metric."""
        
        await self.record_metric(name, duration, MetricType.TIMER, labels)
        
        # Also update histogram data
        await self._update_histogram(name, duration, labels)
    
    async def start_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Start a timer and return timer ID."""
        
        timer_id = f"{name}_{int(time.time() * 1000000)}"
        
        await redis_client.setex(
            f"timer:{timer_id}",
            300,  # 5 minutes expiry
            json.dumps({
                "name": name,
                "labels": labels or {},
                "start_time": time.time()
            })
        )
        
        return timer_id
    
    async def stop_timer(self, timer_id: str) -> float:
        """Stop a timer and record the duration."""
        
        timer_data = await redis_client.get(f"timer:{timer_id}")
        if not timer_data:
            return 0.0
        
        timer_info = json.loads(timer_data)
        duration = time.time() - timer_info["start_time"]
        
        await self.record_timer(
            timer_info["name"],
            duration,
            timer_info["labels"]
        )
        
        # Clean up
        await redis_client.delete(f"timer:{timer_id}")
        
        return duration
    
    def timer_context(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager for timing operations."""
        
        class TimerContext:
            def __init__(self, monitoring_service, metric_name, metric_labels):
                self.monitoring_service = monitoring_service
                self.name = metric_name
                self.labels = metric_labels
                self.start_time = None
            
            async def __aenter__(self):
                self.start_time = time.time()
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                await self.monitoring_service.record_timer(self.name, duration, self.labels)
        
        return TimerContext(self, name, labels)
    
    async def register_health_check(
        self,
        name: str,
        check_func: Callable,
        interval: int = 60,
        timeout: int = 30
    ):
        """Register a health check."""
        
        self.health_checks[name] = {
            "func": check_func,
            "interval": interval,
            "timeout": timeout,
            "last_check": None,
            "last_result": None
        }
        
        logger.info("Health check registered", name=name, interval=interval)
    
    async def get_health_status(self, check_name: Optional[str] = None) -> Dict[str, Any]:
        """Get health status for all or specific health checks."""
        
        if check_name:
            if check_name not in self.health_checks:
                raise ValidationError(f"Health check '{check_name}' not found")
            
            check_info = self.health_checks[check_name]
            result = check_info.get("last_result")
            
            return result.to_dict() if result else {"status": "unknown"}
        
        else:
            # Return all health checks
            overall_status = HealthStatus.HEALTHY
            checks = {}
            
            for name, check_info in self.health_checks.items():
                result = check_info.get("last_result")
                if result:
                    checks[name] = result.to_dict()
                    
                    # Determine overall status
                    if result.status == HealthStatus.UNHEALTHY:
                        overall_status = HealthStatus.UNHEALTHY
                    elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.DEGRADED
                else:
                    checks[name] = {"status": "unknown"}
                    if overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.UNKNOWN
            
            return {
                "overall_status": overall_status.value,
                "checks": checks,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_metrics(
        self,
        name_pattern: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get metrics matching criteria."""
        
        metrics = []
        
        # Filter metrics from buffer
        for metric in self.metrics_buffer:
            # Check time range
            if start_time and metric.timestamp < start_time:
                continue
            if end_time and metric.timestamp > end_time:
                continue
            
            # Check name pattern
            if name_pattern and name_pattern not in metric.name:
                continue
            
            # Check labels
            if labels:
                if not all(metric.labels.get(k) == v for k, v in labels.items()):
                    continue
            
            metrics.append(metric.to_dict())
        
        return metrics
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": cpu_count,
                    "load_avg": list(load_avg)
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "process": {
                    "memory_rss": process_memory.rss,
                    "memory_vms": process_memory.vms,
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get system metrics", error=str(e))
            return {"error": str(e)}
    
    async def get_application_metrics(self) -> Dict[str, Any]:
        """Get application-specific metrics."""
        
        try:
            # Request metrics
            total_requests = sum(len(times) for times in self.request_times.values())
            avg_response_times = {}
            
            for endpoint, times in self.request_times.items():
                if times:
                    avg_response_times[endpoint] = sum(times) / len(times)
            
            # Error metrics
            total_errors = sum(self.error_counts.values())
            error_rate = (total_errors / max(total_requests, 1)) * 100
            
            # Active requests
            active_requests = dict(self.active_requests)
            
            return {
                "requests": {
                    "total": total_requests,
                    "average_response_times": avg_response_times,
                    "active_requests": active_requests
                },
                "errors": {
                    "total": total_errors,
                    "rate_percent": error_rate,
                    "by_endpoint": dict(self.error_counts)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get application metrics", error=str(e))
            return {"error": str(e)}
    
    async def create_alert_rule(
        self,
        name: str,
        metric_name: str,
        condition: str,
        threshold: float,
        duration: int = 300,
        labels: Optional[Dict[str, str]] = None
    ):
        """Create an alert rule."""
        
        self.alert_rules[name] = {
            "metric_name": metric_name,
            "condition": condition,  # "gt", "lt", "eq", "ne"
            "threshold": threshold,
            "duration": duration,
            "labels": labels or {},
            "triggered_at": None,
            "active": False
        }
        
        logger.info("Alert rule created", name=name, metric=metric_name, condition=condition, threshold=threshold)
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get currently active alerts."""
        
        active_alerts = []
        
        for name, rule in self.alert_rules.items():
            if rule["active"]:
                active_alerts.append({
                    "name": name,
                    "metric_name": rule["metric_name"],
                    "condition": rule["condition"],
                    "threshold": rule["threshold"],
                    "triggered_at": rule["triggered_at"].isoformat() if rule["triggered_at"] else None,
                    "duration": rule["duration"]
                })
        
        return active_alerts
    
    async def track_request(self, endpoint: str, response_time: float, status_code: int):
        """Track request metrics."""
        
        # Record response time
        self.request_times[endpoint].append(response_time)
        
        # Keep only recent times (last 1000 requests)
        if len(self.request_times[endpoint]) > 1000:
            self.request_times[endpoint] = self.request_times[endpoint][-1000:]
        
        # Track errors
        if status_code >= 400:
            self.error_counts[endpoint] += 1
        
        # Record metrics
        await self.record_metric(f"http_requests_total", 1, MetricType.COUNTER, {
            "endpoint": endpoint,
            "status_code": str(status_code)
        })
        
        await self.record_metric(f"http_request_duration_seconds", response_time, MetricType.TIMER, {
            "endpoint": endpoint
        })
    
    async def track_active_request(self, endpoint: str, increment: bool = True):
        """Track active requests."""
        
        if increment:
            self.active_requests[endpoint] += 1
        else:
            self.active_requests[endpoint] = max(0, self.active_requests[endpoint] - 1)
        
        await self.record_metric("http_requests_active", self.active_requests[endpoint], MetricType.GAUGE, {
            "endpoint": endpoint
        })
    
    def request_tracker(self, endpoint: str):
        """Context manager for tracking requests."""
        
        class RequestTracker:
            def __init__(self, monitoring_service, endpoint_name):
                self.monitoring_service = monitoring_service
                self.endpoint = endpoint_name
                self.start_time = None
            
            async def __aenter__(self):
                self.start_time = time.time()
                await self.monitoring_service.track_active_request(self.endpoint, True)
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                status_code = 500 if exc_type else 200
                
                await self.monitoring_service.track_request(self.endpoint, duration, status_code)
                await self.monitoring_service.track_active_request(self.endpoint, False)
        
        return RequestTracker(self, endpoint)
    
    async def _register_default_health_checks(self):
        """Register default health checks."""
        
        # Database health check
        async def database_health():
            try:
                start_time = time.time()
                async with db_manager.get_session() as session:
                    await session.execute("SELECT 1")
                response_time = time.time() - start_time
                
                return HealthCheck(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful",
                    details={"response_time": response_time},
                    timestamp=datetime.utcnow(),
                    response_time=response_time
                )
            except Exception as e:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database connection failed: {str(e)}",
                    details={"error": str(e)},
                    timestamp=datetime.utcnow(),
                    response_time=0.0
                )
        
        # Redis health check
        async def redis_health():
            try:
                start_time = time.time()
                await redis_client.ping()
                response_time = time.time() - start_time
                
                return HealthCheck(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    message="Redis connection successful",
                    details={"response_time": response_time},
                    timestamp=datetime.utcnow(),
                    response_time=response_time
                )
            except Exception as e:
                return HealthCheck(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Redis connection failed: {str(e)}",
                    details={"error": str(e)},
                    timestamp=datetime.utcnow(),
                    response_time=0.0
                )
        
        # System health check
        async def system_health():
            try:
                cpu_percent = psutil.cpu_percent()
                memory_percent = psutil.virtual_memory().percent
                disk_percent = psutil.disk_usage('/').percent if hasattr(psutil.disk_usage('/'), 'percent') else 0
                
                status = HealthStatus.HEALTHY
                message = "System resources normal"
                
                if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
                    status = HealthStatus.UNHEALTHY
                    message = "System resources critical"
                elif cpu_percent > 80 or memory_percent > 80 or disk_percent > 80:
                    status = HealthStatus.DEGRADED
                    message = "System resources high"
                
                return HealthCheck(
                    name="system",
                    status=status,
                    message=message,
                    details={
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "disk_percent": disk_percent
                    },
                    timestamp=datetime.utcnow(),
                    response_time=0.1
                )
            except Exception as e:
                return HealthCheck(
                    name="system",
                    status=HealthStatus.UNKNOWN,
                    message=f"System check failed: {str(e)}",
                    details={"error": str(e)},
                    timestamp=datetime.utcnow(),
                    response_time=0.0
                )
        
        await self.register_health_check("database", database_health, 30)
        await self.register_health_check("redis", redis_health, 30)
        await self.register_health_check("system", system_health, 60)
    
    async def _register_default_collectors(self):
        """Register default metric collectors."""
        
        async def collect_system_metrics():
            system_metrics = await self.get_system_metrics()
            
            if "error" not in system_metrics:
                # Record system metrics
                await self.record_metric("system_cpu_percent", system_metrics["cpu"]["usage_percent"])
                await self.record_metric("system_memory_percent", system_metrics["memory"]["percent"])
                await self.record_metric("system_disk_percent", system_metrics["disk"]["percent"])
                
                # Process metrics
                await self.record_metric("process_memory_rss", system_metrics["process"]["memory_rss"])
                await self.record_metric("process_cpu_percent", system_metrics["process"]["cpu_percent"])
        
        self.metric_collectors["system"] = collect_system_metrics
    
    async def _metrics_collection_loop(self):
        """Background loop for collecting metrics."""
        
        while True:
            try:
                for name, collector in self.metric_collectors.items():
                    try:
                        await collector()
                    except Exception as e:
                        logger.error("Metric collector failed", collector=name, error=str(e))
                
                await asyncio.sleep(60)  # Collect every minute
                
            except Exception as e:
                logger.error("Metrics collection loop error", error=str(e))
                await asyncio.sleep(60)
    
    async def _health_check_loop(self):
        """Background loop for health checks."""
        
        while True:
            try:
                current_time = datetime.utcnow()
                
                for name, check_info in self.health_checks.items():
                    last_check = check_info.get("last_check")
                    interval = check_info["interval"]
                    
                    # Check if it's time to run the health check
                    if not last_check or (current_time - last_check).total_seconds() >= interval:
                        try:
                            # Run health check with timeout
                            result = await asyncio.wait_for(
                                check_info["func"](),
                                timeout=check_info["timeout"]
                            )
                            
                            check_info["last_result"] = result
                            check_info["last_check"] = current_time
                            
                        except asyncio.TimeoutError:
                            check_info["last_result"] = HealthCheck(
                                name=name,
                                status=HealthStatus.UNHEALTHY,
                                message="Health check timed out",
                                details={"timeout": check_info["timeout"]},
                                timestamp=current_time,
                                response_time=check_info["timeout"]
                            )
                            check_info["last_check"] = current_time
                            
                        except Exception as e:
                            check_info["last_result"] = HealthCheck(
                                name=name,
                                status=HealthStatus.UNHEALTHY,
                                message=f"Health check failed: {str(e)}",
                                details={"error": str(e)},
                                timestamp=current_time,
                                response_time=0.0
                            )
                            check_info["last_check"] = current_time
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error("Health check loop error", error=str(e))
                await asyncio.sleep(10)
    
    async def _alert_evaluation_loop(self):
        """Background loop for evaluating alert rules."""
        
        while True:
            try:
                current_time = datetime.utcnow()
                
                for name, rule in self.alert_rules.items():
                    try:
                        # Get recent metrics for this rule
                        recent_metrics = await self._get_recent_metrics(
                            rule["metric_name"],
                            rule["labels"],
                            rule["duration"]
                        )
                        
                        if recent_metrics:
                            # Evaluate condition
                            latest_value = recent_metrics[-1]["value"]
                            condition_met = self._evaluate_condition(
                                latest_value,
                                rule["condition"],
                                rule["threshold"]
                            )
                            
                            if condition_met and not rule["active"]:
                                # Alert triggered
                                rule["active"] = True
                                rule["triggered_at"] = current_time
                                
                                logger.warning("Alert triggered", 
                                             alert=name,
                                             metric=rule["metric_name"],
                                             value=latest_value,
                                             threshold=rule["threshold"])
                            
                            elif not condition_met and rule["active"]:
                                # Alert resolved
                                rule["active"] = False
                                rule["triggered_at"] = None
                                
                                logger.info("Alert resolved",
                                          alert=name,
                                          metric=rule["metric_name"],
                                          value=latest_value)
                    
                    except Exception as e:
                        logger.error("Alert evaluation failed", alert=name, error=str(e))
                
                await asyncio.sleep(30)  # Evaluate every 30 seconds
                
            except Exception as e:
                logger.error("Alert evaluation loop error", error=str(e))
                await asyncio.sleep(30)
    
    def _get_metric_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Generate Redis key for metric."""
        
        key_parts = [f"metric:{name}"]
        
        if labels:
            label_parts = [f"{k}={v}" for k, v in sorted(labels.items())]
            key_parts.extend(label_parts)
        
        return ":".join(key_parts)
    
    async def _store_metric_in_redis(self, metric: Metric):
        """Store metric in Redis for real-time access."""
        
        key = self._get_metric_key(metric.name, metric.labels)
        
        # Store current value
        await redis_client.setex(key, 3600, str(metric.value))
        
        # Store in time series (simplified)
        ts_key = f"{key}:ts"
        await redis_client.lpush(ts_key, json.dumps({
            "value": metric.value,
            "timestamp": metric.timestamp.isoformat()
        }))
        
        # Keep only recent values
        await redis_client.ltrim(ts_key, 0, 1000)
        await redis_client.expire(ts_key, 3600)
    
    async def _update_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Update histogram data for timer metrics."""
        
        # Define buckets
        buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        
        for bucket in buckets:
            if value <= bucket:
                bucket_labels = (labels or {}).copy()
                bucket_labels["le"] = str(bucket)
                
                await self.increment_counter(f"{name}_bucket", 1.0, bucket_labels)
    
    async def _get_recent_metrics(
        self,
        metric_name: str,
        labels: Dict[str, str],
        duration_seconds: int
    ) -> List[Dict[str, Any]]:
        """Get recent metrics for alert evaluation."""
        
        key = self._get_metric_key(metric_name, labels)
        ts_key = f"{key}:ts"
        
        # Get recent values from Redis
        values = await redis_client.lrange(ts_key, 0, -1)
        
        recent_metrics = []
        cutoff_time = datetime.utcnow() - timedelta(seconds=duration_seconds)
        
        for value_json in values:
            try:
                data = json.loads(value_json)
                timestamp = datetime.fromisoformat(data["timestamp"])
                
                if timestamp >= cutoff_time:
                    recent_metrics.append({
                        "value": data["value"],
                        "timestamp": timestamp
                    })
            except:
                continue
        
        return sorted(recent_metrics, key=lambda x: x["timestamp"])
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition."""
        
        if condition == "gt":
            return value > threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "eq":
            return abs(value - threshold) < 0.001
        elif condition == "ne":
            return abs(value - threshold) >= 0.001
        else:
            return False
    
    async def _check_alert_rules(self, metric: Metric):
        """Check if metric triggers any alert rules."""
        
        for name, rule in self.alert_rules.items():
            if rule["metric_name"] == metric.name:
                # Check if labels match
                if all(metric.labels.get(k) == v for k, v in rule["labels"].items()):
                    condition_met = self._evaluate_condition(
                        metric.value,
                        rule["condition"],
                        rule["threshold"]
                    )
                    
                    if condition_met:
                        logger.debug("Alert condition met", alert=name, value=metric.value)

# Global instance
monitoring_service = MonitoringService()