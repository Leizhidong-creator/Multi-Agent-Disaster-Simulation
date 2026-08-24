from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "智演 Agent Demo"
    root_dir: Path = Path(__file__).resolve().parents[2]
    frontend_dir: Path = root_dir / "frontend"
    source_data_dir: Path = root_dir / "智演数据检索" / "rag_documents"
    fire_safety_rules_path: Path = root_dir / "fire_safety_rules.txt"
    chroma_dir: Path = root_dir / ".chroma"

    llm_api_keys: str | None = None
    llm_api_key: str | None = None
    dashscope_api_key: str | None = None
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    llm_timeout_seconds: float = 6.0
    slow_brain_step_timeout_seconds: float = 8.0
    local_llm_base_url: str = "http://localhost:8000/v1"
    local_llm_api_key: str | None = None
    local_llm_model: str = "Qwen2-7B-Instruct"
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"

    @property
    def resolved_llm_api_key(self) -> str | None:
        keys = self.resolved_llm_api_keys
        return keys[0] if keys else None

    @property
    def resolved_llm_api_keys(self) -> list[str]:
        values: list[str] = []
        if self.llm_api_keys:
            normalized = self.llm_api_keys.replace("\r", "\n").replace(",", "\n").replace(" ", "\n")
            values.extend(item.strip() for item in normalized.split("\n") if item.strip())
        if self.llm_api_key:
            values.append(self.llm_api_key.strip())
        if self.dashscope_api_key:
            values.append(self.dashscope_api_key.strip())

        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            unique_values.append(value)
        return unique_values

    @property
    def resolved_llm_base_url(self) -> str:
        return self.llm_base_url.rstrip("/")


settings = Settings()
