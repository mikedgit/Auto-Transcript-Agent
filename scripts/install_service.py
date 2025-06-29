#!/usr/bin/env python3
"""Installation script for Auto-Transcript-Agent macOS service."""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import click


def get_current_user() -> str:
    """Get the current username."""
    return os.getenv('USER', os.getenv('USERNAME', 'user'))


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.absolute()


def get_launch_agents_dir() -> Path:
    """Get the LaunchAgents directory for the current user."""
    home_dir = Path.home()
    launch_agents_dir = home_dir / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(exist_ok=True)
    return launch_agents_dir


def customize_plist(project_root: Path, username: str) -> str:
    """
    Read and customize the plist file with actual paths.
    
    Args:
        project_root: Path to the project root
        username: Current username
        
    Returns:
        Customized plist content
    """
    plist_template = project_root / "com.user.autotranscript.plist"
    
    if not plist_template.exists():
        raise click.ClickException(f"Plist template not found: {plist_template}")
    
    # Read template
    with open(plist_template, 'r') as f:
        content = f.read()
    
    # Replace placeholders
    content = content.replace("REPLACE_WITH_USERNAME", username)
    
    return content


def install_plist(project_root: Path, username: str) -> Path:
    """
    Install the LaunchAgent plist file.
    
    Args:
        project_root: Path to the project root
        username: Current username
        
    Returns:
        Path to the installed plist file
    """
    launch_agents_dir = get_launch_agents_dir()
    plist_dest = launch_agents_dir / "com.user.autotranscript.plist"
    
    # Generate customized plist content
    plist_content = customize_plist(project_root, username)
    
    # Write the plist file
    with open(plist_dest, 'w') as f:
        f.write(plist_content)
    
    click.echo(f"✓ Installed plist file: {plist_dest}")
    return plist_dest


def create_log_directory() -> None:
    """Create log directory if it doesn't exist."""
    log_dir = Path("/var/log")
    
    if not log_dir.exists():
        click.echo("⚠ /var/log directory doesn't exist, logs will go to stderr")
        return
    
    # Check if we can write to /var/log
    if not os.access(log_dir, os.W_OK):
        click.echo("⚠ Cannot write to /var/log, you may need to run with sudo for logging")
        click.echo("  Or configure LOG_FILE in .env to a writable location")


def load_service(plist_path: Path) -> bool:
    """
    Load the LaunchAgent service.
    
    Args:
        plist_path: Path to the plist file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
            text=True,
            check=True
        )
        click.echo("✓ Service loaded successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        click.echo(f"✗ Failed to load service: {e.stderr}")
        return False


def unload_service(plist_path: Path) -> bool:
    """
    Unload the LaunchAgent service.
    
    Args:
        plist_path: Path to the plist file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
            text=True,
            check=True
        )
        click.echo("✓ Service unloaded successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        # Unload might fail if service wasn't loaded, which is OK
        if "Could not find specified service" in e.stderr:
            click.echo("✓ Service was not loaded")
            return True
        else:
            click.echo(f"✗ Failed to unload service: {e.stderr}")
            return False


def check_service_status() -> dict:
    """
    Check the status of the service.
    
    Returns:
        Dictionary with service status information
    """
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Look for our service in the output
        service_running = "com.user.autotranscript" in result.stdout
        
        return {
            "running": service_running,
            "output": result.stdout
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "running": False,
            "error": e.stderr
        }


def check_configuration() -> bool:
    """
    Check if configuration is properly set up.
    
    Returns:
        True if configuration looks good, False otherwise
    """
    project_root = get_project_root()
    env_file = project_root / ".env"
    
    if not env_file.exists():
        click.echo("✗ Configuration file .env not found")
        click.echo(f"  Please create {env_file} based on .env.example")
        return False
    
    # Basic validation of .env file
    required_vars = [
        "ASSEMBLYAI_API_KEY",
        "INPUT_DIR",
        "OUTPUT_DIR", 
        "DONE_DIR"
    ]
    
    with open(env_file, 'r') as f:
        content = f.read()
    
    missing_vars = []
    for var in required_vars:
        if f"{var}=" not in content:
            missing_vars.append(var)
    
    if missing_vars:
        click.echo(f"✗ Missing required configuration variables: {', '.join(missing_vars)}")
        return False
    
    click.echo("✓ Configuration file looks good")
    return True


@click.group()
def cli():
    """Auto-Transcript-Agent service installation and management."""
    pass


@cli.command()
@click.option('--force', '-f', is_flag=True, help='Force reinstallation')
def install(force: bool):
    """Install the Auto-Transcript-Agent service."""
    click.echo("Installing Auto-Transcript-Agent service...")
    
    project_root = get_project_root()
    username = get_current_user()
    
    click.echo(f"Project root: {project_root}")
    click.echo(f"Username: {username}")
    
    # Check if virtual environment exists
    venv_path = project_root / ".venv"
    if not venv_path.exists():
        click.echo("✗ Virtual environment not found")
        click.echo("  Please run 'uv sync' first to create the virtual environment")
        sys.exit(1)
    
    # Check configuration
    if not check_configuration():
        click.echo("✗ Configuration check failed")
        sys.exit(1)
    
    # Get plist destination
    launch_agents_dir = get_launch_agents_dir()
    plist_dest = launch_agents_dir / "com.user.autotranscript.plist"
    
    # Check if already installed
    if plist_dest.exists() and not force:
        click.echo(f"✗ Service already installed: {plist_dest}")
        click.echo("  Use --force to reinstall")
        sys.exit(1)
    
    try:
        # Unload existing service if it exists
        if plist_dest.exists():
            click.echo("Unloading existing service...")
            unload_service(plist_dest)
        
        # Install plist file
        install_plist(project_root, username)
        
        # Create log directory
        create_log_directory()
        
        # Load the service
        if load_service(plist_dest):
            click.echo("✓ Auto-Transcript-Agent service installed and started successfully!")
            click.echo("\nService commands:")
            click.echo(f"  Start:  launchctl load {plist_dest}")
            click.echo(f"  Stop:   launchctl unload {plist_dest}")
            click.echo(f"  Status: launchctl list | grep autotranscript")
        else:
            click.echo("✗ Service installation completed but failed to start")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"✗ Installation failed: {e}")
        sys.exit(1)


