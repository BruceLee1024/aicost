from pydantic import BaseModel, Field


class AIProviderConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class AIProvidersConfig(BaseModel):
    deepseek: AIProviderConfig = Field(default_factory=AIProviderConfig)
    qwen: AIProviderConfig = Field(default_factory=AIProviderConfig)
    kimi: AIProviderConfig = Field(default_factory=AIProviderConfig)
    glm: AIProviderConfig = Field(default_factory=AIProviderConfig)
    openai: AIProviderConfig = Field(default_factory=AIProviderConfig)


class AISettingsPayload(BaseModel):
    provider: str = "disabled"
    timeout_seconds: float = 20.0
    enable_audit_logs: bool = False
    providers: AIProvidersConfig = Field(default_factory=AIProvidersConfig)
