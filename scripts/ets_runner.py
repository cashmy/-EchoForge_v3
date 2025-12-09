"""Execute ETS profiles by delegating to the pytest marker harness."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_MATRIX = {
    "pipeline": {
        "marker": "ets_pipeline",
        "tests_path": "tests/ets",
    }
}


def run_profile(profile: str, extra_args: list[str] | None = None) -> int:
    """Run the requested ETS profile via pytest and return its exit code."""

    config = PROFILE_MATRIX.get(profile)
    if not config:
        raise SystemExit(
            f"Unsupported ETS profile '{profile}'. Known profiles: {', '.join(PROFILE_MATRIX)}"
        )

    marker = config["marker"]
    tests_path = config["tests_path"]
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        marker,
        tests_path,
    ]
    if extra_args:
        pytest_cmd.extend(extra_args)

    print(f"[ETS] Running profile '{profile}' via marker '{marker}'...")
    completed = subprocess.run(pytest_cmd, cwd=REPO_ROOT, check=False)
    return completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default="pipeline",
        choices=sorted(PROFILE_MATRIX.keys()),
        help="ETS profile to execute (defaults to 'pipeline').",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional arguments forwarded verbatim to pytest.",
    )
    args = parser.parse_args()

    exit_code = run_profile(args.profile, extra_args=args.pytest_args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
