from pathlib import Path


def test_logon_tasks_run_as_interactive_owner_without_battery_queueing():
    script = (Path(__file__).parent / "scripts/windows/install_jarvis_network.ps1").read_text()
    assert "-LogonType Interactive" in script
    assert "WindowsIdentity]::GetCurrent().Name" in script
    assert "-AllowStartIfOnBatteries" in script
    assert "-DontStopIfGoingOnBatteries" in script
    assert "-StartWhenAvailable" in script
    for name in ("JarvisNetwork", "JarvisVoice", "JarvisDashboard"):
        assert f"-TaskName '{name}'" in script
    assert script.count("-Principal $principal") == 3
