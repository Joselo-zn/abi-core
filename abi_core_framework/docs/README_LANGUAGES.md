# Multi-Language Documentation

ABI-Core documentation is available in multiple languages.

## Available Languages

- **English** (default): [index.md](index.md)
- **Español**: [index_es.md](index_es.md)

## Structure

```
docs/
├── index.md                    # English main index
├── index_es.md                 # Spanish main index
├── getting-started/            # English docs
├── single-agent/
├── multi-agent-basics/
├── ...
└── es/                         # Spanish docs
    ├── getting-started/
    ├── single-agent/
    ├── multi-agent-basics/
    └── ...
```

## Building Documentation

### English (default)
```bash
cd docs
make html
```

### Spanish
```bash
cd docs
sphinx-build -b html -D language=es . _build/html/es
```

## ReadTheDocs Configuration

In `.readthedocs.yaml`:

```yaml
version: 2

sphinx:
  configuration: docs/conf.py

formats:
  - pdf
  - epub

python:
  version: "3.11"
  install:
    - requirements: docs/requirements.txt
```

---

**Maintained by**: José Luis Martínez (jl.mrtz@gmail.com)
