"""Tests for configuration management."""

from pathlib import Path
import pytest

from src.config import Config, load_config, ConfigError, setup_logging


class TestConfig:
    """Test the Config dataclass."""

    def test_valid_config(self, tmp_path):
        """Test creating a valid configuration."""
        config = Config(
            assemblyai_api_key="test_key_123",
            speech_model="best",
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        assert config.assemblyai_api_key == "test_key_123"
        assert config.speech_model == "best"
        assert config.poll_interval == 5  # default
        assert config.max_retries == 3  # default

        # Directories should be created during validation
        assert config.input_dir.exists()
        assert config.output_dir.exists()
        assert config.done_dir.exists()

    def test_invalid_api_key(self, tmp_path):
        """Test that invalid API keys are rejected."""
        with pytest.raises(ValueError, match="ASSEMBLYAI_API_KEY must be set"):
            Config(
                assemblyai_api_key="your_api_key_here",
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
            )

        with pytest.raises(ValueError, match="ASSEMBLYAI_API_KEY must be set"):
            Config(
                assemblyai_api_key="",
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
            )

    def test_invalid_speech_model(self, tmp_path):
        """Test that invalid speech models are rejected."""
        with pytest.raises(ValueError, match="Invalid speech model"):
            Config(
                assemblyai_api_key="test_key",
                speech_model="invalid_model",
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
            )

    def test_invalid_poll_interval(self, tmp_path):
        """Test that invalid poll intervals are rejected."""
        with pytest.raises(ValueError, match="POLL_INTERVAL must be positive"):
            Config(
                assemblyai_api_key="test_key",
                poll_interval=0,
                input_dir=tmp_path / "input",
                output_dir=tmp_path / "output",
                done_dir=tmp_path / "done",
            )

    def test_config_to_dict(self, tmp_path):
        """Test converting config to dictionary."""
        config = Config(
            assemblyai_api_key="test_key_123",
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        config_dict = config.to_dict()

        # API key should be redacted
        assert config_dict["assemblyai_api_key"] == "***REDACTED***"
        assert config_dict["speech_model"] == "best"
        assert config_dict["input_dir"] == str(tmp_path / "input")


class TestLoadConfig:
    """Test the load_config function."""

    def test_load_from_env_file(self, tmp_path):
        """Test loading configuration from .env file."""
        # Create a test .env file
        env_file = tmp_path / ".env"
        env_content = f"""
ASSEMBLYAI_API_KEY=test_api_key_123
SPEECH_MODEL=nano
INPUT_DIR={tmp_path}/input
OUTPUT_DIR={tmp_path}/output
DONE_DIR={tmp_path}/done
POLL_INTERVAL=10
MAX_RETRIES=5
LOG_LEVEL=DEBUG
"""
        env_file.write_text(env_content)

        config = load_config(env_file)

        assert config.assemblyai_api_key == "test_api_key_123"
        assert config.speech_model == "nano"
        assert config.input_dir == tmp_path / "input"
        assert config.poll_interval == 10
        assert config.max_retries == 5
        assert config.log_level == "DEBUG"

    def test_missing_required_env_vars(self, tmp_path):
        """Test that missing required environment variables raise ConfigError."""
        env_file = tmp_path / ".env"
        env_file.write_text("SPEECH_MODEL=best\n")  # Missing required vars

        # Clear any existing environment variables
        import os

        env_backup = {}
        required_vars = ["ASSEMBLYAI_API_KEY", "INPUT_DIR", "OUTPUT_DIR", "DONE_DIR"]
        for var in required_vars:
            if var in os.environ:
                env_backup[var] = os.environ[var]
                del os.environ[var]

        try:
            with pytest.raises(
                ConfigError, match="ASSEMBLYAI_API_KEY environment variable is required"
            ):
                load_config(env_file)
        finally:
            # Restore environment variables
            for var, value in env_backup.items():
                os.environ[var] = value

    def test_load_with_defaults(self, tmp_path):
        """Test loading with default values."""
        import os

        # Clear environment variables that might interfere
        env_backup = {}
        optional_vars = ["SPEECH_MODEL", "POLL_INTERVAL", "MAX_RETRIES", "LOG_LEVEL"]
        for var in optional_vars:
            if var in os.environ:
                env_backup[var] = os.environ[var]
                del os.environ[var]

        try:
            env_file = tmp_path / ".env"
            env_content = f"""
ASSEMBLYAI_API_KEY=test_key
INPUT_DIR={tmp_path}/input
OUTPUT_DIR={tmp_path}/output
DONE_DIR={tmp_path}/done
"""
            env_file.write_text(env_content)

            config = load_config(env_file)

            # Should use default values
            assert config.speech_model == "best"
            assert config.poll_interval == 5
            assert config.max_retries == 3
            assert config.log_level == "INFO"
        finally:
            # Restore environment variables
            for var, value in env_backup.items():
                os.environ[var] = value

    def test_nonexistent_env_file(self):
        """Test loading when .env file doesn't exist."""
        # Should not raise an exception, just use environment variables
        import os

        nonexistent_file = Path("/tmp/nonexistent_file.env")

        # Set required environment variables
        os.environ["ASSEMBLYAI_API_KEY"] = "test_key"
        os.environ["INPUT_DIR"] = "/tmp/input"
        os.environ["OUTPUT_DIR"] = "/tmp/output"
        os.environ["DONE_DIR"] = "/tmp/done"

        try:
            config = load_config(nonexistent_file)
            assert config.assemblyai_api_key == "test_key"
        finally:
            # Clean up environment variables
            for var in ["ASSEMBLYAI_API_KEY", "INPUT_DIR", "OUTPUT_DIR", "DONE_DIR"]:
                os.environ.pop(var, None)


class TestSetupLogging:
    """Test the setup_logging function."""

    def test_setup_console_logging(self, tmp_path):
        """Test setting up console logging."""
        config = Config(
            assemblyai_api_key="test_key",
            log_level="INFO",
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        # Should not raise an exception
        setup_logging(config)

    def test_setup_file_logging(self, tmp_path):
        """Test setting up file logging."""
        log_file = tmp_path / "test.log"
        config = Config(
            assemblyai_api_key="test_key",
            log_level="DEBUG",
            log_file=log_file,
            input_dir=tmp_path / "input",
            output_dir=tmp_path / "output",
            done_dir=tmp_path / "done",
        )

        setup_logging(config)

        # Log file directory should be created
        assert log_file.parent.exists()
