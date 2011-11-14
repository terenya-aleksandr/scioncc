#!/usr/bin/env python

"""
Entry point for importing common Ion packages. Most files should only need to import from here.
"""

__author__ = 'Michael Meisinger'
__license__ = 'Apache 2.0'

__all__ = []

from pyon.ion.resource import all_resources
__all__ += ['all_resources']
