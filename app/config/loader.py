import os
import yaml


class ConfigLoader:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_yaml_config()

    def load_yaml_config(self):
        """Load the YAML configuration file."""
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)

    def override_with_env_variables(self, config, prefix=''):
        """Recursively override configuration with environment variables if they exist."""
        if isinstance(config, dict):
            for key, value in config.items():
                env_key = f"{prefix}{key}".upper()
                if isinstance(value, dict):
                    self.override_with_env_variables(value, prefix=env_key + '_')
                else:
                    env_value = os.environ.get(env_key)
                    if env_value is not None:
                        config[key] = self.convert_type(env_value, type(value))
        return config

    @staticmethod
    def convert_type(value, original_type):
        """Convert the value to the original type."""
        try:
            if original_type is bool:
                return value.lower() in {"true", "1", "t", "y", "yes", "True", "T"}
            elif original_type is list:
                return [v.strip() for v in value.split(',')]
            else:
                return original_type(value)
        except ValueError:
            return value

    def get_config(self):
        """Get the combined configuration."""
        return self.override_with_env_variables(self.config)
