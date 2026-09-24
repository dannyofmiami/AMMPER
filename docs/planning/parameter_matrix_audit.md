# Parameter-matrix audit: what's actually implemented vs. assumed

**Status:** audit complete for the scope below. Triggered by a Windows user
hitting a crash on "Complex ROS" that turned out to be unfinished WIP code
nobody had ever run to completion. That raised the obvious question — what
else in this "production readiness" branch has never actually been
exercised? This document is the answer, as far as it goes.

Related: [[Cellrepair algorithm swap]], [[project_ab_kinetic_model_ignores_dead_cells]]
(same "assumed tested, wasn't" pattern, found in the sibling AMMPER 3.0 work).

---

## 1. Why wasn't Complex ROS tested before — direct answer

Traced through git history (see full detail in the session that found this):

- The diffusion-grid `genROS.py` (the code Complex ROS actually runs) was
  introduced in `MarcellLoza`'s commit `3a5460d`, **titled "WIP: Saving
  progress"**, July 7, 2025. The code's own comments describe it as
  in-progress research ("Step 1: Incorporate green function propagator
  without time dependence... Challenge: How to do lattice and green
  function propagator?"). It replaced a much simpler 49-line v1.0 model that
  had no diffusion grid at all.
- It was carried into this repo unchanged by the August 2026 reorg
  (`5e80c38`, "Port AMMPER-2 organizational changes") — a pure file move,
  confirmed via `git blame` and diff; the algorithm itself was never touched
  or fixed after the WIP commit.
- **422 archived simulation runs in `results/bulk_aB/` used Basic ROS. Zero
  used Complex ROS** until today's manual test. `revisions_2026/` (the
  manuscript pipeline) never references `ROSType` or Complex ROS at all.
- Nothing in `BUGS_AND_CORRECTIONS.md`, the README, or any planning doc
  mentions `genROS` or Complex ROS.

**Plain answer: it was never tested because nobody had ever run it to
completion before today.** It shipped as a selectable GUI/CLI option
anyway, which is what made it look finished when it wasn't. It's now fixed
(the crash) and disabled everywhere (the underlying performance problem) —
see §2.

This is not an isolated case — the same "wired up as an option but never
actually exercised" pattern shows up again in §3 below, in a completely
different part of the codebase (GUI, not simulation engine), independently
discovered.

## 2. Complex ROS — status

Two separate real bugs, found in this order:

1. **Crash**: `train_test_split(ROSData, train_size=0.5)` throws when
   `ROSData` decays to exactly 1 row (can't split 1 item 50/50). **Fixed**
   in all 6 duplicate call sites (`src/ammper/AMMPER.py`, `AMMPERCLI.py`,
   `AMMPERBulk_aB.py`, `AMMPERBulk_GAMMAfinal.py`, `gui/AMMPERGUI.py`,
   `gui/AMMPERrunsGUI.py`) — guarded with a direct coin-flip when only one
   ROS event remains, matching the intended half-life semantics.
2. **Performance**: `genROS()` (`src/ammper/genROS.py:64`) expands every
   single radiation event into an 81-point diffusion grid via `np.vstack`
   *inside* a Python loop (O(n²)), and 150 MeV Proton's `energyThreshold=0`
   means it receives *every* raw RITRACKS physics event unfiltered —
   plausibly hundreds of thousands of rows per run. Observed: 8+ minutes of
   CPU time and 7.4GB+ of climbing memory on a single 30 Gy run before it
   was killed. **Not fixed** — this needs a vectorized rewrite of the
   diffusion-grid generation, which is real engineering work, not a
   one-line patch.

**Decision (made explicitly): disable Complex ROS as a selectable option
everywhere, rather than rewrite it right now**, since it was never
manuscript-relevant (see §1) and the rewrite is nontrivial. Removed from:

| File | What changed |
|---|---|
| `src/ammper/cli.py` | `ROS_TYPES` dict — `"complex"` entry removed, so `--ros-type` only accepts `basic` |
| `src/ammper/AMMPERCLI.py`, `AMMPER.py` | `Prompt.ask` choices narrowed to `["a"]`, prompt text no longer mentions Complex ROS |
| `src/ammper/AMMPERBulk_aB.py`, `AMMPERBulk_GAMMAfinal.py` | passing `ROSType='b'` now raises a clear `ValueError` instead of silently running the broken path (these take a raw positional arg with no prompt, so this is the only guard available) |
| `gui/AMMPERGUI.py`, `gui/AMMPERrunsGUI.py` | "Complex" radio button disabled (`setEnabled(False)`), relabeled "Complex (unavailable)", "Basic" set as the default-checked option |
| `gui/vgui_form.py`, `gui/formgui.py`, `gui/form.ui` | matching widget-level `setEnabled(False)` / label text, so the change survives if the GUI is ever regenerated from the `.ui` source |

Verified: all 9 touched Python files compile; `--ros-type complex` is
rejected by argparse; the CLI prompt rejects `b` and re-prompts; an
offscreen PyQt instantiation of `AMMPERGUI.Widget` confirms
`ROSType == "Basic ROS"` by default, `radioButton_8.isEnabled() == False`.

### Regression this change caused, found and fixed 2026-09-24

**The GUI's Launch button could never be enabled, so `ammper gui` couldn't
start a simulation from 2026-09-23 to 2026-09-24.** The only thing that
ever enabled Launch was `onRadioButtonClicked3` (the ROS-model handler).
Pre-selecting "Basic" at startup meant that handler fired during
`__init__`, before `pushButton_4.setEnabled(False)` further down, and
clicking the already-selected "Basic" never fires it again. The
verification above missed it because it checked widget state and called
the launch code directly, never clicking Launch. It was caught while taking
README screenshots: the setup screen showed Launch greyed out with every
option selected. Confirmed against the last commit: before the change,
clicking Basic enabled Launch; after it, nothing could.

**Fix:** `_updateLaunchEnabled()` now enables Launch once radiation type,
cell type, and ROS model are all set, and all three radio handlers call
it. Verified by clicking through with real `.click()`: fresh window →
disabled; Gamma → disabled; rad51 → enabled; Launch click → the simulation
runs to the results page at the chosen 5 Gy. A window with only a cell
type picked stays disabled. That's slightly stricter than before, when
Launch could be enabled with no radiation type chosen.

**Also fixed in the same pass:** the longer "Complex (unavailable)" label
was truncated to "Complex (u" because the radio button was a fixed 89 px
wide. It now sits at `x=240`, `width=175` (measured text width: 165 px
in IBM Plex Sans 14 pt), still inside its 421 px group box, in both
`vgui_form.py` and `form.ui`.

**Lesson:** GUI changes need a click-through test, not just state checks.

**A second miss from the same change:** removing `"complex"` from
`cli.py`'s `ROS_TYPES` broke `tests/test_cli.py::
test_quickstart_maps_flags_to_the_legacy_argv_contract`, which passed
`--ros-type complex` to check the flag-to-argv mapping. The test suite
wasn't run after the change, only a compile check. It was found on
2026-09-24. The test now uses `--ros-type basic` (expecting ROS code `a`),
and a new `test_quickstart_rejects_the_disabled_complex_ros_model` checks
that `complex` is rejected with exit code 2 and never reaches the
simulator. 32/32 tests pass.

## 3. `AMMPERrunsGUI.py` cannot be instantiated at all — separate, unrelated finding

While verifying the Complex ROS GUI fix, an offscreen PyQt smoke test of
`AMMPERrunsGUI.Widget()` (the multi-run / "Total Runs" batch GUI) crashed
immediately:

```
AttributeError: 'Ui_Widget' object has no attribute 'verticalSlider'
```

A static diff of every `self.ui.X` reference in `AMMPERrunsGUI.py` against
every widget actually defined in `formgui.py` (its generated form) found
**10 missing widgets**, not just the one that happened to crash first:

`verticalSlider`, `plainTextEdit`, `label_42`, `label_43`, `label_44`,
`label_45`, `label_46`, `label_47`, `checkBox_3`, `groupBox_2`

By contrast, the same check against `AMMPERGUI.py` / `vgui_form.py` (the
GUI `ammper gui` actually launches) found **zero** missing references.

### When this broke — corrected after checking history

An earlier draft of this section said the break came from the `5e80c38`
reorg. That was wrong. Running the same static check at every commit that
touched these files:

| Commit | Missing widgets |
|---|---|
| `3a5460d` (MarcellLoza, Jul 2025 — oldest version in any repo we have, `bin/formgui.py`) | same 10 |
| `5e80c38` (reorg, Aug 2026) | same 10 |
| `a752e0a` (GUI overhaul, Sep 20 2026) | same 10 |

`formgui.py`'s own header says it was generated from `formgui.ui` — **a
file that has never been committed to any repo we have.** So this class
has most likely never worked in any version we can see: the form it was
written against was lost before it ever reached git, and the `formgui.py`
that did get committed is a different layout.

### It's also not reachable

An earlier draft said it's launched from `AMMPERGUI`'s second button. Also
wrong — that button launches the CLI. Nothing imports or launches
`AMMPERrunsGUI.py`: `ammper gui` opens only `AMMPERGUI.py`, and no button,
CLI subcommand, or `pyproject.toml` entry point references it. The only
way to reach it is `python gui/AMMPERrunsGUI.py` by hand.

### This was already known

The Sep 20 GUI overhaul (`a752e0a`) did real work in this file — the
`sys.executable` subprocess fix, the results-folder naming change, the
`processEvents()` progress-bar fix, the `radType` argument fix for
`cellROS`, IBM Plex font registration — applied for parity with the other
five entry points. That session's own write-up
(`gui_accessibility_audit.md`, on the AMMPER 3.0 branch's doc tree)
already recorded this file as "unreachable from `ammper gui`" and
"separately confirmed unreachable/broken (throws on `Widget()`
construction)", and scoped it out. What's new here is the full list of
missing widgets and the finding that it was never working to begin with.

`@TODO` left at the crash point (`gui/AMMPERrunsGUI.py`, the
`verticalSlider` line). **Not fixed.**

### The batch feature itself was never implemented either

Beyond the missing widgets, reading the class logic shows that even a
rebuilt form wouldn't give a working batch GUI:

- **"Total Runs" does nothing.** The dial sets `self.simAmt`
  (`dialChange`, ~line 415), but `simSetup()` never loops over it. Every
  launch would run exactly one simulation regardless of the dial.
- **The dose sweep doesn't exist.** The form has "Starting Dosage" and
  "Ending Dosage" fields, but there's no loop between them — only the
  single `self.radAmount` is used.
- **More crashes are waiting past the first one.** `setLabelText` is
  called on plain `QLabel`s (~lines 490–968, e.g. the end-of-run totals).
  That method belongs to `QProgressDialog`/`QInputDialog`, not `QLabel`, so
  it would raise `AttributeError` at the end of every run.
  `self.setEnabled.checkBox_4(True)` (~line 451) is also invalid, and would
  raise as soon as the "Plotting" checkbox is toggled.

### Decision (2026-09-24)

**Batch runs will move to the CLI in AMMPER 3.0, e.g. `ammper run
--replicates N`. They will not be built back into this GUI.**
`AMMPERrunsGUI.py` stays as-is on this branch: no deletion, no rebuild, no
further edits. Nothing launches it, so leaving it in place costs nothing
for production readiness.

The full design, including the requirements the old batch scripts
(`AMMPERruns_aB.py`, `AMMPERruns_GAMMAFINAL.py`) already fail on Windows
and macOS, is in `docs/planning/batch_runs_cli_design.md` on the
`feature/ammper-3.0` branch's doc tree, linked from its
`ammper_3.0_roadmap.md`.

Edits already made to this file today and kept: the Complex ROS
radio-button disable and prompt cleanup (§2), the `train_test_split`
guard (§2), and the `@TODO` at the crash point. None of these change
behavior, since the class can't be instantiated.

## 4. Gamma's `radGen` disagrees across the codebase

Found while checking the GUI's radType handling for other silent
divergences from the CLI (per the existing [[Search whole repo for call
sites]] rule). For the identical nominal "Gamma" configuration:

| File | `radGen` |
|---|---|
| `src/ammper/AMMPERCLI.py` | **10** |
| `gui/AMMPERGUI.py` | **10** |
| `gui/AMMPERrunsGUI.py` | **10** |
| `src/ammper/AMMPER.py` | **2** |
| `src/ammper/AMMPERBulk_aB.py` | **2** |
| `src/ammper/AMMPERBulk_GAMMAfinal.py` | **2** |

Every single one of these six files — including both sides of the split —
carries the same dead comment `#radGenE = 10` right next to the live
`radGen` assignment. That strongly suggests a `radGenE` variable was once
distinct from `radGen`, got collapsed into one, and different files
independently "resolved" the ambiguity to different values rather than
being kept in sync — a copy/paste divergence, not an intentional
per-script difference. `radGen` controls which generation radiation is
applied at, so this isn't cosmetic — it changes *when in the simulation*
Gamma exposure happens, for both the interactive CLI/GUI paths (10) and the
batch/manuscript-adjacent scripts (2).

**Not fixed** — which value is scientifically correct is a domain decision,
not something to silently pick. `@TODO` comments cross-referencing all six
sites left at each location (full detail in `AMMPERCLI.py`, shorter
pointers in the other five).

### Gamma's dose is also handled differently everywhere (found 2026-09-24)

Found while writing up the batch-runs design. The Gamma **dose** passed to
`GammaRadGen()` depends on which entry point you use:

| Entry point | Gamma dose actually simulated | Does the user see it? |
|---|---|---|
| `ammper run` → `AMMPERCLI.py` | **always 1 Gy** (hardcoded `dose = 1`) | No. There's no dose prompt for Gamma. |
| `ammper gui` → `gui/AMMPERGUI.py` | **always 1 Gy** (hardcoded) | No. The dose label reads **"0"** and the slider is disabled. |
| `AMMPERBulk_aB.py` | **always 1 Gy** (hardcoded; `argv[4]` is only read for Proton) | No |
| `AMMPER.py` | whatever the user types (a `FloatPrompt` mid-run, at `g == radGen`) | Yes |
| `AMMPERBulk_GAMMAfinal.py` (manuscript gamma batches) | `argv[4]`, the real requested dose | Yes |

So the two supported user-facing paths, `ammper run` and `ammper gui`,
always simulate Gamma at 1 Gy with no indication. The GUI even displays
0. The hardcodes date to the `5e80c38` reorg (`git blame`). Gamma was in
the §5 matrix below and "passed", but only in the sense that it didn't
crash. The test couldn't have caught the wrong dose, and that's exactly
the limit of crash-only testing.

**FIXED 2026-09-24.** Every supported entry point now uses the dose the
user asked for:

| Entry point | Now |
|---|---|
| `ammper run` → `AMMPERCLI.py` | Prompts for a Gamma dose right after radiation type, like Proton |
| `ammper gui` → `gui/AMMPERGUI.py` | Dose slider is enabled for Gamma, and "Radiation Dose (150 MeV Proton or Gamma)" replaces "(… Proton Only)" |
| `AMMPERBulk_aB.py` | Reads `argv[4]` for Gamma, same as Proton |
| `AMMPER.py` | Same prompt, moved from mid-simulation (it used to interrupt at the radiation generation) to up front, with the same validation |

Rules applied everywhere:

- **Range: greater than 0, up to 30 Gy.** `GammaRadGen(0)` can't build a
  field: it prints an error and returns a 1-D placeholder that crashes
  downstream indexing. The manuscript itself uses the 150 MeV Proton 0 Gy
  run as the gamma control (`ammper_ab_model_gamma.py`), so the error
  message points users there. The GUI enforces this by raising the
  slider's minimum to 2 (2.5 Gy) for Gamma, and it goes back to 1 for
  every other type. 30 Gy is the top of the experimental range.
- **The dose is recorded.** `simDescription.txt` gains a `Dose: X Gy` line
  for Proton and Gamma. The data file stays named `Gamma.txt`, unchanged,
  so nothing that reads it breaks. Nothing in the repo parses
  `simDescription.txt`, so the new line is safe to add.
- **The GUI's output video name is now correct too.** It used `self.Gy`,
  which was always 0 for Gamma, so videos were labeled `…_0Gy_…` for
  runs that were actually 1 Gy.

**Untouched on purpose:** `AMMPERBulk_GAMMAfinal.py` (the manuscript's
gamma runner already honored `argv[4]`, so leaving it alone keeps
manuscript outputs identical), and `gui/AMMPERrunsGUI.py` (still hardcodes
`dose = 1`, but per the §3 decision it isn't edited and can't launch).
`radGen` is also untouched, since that decision is still open (above).

**Verified by output, not just exit code:**

- `AMMPERBulk_aB.py d a a 0` exits 1 with the clear message.
- At 2.5 Gy vs 10 Gy, gen-15 healthy cells were 2,040 vs 137 (single
  replicates), a real dose response where both used to be 1 Gy.
- `ammper run`'s prompt rejects 0 and accepts 2.5, and
  `simDescription.txt` says `Dose: 2.5 Gy`.
- GUI (offscreen): Gamma enables the slider and blocks 0 (a request for
  value 1 clamps to 2), 30 Gy is reachable, and switching back to Proton
  restores 0. A full GUI Gamma run at 5 Gy called `GammaRadGen(5.0)`
  (captured via a wrapper). Before the fix it was always `GammaRadGen(1)`.
- Worst case, 30 Gy through `ammper run` (radiation lands at generation
  10 there, with hundreds of cells): completes in 68 s, so the 30 Gy
  ceiling is usable.

**Caveat, found 2026-09-24: the app's Gamma dose scale is not the
manuscript's.** `GammaRadGen` hardcodes the hit rate `k = 100` (the value
used in the originally submitted manuscript). The revised manuscript
rejects that value (`calibrate_gamma_hit_rate.py`: at `k = 100`, 20 Gy
leaves 1.3% of the population versus 76% measured) and uses a calibrated
shared rate **k ≈ 1.853** (`gamma_hit_rate_calibration.json`). It gets
there without touching the simulator, by running the unmodified
`AMMPERBulk_GAMMAfinal.py` at an *equivalent dose* = nominal × 1.853/100.
For example, the manuscript's "30 Gy" is a simulator dose of 0.556. So
after today's fix, a user who picks 30 Gy in `ammper run`/`ammper gui` gets
about **54× the energy-deposition events** of the manuscript's 30 Gy. The
dose is honored, but on the scale the revised manuscript says is wrong.
This is consistent with the 10 Gy test above leaving only 137 healthy
cells. **Not changed** — whether the app should apply the calibrated rate
is a manuscript/science decision. Changing `k` in `GammaRadGen` directly
would also change what `AMMPERBulk_GAMMAfinal.py` produces, which would
break the manuscript's equivalent-dose runs.

