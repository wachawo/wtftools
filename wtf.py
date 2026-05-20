#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test wtftools without installing it.

When you run this from the repo root:

    python3 wtf.py audit --check uptime
    ./wtf.py info
    ./wtf.py serve --listen 127.0.0.1:8765

Python prepends the script's directory to `sys.path`, so the `wtftools`
package next to this file imports cleanly without a prior `pip install -e .`.
For day-to-day use after install, prefer the proper console-script entry
points: `wtf` (audit/info/…) or `wtfd` (the HTTP daemon).
"""

import sys

from wtftools.main import main

if __name__ == "__main__":
    sys.exit(main())
