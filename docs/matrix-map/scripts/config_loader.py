"""
配置加载器 — 所有脚本共享

优先级（高到低）：
  1. CLI 参数（--url, --token, --env 等）
  2. 环境变量（MATRIX_URL / token_env 指定的变量 / 等）
  3. config.local.yaml (gitignored)
  4. config.yaml (committed default)
  5. 硬编码兜底

密钥处理：
  - 绝不从 yaml 读 token
  - token 只从 environments.{env}.token_env 指定的环境变量读
  - 读不到就报错退出
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.yaml"
CONFIG_LOCAL_FILE = ROOT / "config.local.yaml"


@dataclass
class EnvConfig:
    name: str
    url: str
    token: str              # 实际值（从 env var 读出来）
    caller_id: str
    timeout_sec: int


@dataclass
class Config:
    env: EnvConfig
    api_endpoints: dict
    sync: dict
    validate: dict
    output: dict
    root: Path


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并，override 胜。"""
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        print(f"[ERROR] 解析失败 {path.name}: {e}", file=sys.stderr)
        sys.exit(3)


def load(
    env_name: Optional[str] = None,
    url_override: Optional[str] = None,
    token_override: Optional[str] = None,
    caller_override: Optional[str] = None,
    require_token: bool = True,
) -> Config:
    """
    加载配置。

    Args:
        env_name: 指定环境（test/prod/local）。None 用 default_env。
        url_override: 直接覆盖 URL（CLI --url）
        token_override: 直接覆盖 token（CLI --token，不推荐，建议用 env）
        caller_override: 覆盖 X-Caller-ID
        require_token: 是否强制要 token（validate/build 不调 API，可传 False）
    """
    if not CONFIG_FILE.exists():
        print(f"[ERROR] 缺少 {CONFIG_FILE.name}", file=sys.stderr)
        sys.exit(3)

    base = _load_yaml(CONFIG_FILE)
    local = _load_yaml(CONFIG_LOCAL_FILE)
    cfg = _deep_merge(base, local)

    # 选环境
    envs = cfg.get("environments", {})
    chosen = env_name or os.environ.get("MATRIX_ENV") or cfg.get("default_env", "test")
    if chosen not in envs:
        print(
            f"[ERROR] 环境 '{chosen}' 未定义。可选: {sorted(envs.keys())}",
            file=sys.stderr,
        )
        sys.exit(3)
    env_cfg = envs[chosen]

    # URL：CLI > MATRIX_URL env > config
    url = (
        url_override
        or os.environ.get("MATRIX_URL")
        or env_cfg.get("url")
    )
    if not url:
        print(f"[ERROR] 环境 {chosen} 缺 url", file=sys.stderr)
        sys.exit(3)

    # Token：CLI > 通用 MATRIX_TOKEN env > 环境指定的 token_env
    token_env_name = env_cfg.get("token_env", "MATRIX_TOKEN")
    token = (
        token_override
        or os.environ.get("MATRIX_TOKEN")
        or os.environ.get(token_env_name, "")
    )
    if not token and require_token:
        print(
            f"[ERROR] 缺 token。设置环境变量 {token_env_name} 或 MATRIX_TOKEN",
            file=sys.stderr,
        )
        sys.exit(3)

    # Caller
    caller = (
        caller_override
        or os.environ.get("MATRIX_CALLER_ID")
        or env_cfg.get("caller_id", "map-sync")
    )

    # Timeout
    timeout = int(
        os.environ.get("MATRIX_TIMEOUT", env_cfg.get("timeout_sec", 15))
    )

    return Config(
        env=EnvConfig(
            name=chosen,
            url=url.rstrip("/"),
            token=token,
            caller_id=caller,
            timeout_sec=timeout,
        ),
        api_endpoints=cfg.get("api_endpoints", {}),
        sync=cfg.get("sync", {}),
        validate=cfg.get("validate", {}),
        output=cfg.get("output", {}),
        root=ROOT,
    )


def print_env(cfg: Config) -> None:
    """打印当前用的环境（不打 token）。"""
    print(f"[env={cfg.env.name}] url={cfg.env.url} caller={cfg.env.caller_id} timeout={cfg.env.timeout_sec}s")
