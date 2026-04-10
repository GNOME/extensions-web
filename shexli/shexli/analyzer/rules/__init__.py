# Import rule modules for registration side effects.
from . import api_misuse as _api_misuse
from . import artifact as _artifact
from . import clipboard as _clipboard
from . import imports as _imports
from . import lifecycle as _lifecycle
from . import logging as _logging
from . import metadata as _metadata
from . import obfuscation as _obfuscation
from . import prefs as _prefs
from . import session_modes as _session_modes
from . import subprocess as _subprocess
from . import version_compat as _version_compat
from .api import EXTENSION_RULE_TYPES, JS_FILE_RULE_TYPES

_RULE_MODULES = (
    _api_misuse,
    _artifact,
    _clipboard,
    _imports,
    _lifecycle,
    _logging,
    _metadata,
    _obfuscation,
    _prefs,
    _session_modes,
    _subprocess,
    _version_compat,
)

JS_FILE_RULES = tuple(rule_type() for rule_type in JS_FILE_RULE_TYPES)
EXTENSION_RULES = tuple(rule_type() for rule_type in EXTENSION_RULE_TYPES)
