"""Tests for the ordered public-reporting entry point."""

from __future__ import annotations

from pathlib import Path
import runpy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts/04_reporting/15_build_reporting_bundle.py"


def _script_namespace() -> dict:
    return runpy.run_path(SCRIPT_PATH, run_name="spec_gap_reporting_bundle")


def test_reporting_commands_follow_data_dependencies():
    namespace = _script_namespace()

    commands = namespace["reporting_commands"]("python-test")

    assert [Path(command[1]).name for command in commands] == [
        "12_plot_probe_analysis.py",
        "13_plot_pipeline_overview.py",
        "14_plot_investor_figures.py",
    ]
    assert all(command[0] == "python-test" for command in commands)
    assert commands[0][2:] == (
        "--snapshot-input",
        str(PROJECT_ROOT / "results/scenario1/reporting_snapshot.json"),
    )


def test_reporting_bundle_stops_on_checked_subprocesses():
    namespace = _script_namespace()
    calls = []

    def fake_runner(command, *, cwd, check):
        calls.append((command, cwd, check))

    namespace["run_reporting_bundle"](
        python_executable="python-test",
        runner=fake_runner,
    )

    assert len(calls) == 3
    assert all(cwd == PROJECT_ROOT for _, cwd, _ in calls)
    assert all(check is True for _, _, check in calls)


def test_public_figure_scripts_normalize_svg_whitespace(tmp_path):
    scripts = (
        PROJECT_ROOT / "scripts/04_reporting/13_plot_pipeline_overview.py",
        PROJECT_ROOT / "scripts/04_reporting/14_plot_investor_figures.py",
    )
    for index, script in enumerate(scripts):
        namespace = runpy.run_path(script, run_name=f"spec_gap_svg_{index}")
        svg = tmp_path / f"figure-{index}.svg"
        svg.write_text("<svg>  \n  <path />   \n</svg>\n", encoding="utf-8")

        namespace["_normalize_svg"](svg)

        assert svg.read_text(encoding="utf-8") == "<svg>\n  <path />\n</svg>\n"


def test_public_and_presentation_figures_use_separate_output_directories():
    pipeline = runpy.run_path(
        PROJECT_ROOT / "scripts/04_reporting/13_plot_pipeline_overview.py",
        run_name="spec_gap_pipeline_output",
    )
    presentation = runpy.run_path(
        PROJECT_ROOT / "scripts/04_reporting/14_plot_investor_figures.py",
        run_name="spec_gap_presentation_output",
    )

    assert pipeline["OUTPUT_DIR"] == PROJECT_ROOT / "docs" / "assets"
    assert presentation["OUTPUT_DIR"] == PROJECT_ROOT / "results" / "presentation"
    assert presentation["SNAPSHOT_PATH"] == (
        PROJECT_ROOT / "results" / "scenario1" / "reporting_snapshot.json"
    )
