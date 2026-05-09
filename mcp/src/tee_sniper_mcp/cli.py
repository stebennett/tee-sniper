"""Console-script entry point.

Kept thin so that `tee-sniper-mcp --version` can answer without importing
fastmcp / pydantic and the rest of the runtime stack.
"""

from __future__ import annotations

import sys

from tee_sniper_mcp import __version__


def main() -> None:
    if any(arg in {"--version", "-V"} for arg in sys.argv[1:]):
        print(__version__)
        sys.exit(0)

    from tee_sniper_mcp.server import main as server_main

    server_main()
