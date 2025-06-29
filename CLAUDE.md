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

## Service Troubleshooting for Developers

### Common LaunchAgent Issues

When working on service improvements, be aware of these common pitfalls:

#### 1. Duplicate Keys in plist Files
- **Problem**: XML plist files cannot have duplicate keys (e.g., multiple `<key>KeepAlive</key>`)
- **Symptoms**: `LastExitStatus = 19968`, service loads but never starts
- **Prevention**: Always validate plist files with `plutil -lint`
- **Fix**: Combine duplicate keys into single complex structure

#### 2. Homebrew PATH Issues
- **Problem**: LaunchAgent doesn't inherit user shell PATH, can't find Homebrew tools
- **Symptoms**: "command not found" errors, service fails to start
- **Solution**: Explicitly include `/opt/homebrew/bin` in plist EnvironmentVariables
- **Testing**: Use `launchctl getenv PATH` to check LaunchAgent environment

#### 3. Log File Permissions
- **Problem**: LaunchAgent can't write to `/var/log/` (requires admin permissions)
- **Symptoms**: No log files created, silent failures
- **Solution**: Use user-accessible paths like project directory
- **Best Practice**: Default to user directory, allow configuration override

#### 4. Virtual Environment Reliability
- **Problem**: Direct venv paths may not work reliably in LaunchAgent context
- **Symptoms**: Python import errors, module not found errors
- **Solution**: Use `uv run python` approach for better environment handling
- **Testing**: Compare manual execution vs LaunchAgent execution

### Debugging Workflow

1. **Manual Testing First**
   ```bash
   # Always test manually before deploying as service
   uv run python -m src.transcript_service run
   ```

2. **Validate plist Syntax**
   ```bash
   plutil -lint ~/Library/LaunchAgents/com.user.autotranscript.plist
   ```

3. **Check Service Status**
   ```bash
   launchctl list com.user.autotranscript
   # Look for LastExitStatus != 0
   ```

4. **Monitor Service Logs**
   ```bash
   tail -f service.err.log  # Service stdout/stderr
   tail -f auto-transcript-agent.log  # Application logs
   ```

5. **Test Network Permissions**
   - Run manual test with network directories first
   - Grant macOS permissions when prompted
   - Then deploy as service

### Testing Service Reliability

#### Unit Tests for Service Components
- Mock launchctl commands in tests
- Test plist generation and validation
- Verify log file handling logic
- Test service status checking

#### Integration Tests
- Test full service lifecycle (install → start → test → stop → uninstall)
- Verify file processing through service vs manual execution
- Test with network shares and permission scenarios
- Validate service restart behavior

#### Manual Validation Checklist
- [ ] Service installs without errors
- [ ] Plist file validates with plutil
- [ ] Service starts and shows in `launchctl list`
- [ ] Log files are created and accessible
- [ ] File processing works end-to-end
- [ ] Service survives system restart
- [ ] Network directory permissions work correctly

### macOS Specific Considerations

#### LaunchAgent vs LaunchDaemon
- Use LaunchAgent (user-level) for user directory access
- LaunchDaemon (system-level) has more restrictions
- LaunchAgent requires user login to function

#### Permission Model
- Network shares require explicit user consent
- First run should be manual to trigger permission dialogs
- Service inherits user permissions but not environment

#### Environment Variables
- LaunchAgent gets minimal environment
- Must explicitly set PATH, PYTHONPATH, etc.
- Use absolute paths when possible

### Code Quality for Service Components

#### Error Handling
- Always handle subprocess failures gracefully
- Provide meaningful error messages for service issues
- Log service lifecycle events at appropriate levels

#### Configuration Validation
- Validate all paths exist and are accessible
- Check API keys and network connectivity
- Verify audio format support before processing

#### Resource Management
- Set appropriate resource limits in plist
- Monitor memory usage during long-running operations
- Handle file descriptor limits properly