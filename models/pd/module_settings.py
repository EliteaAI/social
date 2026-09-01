from typing import Optional
from pydantic.v1 import BaseModel


class ModuleSettingsModel(BaseModel):
    default_internal_mcp_enabled: Optional[bool] = None
    default_skill_builder_enabled: Optional[bool] = None
    default_project_context_builder_enabled: Optional[bool] = None
    default_ask_user_enabled: Optional[bool] = None
    default_image_generation_enabled: Optional[bool] = None
    default_data_analysis_enabled: Optional[bool] = None
    default_planner_enabled: Optional[bool] = None
    default_pyodide_enabled: Optional[bool] = None
    default_swarm_enabled: Optional[bool] = None
    default_lazy_tools_mode_enabled: Optional[bool] = None
    default_agent_internal_mcp_enabled: Optional[bool] = None
    default_agent_skill_builder_enabled: Optional[bool] = None
    default_agent_project_context_builder_enabled: Optional[bool] = None
    default_agent_ask_user_enabled: Optional[bool] = None
    default_agent_image_generation_enabled: Optional[bool] = None
    default_agent_data_analysis_enabled: Optional[bool] = None
    default_agent_planner_enabled: Optional[bool] = None
    default_agent_pyodide_enabled: Optional[bool] = None
    default_agent_swarm_enabled: Optional[bool] = None
    default_agent_lazy_tools_mode_enabled: Optional[bool] = None

    class Config:
        orm_mode = True
