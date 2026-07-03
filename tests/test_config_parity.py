"""MODEL-001 — config parity: the embedded DEFAULT_CONFIG must equal ceph_model_routing.yaml,
and every tier must reference secrets/urls by `*_env` env-var keys only (never literals)."""

from __future__ import annotations

import pathlib

from agent import model_routing as mr


def test_yaml_matches_default_config():
    loaded = mr.load_config()                       # reads ceph_model_routing.yaml (PyYAML present)
    assert loaded == mr.DEFAULT_CONFIG, "ceph_model_routing.yaml drifted from DEFAULT_CONFIG"


def test_tiers_use_env_keys_only_no_literals():
    for tier, cfg in mr.DEFAULT_CONFIG["tiers"].items():
        assert "base_url_env" in cfg, f"{tier} missing base_url_env"
        for k, v in cfg.items():
            assert k not in ("base_url", "api_key", "provider_pin"), f"{tier}.{k} is a literal; use {k}_env"
            if k.endswith("_env"):
                assert isinstance(v, str) and v and "$" not in v and "{" not in v, f"{tier}.{k} malformed"


def test_yaml_has_no_interpolation_literals():
    text = (pathlib.Path(mr.__file__).resolve().parent.parent / "ceph_model_routing.yaml").read_text(encoding="utf-8")
    assert "${" not in text, "yaml must use *_env keys, not ${ENV} interpolation"
