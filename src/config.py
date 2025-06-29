"""Configuration management for Auto-Transcript-Agent."""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration settings for the Auto-Transcript-Agent."""

    # AssemblyAI Configuration
    assemblyai_api_key: str

    # Directory Configuration
    input_dir: Path
    output_dir: Path
    done_dir: Path

    # Optional configuration with defaults
    speech_model: str = "best"

    # Service Configuration
    poll_interval: int = 5
    max_retries: int = 3
    retry_delay: int = 60

    # Logging Configuration
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate configuration settings."""
        # Validate API key
        if (
            not self.assemblyai_api_key
            or self.assemblyai_api_key == "your_api_key_here"
        ):
            raise ValueError("ASSEMBLYAI_API_KEY must be set to a valid API key")

        # Validate speech model
        if self.speech_model not in ["best", "nano"]:
            raise ValueError(
                f"Invalid speech model: {self.speech_model}. Must be 'best' or 'nano'"
            )

        # Validate directories exist or can be created
        for dir_path in [self.input_dir, self.output_dir, self.done_dir]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Cannot create directory {dir_path}: {e}")

        # Validate numeric settings
        if self.poll_interval <= 0:
            raise ValueError("POLL_INTERVAL must be positive")

        if self.max_retries < 1:
            raise ValueError("MAX_RETRIES must be at least 1")

        if self.retry_delay < 0:
            raise ValueError("RETRY_DELAY must be non-negative")

        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "assemblyai_api_key": "***REDACTED***",  # Don't expose API key
            "speech_model": self.speech_model,
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "done_dir": str(self.done_dir),
            "poll_interval": self.poll_interval,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "log_level": self.log_level,
            "log_file": str(self.log_file) if self.log_file else None,
        }


class ConfigError(Exception):
    """Custom exception for configuration errors."""

    pass


def load_config(env_file: Optional[Path] = None) -> Config:
    """
    Load configuration from environment variables and .env file.

    Args:
        env_file: Optional path to .env file. If None, looks for .env in current directory.

    Returns:
        Loaded configuration

    Raises:
        ConfigError: If configuration is invalid or missing required values
    """
    # Load .env file if it exists
    if env_file is None:
        env_file = Path.cwd() / ".env"

    if env_file.exists():
        load_dotenv(env_file)
        logging.info(f"Loaded environment variables from {env_file}")
    else:
        logging.info("No .env file found, using environment variables only")

    try:
        # Required settings
        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if not api_key:
            raise ConfigError("ASSEMBLYAI_API_KEY environment variable is required")

        input_dir = os.getenv("INPUT_DIR")
        if not input_dir:
            raise ConfigError("INPUT_DIR environment variable is required")

        output_dir = os.getenv("OUTPUT_DIR")
        if not output_dir:
            raise ConfigError("OUTPUT_DIR environment variable is required")

        done_dir = os.getenv("DONE_DIR")
        if not done_dir:
            raise ConfigError("DONE_DIR environment variable is required")

        # Optional settings with defaults
        speech_model = os.getenv("SPEECH_MODEL", "best")
        poll_interval = int(os.getenv("POLL_INTERVAL", "5"))
        max_retries = int(os.getenv("MAX_RETRIES", "3"))
        retry_delay = int(os.getenv("RETRY_DELAY", "60"))
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        log_file_str = os.getenv("LOG_FILE")
        log_file = Path(log_file_str) if log_file_str else None

        # Create configuration
        config = Config(
            assemblyai_api_key=api_key,
            speech_model=speech_model,
            input_dir=Path(input_dir),
            output_dir=Path(output_dir),
            done_dir=Path(done_dir),
            poll_interval=poll_interval,
            max_retries=max_retries,
            retry_delay=retry_delay,
            log_level=log_level,
            log_file=log_file,
        )

        return config

    except ValueError as e:
        raise ConfigError(f"Configuration validation failed: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to load configuration: {e}")


def setup_logging(config: Config) -> None:
    """
    Set up logging based on configuration.

    Args:
        config: Configuration object with logging settings
    """
    # Configure logging level
    log_level = getattr(logging, config.log_level.upper())

    # Create formatters
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if config.log_file:
        try:
            # Ensure log directory exists
            config.log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(config.log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            logging.info(f"Logging to file: {config.log_file}")
        except Exception as e:
            logging.warning(f"Could not set up file logging to {config.log_file}: {e}")

    # Log configuration (without sensitive data)
    logging.info("Configuration loaded successfully")
    logging.debug(f"Configuration: {config.to_dict()}")


def get_default_config_path() -> Path:
    """Get the default path for the .env configuration file."""
    return Path.cwd() / ".env"


def create_sample_config(path: Optional[Path] = None) -> None:
    """
    Create a sample .env configuration file.

    Args:
        path: Optional path where to create the file. Defaults to .env in current directory.
    """
    if path is None:
        path = get_default_config_path()

    sample_content = """# AssemblyAI Configuration
ASSEMBLYAI_API_KEY=your_api_key_here
SPEECH_MODEL=best  # Options: best, nano

# Directory Configuration
INPUT_DIR=/path/to/input/folder
OUTPUT_DIR=/path/to/output/folder
DONE_DIR=/path/to/done/folder

# Service Configuration
POLL_INTERVAL=5  # Seconds between directory checks
MAX_RETRIES=3    # Maximum retry attempts for failed transcriptions
RETRY_DELAY=60   # Seconds to wait between retries

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=/var/log/auto-transcript-agent.log
"""

    with open(path, "w") as f:
        f.write(sample_content)

    logging.info(f"Sample configuration created at: {path}")
    logging.info("Please edit the configuration file with your actual settings")


def validate_directories(config: Config) -> None:
    """
    Validate that all configured directories are accessible.

    Args:
        config: Configuration to validate

    Raises:
        ConfigError: If directories are not accessible
    """
    errors = []

    # Check input directory
    if not config.input_dir.exists():
        errors.append(f"Input directory does not exist: {config.input_dir}")
    elif not config.input_dir.is_dir():
        errors.append(f"Input path is not a directory: {config.input_dir}")
    elif not os.access(config.input_dir, os.R_OK):
        errors.append(f"Input directory is not readable: {config.input_dir}")

    # Check output directory
    try:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(config.output_dir, os.W_OK):
            errors.append(f"Output directory is not writable: {config.output_dir}")
    except Exception as e:
        errors.append(f"Cannot access output directory {config.output_dir}: {e}")

    # Check done directory
    try:
        config.done_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(config.done_dir, os.W_OK):
            errors.append(f"Done directory is not writable: {config.done_dir}")
    except Exception as e:
        errors.append(f"Cannot access done directory {config.done_dir}: {e}")

    if errors:
        raise ConfigError(
            "Directory validation failed:\n"
            + "\n".join(f"  - {error}" for error in errors)
        )
