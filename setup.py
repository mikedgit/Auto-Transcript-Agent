#!/usr/bin/env python3
"""Setup script for Auto-Transcript-Agent."""

import sys
from pathlib import Path

def main():
    """Main setup function."""
    print("Auto-Transcript-Agent Setup")
    print("=" * 30)
    
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    
    # Check if .env exists
    if not env_file.exists():
        print("Creating .env configuration file...")
        example_file = project_root / ".env.example"
        if example_file.exists():
            import shutil
            shutil.copy(example_file, env_file)
            print(f"✓ Created {env_file}")
            print("Please edit .env with your actual configuration:")
            print("  - Set your AssemblyAI API key")
            print("  - Configure your input, output, and done directories")
        else:
            print("✗ .env.example not found")
            return 1
    else:
        print("✓ .env file already exists")
    
    # Check virtual environment
    venv_path = project_root / ".venv"
    if not venv_path.exists():
        print("\nVirtual environment not found. Please run:")
        print("  uv sync")
        return 1
    else:
        print("✓ Virtual environment exists")
    
    print("\nNext steps:")
    print("1. Edit .env with your configuration")
    print("2. Test the service: uv run python -m src.transcript_service --help")
    print("3. Install as service: uv run python scripts/install_service.py install")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())