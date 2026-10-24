"""Global configuration for RouteRescue AI."""

import os
from pathlib import Path
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "routerescue.db"


class AgentConfig(BaseModel):
    """Configuration for an individual Fetch.ai uAgent."""
    name: str
    seed: str
    port: int
    endpoint: str = "http://127.0.0.1"
    mailbox_key: str | None = None


class SystemSettings(BaseModel):
    """System-wide configuration settings."""
    environment: str = Field(default="development")
    db_path: Path = Field(default=DEFAULT_DB_PATH)
    log_level: str = Field(default="INFO")

    # Bureau host & port for multi-agent local runner
    bureau_port: int = 8000
    bureau_endpoint: str = "http://127.0.0.1:8000/submit"

    # Agent configs
    planner_agent: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            name="recovery_planner_agent",
            seed="routerescue_planner_recovery_seed_phrase_v1",
            port=8001,
        )
    )
    monitor_agent: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            name="disruption_monitor_agent",
            seed="routerescue_monitor_disruption_seed_phrase_v1",
            port=8002,
        )
    )
    rail_agent: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            name="rail_search_agent",
            seed="routerescue_rail_search_seed_phrase_v1",
            port=8003,
        )
    )
    bus_agent: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            name="bus_search_agent",
            seed="routerescue_bus_search_seed_phrase_v1",
            port=8004,
        )
    )
    cab_road_agent: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            name="cab_road_agent",
            seed="routerescue_cab_road_seed_phrase_v1",
            port=8005,
        )
    )

    # API & Dashboard
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    streamlit_port: int = 8501

    # Safety & Human-in-the-loop
    require_user_approval_for_booking: bool = True
    distinguish_verified_vs_simulated: bool = True


settings = SystemSettings()
