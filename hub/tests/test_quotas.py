from types import SimpleNamespace

import pytest

from rosacademy_hub.quotas import DEFAULT_PLAN, PLANS, PlanLimits, apply_limits, limits_for


def make_spawner():
    return SimpleNamespace(
        cpu_limit=None,
        mem_limit=None,
        extra_host_config={
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges"],
            "init": True,
        },
    )


def test_free_and_pro_limits_match_spec():
    assert PLANS["free"] == PlanLimits(cpu=1.0, mem="2G", pids=256)
    assert PLANS["pro"] == PlanLimits(cpu=2.0, mem="4G", pids=512)
    assert DEFAULT_PLAN == "free"


def test_limits_for_known_plan():
    assert limits_for("pro") == PLANS["pro"]


@pytest.mark.parametrize("plan", [None, "", "enterprise", "PRO", ["pro"], {"plan": "pro"}, 42])
def test_unknown_or_malformed_plan_falls_back_to_free(plan):
    assert limits_for(plan) == PLANS["free"]


def test_apply_limits_sets_cpu_mem_and_pids():
    spawner = make_spawner()
    apply_limits(spawner, {"plan": "pro"})
    assert spawner.cpu_limit == 2.0
    assert spawner.mem_limit == "4G"
    assert spawner.extra_host_config["pids_limit"] == 512


def test_apply_limits_keeps_hardening_options():
    spawner = make_spawner()
    apply_limits(spawner, {"plan": "free"})
    assert spawner.extra_host_config["cap_drop"] == ["ALL"]
    assert spawner.extra_host_config["security_opt"] == ["no-new-privileges"]
    assert spawner.extra_host_config["init"] is True


def test_apply_limits_does_not_mutate_shared_config():
    shared = {"cap_drop": ["ALL"]}
    a = SimpleNamespace(cpu_limit=None, mem_limit=None, extra_host_config=shared)
    apply_limits(a, {"plan": "pro"})
    assert "pids_limit" not in shared


@pytest.mark.parametrize("auth_state", [None, {}, {"other": 1}])
def test_apply_limits_without_plan_uses_free(auth_state):
    spawner = make_spawner()
    apply_limits(spawner, auth_state)
    assert spawner.mem_limit == "2G"
    assert spawner.extra_host_config["pids_limit"] == 256


# --- Quota de minutes vérifié auprès de Comptes avant le démarrage

import asyncio  # noqa: E402
import json  # noqa: E402

from tornado import web  # noqa: E402

from rosacademy_hub.quotas import comptes_token, make_quota_hook  # noqa: E402


def run_hook(name, reply):
    calls = []

    async def fetch(url, headers):
        calls.append((url, headers))
        if isinstance(reply, Exception):
            raise reply
        return reply

    hook = make_quota_hook("http://comptes:8300/", "s" * 40, fetch=fetch)
    asyncio.run(hook(SimpleNamespace(user=SimpleNamespace(name=name))))
    return calls


def test_quota_hook_refuses_an_exhausted_student():
    with pytest.raises(web.HTTPError) as err:
        run_hook("u7", (200, json.dumps({"autorise": False}).encode()))
    assert err.value.status_code == 403


def test_quota_hook_sends_the_derived_secret_only():
    calls = run_hook("u7", (200, b'{"autorise": true}'))
    assert calls == [("http://comptes:8300/api/comptes/interne/lab/u7",
                      {"X-Academy-Interne": comptes_token("s" * 40)})]
    assert "s" * 40 not in str(calls)


@pytest.mark.parametrize("reply", [(500, b""), (404, b""), OSError("injoignable")])
def test_quota_hook_lets_the_lab_start_when_comptes_cannot_answer(reply):
    run_hook("u7", reply)


def test_quota_hook_ignores_non_student_accounts():
    assert run_hook("test-e2e-1", (200, b'{"autorise": false}')) == []
