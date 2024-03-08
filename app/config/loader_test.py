import unittest
import os

from .loader import ConfigLoader


class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        """Set up test environment variables and the path to the test config file."""
        os.environ['CONN_REDIS_HOST'] = '192.168.1.1'
        os.environ['CONN_SQL_PASSWORD'] = 'newpassword'
        os.environ['SERVER_PORT'] = '9999'
        os.environ['CONN_REDIS_PORT'] = '6380'
        self.config_path = '../config/config.yaml'

    def tearDown(self):
        """Clean up environment variables after tests."""
        del os.environ['CONN_REDIS_HOST']
        del os.environ['CONN_SQL_PASSWORD']
        del os.environ['SERVER_PORT']
        del os.environ['CONN_REDIS_PORT']

    def test_load_config(self):
        """Test loading the YAML configuration without overrides."""
        config_loader = ConfigLoader(self.config_path)
        config = config_loader.load_yaml_config()
        print(config)
        self.assertIn('conn', config)
        self.assertIn('server', config)

    def test_override_with_env_variables(self):
        """Test overriding configuration with environment variables."""
        config_loader = ConfigLoader(self.config_path)
        combined_config = config_loader.get_config()

        # Test specific overrides
        self.assertEqual(combined_config['conn']['redis']['host'], '192.168.1.1')
        self.assertEqual(combined_config['conn']['sql']['password'], 'newpassword')
        self.assertEqual(combined_config['server']['port'], 9999)  # Testing type conversion
        self.assertEqual(combined_config['conn']['redis']['port'], ['6380'])  # Testing list conversion

    def test_type_conversion(self):
        """Test correct type conversion for environment variables."""
        # This could be part of test_override_with_env_variables but separated here for clarity
        config_loader = ConfigLoader(self.config_path)
        combined_config = config_loader.get_config()

        # Ensure types are correctly converted
        self.assertIsInstance(combined_config['server']['port'], int)
        self.assertIsInstance(combined_config['conn']['redis']['port'], list)


if __name__ == '__main__':
    unittest.main()
