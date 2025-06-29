# 🔧 Troubleshooting Guide

This guide helps diagnose and fix common issues with the Auto-Transcript-Agent service.

## 🚨 Service Not Starting

### Check Service Status

First, verify if the service is actually running vs. just loaded:

```bash
# Check if service is loaded
launchctl list | grep autotranscript

# Get detailed status (most important)
launchctl list com.user.autotranscript

# Check for running processes
ps aux | grep "src.transcript_service" | grep -v grep
```

**Key indicators:**
- `LastExitStatus = 0` → Service started successfully
- `LastExitStatus = 19968` → Service failed to start (common issue)
- No process in `ps aux` → Service isn't actually running

### Common Startup Issues

#### 1. Homebrew PATH Problems

**Problem**: LaunchAgent can't find `uv` because it doesn't inherit your shell's PATH.

**Symptoms**:
- `LastExitStatus = 19968`
- No error logs created
- Service appears loaded but never starts

**Solution**: Ensure your plist includes Homebrew's path:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
</dict>
```

**Fix**: Reinstall service with corrected script:
```bash
uv run python scripts/install_service.py uninstall
uv run python scripts/install_service.py install
```

#### 2. Invalid plist File

**Problem**: Duplicate keys or malformed XML in the plist file.

**Check**: Validate your plist:
```bash
plutil -lint ~/Library/LaunchAgents/com.user.autotranscript.plist
```

**Common issues**:
- Duplicate `<key>KeepAlive</key>` entries
- Missing closing tags
- Invalid XML structure

#### 3. Log File Permission Issues

**Problem**: Service can't write to `/var/log/` (requires admin permissions).

**Symptoms**: No log files created in `/var/log/`

**Solution**: Use user-accessible log paths in plist:
```xml
<key>StandardOutPath</key>
<string>/Users/USERNAME/Custom-Agents/Auto-Transcript-Agent/service.out.log</string>
<key>StandardErrorPath</key>
<string>/Users/USERNAME/Custom-Agents/Auto-Transcript-Agent/service.err.log</string>
```

## 🌐 Network Share Issues (macOS)

### Permission Dialogs

**Problem**: macOS requires explicit permission for apps to access network shares.

**Symptoms**:
- Service starts but can't access input/output directories
- "Permission denied" errors in logs
- Files not being processed on network drives

**Solution**:
1. **Run manually first** to trigger permission dialog:
   ```bash
   uv run python -m src.transcript_service run
   ```
2. **Grant permissions** when macOS prompts
3. **Restart service** after granting permissions

### Network Share Troubleshooting

```bash
# Test directory access
ls -la "/Volumes/YourNetworkShare/YourDirectory"

# Check if directories exist and are writable
touch "/path/to/input/test.txt" && rm "/path/to/input/test.txt"
touch "/path/to/output/test.txt" && rm "/path/to/output/test.txt"
touch "/path/to/done/test.txt" && rm "/path/to/done/test.txt"
```

## 📋 Manual Testing

### Test Service Manually

Run the service manually to isolate issues:

```bash
# Run service in foreground (Ctrl+C to stop)
uv run python -m src.transcript_service run

# Check configuration without starting
uv run python -m src.transcript_service status

# Test single file transcription
uv run python -m src.transcript_service transcribe path/to/audio.mp3
```

### Verify Configuration

```bash
# Check if .env file exists and is readable
cat .env

# Verify directories exist
ls -la "$(grep INPUT_DIR .env | cut -d= -f2)"
ls -la "$(grep OUTPUT_DIR .env | cut -d= -f2)"
ls -la "$(grep DONE_DIR .env | cut -d= -f2)"

# Test API key
uv run python -c "from src.config import Config; print('Config loads:', Config().assemblyai_api_key[:10] + '...')"
```

## 📊 Log Analysis

### Service Logs

Check multiple log locations:

```bash
# Application logs (main log file)
tail -f auto-transcript-agent.log

# Service stdout/stderr (if using user directory)
tail -f service.out.log
tail -f service.err.log

# System logs (if using /var/log - requires sudo)
sudo tail -f /var/log/auto-transcript-agent.out.log
sudo tail -f /var/log/auto-transcript-agent.err.log
```

### Log Patterns

**Successful startup**:
```
Auto-Transcript-Agent service initialized
Starting Auto-Transcript-Agent service...
AudioTranscriber initialized with best model
FolderMonitor initialized
File system watcher started
Polling thread started
Auto-Transcript-Agent service started successfully
```

**Common error patterns**:
- `Command not found` → Homebrew PATH issue
- `Permission denied` → Network share or log file permissions
- `Configuration error` → Missing .env or invalid settings
- `No such file or directory` → Directory paths don't exist

## 🔧 Service Management

### Restart Service

```bash
# Using install script (recommended)
uv run python scripts/install_service.py restart

# Manual restart
launchctl unload ~/Library/LaunchAgents/com.user.autotranscript.plist
launchctl load ~/Library/LaunchAgents/com.user.autotranscript.plist
```

### Reinstall Service

```bash
# Clean reinstall
uv run python scripts/install_service.py uninstall
uv run python scripts/install_service.py install
```

### Force Stop Service

```bash
# Stop service
launchctl unload ~/Library/LaunchAgents/com.user.autotranscript.plist

# Kill any remaining processes
pkill -f "src.transcript_service"
```

## 🐛 Common Error Solutions

### "Service shows as running but no files processed"

1. Check if directories are accessible
2. Verify network share permissions
3. Test with a new audio file
4. Check logs for processing attempts

### "LastExitStatus = 19968"

1. Check Homebrew PATH in plist
2. Validate plist file syntax
3. Verify log file permissions
4. Test manual execution

### "Files detected but transcription fails"

1. Verify AssemblyAI API key
2. Check network connectivity
3. Test with a smaller audio file
4. Review transcription error logs

### "Service won't stay running"

1. Check resource limits in plist
2. Review crash logs
3. Test for memory issues
4. Verify all dependencies installed

## 📞 Getting Help

If you're still experiencing issues:

1. **Run diagnostics**:
   ```bash
   uv run python -m src.transcript_service status
   launchctl list com.user.autotranscript
   ```

2. **Collect logs**:
   - Application log: `auto-transcript-agent.log`
   - Service logs: `service.out.log` and `service.err.log`

3. **Create GitHub issue** with:
   - Error symptoms
   - Log excerpts
   - Configuration details (without API keys)
   - macOS version and setup details

## 🔍 Advanced Debugging

### Monitor File System Events

```bash
# Watch for file system changes
fswatch "/path/to/input/directory"

# Monitor service with detailed logging
LOG_LEVEL=DEBUG uv run python -m src.transcript_service run
```

### Check LaunchAgent Environment

```bash
# View current environment in LaunchAgent context
launchctl getenv PATH
launchctl getenv PYTHONPATH
```

### Validate Dependencies

```bash
# Check uv installation
which uv
uv --version

# Verify Python environment
uv run python --version
uv run python -c "import sys; print(sys.executable)"

# Test imports
uv run python -c "from src.transcript_service import main"
```