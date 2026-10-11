"""Small, explicit configuration for the AXON API."""

from dataclasses import dataclass
import os
from typing import Literal, cast

Environment = Literal["development", "test", "production"]
_VALID_ENVIRONMENTS = {"development", "test", "production"}


@dataclass(frozen=True)
class Settings:
    """Application settings sourced from non-secret process environment."""

    environment: Environment = "development"

    @classmethod
    def from_env(cls) -> "Settings":
        value = os.getenv("AXON_ENV", "development").strip().lower()
        if value not in _VALID_ENVIRONMENTS:
            allowed = ", ".join(sorted(_VALID_ENVIRONMENTS))
            raise ValueError(f"AXON_ENV must be one of: {allowed}")
        return cls(environment=cast(Environment, value))
