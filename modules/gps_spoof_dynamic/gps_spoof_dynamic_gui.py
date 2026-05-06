"""
Wrapper GUI for gps_spoof_dynamic.

Reuses the shared GPS spoof GUI implementation in modules/gps_spoof/gps_spoof_gui.py.
"""

import os
import importlib.util


def prompt_config(parent):
    shared_gui_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "gps_spoof",
        "gps_spoof_gui.py",
    )
    shared_gui_path = os.path.normpath(shared_gui_path)

    spec = importlib.util.spec_from_file_location("gps_spoof_gui_shared", shared_gui_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.prompt_config(parent)
