"""
The `ammper` command-line interface.

Wraps the existing entry-point scripts
(`AMMPERCLI.py`, `AMMPERBulk_aB.py`) and the PyQt5 GUI (`gui/AMMPERGUI.py`)
unchanged, using `runpy` to execute them exactly as if invoked directly with
`python path/to/script.py args...`. 

@author: dannyofmiami
"""

import argparse
import difflib
import importlib.metadata
import os
import re
import runpy
import sys
import time

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.traceback import install as _install_rich_traceback

from ammper import paths as P

_install_rich_traceback(show_locals=False)

# 🪱 a must <3.
BANNER = r"""
   _   _    _    ____    _
  | \ | |  / \  / ___|  / \
  |  \| | / _ \ \___ \ / _ \
  | |\  |/ ___ \ ___) / ___ \
  |_| \_/_/   \_\____/_/   \_\
    _    __  __ __  __ ____  _____ ____
   / \  |  \/  |  \/  |  _ \| ____|  _ \
  / _ \ | |\/| | |\/| | |_) |  _| | |_) |
 / ___ \| |  | | |  | |  __/| |___|  _ <
/_/   \_\_|  |_|_|  |_|_|   |_____|_| \_\
"""

CELL_TYPES = {"wt": "a", "rad51": "b"}
ROS_TYPES = {"basic": "a", "complex": "b"}


def _console():
    return Console()


def _print_banner(console):
    try:
        version = importlib.metadata.version("ammper")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"
    console.print(BANNER, style="bold cyan", highlight=False)
    console.print(
        f"[bold]NASA AMMPER[/bold] v{version} — "
        "Agent-Based Model for Microbial Populations Exposed to Radiation\n"
    )


def _run_module_as_main(module_name, argv):
    """Execute an ammper.* driver script exactly as `python -m` would."""
    old_argv = sys.argv
    sys.argv = argv
    try:
        runpy.run_module(module_name, run_name="__main__")
    finally:
        sys.argv = old_argv


def cmd_run(args):
    """Launch the existing interactive single-run CLI (AMMPERCLI.py)."""
    console = _console()
    _print_banner(console)
    console.print("[cyan]Starting interactive simulation setup...[/cyan]\n")
    _run_module_as_main("ammper.AMMPERCLI", ["AMMPERCLI.py"])
    console.print("\n[bold green][✔] Simulation complete.[/bold green]")
    return 0


def cmd_quickstart(args):
    """Run non-interactive tutorial simulation with defaults."""
    console = _console()
    _print_banner(console)

    cell_code = CELL_TYPES[args.cell_type]
    ros_code = ROS_TYPES[args.ros_type]
    dose = str(args.dose)
    folder = args.name or "quickstart"

    console.print(
        f"[cyan]Running tutorial simulation[/cyan] "
        f"(150 MeV Proton, cell type={args.cell_type}, ROS model={args.ros_type}, "
        f"dose={dose} Gy)...\n"
    )

    start = time.time()
    _run_module_as_main(
        "ammper.AMMPERBulk_aB",
        ["AMMPERBulk_aB.py", "a", cell_code, ros_code, dose, folder],
    )
    elapsed = time.time() - start

    console.print(
        f"\n[bold green][✔] Quickstart complete[/bold green] "
        f"({elapsed:.1f}s)."
    )
    console.print(f"Results written to: [bold]{P.bulk_aB(folder)}[/bold]")
    console.print("[dim]Next: try `ammper gui` to visualize results, or `ammper run` for a full interactive simulation.[/dim]")
    return 0


def cmd_gui(args):
    """Launch the PyQt5 desktop GUI."""
    console = _console()
    _print_banner(console)

    gui_dir = os.path.join(P.ROOT, "gui")
    gui_script = os.path.join(gui_dir, "AMMPERGUI.py")
    if not os.path.isfile(gui_script):
        console.print(f"[bold red][x] GUI script not found at {gui_script}[/bold red]")
        return 1

    console.print("[cyan]Launching AMMPER GUI...[/cyan]")
    old_argv = sys.argv
    sys.argv = [gui_script]
    # `python gui/AMMPERGUI.py` would put gui/ on sys.path automatically (the
    # interpreter does this for the script it's directly given); runpy.run_path
    # does not, so AMMPERGUI.py's bare `from vgui_form import ...` would
    # otherwise fail with ModuleNotFoundError.
    path_inserted = gui_dir not in sys.path
    if path_inserted:
        sys.path.insert(0, gui_dir)
    try:
        runpy.run_path(gui_script, run_name="__main__")
    finally:
        sys.argv = old_argv
        if path_inserted and gui_dir in sys.path:
            sys.path.remove(gui_dir)
    return 0


