
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    YamlConfigSettingsSource,
    PydanticBaseSettingsSource,
)
from typing import Type, Tuple


class Settings(BaseSettings):

    GEMINI_API_KEY: str

    model_config = SettingsConfigDict(
        yaml_file="backend/settings.yaml", yaml_file_encoding="utf-8"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Customize the settings sources and their priority order.

        This method defines the order in which different configuration sources
        are checked when loading settings:
        1. Constructor-provided values
        2. YAML configuration file
        3. Environment variables

        Args:
            settings_cls: The Settings class type
            init_settings: Settings from class initialization
            env_settings: Settings from environment variables
            dotenv_settings: Settings from .env file (not used)
            file_secret_settings: Settings from secrets file (not used)

        Returns:
            A tuple of configuration sources in priority order
        """
        return (
            init_settings,  # First, try init_settings (from constructor)
            YamlConfigSettingsSource(settings_cls),  # Then, try YAML
            env_settings,  # Finally, try environment variables
        )


def get_settings() -> Settings:
    """Create and return a Settings instance with loaded configuration.

    Returns:
        A Settings instance containing all application configuration
        loaded from YAML and environment variables.
    """
    return Settings()
