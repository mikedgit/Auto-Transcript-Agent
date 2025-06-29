# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Dependencies
- `uv sync` - Install runtime dependencies
- `uv sync --dev` - Install runtime + development dependencies
- `uv add <package>` - Add new runtime dependency
- `uv add --dev <package>` - Add new development dependency

### Testing
- `uv run pytest` - Run all tests
- `uv run pytest --cov=src --cov-report=html` - Run tests with HTML coverage report
- `uv run pytest tests/test_transcriber.py -v` - Run specific test file with verbose output
- `uv run pytest -k "test_config"` - Run tests matching pattern
- `uv run pytest --cov-fail-under=95` - Enforce 95% coverage requirement

### Code Quality
- `uv run black src tests` - Format code
- `uv run flake8 src tests` - Lint for style violations
- `uv run mypy src` - Type checking

### CLI and Service Operations
- `uv run python -m src.transcript_service --help` - Show CLI help
- `uv run python -m src.transcript_service run` - Run service manually
- `uv run python -m src.transcript_service status` - Check service status
- `uv run python -m src.transcript_service transcribe <audio_file>` - Transcribe single file
- `uv run python -m src.transcript_service init-config` - Create sample .env file
- `uv run python scripts/install_service.py install` - Install as macOS service
- `uv run python scripts/install_service.py status` - Check service installation status

## Architecture Overview

### Service-Oriented Design
The application follows a modular architecture with clear separation of concerns:

- **TranscriptService** (`src/transcript_service.py`) - Main orchestrator that coordinates all components, handles service lifecycle, CLI interface, and signal handling
- **AudioTranscriber** (`src/transcriber.py`) - AssemblyAI API integration with retry logic, error handling, and file format validation
- **FolderMonitor** (`src/monitor.py`) - File system monitoring using watchdog events with polling fallback, manages file processing pipeline
- **Config** (`src/config.py`) - Environment-based configuration management with validation and logging setup

### File Processing Pipeline
1. **Input Detection**: FolderMonitor watches input directory for new audio files
2. **Validation**: Check file format compatibility and wait for file stability
3. **Transcription**: AudioTranscriber calls AssemblyAI API with configured speech model
4. **Output**: Save transcript as .txt file in output directory
5. **Cleanup**: Move original audio file to done directory

### Configuration Architecture
- Environment variables loaded via python-dotenv from `.env` file
- Config dataclass with validation and type hints
- Supports both file-based (.env) and environment variable configuration
- Required: ASSEMBLYAI_API_KEY, INPUT_DIR, OUTPUT_DIR, DONE_DIR
- Optional: SPEECH_MODEL (best/nano), logging settings, retry configuration

### Event-Driven Monitoring
- Primary: Watchdog file system events for real-time detection
- Fallback: Polling thread for network shares or missed events
- File stability checking to handle incomplete uploads
- Duplicate processing prevention via processed files tracking

### AssemblyAI Integration
- Configurable speech models: "best" (accuracy) vs "nano" (speed)
- Retry logic with exponential backoff for API failures
- Comprehensive error handling for network, API, and quota issues
- Support for multiple audio formats (.mp3, .wav, .m4a, .flac, .aac, .ogg, .webm)

## Key Implementation Details

### Entry Points
- **CLI**: `src/transcript_service.py` with Click-based commands
- **Service**: LaunchAgent plist file for automatic startup
- **Installation**: `scripts/install_service.py` for service management

### Testing Strategy
- 95% code coverage requirement enforced in pyproject.toml
- Comprehensive mocking of AssemblyAI API calls
- Fixture-based temporary directory testing
- Separate test files per module with clear naming conventions

### macOS Service Integration
- LaunchAgent plist template with path substitution
- Automatic service installation with username replacement
- Log file management and service lifecycle controls
- Resource limits and restart policies configured

### Error Handling Patterns
- Custom exception classes (TranscriberError, ConfigError) for specific error types
- Graceful degradation with fallback mechanisms
- Comprehensive logging at appropriate levels
- Signal handling for graceful shutdown

### Development Notes
- Type hints throughout codebase with mypy strict configuration
- Dataclasses for structured configuration and data models
- Threading for concurrent operations (polling, file processing)
- Path objects used consistently instead of string paths