### Related, found while checking the manuscript gamma pipeline

`revisions_2026/code/run_gamma_simulations.py` points at
`src/AMMPERBulk_GAMMAfinal.py`, a pre-reorg path that no longer exists
(the file is at `src/ammper/`). Regenerating the gamma series with it
would fail immediately. **Not changed**, since it's manuscript code and
repointing it is the manuscript owners' call.

## 5. Full radType × cellType matrix — results

Every combination run through `AMMPERBulk_aB.py` with Basic ROS (Complex ROS
now disabled, per §2):

| radType | cellType | Result | Time |
|---|---|---|---|
| 150 MeV Proton | wt | PASS | 2.9s (0 Gy — see caveat below) |
| 150 MeV Proton | rad51 | PASS | 2.9s (0 Gy — see caveat below) |
| 150 MeV Proton | rad51 | PASS | 21.9s (**30 Gy, real dose**) |
| GCRSim | wt | PASS | 9.4s |
| GCRSim | rad51 | PASS | 9.2s |
| Deep Space | wt | PASS | 48.4s |
| Deep Space | rad51 | PASS | 53.4s |
| Gamma | wt | PASS | 10.2s |
| Gamma | rad51 | PASS | 2.5s |

**Caveat on the 0 Gy Proton rows**: 0 Gy skips the actual radiation-generation
code path entirely for Proton specifically (`if Gy != 0:` gates it) — those
two rows only confirm the surrounding scaffolding doesn't crash, not that
radiation/ROS/repair logic works. 150 MeV Proton at real doses was already
extensively exercised earlier this session — 20 replicate runs total across
0/30 Gy, WT, for the [[Cellrepair algorithm swap]] investigation — plus the
30 Gy rad51 run added here to close the cell-type gap. GCRSim, Deep Space,
and Gamma aren't gated by the Gy argument (they use their own fixed fluence
data), so their passes above do exercise real radiation generation.