def _check(console, table, label, ok, detail=""):
    mark = "[bold green]✔[/bold green]" if ok else "[bold red]x[/bold red]"
    table.add_row(mark, label, detail)
    return ok


def cmd_setup(args):
    """Check that the environment is ready to run simulations."""
    console = _console()
    _print_banner(console)

    table = Table(show_header=True, header_style="bold")
    table.add_column("", width=3)
    table.add_column("Check")
    table.add_column("Detail")

    all_ok = True

    for module_name in ("numpy", "pandas", "scipy", "sklearn", "matplotlib", "PyQt5", "rich"):
        try:
            importlib.import_module(module_name)
            ok = True
            detail = "installed"
        except ImportError as exc:
            ok = False
            detail = str(exc)
        all_ok &= _check(console, table, f"dependency: {module_name}", ok, detail)

    data_dirs = {
        "RITRACKS radiation tracks": P.RADIATION_INPUT,
        "alamarBlue experimental data": P.AB_EXPERIMENTAL,
        "BioSentinel experimental data": P.BIOSENTINEL,
        "fluence tables": P.FLUENCE,
    }
    for label, path in data_dirs.items():
        exists = os.path.isdir(path) and bool(os.listdir(path))
        all_ok &= _check(console, table, label, exists, path)

    try:
        figures_dir = P.figures()  # creates FIGURES/ itself if missing
        writable = os.access(figures_dir, os.W_OK)
        detail = figures_dir
    except OSError as exc:
        writable = False
        detail = str(exc)
    all_ok &= _check(console, table, "figures/ output directory is writable", writable, detail)

    console.print(table)

    if all_ok:
        console.print(
            "\n[bold green][✔] Environment looks good.[/bold green] "
            "Try [bold]ammper quickstart[/bold] to run a tutorial simulation."
        )
        return 0
    else:
        console.print(
            "\n[bold red][x] Some checks failed.[/bold red] "
            "See CONTRIBUTING.md for setup instructions, or re-run "
            r'`pip install -e ".\[dev]"` from the repository root.'
        )
        return 1


EPILOG = """\
Examples:
  ammper setup                          check your install is ready to go
  ammper quickstart                     run the ~5s tutorial simulation
  ammper quickstart --dose 2.5          tutorial run at 2.5 Gy instead of 0
  ammper run                            full interactive simulation (prompts you for options)
  ammper gui                            launch the desktop GUI

Notes:
  --debug and --version are global flags: put them before the subcommand,
  e.g. `ammper --debug run`, not `ammper run --debug`.

New to AMMPER? Start with `ammper setup`, then `ammper quickstart`.
"""


_INVALID_CHOICE_RE = re.compile(r"invalid choice: '([^']+)' \(choose from ((?:'[^']+'(?:, )?)+)\)")


class _BrandedArgumentParser(argparse.ArgumentParser):
    """Shows the AMMPER banner whenever help is printed

    A typo like `ammper quickstrat` would otherwise produce
    `invalid choice: 'quickstrat' (choose from 'setup', 'quickstart', ...)`
    —  catch this with a "did you mean...?" suggestion; `error()` does the 
    same thing here for both bad subcommands
    (`quickstrat` -> `quickstart`) and bad option values
    (`--cell-type mutant` -> did you mean `wt`?).
    """

    def print_help(self, file=None):
        _print_banner(_console())
        super().print_help(file)

    def error(self, message):
        console = _console()

        match = _INVALID_CHOICE_RE.search(message)
        if match:
            bad_value, raw_choices = match.groups()
            choices = re.findall(r"'([^']+)'", raw_choices)
            suggestion = difflib.get_close_matches(bad_value, choices, n=1)
            if suggestion:
                console.print(
                    f"[bold red][x] Unknown option '{bad_value}'.[/bold red] "
                    f"Did you mean [bold]'{suggestion[0]}'[/bold]?"
                )
            else:
                console.print(
                    f"[bold red][x] Unknown option '{bad_value}'.[/bold red] "
                    f"Choose from: {', '.join(choices)}"
                )
            self.exit(2)

        if message.startswith("unrecognized arguments:"):
            console.print(f"[bold red][x] {message}[/bold red]")
            console.print(f"[dim]Run `{self.prog} --help` to see the available options.[/dim]")
            self.exit(2)

        super().error(message)


