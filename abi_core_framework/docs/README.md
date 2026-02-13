# ABI-Core Documentation

This directory contains the source files for the ABI-Core documentation, built with [Sphinx](https://www.sphinx-doc.org/) and hosted on [Read the Docs](https://readthedocs.org/).

## Building Documentation Locally

### Prerequisites

```bash
pip install -r requirements.txt
```

### Build HTML

```bash
cd docs
make html
```

The built documentation will be in `_build/html/`. Open `_build/html/index.html` in your browser.

### Build PDF

```bash
make latexpdf
```

### Clean Build

```bash
make clean
```

## Documentation Structure

```
docs/
├── conf.py                 # Sphinx configuration
├── index.md               # Documentation home page
├── requirements.txt       # Documentation dependencies
├── getting-started/       # Getting started guides
├── user-guide/           # User guides
├── architecture/         # Architecture documentation
├── api/                  # API reference
└── development/          # Development guides
```

## Contributing to Documentation

1. Edit the relevant `.md` files
2. Build locally to preview changes
3. Submit a pull request

## Style Guide

- Use Markdown (MyST) for content
- Use code blocks with language specifiers
- Include examples where possible
- Keep line length reasonable (~80-100 chars)
- Use proper heading hierarchy

## Links

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [MyST Parser](https://myst-parser.readthedocs.io/)
- [Read the Docs](https://docs.readthedocs.io/)
