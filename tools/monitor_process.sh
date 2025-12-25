#!/bin/bash
# 进程监控脚本 - 监控优化进程并记录被杀死的原因
# 使用方法: ./monitor_process.sh <进程关键词> [检查间隔秒数]
# 示例: ./monitor_process.sh "unified_optimizer_runner" 30

KEYWORD="${1:-unified_optimizer_runner}"
INTERVAL="${2:-30}"
LOG_DIR="/home/ljt/code_project/green_methanol_for_port_transportation-main/logs/monitor"
LOG_FILE="$LOG_DIR/process_monitor_$(date +%Y%m%d_%H%M%S).log"

# 创建日志目录
mkdir -p "$LOG_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "进程监控启动" | tee -a "$LOG_FILE"
echo "监控关键词: $KEYWORD" | tee -a "$LOG_FILE"
echo "检查间隔: ${INTERVAL}秒" | tee -a "$LOG_FILE"
echo "日志文件: $LOG_FILE" | tee -a "$LOG_FILE"
echo "启动时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 记录初始进程状态
LAST_PIDS=""

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # 获取当前匹配的进程
    CURRENT_PIDS=$(pgrep -f "$KEYWORD" 2>/dev/null | sort | tr '\n' ' ')

    # 获取内存状态
    MEM_INFO=$(free -h | grep "内存" || free -h | grep "Mem")
    SWAP_INFO=$(free -h | grep "交换" || free -h | grep "Swap")

    # 获取系统负载
    LOAD=$(uptime | awk -F'load average:' '{print $2}')

    if [ -n "$CURRENT_PIDS" ]; then
        # 进程存在
        for PID in $CURRENT_PIDS; do
            if [ -d "/proc/$PID" ]; then
                # 获取进程详情
                CPU=$(ps -p $PID -o %cpu= 2>/dev/null || echo "N/A")
                MEM=$(ps -p $PID -o %mem= 2>/dev/null || echo "N/A")
                RSS=$(ps -p $PID -o rss= 2>/dev/null || echo "N/A")
                VSZ=$(ps -p $PID -o vsz= 2>/dev/null || echo "N/A")
                ETIME=$(ps -p $PID -o etime= 2>/dev/null || echo "N/A")

                # 转换为GB
                if [ "$RSS" != "N/A" ]; then
                    RSS_GB=$(echo "scale=2; $RSS / 1024 / 1024" | bc 2>/dev/null || echo "$RSS KB")
                else
                    RSS_GB="N/A"
                fi

                echo "[$TIMESTAMP] PID=$PID | CPU=${CPU}% | MEM=${MEM}% | RSS=${RSS_GB}GB | 运行时间=$ETIME" | tee -a "$LOG_FILE"
            fi
        done

        # 检查是否有新进程启动
        for PID in $CURRENT_PIDS; do
            if [[ ! " $LAST_PIDS " =~ " $PID " ]]; then
                echo "[$TIMESTAMP] [新进程] PID=$PID 启动" | tee -a "$LOG_FILE"
            fi
        done

    else
        # 没有匹配的进程
        if [ -n "$LAST_PIDS" ]; then
            # 之前有进程，现在没有了 - 进程被杀死
            echo "" | tee -a "$LOG_FILE"
            echo "========================================" | tee -a "$LOG_FILE"
            echo "[$TIMESTAMP] [警告] 进程已终止!" | tee -a "$LOG_FILE"
            echo "之前的PID: $LAST_PIDS" | tee -a "$LOG_FILE"
            echo "========================================" | tee -a "$LOG_FILE"

            # 检查OOM Killer日志
            echo "" | tee -a "$LOG_FILE"
            echo "[检查OOM Killer日志]" | tee -a "$LOG_FILE"

            # 尝试读取dmesg (可能需要权限)
            OOM_LOG=$(dmesg 2>/dev/null | grep -i "killed process" | tail -5)
            if [ -n "$OOM_LOG" ]; then
                echo "$OOM_LOG" | tee -a "$LOG_FILE"
            else
                echo "无法读取dmesg (可能需要sudo权限)" | tee -a "$LOG_FILE"
            fi

            # 检查journalctl
            echo "" | tee -a "$LOG_FILE"
            echo "[检查系统日志]" | tee -a "$LOG_FILE"
            JOURNAL_LOG=$(journalctl --since "5 minutes ago" 2>/dev/null | grep -iE "killed|oom|out of memory" | tail -10)
            if [ -n "$JOURNAL_LOG" ]; then
                echo "$JOURNAL_LOG" | tee -a "$LOG_FILE"
            else
                echo "未发现OOM相关日志 (或无权限查看)" | tee -a "$LOG_FILE"
            fi

            # 记录当前内存状态
            echo "" | tee -a "$LOG_FILE"
            echo "[当前内存状态]" | tee -a "$LOG_FILE"
            free -h | tee -a "$LOG_FILE"

            # 记录系统负载
            echo "" | tee -a "$LOG_FILE"
            echo "[系统负载]" | tee -a "$LOG_FILE"
            uptime | tee -a "$LOG_FILE"

            # 检查是否有core dump
            echo "" | tee -a "$LOG_FILE"
            echo "[检查Core Dump]" | tee -a "$LOG_FILE"
            CORE_FILES=$(find /tmp -name "core.*" -mmin -5 2>/dev/null)
            if [ -n "$CORE_FILES" ]; then
                echo "发现Core Dump文件:" | tee -a "$LOG_FILE"
                echo "$CORE_FILES" | tee -a "$LOG_FILE"
            else
                echo "未发现最近的Core Dump文件" | tee -a "$LOG_FILE"
            fi

            echo "========================================" | tee -a "$LOG_FILE"
            echo "" | tee -a "$LOG_FILE"
        else
            echo "[$TIMESTAMP] 没有匹配的进程运行中" | tee -a "$LOG_FILE"
        fi
    fi

    # 每5分钟记录一次系统状态
    MINUTE=$(date +%M)
    if [ $((MINUTE % 5)) -eq 0 ] && [ $(($(date +%S) < $INTERVAL)) ]; then
        echo "" >> "$LOG_FILE"
        echo "[$TIMESTAMP] [系统状态] $MEM_INFO | $SWAP_INFO | Load:$LOAD" >> "$LOG_FILE"
    fi

    LAST_PIDS="$CURRENT_PIDS"
    sleep $INTERVAL
done