**Not covered by this matrix**: Deep Space and GCRSim at non-zero/alternate
doses (not applicable — dose isn't a parameter for them), any dose besides
0/30 Gy for Proton, and no visual/UI-level GUI testing beyond the
instantiation smoke tests in §2–3 (button clicks, plot rendering, file
export dialogs, etc. — untested).

## 6. Which radiation types take a dose — code vs. manuscript (2026-09-24)

Short answer: **only 150 MeV Proton and Gamma have a dose setting**, both
in the code and in the manuscript. GCRSim and Deep Space each simulate one
fixed radiation environment, with no dose parameter at all.

### 6a. What the code supports (as of the 2026-09-24 Gamma dose fix)

| Radiation type | Dose setting? | Allowed doses | Generation radiation is applied | What determines the radiation |
|---|---|---|---|---|
| **150 MeV Proton** | Yes | **0, 2.5, 5, 10, 20, 30 Gy only** | 2 (same in every entry point) | Each dose maps to a fixed number of RITRACKS proton tracks: 0 / 1 / 2 / 4 / 8 / 12. `energyThreshold = 0`, so every deposition is kept. Any other value leaves `trackChoice` undefined and crashes `AMMPERBulk_aB.py`. The CLI and GUI only offer the six valid values. |
| **GCRSim** | No | one fixed environment | 2 | One randomly chosen track at each of the **14 proton energies** in `data/fluence/GCRSimFluence_data.txt` (20–1000 MeV/n), `energyThreshold = 20`. The GUI's dose box shows **"0.5"** for GCRSim. No code reads that value, and nothing documents what it means (Gy? a nominal label?). |
| **Deep Space** | No | one fixed environment | Chronic: **10 traversals spread across generations 1–14** | One traversal per row of `data/fluence/DeepSpaceFluence0.1months_data.txt` (42.76–120.35 MeV, at generations 1, 2, 4, 6, 8, 10, 11, 12, 13, 14). Omnidirectional tracks, `energyThreshold = 20`, **300 µm** simulation space (vs 64 µm for the others). A `DeepSpaceFluence0.2months_data.txt` (35 rows, 45 traversals) also exists, and **nothing uses it**. |
| **Gamma** | Yes (since 2026-09-24) | **>0 to 30 Gy, any value** | **10** in `ammper run`/`ammper gui`, **2** in the other scripts (open, §4) | Uniformly random depositions from `GammaRadGen`: `n_Hits = dose × k` per 1 µm plane, **`k = 100` hardcoded** (uncalibrated; see the §4 caveat). Before 2026-09-24 it was silently 1 Gy in `ammper run`, `ammper gui`, and `AMMPERBulk_aB.py`. |

### 6b. What the manuscript uses (`revisions_2026/main.tex`, `supplemental.tex`)

| Radiation type | Role in the manuscript | Doses |
|---|---|---|
| **150 MeV Proton** | **Main results**: every alamarBlue figure and fit | 0, 2.5, 5, 10, 20, 30 Gy; wild type and *rad51*Δ; 25–62 archived replicate runs per condition in `results/bulk_aB/{WT,rad51}_Basic_*` |
| **Gamma** | **Supplementary Text S2**, "The aB model transfers to a gamma radiation environment" | Nominal 2.5, 5, 10, 20, 30 Gy, both strains, with the **Proton 0 Gy run as the control**. Run at a **calibrated shared hit rate k ≈ 1.853** (`gamma_hit_rate_calibration.json`), implemented as "equivalent doses" (nominal × 1.853/100) passed to the unmodified `AMMPERBulk_GAMMAfinal.py`. An uncalibrated k = 100 series (0.01–30 Gy, `run_gamma_simulations.py`) exists only to show why k = 100 fails. |
| **GCRSim** | Named once in the Introduction ("three radiation environment models … NSRL GCRSim Proton") | **none**: no results, figures, or supplementary content (`supplemental.tex` has 0 mentions) |
| **Deep Space** | Named in the Introduction (the same sentence, plus "chronically at every generation") | **none**: no results or figures |

So GCRSim and Deep Space are described as *capabilities* of AMMPER, but no
published number depends on either one.

## 7. GCRSim and Deep Space — what actually runs, and what's validated (2026-09-24)

Tested because §5's matrix only proved they don't crash, and §4's Gamma
dose bug showed that "doesn't crash" can hide a completely wrong
simulation. This time every run's **output** was checked: final cell
counts by health state, the first generation with damage, the plot count,
and `simDescription.txt`.

### 7a. Entry points

All runs use Basic ROS (Complex ROS is disabled, §2), and neither type
takes a dose.

| Entry point | GCRSim | Deep Space | Notes |
|---|---|---|---|
| `ammper run` (`AMMPERCLI.py`) | ✅ wt, rad51 | ✅ wt, rad51 | Prompts for type → cell type → ROS; no dose prompt for these types |
| `ammper gui` (`AMMPERGUI.py`) | ✅ wt, rad51 | ✅ wt, rad51 | The data file is only written if **"Export results"** is checked (by design, `fileExport`). Plots are always written. Tested offscreen through `simSetup()` |
| `AMMPERBulk_aB.py` (batch) | ✅ wt, rad51 | ✅ wt, rad51 | The dose argument (`argv[4]`) is required positionally but ignored |
| `AMMPER.py` | ✅ wt (exit 0) | ✅ wt (exit 0) | Legacy interactive script; outputs not inspected |
| `AMMPERBulk_GAMMAfinal.py` | ✅ wt (exit 0) | ✅ wt (exit 0) | Runs every type despite the name; outputs not inspected |
| `ammper quickstart` | ❌ | ❌ | Hardcoded to 150 MeV Proton |
| `AMMPERrunsGUI.py` | ❌ | ❌ | Can't be instantiated (§3) |

### 7b. Results

One replicate per cell, 15 generations. Cells are counted at the final
generation as healthy / damaged / dead.

**GCRSim** (64 µm space, ~7–13 s per run):

| Entry point | wt: healthy / damaged / dead | wt first damage | rad51: healthy / damaged / dead | rad51 first damage |
|---|---|---|---|---|
| `AMMPERBulk_aB.py` | 3,817 / 259 / 0 | gen 3 | 3,699 / 0 / 375 | gen 6 |
| `ammper run` | 3,834 / 262 / 0 | gen 7 | 2,714 / 0 / 365 | gen 2 |
| `ammper gui` | 3,809 / 287 / 0 | gen 8 | 3,625 / 0 / 471 | gen 3 |

**Deep Space** (300 µm space, ~52–72 s per run):

| Entry point | wt: healthy / damaged / dead | wt first damage | rad51: healthy / damaged / dead | rad51 first damage |
|---|---|---|---|---|
| `AMMPERBulk_aB.py` | 11,533 / 0 / 0 | none | 11,683 / 0 / 2 | gen 10 |
| `ammper run` | 11,547 / 1 / 0 | gen 13 | 10,876 / 0 / 6 | gen 13 |
| `ammper gui` | 11,166 / 5 / 0 | gen 14 | 11,410 / 0 / 0 | none |

### 7c. What this shows

- **GCRSim behaves plausibly and consistently.** All three entry points
  agree: roughly 6–7% of wild-type cells end up damaged, and about 9–15%
  of *rad51*Δ cells die. Damage starts at or soon after generation 2,
  when the radiation is applied.
- **Both types show the same health-state split as Proton.** Wild type
  only ever reaches "damaged" and *rad51*Δ only ever "dead". That's the
  old `cellRepair` `elif` bug, which is still active on this branch (see
  `ab_kinetic_model_dead_cell_blindspot.md` on `feature/ammper-3.0`), not
  something specific to GCRSim or Deep Space.
- **Deep Space runs, but has almost no effect.** Across 6 inspected runs,
  0–6 cells out of ~11,000 were affected, which is barely distinguishable
  from no radiation. In two runs no cell was damaged at all. That may be
  physically reasonable, but it has **never been checked**. A rough
  geometric estimate (not a validation) is consistent with it:
  - The 10 traversals cross a 300 µm × 300 µm space from random
    directions.
  - Five of them happen by generation 8, when the colony is at most a few
    hundred cells a few tens of µm across, so they very likely miss.
  - Even at generation 15, a compact ~11,500-cell colony (radius ≈ 56 µm)
    covers only ~11% of a face of the space.
  - `energyThreshold = 20` discards small depositions.
  - The damage that does appear shows up at generations 10–14, when the
    colony is largest, which fits this picture.

  Low damage from 0.1 months of deep-space exposure (a low dose) could be
  correct. But there's no archived Deep Space data, no manuscript result,
  and no reference calculation to compare against. The fluence file's
  columns 2–4 are also undocumented, and the 0.2-month file isn't
  "double" the 0.1-month one (45 traversals vs 10), so nobody currently
  knows what dose these files represent.
- **"Works" means runs and produces plausible output, not validated.**
  Neither type has ever been compared against experimental data or an
  independent dose calculation, and the manuscript relies on neither.

### 7d. Two small bugs in both types' radiation setup (found 2026-09-24, not fixed)

1. **The last track is never picked.** Every energy folder under
   `data/radiation_input/ritracks/` has 8 tracks (`Track0`–`Track7`), and
   the code comments say "choose a random track out of the 8 available".
   But `int(rand.uniform(0,7))` only produces 0–6, so Track7 is never
   used. This affects GCRSim and Deep Space in all six driver files. The
   fix is `rand.randint(0,7)`.
2. **GCRSim drops 13 real energy deposits per run.** The line that removes
   the leftover placeholder row (`radData = np.delete(radData,(0),axis =
   0)`) is indented inside the per-energy `for` loop instead of after it,
   in all six driver files. It runs 14 times. The first call removes the
   placeholder, and the other 13 each delete a real deposition. Measured:
   **13 of 5,736 events (0.23%)** in a sampled run. The fix is to move it
   out one level so it runs once after the loop.

Neither is fixed, because both change GCRSim/Deep Space output, even if
only slightly. Neither affects Proton or Gamma, or anything in the
manuscript. `@TODO`s are at every site except `AMMPERrunsGUI.py` (left
untouched per the §3 decision). The full notes are in `AMMPERCLI.py`'s
Deep Space and GCRSim branches, with one-line pointers in `AMMPER.py`,
`AMMPERBulk_aB.py`, `AMMPERBulk_GAMMAfinal.py`, and `gui/AMMPERGUI.py`.

### 7e. Related: 64 µm simulations fill up at 4,096 cells

Found while comparing final cell counts across radiation types. Cells sit
on a 4 µm lattice, so the 64 µm space holds at most **16 × 16 × 16 =
4,096 cells**. 64 µm runs (Proton, GCRSim, Gamma) where most cells stay
healthy end at **~4,030–4,096 total cells**, meaning the population has
filled the space by around generation 13–14. Examples: Proton 0 Gy wt,
mean 4,086 and 4,096 (two 10-replicate batches from the `cellRepair`
comparison); Proton 30 Gy wt, mean 4,069 (old engine) and 4,034 (new
engine), n=10 each; GCRSim wt, 4,076–4,096 across the three runs in §7b. Growth curves in those runs flatten because the box is full,
not because of any biology. Heavily damaged runs end lower because only
healthy cells divide, e.g. GCRSim *rad51*Δ via `ammper run` at 3,079 total,
and Gamma 10 Gy wt at 441. Deep Space's 300 µm space (75³ ≈ 422,000
capacity) doesn't hit this, which is why it reaches ~11,500 cells.

