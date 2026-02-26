import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "fastapi-import-export"
author = "lijianqiao"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
]
autosummary_generate = False
autodoc_typehints = "description"
templates_path = ["_templates"]
exclude_patterns = []
html_theme = "alabaster"
