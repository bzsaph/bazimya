"""`python -m bazimya` — the same entry point as the `bazimya` script."""

import sys

from .console.kernel import Kernel

if __name__ == "__main__":
    sys.exit(Kernel().run(sys.argv))
