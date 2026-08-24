import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=1)
def load_itaewon_parameters() -> dict[str, Any]:
    return _read_json(settings.source_data_dir / "itaewon_accident_parameters.json")


@lru_cache(maxsize=1)
def load_fire_code_chunks() -> dict[str, Any]:
    return _read_json(settings.source_data_dir / "gb50016_fire_code_chunks.json")
