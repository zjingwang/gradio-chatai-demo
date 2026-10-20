# -*- coding: utf-8 -*-
"""
配置文件读写模块 (config.json)
=============================
约定的配置文件在项目根目录: config.json
界面里的「配置」页签与这里每个字段一一对应, 保存即写回该文件。

默认配置 DEFAULT_CONFIG 首次运行时若文件不存在会自动生成。
"""

import copy
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    # ---- 大模型 (LLM) 配置 ----
    "llm": {
        "enabled": False,                    # 是否启用大模型; 关闭时用内置规则回答
        "base_url": "https://api.deepseek.com/v1",  # OpenAI 兼容接口地址
        "api_key": "",                       # API Key
        "model": "deepseek-chat",            # 模型名
        "temperature": 0.7,                  # 采样温度 0~2
        "max_tokens": 1024,                  # 单次回复最大 token 数
        "system_prompt": "你是一个乐于助人的智能助手，请用简体中文回答。",
    },
    # ---- 界面 / 启动配置 ----
    "ui": {
        "theme": "Soft",                     # 主题: Soft/Default/Monochrome/Glass/Ocean/Cyberpunk
        "server_port": 7860,                 # 启动端口 (被占用时自动顺延)
    },
}

# 内存中的当前配置; 启动时从文件加载
_config = None


def _deep_merge(base, override):
    """把 override 合并进 base (支持嵌套 dict); 新字段以 base 默认值为准。"""
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def read_config():
    """总是从磁盘读取一份最新配置 (以文件为准), 不做缓存。"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return _deep_merge(DEFAULT_CONFIG, json.load(f))
        except Exception as exc:
            print(f"[config] 读取 {CONFIG_PATH} 失败: {exc}, 使用默认配置")
            return copy.deepcopy(DEFAULT_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG)


def load_config():
    """启动时从 config.json 载入 (文件不存在才生成默认文件)。"""
    global _config
    _config = read_config()
    if not os.path.exists(CONFIG_PATH):
        save_config(_config)
    return _config


def reload_config():
    """重新从磁盘读取并以新值作为运行期配置。"""
    global _config
    _config = read_config()
    return _config


def save_config(cfg):
    """把配置写回 config.json, 返回文件路径。"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        raise RuntimeError(f"写入配置文件失败: {exc}") from exc
    return CONFIG_PATH


def get_config():
    """返回当前配置 dict (内存); 未加载时先加载。"""
    global _config
    if _config is None:
        load_config()
    return _config