@cli.command()
def uninstall():
    """Uninstall the Auto-Transcript-Agent service."""
    click.echo("Uninstalling Auto-Transcript-Agent service...")
    
    launch_agents_dir = get_launch_agents_dir()
    plist_dest = launch_agents_dir / "com.user.autotranscript.plist"
    
    if not plist_dest.exists():
        click.echo("✓ Service is not installed")
        return
    
    try:
        # Unload the service
        unload_service(plist_dest)
        
        # Remove plist file
        plist_dest.unlink()
        click.echo(f"✓ Removed plist file: {plist_dest}")
        
        click.echo("✓ Auto-Transcript-Agent service uninstalled successfully!")
        
    except Exception as e:
        click.echo(f"✗ Uninstallation failed: {e}")
        sys.exit(1)


@cli.command()
def status():
    """Check the status of the Auto-Transcript-Agent service."""
    click.echo("Checking Auto-Transcript-Agent service status...")
    
    launch_agents_dir = get_launch_agents_dir()
    plist_dest = launch_agents_dir / "com.user.autotranscript.plist"
    
    # Check if plist is installed
    if not plist_dest.exists():
        click.echo("✗ Service is not installed")
        click.echo(f"  Expected plist location: {plist_dest}")
        return
    
    click.echo(f"✓ Service plist found: {plist_dest}")
    
    # Check if service is loaded/running
    status_info = check_service_status()
    
    if status_info["running"]:
        click.echo("✓ Service is running")
    else:
        click.echo("✗ Service is not running")
        if "error" in status_info:
            click.echo(f"  Error: {status_info['error']}")
    
    # Show recent log entries if available
    log_files = [
        "/var/log/auto-transcript-agent.out.log",
        "/var/log/auto-transcript-agent.err.log"
    ]
    
    for log_file in log_files:
        log_path = Path(log_file)
        if log_path.exists():
            click.echo(f"\nRecent entries from {log_file}:")
            try:
                result = subprocess.run(
                    ["tail", "-n", "5", str(log_path)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        click.echo(f"  {line}")
            except subprocess.CalledProcessError:
                click.echo(f"  Could not read {log_file}")


@cli.command()
def restart():
    """Restart the Auto-Transcript-Agent service."""
    click.echo("Restarting Auto-Transcript-Agent service...")
    
    launch_agents_dir = get_launch_agents_dir()
    plist_dest = launch_agents_dir / "com.user.autotranscript.plist"
    
    if not plist_dest.exists():
        click.echo("✗ Service is not installed")
        sys.exit(1)
    
    try:
        # Unload and reload
        unload_service(plist_dest)
        if load_service(plist_dest):
            click.echo("✓ Service restarted successfully!")
        else:
            click.echo("✗ Failed to restart service")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"✗ Restart failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()