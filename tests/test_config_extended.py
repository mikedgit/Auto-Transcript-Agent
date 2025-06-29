"""Extended tests for configuration management to improve coverage."""

from pathlib import Path
import pytest
import logging

from src.config import (
    Config,
    load_config,
    ConfigError,
    setup_logging,
    validate_directories,
    create_sample_config,
    get_default_config_path,
)


class TestConfigExtended:
    """Extended tests for Config class covering edge cases."""

    def test_config_validation_errors(self, tmp_path):
        """Test various configuration validation errors."""
        # Test invalid directory creation
        with pytest.raises(ValueError, match="Cannot create directory"):
            Config(
                assemblyai_api_key="test_key",
                input_dir=Path("/root/restricted_dir"),  # Likely to fail
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
            )

    def test_config_invalid_log_level(self, tmp_path):
        """Test invalid log level validation."""
        with pytest.raises(ValueError, match="Invalid log level"):
            Config(
                assemblyai_api_key="test_key",
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
                log_level="INVALID",
            )

    def test_config_negative_values(self, tmp_path):
        """Test negative values validation."""
        with pytest.raises(ValueError, match="POLL_INTERVAL must be positive"):
            Config(
                assemblyai_api_key="test_key",
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
                poll_interval=-1,
            )

        with pytest.raises(ValueError, match="MAX_RETRIES must be at least 1"):
            Config(
                assemblyai_api_key="test_key",
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
                max_retries=0,
            )

        with pytest.raises(ValueError, match="RETRY_DELAY must be non-negative"):
            Config(
                assemblyai_api_key="test_key",
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
                retry_delay=-5,
            )


class TestLoadConfigExtended:
    """Extended tests for load_config function."""

    def test_load_config_value_error(self, tmp_path):
        """Test ValueError handling in load_config."""
        env_file = tmp_path / ".env"
        env_content = f"""
ASSEMBLYAI_API_KEY=test_key
INPUT_DIR={tmp_path}/input
OUTPUT_DIR={tmp_path}/output
DONE_DIR={tmp_path}/done
POLL_INTERVAL=invalid_number
"""
        env_file.write_text(env_content)

        with pytest.raises(ConfigError, match="Configuration validation failed"):
            load_config(env_file)

    def test_load_config_exception_handling(self, tmp_path):
        """Test general exception handling in load_config."""
        # Create a file that will cause an exception when reading
        env_file = tmp_path / ".env"
        env_file.write_text("ASSEMBLYAI_API_KEY=test_key\nINPUT_DIR=")  # Incomplete

        with pytest.raises(ConfigError, match="Failed to load configuration"):
            load_config(env_file)

    def test_load_config_missing_dirs(self, tmp_path):
        """Test missing directory variables."""
        env_file = tmp_path / ".env"

        # Missing INPUT_DIR
        env_file.write_text("ASSEMBLYAI_API_KEY=test_key\n")
        with pytest.raises(
            ConfigError, match="INPUT_DIR environment variable is required"
        ):
            load_config(env_file)

        # Missing OUTPUT_DIR
        env_file.write_text(
            f"ASSEMBLYAI_API_KEY=test_key\nINPUT_DIR={tmp_path}/input\n"
        )
        with pytest.raises(
            ConfigError, match="OUTPUT_DIR environment variable is required"
        ):
            load_config(env_file)

        # Missing DONE_DIR
        env_file.write_text(
            f"ASSEMBLYAI_API_KEY=test_key\nINPUT_DIR={tmp_path}/input\nOUTPUT_DIR={tmp_path}/output\n"
        )
        with pytest.raises(
            ConfigError, match="DONE_DIR environment variable is required"
        ):
            load_config(env_file)


class TestSetupLoggingExtended:
    """Extended tests for setup_logging function."""

    def test_setup_logging_file_error(self, tmp_path):
        """Test file logging setup with errors."""
        # Try to create log file in non-existent directory with permission issues
        config = Config(
            assemblyai_api_key="test_key",
            log_level="DEBUG",
            log_file=Path("/root/restricted/test.log"),  # Likely to fail
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        # Should not raise exception, just warn
        setup_logging(config)

    def test_setup_logging_different_levels(self, tmp_path):
        """Test setup logging with different log levels."""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in log_levels:
            config = Config(
                assemblyai_api_key="test_key",
                log_level=level,
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
            )

            setup_logging(config)

            # Verify logging level was set
            assert logging.getLogger().level == getattr(logging, level)


class TestValidateDirectories:
    """Test directory validation function."""

    def test_validate_directories_success(self, tmp_path):
        """Test successful directory validation."""
        config = Config(
            assemblyai_api_key="test_key",
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        # Should not raise exception
        validate_directories(config)

    def test_validate_directories_missing_input(self, tmp_path):
        """Test validation with missing input directory."""
        config = Config(
            assemblyai_api_key="test_key",
            input_dir=tmp_path / "nonexistent",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        with pytest.raises(ConfigError, match="Directory validation failed"):
            validate_directories(config)

    def test_validate_directories_file_as_dir(self, tmp_path):
        """Test validation when a file exists where directory should be."""
        # Create a file where input directory should be
        file_path = tmp_path / "input"
        file_path.write_text("this is a file")

        config = Config(
            assemblyai_api_key="test_key",
            input_dir=file_path,
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        with pytest.raises(ConfigError, match="Input path is not a directory"):
            validate_directories(config)


class TestUtilityFunctions:
    """Test utility functions for configuration."""

    def test_get_default_config_path(self):
        """Test getting default config path."""
        path = get_default_config_path()
        assert path.name == ".env"
        assert path.is_absolute()

    def test_create_sample_config(self, tmp_path):
        """Test creating sample configuration."""
        config_path = tmp_path / "test.env"
        create_sample_config(config_path)

        assert config_path.exists()
        content = config_path.read_text()
        assert "ASSEMBLYAI_API_KEY" in content
        assert "INPUT_DIR" in content
        assert "OUTPUT_DIR" in content
        assert "DONE_DIR" in content

    def test_create_sample_config_default_path(self, tmp_path, monkeypatch):
        """Test creating sample config at default path."""
        # Change working directory to temp path
        monkeypatch.chdir(tmp_path)

        create_sample_config()

        default_path = tmp_path / ".env"
        assert default_path.exists()
        content = default_path.read_text()
        assert "ASSEMBLYAI_API_KEY" in content
