"""Frozen-app entry point for PyInstaller.

Lives at the project root so `import papyrik` resolves the package. For normal
development use `python -m papyrik.main` instead.
"""

import sys

from papyrik.main import main

if __name__ == "__main__":
    sys.exit(main())
