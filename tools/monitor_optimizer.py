#!/usr/bin/env python3
"""
进程监控工具 - 监控优化进程并诊断被杀死的原因

功能:
1. 实时监控进程CPU/内存使用
2. 检测进程终止并分析原因
3. 检查OOM Killer日志
4. 记录详细的监控日志
5. 支持多进程监控

使用方法:
    python monitor_optimizer.py --keyword "unified_optimizer" --interval 30
    python monitor_optimizer.py --pid 12345 --interval 10
"""

import os
import sys
import time
import argparse
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import json

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("警告: psutil未安装，部分功能受限。安装: pip install psutil")


class ProcessMonitor:
    """进程监控器"""

    def __init__(
        self,
        keyword: Optional[str] = None,
        pids: Optional[List[int]] = None,
        interval: int = 30,
        log_dir: Optional[str] = None,
    ):
        self.keyword = keyword
        self.target_pids = set(pids) if pids else set()
        self.interval = interval
        self.tracked_pids: Set[int] = set()
        self.process_history: Dict[int, dict] = {}

        # 设置日志目录
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs" / "monitor"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 设置日志
        self.log_file = self.log_dir / f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self._setup_logging()

    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger("ProcessMonitor")
        self.logger.setLevel(logging.INFO)

        # 文件handler
        fh = logging.FileHandler(self.log_file, encoding='utf-8')
        fh.setLevel(logging.INFO)

        # 控制台handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # 格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def find_processes(self) -> List[dict]:
        """查找匹配的进程"""
        processes = []

        if HAS_PSUTIL:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'create_time']):
                try:
                    pinfo = proc.info
                    cmdline = ' '.join(pinfo['cmdline']) if pinfo['cmdline'] else ''

                    # 检查是否匹配
                    match = False
                    if self.keyword and self.keyword in cmdline:
                        match = True
                    if pinfo['pid'] in self.target_pids:
                        match = True

                    if match:
                        processes.append({
                            'pid': pinfo['pid'],
                            'name': pinfo['name'],
                            'cmdline': cmdline[:200],  # 截断
                            'cpu_percent': proc.cpu_percent(),
                            'memory_mb': pinfo['memory_info'].rss / 1024 / 1024 if pinfo['memory_info'] else 0,
                            'memory_gb': pinfo['memory_info'].rss / 1024 / 1024 / 1024 if pinfo['memory_info'] else 0,
                            'create_time': datetime.fromtimestamp(pinfo['create_time']).strftime('%Y-%m-%d %H:%M:%S'),
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            # 使用ps命令
            try:
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.split('\n')[1:]:
                    if self.keyword and self.keyword in line:
                        parts = line.split()
                        if len(parts) >= 11:
                            processes.append({
                                'pid': int(parts[1]),
                                'cpu_percent': float(parts[2]),
                                'memory_mb': float(parts[5]) / 1024 if parts[5].isdigit() else 0,
                                'cmdline': ' '.join(parts[10:])[:200],
                            })
            except Exception as e:
                self.logger.error(f"无法获取进程列表: {e}")

        return processes

    def get_system_status(self) -> dict:
        """获取系统状态"""
        status = {}

        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            status = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_total_gb': mem.total / 1024 / 1024 / 1024,
                'memory_used_gb': mem.used / 1024 / 1024 / 1024,
                'memory_available_gb': mem.available / 1024 / 1024 / 1024,
                'memory_percent': mem.percent,
                'swap_total_gb': swap.total / 1024 / 1024 / 1024,
                'swap_used_gb': swap.used / 1024 / 1024 / 1024,
                'swap_percent': swap.percent,
                'load_avg': os.getloadavg(),
            }
        else:
            # 使用free命令
            try:
                result = subprocess.run(['free', '-b'], capture_output=True, text=True)
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Mem:' in line or '内存' in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            status['memory_total_gb'] = int(parts[1]) / 1024 / 1024 / 1024
                            status['memory_used_gb'] = int(parts[2]) / 1024 / 1024 / 1024
            except Exception:
                pass

        return status

    def check_oom_killer(self) -> List[str]:
        """检查OOM Killer日志"""
        oom_logs = []

        # 尝试dmesg
        try:
            result = subprocess.run(
                ['dmesg'],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'killed process' in line.lower() or 'oom' in line.lower():
                    oom_logs.append(f"[dmesg] {line}")
        except Exception:
            pass

        # 尝试journalctl
        try:
            result = subprocess.run(
                ['journalctl', '--since', '10 minutes ago', '--no-pager'],
                capture_output=True,
                text=True,
                timeout=10
            )
            for line in result.stdout.split('\n'):
                if 'killed' in line.lower() or 'oom' in line.lower():
                    oom_logs.append(f"[journal] {line}")
        except Exception:
            pass

        return oom_logs[-20:]  # 最近20条

    def analyze_termination(self, pid: int) -> dict:
        """分析进程终止原因"""
        analysis = {
            'pid': pid,
            'timestamp': datetime.now().isoformat(),
            'possible_causes': [],
            'oom_logs': [],
            'system_status': self.get_system_status(),
        }

        # 检查OOM
        oom_logs = self.check_oom_killer()
        if oom_logs:
            analysis['oom_logs'] = oom_logs
            for log in oom_logs:
                if str(pid) in log:
                    analysis['possible_causes'].append('OOM Killer (内存不足被系统杀死)')
                    break

        # 检查系统状态
        sys_status = analysis['system_status']
        if sys_status.get('swap_percent', 0) > 90:
            analysis['possible_causes'].append('交换分区接近满载')
        if sys_status.get('memory_percent', 0) > 95:
            analysis['possible_causes'].append('系统内存使用率过高')

        # 检查进程历史
        if pid in self.process_history:
            hist = self.process_history[pid]
            if hist.get('memory_gb', 0) > 50:
                analysis['possible_causes'].append(f'进程内存使用量大 ({hist["memory_gb"]:.1f}GB)')

        if not analysis['possible_causes']:
            analysis['possible_causes'].append('原因未知 (可能是手动终止、信号中断或程序错误)')

        return analysis

    def run(self):
        """运行监控"""
        self.logger.info("=" * 60)
        self.logger.info("进程监控启动")
        self.logger.info(f"监控关键词: {self.keyword}")
        self.logger.info(f"监控PID: {self.target_pids if self.target_pids else '自动检测'}")
        self.logger.info(f"检查间隔: {self.interval}秒")
        self.logger.info(f"日志文件: {self.log_file}")
        self.logger.info("=" * 60)

        try:
            while True:
                # 查找进程
                processes = self.find_processes()
                current_pids = {p['pid'] for p in processes}

                # 记录进程状态
                for proc in processes:
                    pid = proc['pid']
                    self.process_history[pid] = proc

                    self.logger.info(
                        f"[运行中] PID={pid} | "
                        f"CPU={proc.get('cpu_percent', 0):.1f}% | "
                        f"内存={proc.get('memory_gb', 0):.2f}GB | "
                        f"启动={proc.get('create_time', 'N/A')}"
                    )

                    # 检查是否是新进程
                    if pid not in self.tracked_pids:
                        self.logger.info(f"[新进程] PID={pid} 开始监控")
                        self.tracked_pids.add(pid)

                # 检查是否有进程终止
                terminated_pids = self.tracked_pids - current_pids
                for pid in terminated_pids:
                    self.logger.warning("=" * 60)
                    self.logger.warning(f"[进程终止] PID={pid}")

                    # 分析原因
                    analysis = self.analyze_termination(pid)

                    self.logger.warning(f"可能原因: {', '.join(analysis['possible_causes'])}")

                    if analysis['oom_logs']:
                        self.logger.warning("OOM相关日志:")
                        for log in analysis['oom_logs'][:5]:
                            self.logger.warning(f"  {log}")

                    self.logger.warning(f"系统状态: 内存使用 {analysis['system_status'].get('memory_percent', 'N/A')}%, "
                                       f"Swap使用 {analysis['system_status'].get('swap_percent', 'N/A')}%")

                    # 保存分析结果
                    analysis_file = self.log_dir / f"termination_analysis_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
                    self.logger.warning(f"分析结果已保存: {analysis_file}")

                    self.logger.warning("=" * 60)
                    self.tracked_pids.discard(pid)

                # 如果没有进程在运行
                if not processes and not self.tracked_pids:
                    self.logger.info("[等待中] 没有匹配的进程运行")

                # 定期记录系统状态
                if int(time.time()) % 300 < self.interval:  # 每5分钟
                    sys_status = self.get_system_status()
                    self.logger.info(
                        f"[系统状态] CPU={sys_status.get('cpu_percent', 'N/A')}% | "
                        f"内存={sys_status.get('memory_percent', 'N/A')}% | "
                        f"Swap={sys_status.get('swap_percent', 'N/A')}%"
                    )

                time.sleep(self.interval)

        except KeyboardInterrupt:
            self.logger.info("监控已停止 (用户中断)")


def main():
    parser = argparse.ArgumentParser(description='进程监控工具')
    parser.add_argument('--keyword', '-k', type=str, default='unified_optimizer',
                        help='进程关键词 (默认: unified_optimizer)')
    parser.add_argument('--pid', '-p', type=int, nargs='+',
                        help='指定监控的PID')
    parser.add_argument('--interval', '-i', type=int, default=30,
                        help='检查间隔秒数 (默认: 30)')
    parser.add_argument('--log-dir', '-l', type=str,
                        help='日志目录')

    args = parser.parse_args()

    monitor = ProcessMonitor(
        keyword=args.keyword,
        pids=args.pid,
        interval=args.interval,
        log_dir=args.log_dir,
    )
    monitor.run()


if __name__ == '__main__':
    main()
