"""Standalone entry point to the SAME canonical MantleOS KPP modules."""
import importlib as _importlib
import sys as _sys
if not (3, 11) <= _sys.version_info[:2] < (3, 15):
    raise RuntimeError('KPP/MantleOS requires Python 3.11 through 3.14')
from mantleos.kpp import __version__
for _name in ['adaptation', 'anchor', 'build', 'cells', 'cli', 'conformance', 'core', 'economy', 'graph', 'gui', 'ingest', 'pantry', 'png', 'portability', 'reflex', 'scanner', 'server', 'specimens', 'systems', 'testing', 'tissue', 'workshop', 'anchors']:
    _module = _importlib.import_module('mantleos.kpp.' + _name)
    _sys.modules[__name__ + '.' + _name] = _module
    globals()[_name] = _module
