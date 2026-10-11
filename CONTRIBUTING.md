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

## RITRACKS data (150 MeV tutorial folder vs. the Zenodo dataset)

The full RITRACKS dataset (49 proton-energy folders, ~3.8GB on disk) is published on Zenodo,
concept DOI [10.5281/zenodo.22992521](https://doi.org/10.5281/zenodo.22992521) (always the latest
version; cite this), pinned here to version `10.5281/zenodo.22992522`. The record holds one zip per
energy (`<energy>.zip`, containing a single top-level `<energy>/` folder), ~1.3GB in total. Only the
150 MeV Proton folder (`data/radiation_input/ritracks/150/`, ~11MB) is needed for 150 MeV Proton and
Gamma; GCRSim needs 14 folders (~119MB download) and Deep Space 10 (~193MB). Today this repo still
ships all 49 folders; do not remove any until the trim to `150/` is agreed and merged.

`data/radiation_input/MANIFEST.json` is the source of truth: `zenodo_doi` (pinned version),
`zenodo_concept_doi`, `zenodo_record_id`, the folder lists, and a `files` block with each zip's
`size`, `md5` (as Zenodo reports it) and `sha256`. `ammper data pull [gcrsim|deep-space|ENERGY...]`
downloads from that record, checks size and sha256, and extracts atomically; `ammper run` and the GUI
offer to run it when a run needs folders that are missing.

If the Zenodo deposit is ever re-published (a new version), regenerate the `files` block and the DOI
fields in `MANIFEST.json`, e.g. from the record's API (`https://zenodo.org/api/records/<id>`) plus a
sha256 of each downloaded zip, then re-run the tests. Nothing else needs to change. Keep macOS junk
(`.DS_Store`) out of the zips; `ammper data pull` skips it, but it should not be uploaded.
Shrinking `.git` itself (rewriting history to drop the old data blobs, which also live under the old
`radiationData/` path) is a separate step, not yet done.

Any change to a shared simulation entry point that touches `radType` or the
RITRACKS read path should also be checked against `gui/AMMPERGUI.py` and
`gui/AMMPERrunsGUI.py` — both duplicate the simulation loop from
`src/ammper/` rather than importing it, so a signature change made only in
`src/` silently breaks the GUI. Grep the whole repo, not just `src/`.

## Commits and PRs

Open a PR against `main`. CI (`.github/workflows/ci.yml`) installs the
package and runs `pytest` on Python 3.9 and 3.11. Ensure it passes before review.
