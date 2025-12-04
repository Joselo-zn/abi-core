# Configuration file for the Sphinx documentation builder.

# -- Project information -----------------------------------------------------
project = 'ABI-Core'
copyright = '2025, José Luis Martínez'
author = 'José Luis Martínez'
release = '0.1.0b121'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_copybutton',
    'sphinx_design',
    'myst_parser',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
html_theme = 'furo'
html_static_path = ['_static']

# -- Options for MyST parser -------------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

# -- Internationalization ----------------------------------------------------
language = 'en'  # Default language
locale_dirs = ['locales/']   # Path to translations
gettext_compact = False      # Optional

# Supported languages
# To build Spanish version: sphinx-build -b html -D language=es docs docs/_build/html/es
