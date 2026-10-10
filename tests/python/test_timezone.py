import time
from datetime import datetime

import pytest

import scanner


@pytest.fixture
def restore_tz(monkeypatch):
    yield monkeypatch
    # monkeypatch restores os.environ; make the C library follow suit
    if hasattr(time, "tzset"):
        time.tzset()


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset() is POSIX only")
def test_read_environment_applies_tz_to_local_time(tmp_path, restore_tz):
    """#111: TZ from env.txt must reach datetime.now(), not only os.environ."""
    env_file = tmp_path / "env.txt"
    env_file.write_text("TZ=Asia/Tokyo\n")
    restore_tz.setattr(scanner, "ENVIRONMENT_FILE_PATH", str(env_file))
    restore_tz.setenv("TZ", "UTC")
    time.tzset()
    assert time.localtime().tm_gmtoff == 0

    scanner.read_environment()

    assert time.localtime().tm_gmtoff == 9 * 3600, "Tokyo has no DST, offset must be +9h"
    local = datetime.now()
    utc = datetime.utcnow()
    assert round((local - utc).total_seconds() / 3600) == 9


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset() is POSIX only")
def test_job_names_follow_tz(tmp_path, restore_tz):
    env_file = tmp_path / "env.txt"
    env_file.write_text("TZ=Etc/GMT-5\n")  # POSIX sign convention: GMT-5 means UTC+5
    restore_tz.setattr(scanner, "ENVIRONMENT_FILE_PATH", str(env_file))
    scanner.read_environment()
    stamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    expected_hour = (datetime.utcnow().hour + 5) % 24
    assert int(stamp.split("-")[3]) == expected_hour


def test_apply_timezone_is_safe_without_tzset(monkeypatch):
    monkeypatch.delattr(time, "tzset", raising=False)
    scanner.apply_timezone()  # must not raise
