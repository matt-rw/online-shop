# Code Quality & Linting Guide

## Overview

This project uses several code quality tools to maintain consistent, clean, and error-free code:

**Python:**
- **Black**: Code formatter (opinionated, PEP 8 compliant)
- **isort**: Import statement organizer
- **Flake8**: Style guide enforcement (PEP 8)
- **mypy**: Static type checker
- **pylint**: Code analysis tool

**HTML/Templates:**
- **djLint**: Django/Jinja template formatter and linter

**Git Hooks:**
- **pre-commit**: Automatic checks before each commit

---

## Quick Start

### 1. Install Dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run All Checks

```bash
# Format Python code
black .
isort .

# Format HTML templates
djlint --reformat templates/ shop/templates/ online_shop/templates/

# Check for style issues
flake8 .
djlint --lint templates/ shop/templates/ online_shop/templates/

# Run type checking (optional)
mypy shop/ online_shop/

# Run code analysis (optional)
pylint shop/ online_shop/
```

### 3. Set Up Pre-Commit Hooks (Recommended)

Pre-commit hooks run automatically before each commit:

```bash
source venv/bin/activate
pre-commit install
```

Now the hooks will run automatically on `git commit`. To run manually:

```bash
pre-commit run --all-files
```

---

## Individual Tool Usage

### Black (Code Formatter)

**Format all files:**
```bash
black .
```

**Check without modifying (CI mode):**
```bash
black --check .
```

**Format specific files/directories:**
```bash
black shop/views.py shop/models/
```

**Configuration**: `pyproject.toml` → `[tool.black]`

---

### isort (Import Organizer)

**Sort all imports:**
```bash
isort .
```

**Check without modifying:**
```bash
isort --check-only .
```

**Show diff of changes:**
```bash
isort --diff .
```

**Configuration**: `pyproject.toml` → `[tool.isort]`

Import order:
1. Future imports
2. Standard library
3. Django
4. Wagtail
5. Third-party
6. First-party (your app)
7. Local folder

---

### Flake8 (Style Checker)

**Check all files:**
```bash
flake8 .
```

**Check specific files:**
```bash
flake8 shop/views.py
```

**Show statistics:**
```bash
flake8 --statistics .
```

**Configuration**: `.flake8`

Common issues:
- `E501`: Line too long (handled by black)
- `F401`: Imported but unused
- `E128`: Continuation line indentation

---

### mypy (Type Checker)

**Type check all files:**
```bash
mypy shop/ online_shop/
```

**Check specific file:**
```bash
mypy shop/views.py
```

**Show error codes:**
```bash
mypy --show-error-codes shop/
```

**Configuration**: `pyproject.toml` → `[tool.mypy]`

Note: Type hints are optional but recommended for critical functions.

---

### pylint (Code Analysis)

**Analyze all files:**
```bash
pylint shop/ online_shop/
```

**Analyze specific module:**
```bash
pylint shop.views
```

**Generate report:**
```bash
pylint shop/ --output-format=text > pylint-report.txt
```

**Configuration**: `pyproject.toml` → `[tool.pylint]`

---

### djLint (HTML/Template Formatter & Linter)

**Format all templates:**
```bash
djlint --reformat templates/ shop/templates/ online_shop/templates/
```

**Check without modifying:**
```bash
djlint --check templates/ shop/templates/ online_shop/templates/
```

**Lint for errors:**
```bash
djlint --lint templates/ shop/templates/ online_shop/templates/
```

**Format specific file:**
```bash
djlint --reformat templates/home/home_page.html
```

**Check specific file:**
```bash
djlint --check templates/home/home_page.html
```

**Configuration**: `.djlintrc` (JSON format)

**What it does:**
- Formats HTML/Django templates consistently
- Adds blank lines after `{% load %}`, `{% extends %}`, `{% include %}`
- Adds blank lines before/after `{% block %}` tags
- Enforces consistent indentation (2 spaces)
- Validates Django template syntax
- Checks for accessibility issues
- Formats embedded CSS and JavaScript
- Normalizes HTML tag names (e.g., `doctype` → `DOCTYPE`)

**Common issues caught:**
- Inconsistent indentation
- Missing blank lines between template tags
- Long lines (>120 chars)
- Accessibility warnings (e.g., missing alt attributes)

**Ignored rules** (configured in `.djlintrc`):
- `H006`: img tag should have height and width attributes (optional for responsive images)
- `H030`: Consider adding a lang attribute to the html tag (handled in base template)
- `H031`: Consider adding meta tags (handled in base template)
- `T002`: Double quotes should be used in tags (Tailwind uses single quotes in classes)

---

## Pre-Commit Hooks

### Installation

```bash
pre-commit install
```

### What Gets Checked

Before each commit, the following run automatically:

1. **Trailing whitespace removal**
2. **End-of-file fixer**
3. **YAML/JSON/TOML validation**
4. **Large file detection** (max 5MB)
5. **Merge conflict detection**
6. **Private key detection**
7. **Black formatting** (Python code)
8. **isort import sorting** (Python imports)
9. **Flake8 linting** (Python style)
10. **djLint formatting** (HTML/Django templates)
11. **djLint linting** (Template validation)
12. **Django system checks**
13. **Migration checks**

### Manual Run

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Run specific hook
pre-commit run black --all-files
```

### Skip Hooks (Emergency Only)

```bash
# Skip all hooks
git commit --no-verify -m "message"

