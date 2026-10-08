#!/usr/bin/env python3
"""Запуск Книжного червя без установки пакета."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from knizhny_cherv.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
