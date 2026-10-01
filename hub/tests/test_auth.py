import time

import jwt
import pytest

from rosacademy_hub.auth import TokenError, verify_token

SECRET = "s" * 40


def make(sub="u-42", plan="free", aud="ros-lab", iat=None, ttl=300, secret=SECRET, alg="HS256", **extra):
    now = int(time.time()) if iat is None else iat
    claims = {"sub": sub, "plan": plan, "aud": aud, "iat": now, "exp": now + ttl, **extra}
    return jwt.encode(claims, secret, algorithm=alg)


def test_valid_token_returns_user_and_plan():
    result = verify_token(make(plan="pro"), SECRET)
    assert result == {"name": "u-42", "auth_state": {"plan": "pro"}}


def test_missing_plan_is_passed_as_none():
    now = int(time.time())
    token = jwt.encode({"sub": "u-1", "aud": "ros-lab", "iat": now, "exp": now + 60}, SECRET, algorithm="HS256")
    assert verify_token(token, SECRET)["auth_state"] == {"plan": None}


def test_empty_token_is_refused():
    with pytest.raises(TokenError):
        verify_token("", SECRET)


def test_garbage_token_is_refused():
    with pytest.raises(TokenError):
        verify_token("not-a-jwt", SECRET)


def test_wrong_secret_is_refused():
    with pytest.raises(TokenError):
        verify_token(make(secret="x" * 40), SECRET)


def test_expired_token_is_refused():
    with pytest.raises(TokenError):
        verify_token(make(iat=int(time.time()) - 4000, ttl=300), SECRET)


def test_wrong_audience_is_refused():
    with pytest.raises(TokenError):
        verify_token(make(aud="other-app"), SECRET)


def test_too_long_lifetime_is_refused():
    with pytest.raises(TokenError):
        verify_token(make(ttl=24 * 3600), SECRET)


def test_alg_none_is_refused():
    now = int(time.time())
    token = jwt.encode({"sub": "u-1", "aud": "ros-lab", "iat": now, "exp": now + 60}, None, algorithm="none")
    with pytest.raises(TokenError):
        verify_token(token, SECRET)


@pytest.mark.parametrize("sub", ["../root", "Admin", "a" * 33, "-start", "user name", "élève"])
def test_unsafe_subject_is_refused(sub):
    with pytest.raises(TokenError):
        verify_token(make(sub=sub), SECRET)


def test_missing_exp_is_refused():
    token = jwt.encode({"sub": "u-1", "aud": "ros-lab", "iat": int(time.time())}, SECRET, algorithm="HS256")
    with pytest.raises(TokenError):
        verify_token(token, SECRET)
