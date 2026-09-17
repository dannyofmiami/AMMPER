# Contributing to AMMPER

## Development setup

AMMPER is a pip-installable package (`pyproject.toml`, code under `src/ammper/`).
Install it in editable mode so changes to `src/` show:

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --upgrade pip       # editable installs need pip >= 21.3; many
                                 # systems still ship an older default pip
pip install -e ".[dev]"
```

The `dev` extra brings in `pytest` and `ruff`. `import ammper` and
`from ammper import paths` then work from any working directory

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

`pyproject.toml`'s `[tool.ruff]` section scopes the ruleset to
pyflakes/pycodestyle errors and import sorting (`E4`, `E7`, `E9`, `F`, `I`)

## Project layout

See the "Layout" section of `README.md` for what lives where
(`src/ammper/` the model, `analysis/` the figure pipelines, `gui/` the PyQt5
interface, `data/` and `results/` inputs/outputs).

## Paths

Never hardcode paths to `data/`, `results/`, or `figures/`. Import the path
helper instead:

```python
from ammper import paths as P
df = pd.read_csv(P.ab_experimental("AlamarblueRawdataWTKGy.csv"))
```

(Older scripts outside `src/ammper/` still do `import ammper_paths as P`,
which is a thin backward-compatible shim over `ammper.paths` — new code
inside `src/ammper/` should use the `from ammper import paths` form.)

## Commits and PRs

Open a PR against `main`. CI (`.github/workflows/ci.yml`) installs the
package and runs `pytest` on Python 3.9 and 3.11. Ensure it passes before review.
