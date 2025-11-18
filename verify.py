#!/usr/bin/env python3
"""
NERVA Installation Verification Script

Checks that all required components are present and dependencies are installed.
"""
import sys
from pathlib import Path


def check_file(path: Path, name: str) -> bool:
    """Check if a file exists."""
    if path.exists():
        print(f"✓ {name}")
        return True
    else:
        print(f"✗ {name} - MISSING")
        return False


def check_module(module_name: str) -> bool:
    """Check if a Python module is importable."""
    try:
        __import__(module_name)
        print(f"✓ {module_name}")
        return True
    except ImportError:
        print(f"✗ {module_name} - NOT INSTALLED")
        return False


def main():
    print("=" * 60)
    print("NERVA Installation Verification")
    print("=" * 60)

    root = Path(__file__).parent
    nerva = root / "nerva"

    all_good = True

    # Check core files
    print("\n[Core Files]")
    files = [
        (nerva / "__init__.py", "nerva/__init__.py"),
        (nerva / "config.py", "nerva/config.py"),
        (nerva / "types.py", "nerva/types.py"),
        (nerva / "bus.py", "nerva/bus.py"),
        (nerva / "run_context.py", "nerva/run_context.py"),
        (nerva / "dag.py", "nerva/dag.py"),
        (nerva / "workflows.py", "nerva/workflows.py"),
        (nerva / "main.py", "nerva/main.py"),
        (nerva / "console.py", "nerva/console.py"),
    ]
    for path, name in files:
        if not check_file(path, name):
            all_good = False

    # Check modules
    print("\n[Modules]")
    modules = [
        (nerva / "llm", "LLM clients"),
        (nerva / "vision", "Vision components"),
        (nerva / "voice", "Voice components"),
        (nerva / "repos", "Repo indexing"),
        (nerva / "memory", "Memory system"),
        (nerva / "ops", "Daily ops"),
        (nerva / "hydra_adapter", "HydraContext adapter"),
    ]
    for path, name in modules:
        if not check_file(path / "__init__.py", f"{name} ({path.name}/__init__.py)"):
            all_good = False

    # Check dependencies
    print("\n[Python Dependencies]")
    deps = [
        "aiohttp",
        "textual",
    ]
    for dep in deps:
        if not check_module(dep):
            all_good = False

    # Optional dependencies
    print("\n[Optional Dependencies]")
    optional = [
        "mss",
        "whisper",
        # "faster_whisper",
        # "sounddevice",
        # "sentence_transformers",
    ]
    for dep in optional:
        check_module(dep)  # Don't fail on optional deps

    # Check metadata
    print("\n[Project Metadata]")
    meta = [
        (root / "pyproject.toml", "pyproject.toml"),
        (root / "README.md", "README.md"),
        (root / "SETUP.md", "SETUP.md"),
        (root / "QUICKSTART.md", "QUICKSTART.md"),
        (root / ".gitignore", ".gitignore"),
    ]
    for path, name in meta:
        if not check_file(path, name):
            all_good = False

    # Summary
    print("\n" + "=" * 60)
    if all_good:
        print("✓ All core files present!")
        print("\nNext steps:")
        print("1. Install: pip install -e .")
        print("2. Start Ollama: ollama serve")
        print("3. Run console: nerva-console")
        print("4. Or run CLI: nerva voice 'Hello NERVA'")
    else:
        print("✗ Some files are missing. Re-run the setup.")
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
