"""An end-to-end composition of three catalog capabilities.

This package exists so its modules can import one another as a relocatable
unit, the same way a catalog entry does (charter section 31): the entry can
be lifted out of this repository and still import itself correctly.
"""

from __future__ import annotations

__all__: list[str] = []
