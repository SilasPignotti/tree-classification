# 📋 CLAUDE.md

## Project Overview

**Master's thesis project:** Cross-city transferability of tree species classification models using remote sensing data (Sentinel-2, LiDAR CHM, tree cadastres) across German cities.

**Target region:** Wismar (Baltic coast)  
**Primary training cities:** Hamburg, Berlin  
**Test city:** Rostock (proxy for Wismar)  
**Methods:** Random Forest vs. 1D-CNN

## Core Development Philosophy

### KISS (Keep It Simple, Stupid)

Simplicity should be a key goal in design. Choose straightforward solutions over complex ones whenever possible. Simple solutions are easier to understand, maintain, and debug.

### YAGNI (You Aren't Gonna Need It)

Avoid building functionality on speculation. Implement features only when they are needed, not when you anticipate they might be useful in the future.

## Code Structure & Modularity

### File and Function Limits

- **Never create a file longer than 500 lines of code**. If approaching this limit, refactor by splitting into modules.
- **Functions should be under 50 lines** with a single, clear responsibility.
- **Classes should be under 100 lines** and represent a single concept or entity.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
- **Line lenght should be max 100 characters** ruff rule in pyproject.toml

### Design Principles

- **Dependency Inversion**: High-level modules should not depend on low-level modules. Both should depend on abstractions.
- **Open/Closed Principle**: Software entities should be open for extension but closed for modification.
- **Single Responsibility**: Each function, class, and module should have one clear purpose.
- **Fail Fast**: Check for potential errors early and raise exceptions immediately when issues occur.

### Code Style

- **Clean & efficient:** Vectorized ops (NumPy/Pandas), no loops
- **Geodata:** Use `rasterio`/`rioxarray` for rasters, `geopandas` for vectors
- **Documentation:** Concise markdown cells, inline comments for non-obvious logic
- **Naming:** Explicit (e.g., `CHM_1m_Hamburg.tif`, not `chm_hh.tif`)

## Project Structure

```
project/
├── data/
│   ├── raw/              # DOM, DGM, tree cadastres (not in git)
│   └── processed/        # CHM, aligned features (not in git)
├── scripts/              # Standalone data processing scripts
├── notebooks/            # EDA, experiments, visualizations
├── src/                  # Reusable modules (preprocessing, models, eval)
└── docs/                 # Method documentation, experiment logs
```

## Communication

- **Language:** German for markdown/comments, English for code/variables
- **Tone:** Research-oriented, precise terminology from docs/Projektdesign.json`
- **Decisions:** Always map to experimental structure before suggesting solutions

## Development Environment

### UV Package Management

This project uses UV for blazing-fast Python package and environment management.

```bash
# Create virtual environment
uv venv

# Sync dependencies
uv sync

# Add a package ***NEVER UPDATE A DEPENDENCY DIRECTLY IN PYPROJECT.toml***
# ALWAYS USE UV ADD
uv add requests

# Add development dependency
uv add --dev pytest ruff mypy

# Remove a package
uv remove requests

# Run commands in the environment
uv run python script.py
uv run pytest
uv run ruff check .

# Install specific Python version
uv python install 3.12
```

## Style & Conventions

### Python Style Guide

- **Follow PEP8** with these specific choices:
  - Line length: 100 characters (set by Ruff in pyproject.toml)
  - Use double quotes for strings
  - Use trailing commas in multi-line structures
- **Always use type hints** for function signatures and class attributes
- **Format with `ruff format`** (faster alternative to Black)
- **Use `pydantic` v2** for data validation and settings management

### Naming Conventions

- **Variables and functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private attributes/methods**: `_leading_underscore`
- **Type aliases**: `PascalCase`
- **Enum values**: `UPPER_SNAKE_CASE`

## Documentation Standards

### Code Documentation

- Every module should have a docstring explaining its purpose
- Public functions must have complete docstrings
- Maintain CHANGELOG.md for version history

### Docstring Standards

Use Google-style docstrings for all public functions, classes, and modules:

```python
def calculate_discount(
    price: Decimal,
    discount_percent: float,
    min_amount: Decimal = Decimal("0.01")
) -> Decimal:
    """
    Calculate the discounted price for a product.

    Args:
        price: Original price of the product
        discount_percent: Discount percentage (0-100)
        min_amount: Minimum allowed final price

    Returns:
        Final price after applying discount

    Raises:
        ValueError: If discount_percent is not between 0 and 100
        ValueError: If final price would be below min_amount

    Example:
        >>> calculate_discount(Decimal("100"), 20)
        Decimal('80.00')
    """
```

## Useful Resources

### Essential Tools

- UV Documentation: https://github.com/astral-sh/uv

### Python Best Practices

- PEP 8: https://pep8.org/
- PEP 484 (Type Hints): https://www.python.org/dev/peps/pep-0484/
- The Hitchhiker's Guide to Python: https://docs.python-guide.org/

## Important Notes

- **NEVER ASSUME OR GUESS** - When in doubt, ask for clarification
- **Always verify file paths and module names** before use
- **Keep CLAUDE.md updated** when adding new patterns or dependencies

---

_This document serves as the entry point to comprehensive project documentation. Consult the referenced files for detailed guidance on specific topics._
