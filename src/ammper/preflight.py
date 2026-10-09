"""
Machine pre-flight checks for AMMPER.

@author: dannyofmiami
"""

import ctypes
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

# Peak resident memory per 1,000 ROS events, plus a fixed interpreter/numpy base.
# Measured 0.264-0.275 GB per 1,000 events; the upper end is used.
GB_PER_1000_EVENTS = 0.275
BASE_GB = 0.3

# Time model t = T0 + T1*k + T2*k^2, k = thousands of ROS events (Apple M-series).
T0_S, T1_S, T2_S = 2.0, 0.68, 0.1346

# Number of deposition events in one 150 MeV Proton track (Track 1, as used by
# AMMPERBulk_aB.py / AMMPERCLI.py) and the number of tracks used per dose.
PROTON_EVENTS_PER_TRACK = 6916
PROTON_TRACKS = {0.0: 0, 2.5: 1, 5.0: 2, 10.0: 4, 20.0: 8, 30.0: 12}

# GammaRadGen emits 64 * (100 * dose) + 1 events (6,401 at the fixed 1 Gy).
GAMMA_EVENTS_PER_GY = 6400

# A run needs this much more than its estimated peak (spikes, plotting, the OS).
HEADROOM = 1.25
# Above this fraction of *available* memory a run is allowed but flagged.
WARN_FRACTION = 0.6
# Complex ROS run types we have not measured (GCRSim, Deep Space, untabulated doses): warn
# only a machine with less than this much free memory, so capable machines are not nagged.
UNCHARACTERIZED_MIN_FREE_GB = 16.0
# If free memory cannot be read, only warn for runs estimated above this peak (GB), i.e. the
# higher doses; low-dose runs fit on practically any machine.
UNDETECTABLE_WARN_ABOVE_GB = 4.0

FORCE_ENV_VAR = "AMMPER_FORCE_COMPLEX_ROS"

PROTON = "150 MeV Proton"
GAMMA = "Gamma"


class ComplexROSCapacityError(RuntimeError):
    """Raised when this machine cannot safely run the requested Complex ROS job."""


@dataclass(frozen=True)
class MachineSpecs:
    system: str
    machine: str
    cpu_count: int
    total_ram_gb: Optional[float]
    available_ram_gb: Optional[float]


@dataclass(frozen=True)
class Estimate:
    events: int
    peak_gb: float
    minutes: float


@dataclass(frozen=True)
class Verdict:
    level: str  # "ok" | "warn" | "block"
    message: str
    estimate: Optional[Estimate]
    specs: MachineSpecs


# --------------------------------------------------------------------------- #
# Hardware detection (stdlib only; psutil is used if it happens to be installed)
# --------------------------------------------------------------------------- #

_GB = 1024 ** 3


def _memory_psutil():
    try:
        import psutil
    except ImportError:
        return None
    vm = psutil.virtual_memory()
    return vm.total / _GB, vm.available / _GB


def _memory_windows():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullTotalPhys / _GB, status.ullAvailPhys / _GB


def _memory_linux():
    info = {}
    with open("/proc/meminfo") as fh:
        for line in fh:
            key, _, rest = line.partition(":")
            info[key] = int(rest.split()[0]) * 1024
    total = info["MemTotal"]
    available = info.get("MemAvailable", info.get("MemFree", 0))
    return total / _GB, available / _GB


def _memory_macos():
    total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
    out = subprocess.check_output(["vm_stat"], text=True)
    page = int(re.search(r"page size of (\d+) bytes", out).group(1))

    def pages(label):
        m = re.search(label + r":\s+(\d+)", out)
        return int(m.group(1)) if m else 0

    # free + inactive + speculative + purgeable is what the OS can hand out
    # without swapping; "free" alone badly under-reports on macOS.
    available = (pages("Pages free") + pages("Pages inactive")
                 + pages("Pages speculative") + pages("Pages purgeable")) * page
    return total / _GB, available / _GB


def detect_machine():
    """Return the current machine's specs. RAM fields are None if undetectable."""
    system = platform.system()
    mem = _memory_psutil()
    if mem is None:
        try:
            if system == "Windows":
                mem = _memory_windows()
            elif system == "Darwin":
                mem = _memory_macos()
            elif system == "Linux":
                mem = _memory_linux()
        except Exception:
            mem = None
    total, available = mem if mem else (None, None)
    return MachineSpecs(
        system=system,
        machine=platform.machine(),
        cpu_count=os.cpu_count() or 1,
        total_ram_gb=total,
        available_ram_gb=available,
    )


# --------------------------------------------------------------------------- #
# Cost model
# --------------------------------------------------------------------------- #

def complex_ros_events(rad_type, dose_gy):
    """ROS deposition events a Complex ROS run will feed to genROS, or None if
    that radiation type / dose has not been characterized."""
    if rad_type == PROTON:
        tracks = PROTON_TRACKS.get(float(dose_gy))
        return None if tracks is None else tracks * PROTON_EVENTS_PER_TRACK
    if rad_type == GAMMA:
        return int(GAMMA_EVENTS_PER_GY * dose_gy) + 1
    return None


