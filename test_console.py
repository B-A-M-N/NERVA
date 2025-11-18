#!/usr/bin/env python3
"""Quick test to verify the console can be imported and initialized."""

import sys

try:
    from nerva.console import NervaConsole
    print("✓ Console import successful")

    # Try to create the app (don't run it)
    app = NervaConsole()
    print("✓ Console initialization successful")
    print("\nThe console should work!")
    print("\nTo launch the full TUI:")
    print("  nerva-console")
    print("\nOr if that doesn't work:")
    print("  python -m nerva.console")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
