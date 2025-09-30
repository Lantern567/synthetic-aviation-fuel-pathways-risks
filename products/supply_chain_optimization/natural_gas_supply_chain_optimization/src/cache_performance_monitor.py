"""
Cache Performance Monitor
缓存性能监控器 - 提供实时缓存性能监控、分析和报告功能
"""

import os
import json
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import logging
import psutil
from pathlib import Path

# 尝试导入已有的缓存组件
try:
    from unified_cache_configuration import UnifiedCacheConfiguration
    from pipeline_route_cache_manager import PipelineRouteCacheManager
    from data_cache_manager import DataCacheManager
    CACHE_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"部分缓存组件不可用: {e}")
    CACHE_COMPONENTS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CacheMetrics:
    """缓存指标数据类"""
    timestamp: str
    cache_type: str  # 'graphhopper', 'pipeline', 'data'
    operation: str   # 'read', 'write', 'hit', 'miss', 'cleanup'

    # 性能指标
    execution_time_ms: float = 0.0
    data_size_bytes: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

    # 缓存状态指标
    cache_size_entries: int = 0
    cache_size_bytes: int = 0
    hit_rate_percent: float = 0.0

    # 错误信息
    error_message: Optional[str] = None
    success: bool = True

@dataclass
class PerformanceSummary:
    """性能总结数据类"""
    time_period: str
    total_operations: int
    average_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    total_data_processed_mb: float
    average_hit_rate_percent: float
    error_count: int
    cache_efficiency_score: float  # 综合效率评分