def estimate_complex_ros(rad_type, dose_gy):
    events = complex_ros_events(rad_type, dose_gy)
    if events is None:
        return None
    k = events / 1000.0
    return Estimate(
        events=events,
        peak_gb=BASE_GB + GB_PER_1000_EVENTS * k,
        minutes=(T0_S + T1_S * k + T2_S * k * k) / 60.0,
    )


def check_complex_ros(rad_type, dose_gy, specs=None):
    """Decide whether this machine should run Complex ROS for this job.

    Returns a Verdict; never raises. ``block`` means the estimated peak memory
    exceeds the memory currently available.
    """
    specs = specs or detect_machine()
    est = estimate_complex_ros(rad_type, dose_gy)

    if est is None:
        message = (f"Complex ROS memory use has not been characterized for {rad_type} at "
                   f"{dose_gy:g} Gy (only 150 MeV Proton at 0/2.5/5/10/20/30 Gy and Gamma are). "
                   "It may need several GB or more; close other applications before running.")
        free = specs.available_ram_gb
        if free is not None and free >= UNCHARACTERIZED_MIN_FREE_GB:
            return Verdict("ok", message + f" ~{free:.1f} GB free: likely fine.", None, specs)
        return Verdict("warn", message, None, specs)

    need = est.peak_gb * HEADROOM
    summary = (f"{rad_type}, {dose_gy:g} Gy, Complex ROS: ~{est.events:,} ROS events, "
               f"estimated peak memory ~{est.peak_gb:.1f} GB, ~{est.minutes:.1f} min on an "
               "Apple M-series chip (slower CPUs take longer).")

    if specs.available_ram_gb is None:
        if est.peak_gb <= UNDETECTABLE_WARN_ABOVE_GB:
            return Verdict("ok", summary + " Free memory could not be detected; this run is "
                           "small enough that it is not expected to be a problem.", est, specs)
        return Verdict(
            "warn",
            summary + " Could not detect available memory on this machine, so the run was "
            "not checked. Make sure at least "
            f"{need:.0f} GB of RAM is free.",
            est, specs)

    avail = specs.available_ram_gb
    if need > avail:
        return Verdict(
            "block",
            summary + f" This machine has ~{avail:.1f} GB free (of "
            f"{specs.total_ram_gb:.1f} GB) and the run needs ~{need:.1f} GB, so "
            "it would swap or crash. Use a lower dose, Basic ROS, or a machine with more RAM.",
            est, specs)
    if need > WARN_FRACTION * avail:
        return Verdict(
            "warn",
            summary + f" This will use most of the ~{avail:.1f} GB currently free; close "
            "other applications first.",
            est, specs)
    return Verdict("ok", summary + f" ~{avail:.1f} GB free: OK.", est, specs)


def require_complex_ros_capacity(rad_type, dose_gy, specs=None, env=None):
    """Raise ComplexROSCapacityError if this machine cannot safely run the job.

    Call this before any Complex ROS run. Returns the Verdict otherwise (callers
    should print its message when the level is "warn"). Setting
    AMMPER_FORCE_COMPLEX_ROS=1 downgrades a block to a warning.
    """
    env = os.environ if env is None else env
    verdict = check_complex_ros(rad_type, dose_gy, specs)
    if verdict.level == "block":
        if env.get(FORCE_ENV_VAR) == "1":
            return Verdict("warn", "OVERRIDE (" + FORCE_ENV_VAR + "=1): " + verdict.message,
                           verdict.estimate, verdict.specs)
        raise ComplexROSCapacityError(
            verdict.message + f" Set {FORCE_ENV_VAR}=1 to override at your own risk.")
    return verdict


def complex_ros_warning(rad_type, dose_gy, specs=None):
    """User-facing warning text if this machine may not cope with a Complex ROS run,
    or None when it is fine. Used to warn (not forbid) in the CLI and the GUI."""
    verdict = check_complex_ros(rad_type, dose_gy, specs)
    return None if verdict.level == "ok" else verdict.message


def complex_ros_table(specs=None):
    """Rows (rad_type, dose, Estimate, level) for every characterized Complex ROS run,
    for display by ``ammper setup``."""
    specs = specs or detect_machine()
    jobs = [(PROTON, d) for d in sorted(PROTON_TRACKS) if d > 0] + [(GAMMA, 1.0)]
    return [(rad_type, dose, estimate_complex_ros(rad_type, dose),
             check_complex_ros(rad_type, dose, specs).level) for rad_type, dose in jobs]


def max_safe_proton_dose(specs=None):
    """Highest tabulated 150 MeV Proton dose this machine can run with Complex ROS
    without a "block" verdict (0.0 if none)."""
    specs = specs or detect_machine()
    best = 0.0
    for dose in sorted(PROTON_TRACKS):
        if check_complex_ros(PROTON, dose, specs).level != "block":
            best = dose
    return best
