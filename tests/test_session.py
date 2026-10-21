import json
import stat

import pytest

from tests.fakes import ENV, FakeClient
from wyzectl.session import ConfigError, Credentials, Session


def creds():
    return Credentials.from_env(ENV)


@pytest.fixture
def session(tmp_path):
    FakeClient.logins = 0
    return Session(
        creds, cache_path=tmp_path / "wyzectl" / "session.json", client_factory=FakeClient
    )


def test_missing_env_names_every_variable():
    with pytest.raises(ConfigError) as e:
        Credentials.from_env({"WYZE_EMAIL": "x"})
    assert "WYZE_PASSWORD" in str(e.value) and "WYZE_API_KEY" in str(e.value)


def test_repr_hides_credentials():
    assert "test@example.com" not in repr(creds())
    assert "not-a-password" not in repr(creds())


def test_first_call_logs_in_and_caches_privately(session, tmp_path):
    session.call(lambda c: c.devices_list())
    path = tmp_path / "wyzectl" / "session.json"
    assert FakeClient.logins == 1
    assert json.loads(path.read_text()) == {
        "access_token": "access-1",
        "refresh_token": "refresh-1",
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_cached_session_is_reused_without_login(session, tmp_path):
    session.call(lambda c: c.devices_list())
    again = Session(
        creds, cache_path=tmp_path / "wyzectl" / "session.json", client_factory=FakeClient
    )
    again.call(lambda c: c.devices_list())
    assert FakeClient.logins == 1


def test_expired_token_is_refreshed_and_saved(session, tmp_path):
    session.client.expired = True
    session.call(lambda c: c.devices_list())
    assert FakeClient.logins == 1
    saved = json.loads((tmp_path / "wyzectl" / "session.json").read_text())
    assert saved["access_token"] == "access-1-r"


def test_failed_refresh_falls_back_to_login(session):
    session.client.expired = True
    session.client.refresh_fails = True
    session.call(lambda c: c.devices_list())
    assert FakeClient.logins == 2


def test_other_api_errors_are_not_retried(session):
    from wyze_sdk.errors import WyzeApiError

    def boom(client):
        raise WyzeApiError("nope", {"code": "1003"})

    with pytest.raises(WyzeApiError):
        session.call(boom)
    assert FakeClient.logins == 1


def test_forget_removes_cache(session, tmp_path):
    session.call(lambda c: c.devices_list())
    session.forget()
    assert not (tmp_path / "wyzectl" / "session.json").exists()
