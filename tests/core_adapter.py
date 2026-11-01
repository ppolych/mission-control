"""Test adapter for legacy multi-module fault injection."""
import importlib
import types
from pathlib import Path

def bind(module):
    modules = [importlib.import_module('mission_control.' + path.stem)
               for path in (Path(module.__file__).parent / 'mission_control').glob('*.py')
               if path.stem != '__init__']
    originals = {}
    class Adapter(types.ModuleType):
        def __getattr__(self, name):
            for owner in modules:
                if hasattr(owner, name):
                    return getattr(owner, name)
            raise AttributeError(name)
        def __setattr__(self, name, value):
            for owner in modules:
                if hasattr(owner, name):
                    originals.setdefault((owner, name), getattr(owner, name))
                    setattr(owner, name, value)
            super().__setattr__(name, value)
        def __delattr__(self, name):
            for owner in modules:
                if (owner, name) in originals:
                    setattr(owner, name, originals.pop((owner, name)))
            if name in self.__dict__:
                super().__delattr__(name)
    module.__class__ = Adapter
