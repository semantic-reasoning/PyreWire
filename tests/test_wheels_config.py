"""Regression: cibuildwheel matrix and supporting scripts stay wired (#30 + #31).

The wheel build is what makes `pip install pyrewire` work without a
system wirelog. A future refactor that drops the per-platform
`repair-wheel-command` would silently regress to broken wheels. This
test parses the YAML/TOML and asserts the required pieces exist.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (_repo_root() / path).read_text()


def test_pyproject_has_cibuildwheel_table():
    text = _read("pyproject.toml")
    assert "[tool.cibuildwheel]" in text
    assert "[tool.cibuildwheel.linux]" in text
    assert "[tool.cibuildwheel.macos]" in text
    assert "[tool.cibuildwheel.windows]" in text


def test_pyproject_declares_python_311_plus():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    project = pyproject["project"]
    assert project["requires-python"] == ">=3.11"
    assert "Programming Language :: Python :: 3.10" not in project["classifiers"]
    assert "Programming Language :: Python :: 3.11" in project["classifiers"]
    assert "Programming Language :: Python :: 3.13" in project["classifiers"]
    assert "Programming Language :: Python :: 3.14" in project["classifiers"]


def test_cibuildwheel_drops_cp310():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    build = pyproject["tool"]["cibuildwheel"]["build"]
    assert "cp310" not in build
    assert build == "cp311-* cp312-* cp313-* cp314-*"


def test_build_system_requires_packaging_24_2_minimum():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    requires = pyproject["build-system"]["requires"]
    assert "packaging>=24.2" in requires


def test_cibuildwheel_dependency_versions_is_latest():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    assert pyproject["tool"]["cibuildwheel"]["dependency-versions"] == "latest"


def test_windows_cibuildwheel_arch_is_amd64_only():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    assert pyproject["tool"]["cibuildwheel"]["windows"]["archs"] == ["AMD64"]


def test_windows_cibuildwheel_uses_forward_slash_paths():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    windows = pyproject["tool"]["cibuildwheel"]["windows"]
    assert windows["environment"]["WIRELOG_PREFIX"] == "C:/wirelog-install"
    assert windows["environment"]["WIRELOG_LIB"] == "C:/wirelog-install/bin/wirelog-1.dll"
    repair_cmd = windows["repair-wheel-command"]
    assert "--add-path C:/wirelog-install/bin" in repair_cmd
    assert "C:\\wirelog-install" not in windows["environment"]["WIRELOG_PREFIX"]
    assert "C:\\wirelog-install" not in windows["environment"]["WIRELOG_LIB"]
    assert "C:\\wirelog-install" not in repair_cmd


def test_wheels_build_matrix_uses_current_hosted_runners():
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    matrix = wf["jobs"]["build_wheels"]["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-24.04", "macos-15", "windows-2025-vs2026"]


def test_wheels_workflow_uses_node24_actions():
    text = _read(".github/workflows/wheels.yml")
    assert "actions/checkout@v4" not in text
    assert "actions/setup-python@v5" not in text
    assert "actions/checkout@v5" in text
    assert "actions/setup-python@v6" in text


def test_each_platform_has_repair_wheel_command():
    """The wheel-repair step (#31) is what bundles libwirelog into the
    wheel. Missing it on any platform breaks `pip install pyrewire`."""
    text = _read("pyproject.toml")
    sections = re.split(r"\n(?=\[tool\.cibuildwheel\.[a-z]+\])", text)
    for section in sections:
        if section.startswith("[tool.cibuildwheel.linux]"):
            assert "auditwheel repair" in section
        elif section.startswith("[tool.cibuildwheel.macos]"):
            assert "delocate-wheel" in section
        elif section.startswith("[tool.cibuildwheel.windows]"):
            assert "delvewheel repair" in section


def test_cibuildwheel_copies_wirelog_before_build():
    """The `before-build` hook must copy `WIRELOG_LIB` into
    `src/pyrewire/_lib` before wheel packaging."""
    pyproject = tomllib.loads(_read("pyproject.toml"))
    before_build = pyproject["tool"]["cibuildwheel"].get("before-build", "")
    assert before_build, "cibuildwheel before-build hook is required"
    assert "bundle_libwirelog.py" in before_build
    assert (_repo_root() / "scripts" / "bundle_libwirelog.py").is_file()


def test_wheel_package_data_includes_wirelog_binaries():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    pyrewire_lib_data = pyproject["tool"]["setuptools"]["package-data"]["pyrewire._lib"]
    assert "*.so" in pyrewire_lib_data
    assert "*.so.*" in pyrewire_lib_data
    assert "*.dylib" in pyrewire_lib_data
    assert "*.dll" in pyrewire_lib_data


def test_windows_repair_installs_delvewheel():
    """Windows repair needs delvewheel installed explicitly."""
    pyproject = tomllib.loads(_read("pyproject.toml"))
    command = pyproject["tool"]["cibuildwheel"]["windows"]["repair-wheel-command"]
    assert "pip install delvewheel" in command
    assert command.index("pip install delvewheel") < command.index("delvewheel repair")
    assert "--no-mangle-all" in command


def test_setup_py_forces_platform_wheel():
    """A pure wheel (`py3-none-any`) cannot run repair tooling."""
    setup_py = _repo_root() / "setup.py"
    assert setup_py.is_file(), "setup.py shim is required for platform-specific wheel tags"
    text = setup_py.read_text()
    assert "class _BinaryDistribution" in text
    assert "def has_ext_modules" in text


def test_wheels_workflow_triggers_on_v_tags_and_dispatch():
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    on = wf.get("on") or wf.get(True)
    assert isinstance(on, dict)
    push = on.get("push") or {}
    assert "v*" in (push.get("tags") or [])
    assert "workflow_dispatch" in on


def test_wheels_workflow_uploads_artifacts():
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    steps = wf["jobs"]["build_wheels"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert any(
        "upload-artifact" in u for u in uses
    ), "wheels workflow must upload built wheels as artifacts"


def test_wheels_workflow_initializes_msvc_before_cibuildwheel():
    text = _read(".github/workflows/wheels.yml")
    wf = yaml.safe_load(text)
    steps = wf["jobs"]["build_wheels"]["steps"]
    msvc_steps = [s for s in steps if "Visual Studio toolchain" in str(s.get("name", ""))]
    assert msvc_steps, "build_wheels should initialize MSVC on Windows"
    msvc_step = msvc_steps[0]
    assert msvc_step.get("if") == "runner.os == 'Windows'"
    assert msvc_step.get("shell") == "pwsh"
    run = msvc_step.get("run", "")
    assert "vswhere.exe" in run
    assert "VsDevCmd.bat" in run
    assert "cmd.exe" in run
    assert "-arch=x64 && set" in run
    assert "GITHUB_ENV" in run
    assert "GITHUB_PATH" not in run
    assert "Get-Command bash.exe" in run
    assert "C:\\Program Files\\Git\\bin\\bash.exe" in run
    assert 'Write-Host "Using bash.exe from $bashPath"' in run
    assert '$entry -like "*\\Microsoft\\WindowsApps"' in run
    assert "[void]$orderedPathEntries.Add($bashDir)" in run
    assert '"PATH=$orderedPath" | Out-File -FilePath $env:GITHUB_ENV' in run
    assert "$msvcEnvVars = @(" in run
    assert "$envMap.ContainsKey($name)" in run
    assert "Out-File -FilePath $env:GITHUB_ENV" in run
    for name in (
        "INCLUDE",
        "LIB",
        "LIBPATH",
        "VCToolsInstallDir",
        "VCToolsRedistDir",
        "VCINSTALLDIR",
        "VSINSTALLDIR",
        "WindowsLibPath",
        "WindowsSdkBinPath",
        "WindowsSdkDir",
        "WindowsSDKLibVersion",
        "WindowsSdkVerBinPath",
        "WindowsSDKVersion",
        "UCRTVersion",
        "UniversalCRTSdkDir",
        "VSCMD_ARG_HOST_ARCH",
        "VSCMD_ARG_TGT_ARCH",
        "VSCMD_VER",
    ):
        assert f'"{name}"' in run
    assert "shell: cmd" not in text
    assert "for %%" not in run
    assert "call if" not in run
    assert "%%%%v%%" not in run
    assert "%PATH:;=" not in run
    assert "call set " not in run
    assert "tokens=1,* delims==" not in run
    assert "echo PATH=%PATH%" not in run
    assert not re.search(r"set\s*>>", run)
    assert not re.search(r">>\s*\"?%GITHUB_ENV%\"?", run)
    assert not re.search(r"\$cmdOutput\s*\|\s*Out-File[^\n]+GITHUB_ENV", run)
    assert not re.search(r"Out-File[^\n]+GITHUB_ENV[^\n]+\$cmdOutput", run)
    msvc_idx = steps.index(msvc_step)
    cibw_idx = next(i for i, s in enumerate(steps) if "pypa/cibuildwheel" in s.get("uses", ""))
    assert msvc_idx < cibw_idx


def test_wheels_workflow_avoids_node20_action():
    text = _read(".github/workflows/wheels.yml")
    assert "ilammy/msvc-dev-cmd" not in text


def test_wheels_workflow_uses_cibuildwheel_action():
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    steps = wf["jobs"]["build_wheels"]["steps"]
    assert any("pypa/cibuildwheel" in s.get("uses", "") for s in steps)


def test_wheels_workflow_uses_cibuildwheel_v3_4_1():
    text = _read(".github/workflows/wheels.yml")
    assert "pypa/cibuildwheel@v3.4.1" in text
    assert "pypa/cibuildwheel@v2.21.3" not in text


def test_cibuildwheel_test_requires_pytest_cov():
    """cibuildwheel runs pytest from a fresh env, so it must install the
    plugin required by pyproject's coverage addopts."""
    pyproject = tomllib.loads(_read("pyproject.toml"))
    requires = pyproject["tool"]["cibuildwheel"]["test-requires"]
    assert "pytest" in requires
    assert "pytest-cov" in requires


def test_cibuildwheel_test_command_clears_pytest_addopts():
    """Wheels tests should clear repository addopts so CI-wide coverage rules
    don't leak into the integration-only wheel checks."""
    pyproject = tomllib.loads(_read("pyproject.toml"))
    test_command = pyproject["tool"]["cibuildwheel"]["test-command"]
    assert "-o addopts=" in test_command


def test_wheel_install_workflow_installs_pytest_cov():
    """The wheel install smoke test also runs pytest against this repo's
    pyproject, whose addopts require pytest-cov."""
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    steps = wf["jobs"]["install_test"]["steps"]
    install_steps = [s for s in steps if "pip install" in str(s.get("run", ""))]
    assert any("pytest-cov" in str(s.get("run", "")) for s in install_steps)


def test_build_wirelog_powershell_script_exists():
    """The Windows runner needs a PowerShell-flavoured build script."""
    ps1 = _repo_root() / "scripts" / "build_wirelog.ps1"
    assert ps1.is_file()
    text = ps1.read_text()
    assert "meson" in text
    assert "WIRELOG_VERSION" in text


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "POSIX-only: NTFS has no executable bit; "
        "the bash script is consumed by Linux/macOS runners"
    ),
)
def test_build_wirelog_bash_script_exists():
    """The Linux/macOS runners share the bash script."""
    sh = _repo_root() / "scripts" / "build_wirelog.sh"
    assert sh.is_file()
    assert sh.stat().st_mode & 0o111, "build_wirelog.sh must be executable"


def test_macos_cibuildwheel_uses_home_wirelog_prefix():
    """macOS wheels should install and repair wirelog from a user-writable prefix."""
    pyproject = tomllib.loads(_read("pyproject.toml"))
    macos = pyproject["tool"]["cibuildwheel"]["macos"]
    assert macos["environment"]["WIRELOG_PREFIX"] == "$HOME/wirelog-install"
    assert macos["environment"]["WIRELOG_LIB"] == "$HOME/wirelog-install/lib/libwirelog.1.dylib"
    assert macos["environment"]["DYLD_LIBRARY_PATH"] == "$HOME/wirelog-install/lib"
    assert "$HOME/wirelog-install" in macos["before-all"]
    assert "DYLD_LIBRARY_PATH=$HOME/wirelog-install/lib" in macos["repair-wheel-command"]
    assert "/usr/local/wirelog-install" not in macos["before-all"]
    assert "/usr/local/wirelog-install" not in macos["repair-wheel-command"]