This isn't a bug, and every archived manuscript run shares it, so it's
consistent across the published data. But it's directly relevant to the
AMMPER 3.0 "larger simulations / larger starting populations" workstream
(Bobby): a larger population won't show up in 64 µm runs unless `N` grows
too, and runtime and memory need checking at the new size.

## 8. Open items

- [ ] Decide Gamma's correct `radGen` (2 or 10) and reconcile all six files (§4).
- [x] ~~Gamma dose silently fixed at 1 Gy~~ — **fixed 2026-09-24** (§4):
      requested dose honored in `ammper run`, `ammper gui`,
      `AMMPERBulk_aB.py`, and `AMMPER.py`, with range >0–30 Gy and the
      dose recorded in `simDescription.txt`.
- [ ] Decide whether the app's Gamma dose should use the manuscript's
      calibrated hit rate (k ≈ 1.853) instead of `GammaRadGen`'s hardcoded
      k = 100. Today, "30 Gy" in the app is about 54× the manuscript's
      calibrated 30 Gy (§4 caveat). Resolve alongside Gamma `radGen`.
- [ ] `revisions_2026/code/run_gamma_simulations.py` points at a pre-reorg
      path (`src/AMMPERBulk_GAMMAfinal.py`) and would fail if run (§4).
      Manuscript owners' call.
