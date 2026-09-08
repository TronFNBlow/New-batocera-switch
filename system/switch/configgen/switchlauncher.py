#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os
import argparse
from pathlib import Path
from typing import Any

# Force Python to bypass old compiled bytecode caches entirely
sys.dont_write_bytecode = True

# Hook into the exact internal module where batocera checks for generators now
import configgen.generators.importer
from batocera_launch import Emulator

# Custom Core Generators
from generators.edenGenerator import EdenGenerator
from generators.ryujinxGenerator import RyujinxGenerator

# Capture the target ROM dynamically from standard sys.argv for the interceptor
ROM_PATH_STR = sys.argv[sys.argv.index("-rom") + 1] if "-rom" in sys.argv else ""

# Save a pointer to the native importer engine
_original_get_generator = configgen.generators.importer.get_generator

# 1. New Generator Interceptor targeting the proper module
def _new_get_generator(emulator: str, core: str | None = None):
    yuzuemu = {
        'eden-emu': 1,
        'citron-emu': 1,
        'eden-pgo': 1,
        'eden-nightly': 1
    }

    rom_name = os.path.basename(ROM_PATH_STR)
    if rom_name == 'ryujinx_config.xci_config':
        emulator = 'ryujinx-emu'
   
    print(f"Selected emulator: {emulator}", file=sys.stderr)    
    print(f"Selected Rom : {rom_name}", file=sys.stderr)    

    if emulator in yuzuemu:
        return EdenGenerator()

    if emulator == 'ryujinx-emu':
        return RyujinxGenerator()

    # Fallback safely to Batocera's native generator layout matching code
    return _original_get_generator(emulator, core)

# Inject the generator override into the active importer location
configgen.generators.importer.get_generator = _new_get_generator


# 2. System Config Interceptor via Emulator Initialization Hook
_original_emulator_init = Emulator.__init__

def _new_emulator_init(self, args: Any, original_rom: Path, /):
    _original_emulator_init(self, args, original_rom)
    
    # Inject alternative custom config overrides
    switch_defaults = Path("/userdata/system/switch/configgen/configgen-defaults.yml")
    switch_arch = Path("/userdata/system/switch/configgen/configgen-defaults-arch.yml")

    from batocera_launch.Emulator import _load_defaults, _dict_merge

    if switch_defaults.exists() and switch_arch.exists():
        system_name = args.system if hasattr(args, 'system') else "switch"
        defaults = _load_defaults(system_name, switch_defaults, switch_arch)
        if "options" in defaults:
            _dict_merge(self.config, defaults["options"])

    # Handle specific HUD tracking parameters
    current_emu = self.config.get('emulator', '')
    if current_emu == "ryujinx-emu":
        self.config["hud_support"] = False
    else:
        self.config["hud_support"] = True

# Inject our configuration patch straight into the initialization layout
Emulator.__init__ = _new_emulator_init


if __name__ == "__main__":
    # Standard argparse parameters matching modern architecture expectations
    parser = argparse.ArgumentParser()
    parser.add_argument("-rom", type=Path, required=True)
    parser.add_argument("-system", type=str, required=True)
    parser.add_argument("-emulator", type=str, default="default")
    parser.add_argument("-core", type=str, default="default")
    parser.add_argument("-players", type=str, default="")
    
    parsed_args, unknown = parser.parse_known_args(sys.argv[1:])

    # Force dynamic module execution to launch Batocera's modern operational routines
    import runpy
    try:
        runpy.run_module("batocera_launch", run_name="__main__")
    except Exception as e:
        print(f"Launcher handoff error: {e}", file=sys.stderr)
        sys.exit(1)