class CachePerformanceMonitor:
    """缓存性能监控器"""

    def __init__(self,
                 monitor_dir: str = "cache/performance_monitoring",
                 enable_realtime_monitoring: bool = True,
                 metrics_retention_days: int = 7,
                 sampling_interval_seconds: int = 30):
        """
        初始化性能监控器

        Args:
            monitor_dir: 监控数据存储目录
            enable_realtime_monitoring: 是否启用实时监控
            metrics_retention_days: 指标数据保留天数
            sampling_interval_seconds: 采样间隔(秒)
        """
        self.monitor_dir = Path(monitor_dir)
        self.monitor_dir.mkdir(parents=True, exist_ok=True)

        self.enable_realtime_monitoring = enable_realtime_monitoring
        self.metrics_retention_days = metrics_retention_days
        self.sampling_interval_seconds = sampling_interval_seconds

        # 监控数据库
        self.metrics_db_path = self.monitor_dir / "cache_metrics.db"
        self.reports_dir = self.monitor_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)

        # 实时监控数据
        self.realtime_metrics = deque(maxlen=1000)  # 保留最近1000个指标
        self.monitoring_active = False
        self.monitoring_thread = None

        # 性能统计
        self.operation_stats = defaultdict(list)  # 操作类型 -> [执行时间列表]
        self.cache_type_stats = defaultdict(dict)  # 缓存类型 -> 统计信息

        # 初始化数据库
        self._initialize_metrics_database()

        # 启动实时监控
        if enable_realtime_monitoring:
            self.start_monitoring()

        logger.info(f"缓存性能监控器初始化完成，监控目录: {monitor_dir}")

    def _initialize_metrics_database(self):
        """初始化指标数据库"""
        try:
            # 确保缓存目录存在
            cache_dir = os.path.dirname(self.metrics_db_path)
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"确保性能监控目录存在: {cache_dir}")

            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()

            # 创建指标表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cache_type TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    execution_time_ms REAL,
                    data_size_bytes INTEGER,
                    memory_usage_mb REAL,
                    cpu_usage_percent REAL,
                    cache_size_entries INTEGER,
                    cache_size_bytes INTEGER,
                    hit_rate_percent REAL,
                    error_message TEXT,
                    success BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建性能汇总表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time_period TEXT NOT NULL,
                    cache_type TEXT,
                    total_operations INTEGER,
                    avg_response_time_ms REAL,
                    max_response_time_ms REAL,
                    min_response_time_ms REAL,
                    total_data_processed_mb REAL,
                    average_hit_rate_percent REAL,
                    error_count INTEGER,
                    cache_efficiency_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON cache_metrics(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_type ON cache_metrics(cache_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_operation ON cache_metrics(operation)')

            conn.commit()
            conn.close()

            logger.info("性能监控数据库初始化完成")

        except Exception as e:
            logger.error(f"性能监控数据库初始化失败: {e}")
            raise

    def record_metric(self, metric: CacheMetrics):
        """记录缓存指标"""
        try:
            # 添加到实时监控队列
            self.realtime_metrics.append(metric)

            # 更新操作统计
            self.operation_stats[metric.operation].append(metric.execution_time_ms)

            # 保存到数据库
            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO cache_metrics (
                    timestamp, cache_type, operation, execution_time_ms, data_size_bytes,
                    memory_usage_mb, cpu_usage_percent, cache_size_entries,
                    cache_size_bytes, hit_rate_percent, error_message, success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metric.timestamp, metric.cache_type, metric.operation,
                metric.execution_time_ms, metric.data_size_bytes,
                metric.memory_usage_mb, metric.cpu_usage_percent,
                metric.cache_size_entries, metric.cache_size_bytes,
                metric.hit_rate_percent, metric.error_message, metric.success
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"记录缓存指标失败: {e}")

    def create_operation_metric(self, cache_type: str, operation: str,
                               execution_time_ms: float = 0.0,
                               data_size_bytes: int = 0,
                               error_message: str = None,
                               success: bool = True,
                               additional_data: Dict = None) -> CacheMetrics:
        """创建操作指标对象"""

        # 获取系统资源使用情况
        try:
            process = psutil.Process()
            memory_usage_mb = process.memory_info().rss / 1024 / 1024
            cpu_usage_percent = process.cpu_percent()
        except:
            memory_usage_mb = 0.0
            cpu_usage_percent = 0.0

        metric = CacheMetrics(
            timestamp=datetime.now().isoformat(),
            cache_type=cache_type,
            operation=operation,
            execution_time_ms=execution_time_ms,
            data_size_bytes=data_size_bytes,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            error_message=error_message,
            success=success
        )

        # 添加额外数据
        if additional_data:
            for key, value in additional_data.items():
                if hasattr(metric, key):
                    setattr(metric, key, value)

        return metric

    def start_monitoring(self):
        """启动实时监控"""
        if self.monitoring_active:
            logger.warning("性能监控已在运行")
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()

        logger.info("实时性能监控已启动")

    def stop_monitoring(self):
        """停止实时监控"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("实时性能监控已停止")

    def _monitoring_loop(self):
        """监控循环"""
        while self.monitoring_active:
            try:
                # 收集系统级监控数据
                self._collect_system_metrics()

                # 收集缓存组件状态
                if CACHE_COMPONENTS_AVAILABLE:
                    self._collect_cache_component_metrics()

                time.sleep(self.sampling_interval_seconds)

            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(self.sampling_interval_seconds)

    def _collect_system_metrics(self):
        """收集系统级指标"""
        try:
            # CPU和内存使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()

            # 磁盘使用情况
            cache_disk_usage = psutil.disk_usage(str(self.monitor_dir.parent))

            system_metric = CacheMetrics(
                timestamp=datetime.now().isoformat(),
                cache_type="system",
                operation="monitoring",
                memory_usage_mb=memory.used / 1024 / 1024,
                cpu_usage_percent=cpu_percent
            )

            self.realtime_metrics.append(system_metric)

        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")

    def _collect_cache_component_metrics(self):
        """收集缓存组件指标"""
        try:
            # 这里可以集成各种缓存组件的统计信息
            # 由于组件可能不可用，这里使用基本的文件大小检查

            cache_dirs = [
                ("data", "cache/filtered_500km_data"),
                ("graphhopper", "cache/path_planning_cache/graphhopper_routes"),
                ("pipeline", "cache/path_planning_cache/pipeline_routes")
            ]

            for cache_type, cache_dir in cache_dirs:
                if os.path.exists(cache_dir):
                    total_size = 0
                    file_count = 0

                    for root, dirs, files in os.walk(cache_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                                file_count += 1
                            except:
                                pass

                    cache_metric = CacheMetrics(
                        timestamp=datetime.now().isoformat(),
                        cache_type=cache_type,
                        operation="status_check",
                        cache_size_entries=file_count,
                        cache_size_bytes=total_size
                    )

                    self.realtime_metrics.append(cache_metric)

        except Exception as e:
            logger.error(f"收集缓存组件指标失败: {e}")

    def get_realtime_metrics(self, cache_type: str = None,
                           operation: str = None,
                           limit: int = 100) -> List[Dict]:
        """获取实时指标数据"""
        metrics = list(self.realtime_metrics)

        # 过滤条件
        if cache_type:
            metrics = [m for m in metrics if m.cache_type == cache_type]
        if operation:
            metrics = [m for m in metrics if m.operation == operation]

        # 限制数量
        metrics = metrics[-limit:]

        return [asdict(metric) for metric in metrics]

    def generate_performance_summary(self,
                                   time_period: str = "1h",
                                   cache_type: str = None) -> PerformanceSummary:
        """
        生成性能总结报告

        Args:
            time_period: 时间期间 ("1h", "24h", "7d")
            cache_type: 缓存类型过滤

        Returns:
            性能总结对象
        """
        # 计算时间范围
        now = datetime.now()
        if time_period == "1h":
            start_time = now - timedelta(hours=1)
        elif time_period == "24h":
            start_time = now - timedelta(hours=24)
        elif time_period == "7d":
            start_time = now - timedelta(days=7)
        else:
            start_time = now - timedelta(hours=1)

        try:
            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()

            # 构建查询条件
            query_conditions = ["datetime(timestamp) >= datetime(?)"]
            params = [start_time.isoformat()]

            if cache_type:
                query_conditions.append("cache_type = ?")
                params.append(cache_type)

            where_clause = " AND ".join(query_conditions)

            # 查询统计数据
            cursor.execute(f'''
                SELECT
                    COUNT(*) as total_operations,
                    AVG(execution_time_ms) as avg_response_time,
                    MAX(execution_time_ms) as max_response_time,
                    MIN(execution_time_ms) as min_response_time,
                    SUM(data_size_bytes) / 1024.0 / 1024.0 as total_data_mb,
                    AVG(hit_rate_percent) as avg_hit_rate,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                FROM cache_metrics
                WHERE {where_clause}
            ''', params)

            result = cursor.fetchone()
            conn.close()

            if result and result[0] > 0:
                total_ops, avg_time, max_time, min_time, total_data, avg_hit_rate, error_count = result

                # 计算缓存效率评分 (0-100)
                efficiency_score = self._calculate_efficiency_score(
                    avg_hit_rate or 0, avg_time or 0, error_count, total_ops
                )

                return PerformanceSummary(
                    time_period=time_period,
                    total_operations=total_ops,
                    average_response_time_ms=avg_time or 0,
                    max_response_time_ms=max_time or 0,
                    min_response_time_ms=min_time or 0,
                    total_data_processed_mb=total_data or 0,
                    average_hit_rate_percent=avg_hit_rate or 0,
                    error_count=error_count,
                    cache_efficiency_score=efficiency_score
                )
            else:
                return PerformanceSummary(
                    time_period=time_period,
                    total_operations=0,
                    average_response_time_ms=0,
                    max_response_time_ms=0,
                    min_response_time_ms=0,
                    total_data_processed_mb=0,
                    average_hit_rate_percent=0,
                    error_count=0,
                    cache_efficiency_score=0
                )

        except Exception as e:
            logger.error(f"生成性能总结失败: {e}")
            return PerformanceSummary(
                time_period=time_period,
                total_operations=0,
                average_response_time_ms=0,
                max_response_time_ms=0,
                min_response_time_ms=0,
                total_data_processed_mb=0,
                average_hit_rate_percent=0,
                error_count=0,
                cache_efficiency_score=0
            )

    def _calculate_efficiency_score(self, hit_rate: float, avg_response_time: float,
                                  error_count: int, total_operations: int) -> float:
        """计算缓存效率评分"""
        score = 0

        # 命中率权重：40%
        score += (hit_rate / 100.0) * 40

        # 响应时间权重：30% (越快越好，假设100ms以下为最佳)
        if avg_response_time > 0:
            time_score = max(0, (100 - avg_response_time) / 100)
            score += time_score * 30
        else:
            score += 30

        # 错误率权重：20%
        if total_operations > 0:
            error_rate = error_count / total_operations
            score += (1 - error_rate) * 20
        else:
            score += 20

        # 可用性权重：10%
        if total_operations > 0:
            score += 10

        return min(100, max(0, score))

    def generate_detailed_report(self,
                               time_period: str = "24h",
                               output_format: str = "json") -> str:
        """
        生成详细性能报告

        Args:
            time_period: 时间期间
            output_format: 输出格式 ("json", "html")

        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 生成各类型缓存的性能总结
        cache_types = ["graphhopper", "pipeline", "data", "system"]
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "time_period": time_period,
            "summaries": {},
            "realtime_sample": self.get_realtime_metrics(limit=50)
        }

        for cache_type in cache_types:
            summary = self.generate_performance_summary(time_period, cache_type)
            report_data["summaries"][cache_type] = asdict(summary)

        # 整体总结
        overall_summary = self.generate_performance_summary(time_period)
        report_data["overall_summary"] = asdict(overall_summary)

        # 保存报告
        if output_format == "json":
            report_file = self.reports_dir / f"performance_report_{timestamp}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
        elif output_format == "html":
            report_file = self.reports_dir / f"performance_report_{timestamp}.html"
            html_content = self._generate_html_report(report_data)
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(html_content)

        logger.info(f"详细性能报告已生成: {report_file}")
        return str(report_file)

    def _generate_html_report(self, report_data: Dict) -> str:
        """生成HTML格式的报告"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>缓存性能监控报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f0f0f0; padding: 15px; border-radius: 5px; }
        .summary { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .metric { display: inline-block; margin: 10px; padding: 10px; background: #f9f9f9; border-radius: 3px; }
        .good { color: green; }
        .warning { color: orange; }
        .error { color: red; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>缓存性能监控报告</h1>
        <p>生成时间: {generated_at}</p>
        <p>时间期间: {time_period}</p>
    </div>

    <div class="summary">
        <h2>整体性能总结</h2>
        <div class="metric">总操作数: {total_operations}</div>
        <div class="metric">平均响应时间: {avg_response_time:.2f}ms</div>
        <div class="metric">平均命中率: {avg_hit_rate:.1f}%</div>
        <div class="metric">效率评分: {efficiency_score:.1f}/100</div>
        <div class="metric">错误数: {error_count}</div>
    </div>

    <div class="summary">
        <h2>各缓存类型性能</h2>
        {cache_type_summaries}
    </div>

    <div class="summary">
        <h2>实时监控样本</h2>
        {realtime_table}
    </div>
</body>
</html>"""

        # 填充模板数据
        overall = report_data["overall_summary"]
        cache_summaries = ""

        for cache_type, summary in report_data["summaries"].items():
            if summary["total_operations"] > 0:
                cache_summaries += f"""
                <h3>{cache_type.title()}缓存</h3>
                <div class="metric">操作数: {summary['total_operations']}</div>
                <div class="metric">响应时间: {summary['average_response_time_ms']:.2f}ms</div>
                <div class="metric">命中率: {summary['average_hit_rate_percent']:.1f}%</div>
                <div class="metric">效率评分: {summary['cache_efficiency_score']:.1f}/100</div>
                """

        # 生成实时监控表格
        realtime_table = "<table><tr><th>时间</th><th>缓存类型</th><th>操作</th><th>执行时间</th><th>状态</th></tr>"
        for metric in report_data["realtime_sample"][-10:]:  # 最近10条
            status_class = "good" if metric["success"] else "error"
            realtime_table += f"""
            <tr>
                <td>{metric['timestamp'][:19]}</td>
                <td>{metric['cache_type']}</td>
                <td>{metric['operation']}</td>
                <td>{metric['execution_time_ms']:.2f}ms</td>
                <td class="{status_class}">{'成功' if metric['success'] else '失败'}</td>
            </tr>"""
        realtime_table += "</table>"

        return html_template.format(
            generated_at=report_data["generated_at"],
            time_period=report_data["time_period"],
            total_operations=overall["total_operations"],
            avg_response_time=overall["average_response_time_ms"],
            avg_hit_rate=overall["average_hit_rate_percent"],
            efficiency_score=overall["cache_efficiency_score"],
            error_count=overall["error_count"],
            cache_type_summaries=cache_summaries,
            realtime_table=realtime_table
        )

    def cleanup_old_metrics(self):
        """清理过期的监控指标"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.metrics_retention_days)

            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM cache_metrics
                WHERE datetime(timestamp) < datetime(?)
            ''', (cutoff_date.isoformat(),))

            deleted_count = cursor.rowcount

            cursor.execute('''
                DELETE FROM performance_summaries
                WHERE datetime(created_at) < datetime(?)
            ''', (cutoff_date.isoformat(),))

            deleted_summaries = cursor.rowcount

            conn.commit()
            conn.close()

            logger.info(f"清理过期监控数据: {deleted_count}条指标, {deleted_summaries}条总结")

        except Exception as e:
            logger.error(f"清理过期监控数据失败: {e}")

    def get_monitor_status(self) -> Dict:
        """获取监控器状态"""
        return {
            "monitoring_active": self.monitoring_active,
            "realtime_metrics_count": len(self.realtime_metrics),
            "database_path": str(self.metrics_db_path),
            "database_exists": self.metrics_db_path.exists(),
            "database_size_mb": self.metrics_db_path.stat().st_size / 1024 / 1024 if self.metrics_db_path.exists() else 0,
            "reports_count": len(list(self.reports_dir.glob("*.json"))) + len(list(self.reports_dir.glob("*.html"))),
            "retention_days": self.metrics_retention_days,
            "sampling_interval_seconds": self.sampling_interval_seconds
        }


# 全局性能监控器实例
performance_monitor = CachePerformanceMonitor()