- [ ] Rewrite `genROS()`'s diffusion-grid generation to be vectorized, if
      Complex ROS is ever wanted (§2) — or formally retire it.
- [x] ~~Reconcile or rewrite `AMMPERrunsGUI.py`, or deprecate it~~ —
      **decided 2026-09-24:** batch runs move to the CLI in AMMPER 3.0
      (`ammper run --replicates N`). `AMMPERrunsGUI.py` is left untouched
      until then (§3). Design: `batch_runs_cli_design.md` on
      `feature/ammper-3.0`.
- [ ] Until AMMPER 3.0 ships, replicate batches have no supported entry
      point. `AMMPERruns_aB.py`/`AMMPERruns_GAMMAFINAL.py` are hardcoded,
      depend on the working directory, and don't work on macOS/Linux (see
      the design doc). Anyone who needs N replicates before then has to
      loop `ammper quickstart --name <folder>` or `AMMPERBulk_aB.py`
      themselves.
- [ ] Broader GUI functional testing (not just instantiation) — out of
      scope for this pass.
- [ ] **Validate Deep Space** (§7c). It runs, but affects only 0–6 of
      ~11,000 cells per run. Decide whether that's physically right for
      0.1 months of exposure: document what the fluence file's columns 2–4
      and the 0.1/0.2-month files represent, compute the dose they
      correspond to, and compare. Until then, Deep Space results shouldn't
      be interpreted quantitatively.
