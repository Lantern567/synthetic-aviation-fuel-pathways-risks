# parallel_workers 参数修复说明

## 问题描述

用户运行命令时出现错误：
```bash
python run_optimizer.py --process one_step --threads 128 --parallel-workers 128
```

错误信息：
```
TypeError: UnifiedSAFOptimizer.__init__() got an unexpected keyword argument 'parallel_workers'
```

## 问题原因

`UnifiedSAFOptimizer` 类的 `__init__` 方法缺少 `parallel_workers` 参数，但命令行工具 `run_optimizer.py` 尝试传递此参数。

## 修复内容

### 1. 修改文件
`src/runner/unified_optimizer_runner.py`

### 2. 具体修改

#### 修改1: 添加参数定义 (第76行)
```python
def __init__(
    self,
    process_type: str = 'two_step',
    threads: Optional[int] = None,
    time_limit: int = 3600,
    mip_gap: float = 0.01,
    time_horizon_weeks: int = 1,
    parallel_workers: Optional[int] = None,  # ← NEW
    osm_pbf_path: Optional[str] = None,
    ...
):
```

#### 修改2: 更新文档字符串 (第96行)
```python
Args:
    ...
    parallel_workers: 数据处理+距离计算并行workers数,None时自动检测(cpu_count)  # ← NEW
    ...
```

#### 修改3: 保存参数 (第140行)
```python
self.threads = self._determine_threads(threads)
self.parallel_workers = parallel_workers  # ← NEW
self.time_limit = time_limit
self.mip_gap = mip_gap
```

#### 修改4: 传递参数给底层优化器 (第276-285行)
```python
# 准备override_params传递parallel_workers
override_params = {}
if self.parallel_workers is not None:
    override_params['parallel_workers'] = self.parallel_workers

self.optimizer = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=self.time_horizon_weeks,
    osm_pbf_path=self.osm_pbf_path,
    override_params=override_params if override_params else None,  # ← NEW
)
```

## 修复后使用方式

### 基本使用
```bash
# 使用默认parallel_workers (自动检测CPU核心数)
python run_optimizer.py --process two_step

# 显式指定parallel_workers
python run_optimizer.py --process two_step --parallel-workers 64

# 完整配置
python run_optimizer.py --process one_step \
  --threads 128 \
  --parallel-workers 128 \
  --time-limit 14400 \
  --mip-gap 0.01
```

### Python API使用
```python
from src.runner import UnifiedSAFOptimizer

# 方式1: 使用默认parallel_workers
optimizer = UnifiedSAFOptimizer(
    process_type='two_step',
    threads=64
)

# 方式2: 显式指定parallel_workers
optimizer = UnifiedSAFOptimizer(
    process_type='two_step',
    threads=64,
    parallel_workers=64  # 数据处理+距离计算并行
)

results = optimizer.run()
```

## 参数说明

### `--parallel-workers` / `parallel_workers`

**控制阶段**: Stage 1 (数据处理) + Stage 2 (距离计算)

**功能**:
- **Stage 1**: 并行处理可再生能源、机场、CO₂源数据
- **Stage 2**: 并行调用GraphHopper API计算距离 ⭐ **加速30-60倍**

**默认值**: `None` (自动检测CPU核心数)

**推荐值**:
- 高性能服务器: 128
- 标准服务器: 64
- 工作站: 32
- 低配环境: 16

### `--threads` / `threads`

**控制阶段**: Stage 3 (Gurobi求解器)

**功能**: Gurobi MILP求解器的并行线程数

**默认值**: `None` (自动检测, CPU核心数-2)

**推荐值**: 与CPU核心数相同或稍少

## 三阶段并行架构

```
时间线: [Stage 1] → [Stage 2] → [Stage 3]

Stage 1: 数据处理并行
  参数: parallel_workers
  耗时: 1-2分钟 (原15-30分钟, 加速15-30倍)

Stage 2: 距离计算并行 ⭐
  参数: parallel_workers
  耗时: 5-12秒 (原4-12分钟, 加速30-60倍)

Stage 3: Gurobi求解器并行
  参数: threads
  耗时: 30-120分钟 (取决于问题规模和Gap)
```

## 验证修复

### 测试命令
```bash
# 测试帮助信息
python run_optimizer.py --help

# 测试基本运行 (使用默认parallel_workers)
python run_optimizer.py --process two_step

# 测试显式parallel_workers
python run_optimizer.py --process two_step --parallel-workers 32
```

### 预期输出
```
================================================================================
SAF供应链优化 - TWO_STEP
================================================================================
工艺路线: two_step
Gurobi线程数: 自动检测
并行Workers: 32  ← 显示正确的parallel_workers值
时间限制: 3600秒 (60.0分钟)
MIP Gap: 1.00%
优化周数: 1
================================================================================
```

## 注意事项

1. **参数独立性**: `threads` 和 `parallel_workers` 控制不同阶段，可以同时设置为最大值
2. **内存考虑**: 每个worker约200-500MB内存，根据系统内存调整
3. **距离计算性能**: `parallel_workers` 越大，距离计算越快（30-60倍加速）
4. **自动检测**: 不指定参数时，系统会自动使用最优值

## 修复完成时间
2025-10-23

## 相关文件
- `src/runner/unified_optimizer_runner.py` (修改)
- `run_optimizer.py` (使用)
- `README_QUICK_START.md` (文档)
