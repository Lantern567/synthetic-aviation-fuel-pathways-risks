# SAF供应链优化 - 快速使用指南

## 快速开始

### 基本用法

```bash
# 两步法，使用默认配置
python run_optimizer.py --process two_step

# 一步法，使用默认配置
python run_optimizer.py --process one_step
```

### 常用配置

```bash
# 两步法，64线程，2小时时限
python run_optimizer.py --process two_step --threads 64 --parallel-workers 64 --time-limit 7200

# 一步法，128线程，4小时时限，1% Gap
python run_optimizer.py --process one_step --threads 128 --parallel-workers 128 --time-limit 14400 --mip-gap 0.01

# 内存受限环境 (16线程)
python run_optimizer.py --process two_step --threads 16 --parallel-workers 16 --time-limit 3600
```

### 自定义配置文件

```bash
# 使用自定义配置
python run_optimizer.py --process one_step --config shared/data/my_config.yaml --threads 64
```

## 命令行参数

| 参数 | 必选 | 默认值 | 说明 | 控制阶段 |
|------|-----|--------|------|---------|
| `--process` | ✓ | - | `two_step` 或 `one_step` | - |
| `--config` | ✗ | 内置配置 | 自定义配置文件路径 | - |
| `--threads` | ✗ | CPU核心数-2 | **Gurobi求解器**线程数 | Stage 3 |
| `--parallel-workers` | ✗ | CPU核心数 | **数据处理+距离计算**并行数 | Stage 1+2 |
| `--time-limit` | ✗ | 3600 | 求解时间限制(秒) | Stage 3 |
| `--mip-gap` | ✗ | 0.01 | MIP优化间隙(1%) | Stage 3 |
| `--weeks` | ✗ | 1 | 优化时间范围(周) | - |
| `--log-level` | ✗ | INFO | 日志级别 | - |

**重要说明**:
- `--threads`: 只影响**Gurobi求解器**阶段（Stage 3）
- `--parallel-workers`: 同时影响**数据处理**（Stage 1）和**距离计算**（Stage 2），包括GraphHopper API并行调用，实现30-60倍加速

## 性能配置建议

### 高性能服务器 (128核, 256GB内存)
```bash
python run_optimizer.py --process two_step \
  --threads 128 \
  --parallel-workers 128 \
  --time-limit 14400 \
  --mip-gap 0.001
```

### 标准服务器 (64核, 128GB内存)
```bash
python run_optimizer.py --process two_step \
  --threads 64 \
  --parallel-workers 64 \
  --time-limit 7200 \
  --mip-gap 0.01
```

### 工作站 (32核, 64GB内存)
```bash
python run_optimizer.py --process two_step \
  --threads 32 \
  --parallel-workers 32 \
  --time-limit 3600 \
  --mip-gap 0.02
```

### 低配环境 (16核, 32GB内存)
```bash
python run_optimizer.py --process two_step \
  --threads 16 \
  --parallel-workers 16 \
  --time-limit 1800 \
  --mip-gap 0.05
```

## 三阶段并行架构

```
Stage 1: 数据处理并行 (parallel_workers)
  └─ 可再生能源、机场、CO₂源数据处理

Stage 2: 距离计算并行 (parallel_workers)  ← 加速30-60倍
  └─ GraphHopper路径规划API并行调用

Stage 3: Gurobi求解器并行 (threads)
  └─ MILP模型求解
```

## 查看帮助

```bash
python run_optimizer.py --help
```

## 输出结果

结果保存在 `results/` 目录:
- `tables/` - CSV表格 (设施位置、生产计划、运输计划)
- `figures/` - 图表 (供应链地图、成本分析)
- `reports/` - 优化报告
- `logs/` - 运行日志

## 详细文档

- [并行距离计算实现说明](docs/并行距离计算实现说明.md)
- [两步法和一步法运行指南](docs/两步法和一步法运行指南.md)