- [ ] Decide what to do with `DeepSpaceFluence0.2months_data.txt`, which
      nothing uses: wire it up as an option or remove it (§6a).
- [ ] Document or remove the GUI's "0.5" dose label for GCRSim. No code
      reads it and nothing explains it (§6a).
- [ ] Fix the Track7-never-picked bug (`int(rand.uniform(0,7))` →
      `rand.randint(0,7)`) in all six driver files (§7d #1). Changes
      GCRSim/Deep Space output only.
- [ ] Fix the GCRSim in-loop `np.delete` that drops 13 real events per
      run (dedent one level) in all six driver files (§7d #2). Changes
      GCRSim output only.
- [ ] **The GUI's images and results depend on the working directory, and
      so do `ammper run`'s results.** `AMMPERCLI.py` also writes to
      `"Results/"` relative to the current folder (on Linux, whose file
      system is case-sensitive, that's a separate folder from
      `results/`). `vgui_form.py` loads every image as `"images/…"`, and
      `AMMPERGUI.py` writes results to `"Results/"`, both relative to the
      folder `ammper gui` is launched from. From the repo root they resolve to
      `images/` and `results/`, and from `gui/` to `gui/images/` and
      `gui/Results/` (which is why a duplicate `gui/images/` exists). From
      anywhere else, the typical case after `pip install`, every logo is
      missing and results land in `<that folder>/Results/`. Confirmed
      2026-09-24: the logos were blank when launched from a scratch
      folder. Fix: resolve both from `P.ROOT`, or have `cmd_gui` `chdir`
      before launching.
- [ ] AMMPER 3.0 larger-simulation work: 64 µm runs are capped at 4,096
      cells by the box size (§7e). Larger starting populations need a
      larger `N` to show up at all.
