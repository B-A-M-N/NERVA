# nerva/config.py
from dataclasses import dataclass, field
from pathlib import Path
import os


def _env_flag(name: str, default: bool) -> bool:
    """Return True/False based on environment variable presence."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Parse int environment variable with fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class NervaConfig:
    """Global configuration for NERVA system."""

    # LLM settings (Ollama direct access)
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    qwen_model: str = field(default_factory=lambda: os.getenv("QWEN_MODEL", "qwen3:4b"))  # Fast text model

    # SOLLOL routing (load balancing and orchestration)
    use_sollol: bool = field(default_factory=lambda: _env_flag("NERVA_USE_SOLLOL", True))
    sollol_base_url: str = field(default_factory=lambda: os.getenv("SOLLOL_BASE_URL", "http://localhost:8000"))
    sollol_model: str = field(default_factory=lambda: os.getenv("SOLLOL_MODEL", "llama3.2"))
    sollol_priority: int = field(default_factory=lambda: _env_int("SOLLOL_PRIORITY", 5))

    # Vision model settings (routed through SOLLOL - it will auto-route to nodes with the model)
    qwen_vision_model: str = field(default_factory=lambda: os.getenv("QWEN_VISION_MODEL", "qwen3-vl:4b"))
    vision_timeout: int = field(default_factory=lambda: _env_int("VISION_TIMEOUT", 300))  # 5 min for slow vision models

    # Paths
    repos_root: Path = Path.home() / "projects"
    memory_db_path: Path = Path.home() / ".nerva" / "memory.db"
    logs_path: Path = Path.home() / ".nerva" / "logs"

    # Voice settings
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "medium"))
    kokoro_model: str = field(default_factory=lambda: os.getenv("KOKORO_MODEL", "kokoro-82m"))

    # Screen capture
    screenshot_interval: int = field(default_factory=lambda: _env_int("SCREENSHOT_INTERVAL", 30))

    # Daily ops
    daily_ops_hour: int = field(default_factory=lambda: _env_int("DAILY_OPS_HOUR", 9))

    def __post_init__(self) -> None:
        """Ensure required directories exist."""
        self.memory_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)
