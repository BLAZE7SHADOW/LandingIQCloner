#!/usr/bin/env python3
"""
Setup script for Website Cloner
"""
import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and print status"""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up Website Cloner...")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install requirements
    if not run_command("pip3 install -r requirements.txt", "Installing Python packages"):
        sys.exit(1)
    
    # Install Playwright browsers
    if not run_command("python3 -m playwright install chromium", "Installing Playwright browsers"):
        sys.exit(1)
    
    # Create necessary directories
    os.makedirs("captured_sites", exist_ok=True)
    print("✅ Created captured_sites directory")
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("\nTo start the application:")
    print("  python app.py")
    print("\nThen open your browser to:")
    print("  http://localhost:5000")
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()