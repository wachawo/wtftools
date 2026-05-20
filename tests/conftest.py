#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared pytest fixtures."""

import pytest

from wtftools import colors


@pytest.fixture(autouse=True)
def no_colors():
    """Force-disable colors so output assertions are deterministic."""
    colors.init_colors(force_no_color=True)
    yield