# Skip specific hooks
SKIP=flake8,mypy git commit -m "message"
```

---

## GitHub Actions CI/CD

**File**: `.github/workflows/ci.yml`

### What Runs on Every Push/PR

1. **Code quality checks**:
   - Black (check only, doesn't auto-format)
   - isort (check only)
   - Flake8 linting

2. **Django checks**:
   - System check
   - Missing migrations check
   - Tests (if any)
   - Static files collection

3. **Security checks**:
   - Dependency vulnerability scanning (safety)

### View Results

- Go to GitHub → **Actions** tab
- See all workflow runs
- Click on any run to see details
- Fix any failures shown

### Local Simulation

Run the same checks locally before pushing:

```bash
# Code quality
black --check .
isort --check-only .
flake8 .

# Django checks
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput

# Security
pip install safety
safety check
```

---

## Configuration Files

### `pyproject.toml`

Contains configuration for:
- Black formatting (line length, target version)
- isort import sorting (sections, profiles)
- mypy type checking (strictness level)
- pylint code analysis (rules, ignores)

### `.flake8`

Flake8-specific configuration:
- Line length (matches black: 100)
- Ignored error codes
- Excluded directories
- Complexity limits

### `.pre-commit-config.yaml`

Defines all pre-commit hooks:
- Which tools run
- Tool versions
- Arguments/options
- File exclusions

---

## Common Workflows

### Before Committing

```bash
# 1. Format your code
black .
isort .

# 2. Check for issues
flake8 .

# 3. Run Django checks
python manage.py check

# 4. Commit (pre-commit will run automatically)
git add .
git commit -m "Your message"
```

### Fixing Issues

**Black formatting issues:**
```bash
black .  # Auto-fixes all formatting
```

**Import sorting issues:**
```bash
isort .  # Auto-fixes all imports
```

**Flake8 issues:**
```bash
flake8 .  # Shows issues, fix manually
```

### Ignoring Specific Issues

**Inline ignore (Flake8):**
```python
result = some_long_function(arg1, arg2, arg3)  # noqa: E501
```

**File-level ignore (Flake8):**
```python
# flake8: noqa
```

**Type ignore (mypy):**
```python
result = some_function()  # type: ignore
```

---

## Best Practices

1. **Run formatters first**: `black`, `isort`, and `djlint --reformat` auto-fix most issues
2. **Check before committing**: Use pre-commit hooks
3. **Fix incrementally**: Don't try to fix everything at once
4. **Use CI/CD**: Let GitHub Actions catch issues early
5. **Don't disable checks**: Unless absolutely necessary
6. **Add type hints**: To critical functions over time
7. **Review linter warnings**: They often catch real bugs
8. **Format templates**: Run djLint on new/modified templates before committing

---

## Troubleshooting

### "pre-commit not found"

```bash
source venv/bin/activate
pip install pre-commit
pre-commit install
```

### "Black would reformat many files"

This is normal for a new setup. Run:
```bash
black .
git add .
git commit -m "Apply black formatting"
```

### "Import sorting conflicts with black"

This shouldn't happen with our config (isort uses black profile). If it does:
```bash
isort --profile black .
```

### "Flake8 errors in migrations"

Migrations are excluded in `.flake8`. If you see errors, check the exclude list.

### "Too many linting errors"

Fix gradually:
1. Run `black .` and `isort .` first (auto-fixes most)
2. Commit those changes
3. Fix remaining flake8 issues incrementally
4. Address pylint/mypy warnings over time

---

## Cheat Sheet

```bash
# Format everything (Python + HTML)
black . && isort . && djlint --reformat templates/ shop/templates/ online_shop/templates/

# Check everything (no changes)
black --check . && isort --check-only . && flake8 . && djlint --check templates/ shop/templates/ online_shop/templates/

# Install pre-commit hooks
pre-commit install

# Run pre-commit manually
pre-commit run --all-files

# Skip pre-commit (emergency only)
git commit --no-verify -m "message"

# Check Django
python manage.py check

# Security scan
safety check
```

---

## Current Status

After initial setup, the codebase has:

- ✅ **Linting tools installed** (black, isort, flake8, mypy, pylint, djlint)
- ✅ **Configuration files created** (pyproject.toml, .flake8, .djlintrc)
- ✅ **Pre-commit hooks configured** (.pre-commit-config.yaml)
- ✅ **GitHub Actions CI/CD** (.github/workflows/ci.yml)
- ✅ **Python code formatted** (black, isort applied)
- ✅ **HTML templates formatted** (djlint applied to 43 files)
- ⚠️  **~302 flake8 issues remain** (mostly unused imports, can be fixed incrementally)

### Recommended Next Steps

1. **Install pre-commit hooks**: `pre-commit install`
2. **Test pre-commit**: Make a small change and commit to see hooks in action
3. **Fix flake8 issues**: Incrementally over time (remove unused imports, etc.)
4. **Add type hints**: To critical functions gradually
5. **Review GitHub Actions**: Push to see CI/CD pipeline in action

---

## Resources

- [Black documentation](https://black.readthedocs.io/)
- [isort documentation](https://pycqa.github.io/isort/)
- [Flake8 documentation](https://flake8.pycqa.org/)
- [mypy documentation](https://mypy.readthedocs.io/)
- [pylint documentation](https://pylint.pycqa.org/)
- [djLint documentation](https://djlint.com/)
- [pre-commit documentation](https://pre-commit.com/)
- [PEP 8 Style Guide](https://peps.python.org/pep-0008/)
