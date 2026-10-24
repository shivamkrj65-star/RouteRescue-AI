"""Global application settings and constants."""

import os
from datetime import timedelta, timezone
from pathlib import Path
from pydantic import BaseModel, Field

# Project Root Directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Timezone standard for demonstration network (Indian Standard Time: UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


class Settings(BaseModel):
    """Configuration settings for RouteRescue AI."""
    app_name: str = "RouteRescue AI"
    version: str = "0.1.0"
    environment: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Database Path
    db_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "routerescue.db"))
        )
    )

    # API Server
    api_host: str = Field(default_factory=lambda: os.getenv("API_HOST", "127.0.0.1"))
    api_port: int = Field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))

    # Streamlit Frontend
    streamlit_port: int = Field(default_factory=lambda: int(os.getenv("STREAMLIT_PORT", "8501")))

    # Demonstration network metadata
    corridor_region: str = "Northern India (Delhi, Jaipur, Chandigarh, Agra)"
    is_demo_mode: bool = True
    synthetic_label: str = "DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)"


settings = Settings()
