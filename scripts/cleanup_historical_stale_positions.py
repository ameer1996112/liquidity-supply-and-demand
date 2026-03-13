#!/usr/bin/env python3
"""Cleanup historical stale positions: Close zero-PNL active/executed signals older than 30d."""

import argparse
from datetime import datetime