def build_parser():
    parser = _BrandedArgumentParser(
        prog="ammper",
        description="NASA AMMPER — Agent-Based Model for Microbial Populations "
        "Exposed to Radiation.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version",
        version=f"ammper {_safe_version()}",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="show the full traceback instead of a short error message",
    )
    subparsers = parser.add_subparsers(
        dest="command", metavar="{setup,quickstart,run,gui}",
        parser_class=_BrandedArgumentParser,
    )

    p_setup = subparsers.add_parser(
        "setup",
        help="check that dependencies and data are ready to run simulations",
        description="Check that dependencies and data are ready to run simulations.",
    )
    p_setup.set_defaults(func=cmd_setup)

    p_quickstart = subparsers.add_parser(
        "quickstart",
        help="run a short, non-interactive tutorial simulation",
        description="Run a short (~5s at the default 0 Gy dose), non-interactive "
        "tutorial simulation — a wild-type cell population under 150 MeV proton "
        "radiation with the basic ROS model, unless overridden below.",
    )
    p_quickstart.add_argument(
        "--dose", type=float, default=0.0,
        help="radiation dose in Gy (default: 0, the fastest baseline run)",
    )
    p_quickstart.add_argument(
        "--cell-type", type=str.lower, choices=sorted(CELL_TYPES), default="wt",
        help="cell strain to simulate (default: wt)",
    )
    p_quickstart.add_argument(
        "--ros-type", type=str.lower, choices=sorted(ROS_TYPES), default="basic",
        help="reactive-oxygen-species model (default: basic)",
    )
    p_quickstart.add_argument(
        "--name", default=None,
        help="results subfolder name under results/bulk_aB/ (default: quickstart)",
    )
    p_quickstart.set_defaults(func=cmd_quickstart)

    p_run = subparsers.add_parser(
        "run",
        help="run a full interactive simulation (prompts for options)",
        description="Run a full simulation. You'll be prompted for radiation "
        "type, cell type, ROS model, and dose.",
    )
    p_run.set_defaults(func=cmd_run)

    p_gui = subparsers.add_parser(
        "gui",
        help="launch the AMMPER desktop GUI",
        description="Launch the PyQt5 desktop GUI.",
    )
    p_gui.set_defaults(func=cmd_gui)

    return parser


def _safe_version():
    try:
        return importlib.metadata.version("ammper")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


def _interactive_menu(parser, console):
    """A guided prompt for `ammper` run with no arguments and a real terminal
    attached — friendlier for a first-time user than a static help dump."""
    _print_banner(console)
    console.print("What would you like to do?\n")
    console.print("  [bold]setup[/bold]       check your install is ready to go")
    console.print("  [bold]quickstart[/bold]  run the ~5s tutorial simulation")
    console.print("  [bold]run[/bold]         full interactive simulation")
    console.print("  [bold]gui[/bold]         launch the desktop GUI")
    console.print("  [bold]help[/bold]        show the full --help text")
    console.print()

    choice = Prompt.ask(
        "Enter a command",
        choices=["setup", "quickstart", "run", "gui", "help", "quit"],
        default="setup",
        console=console,
    )

    if choice == "quit":
        return 0
    if choice == "help":
        parser.print_help()
        return 0

    args = parser.parse_args([choice])
    return args.func(args)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if not getattr(args, "command", None):
            if sys.stdin.isatty():
                return _interactive_menu(parser, _console())
            parser.print_help()
            return 0
        return args.func(args)
    except (KeyboardInterrupt, EOFError):
        _console().print("\n[yellow]Interrupted.[/yellow]")
        return 130
    except Exception as exc:  # noqa: BLE001 - top-level UX guard, not a bug swallow
        if args.debug:
            raise
        console = _console()
        console.print(f"\n[bold red][x] {type(exc).__name__}: {exc}[/bold red]")
        console.print("[dim]Re-run with --debug to see the full traceback.[/dim]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
