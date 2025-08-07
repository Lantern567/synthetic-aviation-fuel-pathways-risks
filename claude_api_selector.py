#!/usr/bin/env python3
"""
Claude Code API 配置选择器
允许用户在启动时选择不同的API端点和密钥
"""

import json
import os
import sys
import subprocess
from pathlib import Path
import winreg

# API配置选项
API_CONFIGS = {
    "1": {
        "name": "GAC Code (当前)",
        "api_url": "https://gaccode.com/claudecode",
        "api_key": "sk-ant-oat01-8b1b9779ff075b50b427361ba2e227e765e59768ddeb8bc6276f651e31431005"
    },
    "2": {
        "name": "CC Vibe Coding",
        "api_url": "https://cc-vibecoding.vip/claudecode",
        "api_key": "sk-ccvb-code-sSWj-PanrM9XJTgNpLY7KKRQoVjPmOGTifGjcWzrAft-CjtWhTy1IxvHtoJpgRbATM9CzYOWkVmbk7e3NjwlIw"
    }
}

def get_claude_config_path():
    """获取Claude配置文件路径"""
    home = Path.home()
    config_path = home / ".claude.json"
    
    # 检查CLAUDE_CONFIG_DIR环境变量
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        config_path = Path(config_dir) / ".claude.json"
    
    return config_path

def load_current_config():
    """加载当前Claude配置"""
    config_path = get_claude_config_path()
    
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"警告：无法读取配置文件 {config_path}: {e}")
        return {}

def save_config(config):
    """保存Claude配置"""
    config_path = get_claude_config_path()
    
    # 确保配置目录存在
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"配置已保存到: {config_path}")
        return True
    except IOError as e:
        print(f"错误：无法保存配置文件: {e}")
        return False

def display_menu():
    """显示API选择菜单"""
    print("\n" + "="*50)
    print("Claude Code API 端点选择器")
    print("="*50)
    print()
    
    for key, config in API_CONFIGS.items():
        print(f"{key}. {config['name']}")
        print(f"   URL: {config['api_url']}")
        print(f"   密钥: {config['api_key'][:20]}...")
        print()
    
    print("0. 退出不修改")
    print()

def get_user_choice():
    """获取用户选择"""
    while True:
        choice = input("请选择API配置 (0-2): ").strip()
        
        if choice == "0":
            return None
        elif choice in API_CONFIGS:
            return choice
        else:
            print("无效选择，请输入 0-2")

def set_environment_variable_windows(name, value):
    """在Windows系统中设置持久化环境变量"""
    try:
        # 打开当前用户环境变量注册表项
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
        
        # 设置环境变量
        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
        
        # 关闭注册表项
        winreg.CloseKey(key)
        
        # 通知系统环境变量已更改
        import ctypes
        from ctypes import wintypes
        
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        
        result = ctypes.c_long()
        SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
        SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))
        
        return True
    except Exception as e:
        print(f"设置Windows环境变量失败: {e}")
        return False

def set_environment_variable_unix(name, value):
    """在Unix/Linux系统中设置环境变量到shell配置文件"""
    try:
        home = Path.home()
        shell_configs = [
            home / ".bashrc",
            home / ".zshrc", 
            home / ".profile"
        ]
        
        env_line = f'export {name}="{value}"\n'
        
        # 尝试找到存在的shell配置文件
        config_file = None
        for config in shell_configs:
            if config.exists():
                config_file = config
                break
        
        # 如果没有找到，创建.bashrc
        if not config_file:
            config_file = home / ".bashrc"
        
        # 读取现有内容
        existing_lines = []
        if config_file.exists():
            with open(config_file, 'r') as f:
                existing_lines = f.readlines()
        
        # 检查是否已存在该环境变量
        var_exists = False
        for i, line in enumerate(existing_lines):
            if line.strip().startswith(f'export {name}='):
                existing_lines[i] = env_line
                var_exists = True
                break
        
        # 如果不存在，添加到末尾
        if not var_exists:
            existing_lines.append(env_line)
        
        # 写回文件
        with open(config_file, 'w') as f:
            f.writelines(existing_lines)
        
        print(f"已将环境变量添加到: {config_file}")
        print(f"请重新启动终端或运行: source {config_file}")
        
        return True
    except Exception as e:
        print(f"设置Unix环境变量失败: {e}")
        return False

def set_persistent_environment_variable(name, value):
    """设置持久化环境变量"""
    if sys.platform == "win32":
        return set_environment_variable_windows(name, value)
    else:
        return set_environment_variable_unix(name, value)

def update_api_config(choice):
    """更新API配置"""
    if choice is None:
        print("未修改配置，退出。")
        return False
    
    selected_config = API_CONFIGS[choice]
    
    # 加载当前配置
    current_config = load_current_config()
    
    # 更新API URL
    current_config["customApiUrl"] = selected_config["api_url"]
    
    # 保存配置
    if save_config(current_config):
        print(f"\n✅ 已切换到: {selected_config['name']}")
        print(f"API URL: {selected_config['api_url']}")
        
        # 设置当前进程环境变量
        os.environ["ANTHROPIC_API_KEY"] = selected_config["api_key"]
        os.environ["ANTHROPIC_BASE_URL"] = selected_config["api_url"]
        
        # 设置持久化环境变量
        print("正在设置持久化环境变量...")
        api_key_success = set_persistent_environment_variable("ANTHROPIC_API_KEY", selected_config["api_key"])
        base_url_success = set_persistent_environment_variable("ANTHROPIC_BASE_URL", selected_config["api_url"])
        
        if api_key_success and base_url_success:
            print("✅ 环境变量已持久化设置")
        else:
            print("⚠️ 部分环境变量设置失败，但当前会话仍可使用")
        
        return True
    
    return False

def launch_claude_code():
    """启动Claude Code"""
    print("\n正在启动 Claude Code...")
    
    try:
        # 在Windows上启动Claude Code
        if sys.platform == "win32":
            subprocess.run(["claude"], check=True)
        else:
            subprocess.run(["claude"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"启动Claude Code失败: {e}")
    except FileNotFoundError:
        print("未找到 'claude' 命令，请确保Claude Code已正确安装")

def main():
    """主函数"""
    try:
        # 显示菜单
        display_menu()
        
        # 获取用户选择
        choice = get_user_choice()
        
        # 更新配置
        if update_api_config(choice):
            # 询问是否启动Claude Code
            launch_choice = input("\n是否现在启动 Claude Code? (y/N): ").strip().lower()
            if launch_choice in ['y', 'yes', '是']:
                # 设置API密钥和基础URL环境变量
                if choice:
                    selected_config = API_CONFIGS[choice]
                    os.environ["ANTHROPIC_API_KEY"] = selected_config["api_key"]
                    os.environ["ANTHROPIC_BASE_URL"] = selected_config["api_url"]
                
                launch_claude_code()
    
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()