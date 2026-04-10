"""
config/settings.py — Single source of truth for all runtime configuration.
All values can be overridden via environment variables.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ModelConfig:
    name: str = os.getenv("GEMMACORE_MODEL", "gemma3:4b")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    temperature: float = float(os.getenv("GEMMACORE_TEMPERATURE", "0.7"))
    num_ctx: int = int(os.getenv("GEMMACORE_CTX", "4096"))
    max_retries: int = int(os.getenv("GEMMACORE_RETRIES", "3"))
    retry_delay: float = float(os.getenv("GEMMACORE_RETRY_DELAY", "3.0"))


@dataclass
class MemoryConfig:
    path: str = os.getenv("GEMMACORE_MEMORY_PATH", "./data/memory_db")
    short_term_capacity: int = int(os.getenv("GEMMACORE_STM_CAPACITY", "20"))
    episodic_max_entries: int = int(os.getenv("GEMMACORE_EPISODIC_MAX", "500"))
    semantic_top_k: int = int(os.getenv("GEMMACORE_SEMANTIC_K", "5"))
    long_term_enabled: bool = os.getenv("GEMMACORE_LTM", "false").lower() == "true"


@dataclass
class PersonalityDefaults:
    curiosity: float = 1.0
    risk_tolerance: float = 0.40
    persistence: float = 0.80
    verbosity: float = 0.60
    skepticism: float = 0.50


@dataclass
class SkillPermissions:
    """Permission levels: 0=free, 1=notify, 2=require_approval"""
    file_read: int = 0
    file_write: int = 2
    memory_read: int = 0
    memory_write: int = 0
    academic_search: int = 2


@dataclass
class AgentConfig:
    max_iterations: int = int(os.getenv("GEMMACORE_MAX_ITER", "10"))
    headless_browser: bool = os.getenv("GEMMACORE_HEADLESS", "true").lower() == "true"
    require_approval: bool = os.getenv("GEMMACORE_APPROVAL", "true").lower() == "true"
    context_window_limit: int = int(os.getenv("GEMMACORE_WINDOW_LIMIT", "8000"))
    log_path: str = os.getenv("GEMMACORE_LOG_PATH", "./data/logs/agent.log")
    trace_path: str = os.getenv("GEMMACORE_TRACE_PATH", "./data/logs/trace.jsonl")
    workspace_path: str = os.getenv("GEMMACORE_WORKSPACE", "./workspace")


@dataclass
class Settings:
    model: ModelConfig = field(default_factory=ModelConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    personality: PersonalityDefaults = field(default_factory=PersonalityDefaults)
    permissions: SkillPermissions = field(default_factory=SkillPermissions)
    agent: AgentConfig = field(default_factory=AgentConfig)


# Global singleton — import this everywhere
settings = Settings()
