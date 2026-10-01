from types import SimpleNamespace

import pytest

from rosacademy_hub.quotas import DEFAULT_PLAN, PLANS, PlanLimits, apply_limits, limits_for


def make_spawner():
    return SimpleNamespace(
        cpu_limit=None,
        mem_limit=None,
        extra_host_config={"cap_drop": ["ALL"], "security_opt": ["no-new-privileges"]},
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
