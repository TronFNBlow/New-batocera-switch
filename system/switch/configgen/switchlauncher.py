#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import runpy
import sys

from pathlib import Path

# ----------------------------------------------------------
# Prevent stale pyc files
# ----------------------------------------------------------

sys.dont_write_bytecode = True

# ----------------------------------------------------------
# Optional ROM/emulator information
# ----------------------------------------------------------
#
# Preserve v43 compatibility by capturing ROM and emulator
# information directly from the command line before
# batocera_launch takes over startup.
#
# Used for:
#
# - ryujinx_config.xci_config detection
# - v43 -emulator override compatibility
# - special Switch configuration cartridges
#
# ----------------------------------------------------------

ROM_PATH = ''
EMULATOR_OVERRIDE = None

try:
    if '-rom' in sys.argv:
        ROM_PATH = sys.argv[sys.argv.index('-rom') + 1]
except (ValueError, IndexError):
    pass

try:
    if '-emulator' in sys.argv:
        EMULATOR_OVERRIDE = sys.argv[sys.argv.index('-emulator') + 1]
except (ValueError, IndexError):
    pass

# ----------------------------------------------------------
# Import custom generators early
# ----------------------------------------------------------

try:
    from generators.edenGenerator import EdenGenerator
except Exception as e:
    print(f'[SWITCH] Failed importing EdenGenerator: {e}', file=sys.stderr)
    raise

try:
    from generators.ryujinxGenerator import RyujinxGenerator
except Exception as e:
    print(f'[SWITCH] Failed importing RyujinxGenerator: {e}', file=sys.stderr)
    raise

# ----------------------------------------------------------
# Generator interception
# ----------------------------------------------------------
# Custom Switch routing:
# eden-emu / eden-nightly / eden-pgo / citron-emu -> EdenGenerator
# ryujinx-emu -> RyujinxGenerator
# Everything else falls back to Batocera.
# ----------------------------------------------------------

import configgen.generators.importer

_original_get_generator = configgen.generators.importer.get_generator


def switch_get_generator(emulator: str, core: str | None = None):
    switch_generators = {'eden-emu', 'eden-nightly', 'eden-pgo', 'citron-emu'}

    rom_name = os.path.basename(ROM_PATH)

    # Preserve v43 behaviour: force Ryujinx settings cartridge
    if rom_name == 'ryujinx_config.xci_config':
        emulator = 'ryujinx-emu'

    print(f'[SWITCH] emulator={emulator}', file=sys.stderr)
    print(f'[SWITCH] rom={rom_name}', file=sys.stderr)

    if emulator in switch_generators:
        return EdenGenerator()

    if emulator == 'ryujinx-emu':
        return RyujinxGenerator()

    return _original_get_generator(emulator, core)


configgen.generators.importer.get_generator = switch_get_generator

try:
    import configgen.launch
    configgen.launch.get_generator = switch_get_generator
except ImportError:
    pass

try:
    import configgen.emulatorlauncher
    configgen.emulatorlauncher.get_generator = switch_get_generator
except ImportError:
    pass

# ----------------------------------------------------------
# Switch defaults override
# ----------------------------------------------------------
# Preserve support for custom Switch defaults while using
# the native v44 launcher.
# ----------------------------------------------------------

from batocera_launch.config import defaults

_original_load_system_defaults = defaults.load_system_defaults


def switch_load_system_defaults(system_name: str):
    switch_defaults = Path('/userdata/system/switch/configgen/configgen-defaults.yml')
    switch_arch_defaults = Path('/userdata/system/switch/configgen/configgen-defaults-arch.yml')

    if switch_defaults.exists() and switch_arch_defaults.exists():
        data = defaults.load_defaults(
            system_name,
            switch_defaults,
            switch_arch_defaults,
        ) or {}

        result = {
            'emulator': data.get('emulator'),
            'core': data.get('core'),
        }

        if 'options' in data:
            result.update(data['options'])

        emulator = EMULATOR_OVERRIDE or result.get('emulator')

        # Force hud_support off for Ryujinx only.
        if emulator == 'ryujinx-emu':
            result['hud_support'] = False
        else:
            result.setdefault('hud_support', True)

        return result

    result = _original_load_system_defaults(system_name)

    emulator = EMULATOR_OVERRIDE or result.get('emulator')

    if emulator == 'ryujinx-emu':
        result['hud_support'] = False
    else:
        result.setdefault('hud_support', True)

    return result


defaults.load_system_defaults = switch_load_system_defaults

# ----------------------------------------------------------
# Launch native Batocera v44
# ----------------------------------------------------------
# All v44 functionality remains intact.
# ----------------------------------------------------------

if __name__ == '__main__':
    runpy.run_module('batocera_launch', run_name='__main__')
