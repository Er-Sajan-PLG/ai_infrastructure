"""A real, stdlib-only socket for model-provider-abstraction.

This package exists so its modules can import one another as a relocatable
unit, the same way a catalog entry does (charter section 31): the integration
can be lifted out of this repository and still import itself correctly.

It consumes ``model_provider`` through its public interface only -- the
``Transport`` protocol, ``WireRequest``/``WireResponse`` values, and the
``TransportError``/``ProviderTimeoutError`` failure types. It never imports a
provider adapter's internals and never touches ``catalog/`` otherwise.
"""

from __future__ import annotations

__all__: list[str] = []
