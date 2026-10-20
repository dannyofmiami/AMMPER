# Contributing to AMMPER

## Development setup

AMMPER is a pip-installable package (`pyproject.toml`, code under `src/ammper/`).
Install it in editable mode so changes to `src/` show:

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Running tests

```bash
pytest
```

Tests live in `tests/` and target the simulation engine in `src/ammper/`
(`pyproject.toml`'s `[tool.pytest.ini_options]` points pytest there). New
logic in `src/ammper/` should come with a test in `tests/` covering it.

## Linting

```bash
ruff check .
```

## Project layout

See the "Layout" section of `README.md` for what lives where
(`src/ammper/` the model, `analysis/` the figure pipelines, `gui/` the PyQt5
interface, `data/` and `results/` inputs/outputs).

## Paths

Don't hardcode paths to `data/`, `results/`, or `figures/`. Import the path
helper instead:

```python
from ammper import paths as P
df = pd.read_csv(P.ab_experimental("AlamarblueRawdataWTKGy.csv"))
```

(Older scripts outside `src/ammper/` still do `import ammper_paths as P`,
which is a thin backward-compatible shim over `ammper.paths` — new code
inside `src/ammper/` should use the `from ammper import paths` form.)

## RITRACKS data (what a clone carries vs. the Zenodo dataset)

The full RITRACKS dataset (49 proton-energy folders, ~3.8GB on disk) is published on Zenodo,
concept DOI [10.5281/zenodo.22992521](https://doi.org/10.5281/zenodo.22992521) (cite this).

Which folders a radiation type reads comes from the tables (`ammper.data_check`).

## Packaging: what ships inside the package

Everything `ammper setup`, `quickstart`, `run` and `gui` need at run time lives **inside**
`src/ammper/` so a normal install (a wheel, `pip install .`) works from any folder, not just a clone:

## Commits and PRs

Open a PR against `main`. CI (`.github/workflows/ci.yml`) installs the
package and runs `pytest` on Python 3.9 and 3.11. Ensure it passes before review.
