"""
Tests for abi_core.capabilities (Phase 0 — foundations).

Covers the capability profile vector, gap detection, scalar match scoring,
model selection/ranking, the seed catalog, and profile refinement.
"""

import pytest

from abi_core.capabilities import (
    CAPABILITY_DIMENSIONS,
    CapabilityProfile,
    TaskProfile,
    ModelProfile,
    SOURCE_SEED,
    SOURCE_MEASURED,
    capability_gaps,
    match_score,
    rank_models,
    select_model,
    seed_catalog,
    get_seed_profile,
)


class TestCapabilityProfile:
    def test_seven_dimensions(self):
        assert len(CAPABILITY_DIMENSIONS) == 7
        assert "instruction_following" in CAPABILITY_DIMENSIONS

    def test_defaults_zero(self):
        p = CapabilityProfile()
        assert all(p.get(d) == 0.0 for d in CAPABILITY_DIMENSIONS)

    def test_clamped_to_unit_range(self):
        p = CapabilityProfile(code_generation=1.5, tool_usage=-0.3)
        assert p.code_generation == 1.0
        assert p.tool_usage == 0.0

    def test_dict_roundtrip(self):
        p = CapabilityProfile(reasoning=0.7, planning=0.4)
        assert CapabilityProfile.from_dict(p.to_dict()) == p

    def test_get_unknown_dimension_raises(self):
        with pytest.raises(KeyError):
            CapabilityProfile().get("charisma")


class TestGaps:
    def test_gap_only_where_task_exceeds_model(self):
        task = TaskProfile(capabilities=CapabilityProfile(tool_usage=0.95, code_generation=0.9))
        model = ModelProfile("m", CapabilityProfile(tool_usage=0.30, code_generation=0.95))
        gaps = capability_gaps(task, model)
        # tool_usage is a gap (0.95 > 0.30); code_generation is not (model exceeds)
        assert set(gaps.keys()) == {"tool_usage"}
        assert gaps["tool_usage"] == pytest.approx(0.65)

    def test_no_gaps_when_model_covers(self):
        task = TaskProfile(capabilities=CapabilityProfile(reasoning=0.5))
        model = ModelProfile("m", CapabilityProfile(reasoning=0.8))
        assert capability_gaps(task, model) == {}


class TestMatchScore:
    def test_perfect_cover_scores_one(self):
        task = TaskProfile(capabilities=CapabilityProfile(code_generation=0.5, reasoning=0.5))
        model = ModelProfile("m", CapabilityProfile(code_generation=0.9, reasoning=0.9))
        assert match_score(task, model) == pytest.approx(1.0)

    def test_empty_task_scores_one(self):
        task = TaskProfile(capabilities=CapabilityProfile())
        model = ModelProfile("m", CapabilityProfile())
        assert match_score(task, model) == 1.0

    def test_surplus_does_not_reward(self):
        # Two models both fully cover the task; extra capability must not matter.
        task = TaskProfile(capabilities=CapabilityProfile(tool_usage=0.5))
        just_enough = ModelProfile("a", CapabilityProfile(tool_usage=0.5))
        way_over = ModelProfile("b", CapabilityProfile(tool_usage=1.0, reasoning=1.0))
        assert match_score(task, just_enough) == pytest.approx(match_score(task, way_over))

    def test_deficit_penalizes_proportionally(self):
        task = TaskProfile(capabilities=CapabilityProfile(tool_usage=1.0))
        model = ModelProfile("m", CapabilityProfile(tool_usage=0.4))
        # single dimension, weight = requirement = 1.0, deficit 0.6 → score 0.4
        assert match_score(task, model) == pytest.approx(0.4)

    def test_weights_shift_emphasis(self):
        # Task requires two dims equally by value, but weights tool_usage heavier.
        task = TaskProfile(
            capabilities=CapabilityProfile(tool_usage=1.0, reasoning=1.0),
            weights={"tool_usage": 3.0, "reasoning": 1.0},
        )
        # Model lacks tool_usage but has reasoning.
        model = ModelProfile("m", CapabilityProfile(tool_usage=0.0, reasoning=1.0))
        # penalty = 3*1.0 + 1*0.0 = 3; total_w = 4 → 1 - 3/4 = 0.25
        assert match_score(task, model) == pytest.approx(0.25)


class TestSelection:
    def test_small_obedient_beats_large_disobedient_for_orchestration(self):
        # The article's thesis: orchestration needs instruction_following, not raw power.
        orchestration = TaskProfile(capabilities=CapabilityProfile(
            instruction_following=0.9,
            structured_output=0.8,
            reasoning=0.4,
        ))
        big = ModelProfile("devstral:24b", CapabilityProfile(
            reasoning=0.9, code_generation=0.9, instruction_following=0.35, structured_output=0.85,
        ))
        small = ModelProfile("qwen2.5:3b", CapabilityProfile(
            reasoning=0.45, instruction_following=0.75, structured_output=0.70,
        ))
        result = select_model(orchestration, [big, small])
        assert result.model_name == "qwen2.5:3b"

    def test_empty_catalog_returns_none(self):
        task = TaskProfile(capabilities=CapabilityProfile(reasoning=0.5))
        result = select_model(task, [])
        assert result.model is None
        assert result.score == 0.0

    def test_ranking_is_deterministic_on_ties(self):
        task = TaskProfile(capabilities=CapabilityProfile())  # everyone scores 1.0
        m_b = ModelProfile("b", CapabilityProfile())
        m_a = ModelProfile("a", CapabilityProfile())
        ranked = rank_models(task, [m_b, m_a])
        assert [sm.model.model for sm in ranked] == ["a", "b"]  # tie broken by name

    def test_result_reports_gaps_of_chosen_model(self):
        task = TaskProfile(capabilities=CapabilityProfile(tool_usage=0.9))
        model = ModelProfile("m", CapabilityProfile(tool_usage=0.3))
        result = select_model(task, [model])
        assert "tool_usage" in result.gaps


class TestSeedCatalog:
    def test_seed_profiles_are_marked_seed(self):
        for mp in seed_catalog():
            assert mp.source == SOURCE_SEED
            assert mp.samples == 0

    def test_seed_encodes_big_model_low_adherence(self):
        devstral = get_seed_profile("devstral:24b")
        qwen = get_seed_profile("qwen2.5:3b")
        assert devstral is not None and qwen is not None
        # big model: high code, low instruction_following
        assert devstral.capability("code_generation") > 0.8
        assert devstral.capability("instruction_following") < qwen.capability("instruction_following")

    def test_seed_catalog_filter(self):
        subset = seed_catalog(["qwen2.5:3b", "does-not-exist"])
        assert [m.model for m in subset] == ["qwen2.5:3b"]


class TestObservationRefinement:
    def test_observation_updates_score_and_marks_measured(self):
        mp = get_seed_profile("devstral:24b")
        # observe a strong tool_usage once
        updated = mp.with_observation("tool_usage", 0.9)
        assert updated.source == SOURCE_MEASURED
        assert updated.samples == mp.samples + 1
        # running mean from n=0: new value == observed
        assert updated.capability("tool_usage") == pytest.approx(0.9)
        # original is unchanged (frozen / immutable)
        assert mp.source == SOURCE_SEED


class TestIO:
    def test_save_load_roundtrip(self, tmp_path):
        from abi_core.capabilities import save_profiles, load_profiles, seed_catalog

        path = tmp_path / "profiles.json"
        original = seed_catalog()
        save_profiles(original, path, generator="test")
        loaded = load_profiles(path)

        assert {m.model for m in loaded} == {m.model for m in original}
        by_name = {m.model: m for m in loaded}
        for m in original:
            assert by_name[m.model].capabilities == m.capabilities
            assert by_name[m.model].source == m.source

    def test_load_missing_file_raises(self, tmp_path):
        from abi_core.capabilities import load_profiles

        with pytest.raises(FileNotFoundError):
            load_profiles(tmp_path / "nope.json")

    def test_load_invalid_json_raises(self, tmp_path):
        from abi_core.capabilities import load_profiles

        p = tmp_path / "bad.json"
        p.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError):
            load_profiles(p)

    def test_load_rejects_newer_schema(self, tmp_path):
        import json
        from abi_core.capabilities import load_profiles

        p = tmp_path / "future.json"
        p.write_text(json.dumps({"schema_version": 999, "models": []}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_profiles(p)

    def test_load_catalog_returns_dict(self, tmp_path):
        from abi_core.capabilities import save_profiles, load_catalog, seed_catalog

        path = tmp_path / "profiles.json"
        save_profiles(seed_catalog(), path)
        catalog = load_catalog(path)
        assert "qwen2.5:3b" in catalog
        assert catalog["qwen2.5:3b"].model == "qwen2.5:3b"

    def test_missing_dimensions_default_zero(self, tmp_path):
        import json
        from abi_core.capabilities import load_profiles

        p = tmp_path / "partial.json"
        p.write_text(json.dumps({
            "schema_version": 1,
            "models": [{"model": "x", "capabilities": {"reasoning": 0.5}}],
        }), encoding="utf-8")
        loaded = load_profiles(p)
        assert loaded[0].capability("reasoning") == 0.5
        assert loaded[0].capability("tool_usage") == 0.0


class TestViz:
    def test_render_bars_has_row_per_dimension(self):
        from abi_core.capabilities import render_bars, get_seed_profile

        out = render_bars(get_seed_profile("qwen2.5:3b").capabilities, primary_label="qwen")
        # one line per dimension (no legend line when secondary is None)
        assert out.count("\n") == len(CAPABILITY_DIMENSIONS) - 1

    def test_render_bars_overlay_shows_gap(self):
        from abi_core.capabilities import render_bars

        model = CapabilityProfile(tool_usage=0.3)
        task = CapabilityProfile(tool_usage=0.9)
        out = render_bars(model, primary_label="model", secondary=task, secondary_label="required")
        assert "gap" in out
        assert "legend" in out


class TestStats:
    def test_wilson_zero_n_is_maximally_uncertain(self):
        from abi_core.capabilities.stats import wilson_interval
        ci = wilson_interval(0, 0)
        assert ci.low == 0.0 and ci.high == 1.0

    def test_wilson_bounds_clamped(self):
        from abi_core.capabilities.stats import wilson_interval
        ci = wilson_interval(10, 10)  # all successes
        assert 0.0 <= ci.low <= ci.high <= 1.0
        assert ci.ratio == 1.0

    def test_wilson_narrows_with_n(self):
        from abi_core.capabilities.stats import wilson_interval
        narrow = wilson_interval(50, 100)
        wide = wilson_interval(5, 10)
        assert narrow.width < wide.width

    def test_wilson_rejects_bad_successes(self):
        from abi_core.capabilities.stats import wilson_interval
        with pytest.raises(ValueError):
            wilson_interval(11, 10)

    def test_stop_at_ceiling(self):
        from abi_core.capabilities.stats import should_stop
        assert should_stop(20, 40, n_max=40) is True

    def test_no_stop_below_floor(self):
        from abi_core.capabilities.stats import should_stop
        assert should_stop(5, 5, n_min=10) is False

    def test_stop_when_interval_narrow(self):
        from abi_core.capabilities.stats import should_stop, wilson_interval
        # 100 clean trials → very narrow interval → stop even below n_max
        assert should_stop(100, 100, n_min=10, n_max=1000, ci_width=0.15) is True


class TestProbes:
    def test_probe_rejects_bad_dimension(self):
        from abi_core.capabilities.probes import Probe
        with pytest.raises(ValueError):
            Probe(id="x", dimension="nope", difficulty="easy", prompt="p", verify=lambda o: True)

    def test_probe_rejects_bad_difficulty(self):
        from abi_core.capabilities.probes import Probe
        with pytest.raises(ValueError):
            Probe(id="x", dimension="reasoning", difficulty="insane", prompt="p", verify=lambda o: True)

    def test_probe_result_ratio_and_interval(self):
        from abi_core.capabilities.probes import ProbeResult
        r = ProbeResult(probe_id="p", dimension="reasoning", difficulty="easy", successes=8, n=10)
        assert r.ratio == pytest.approx(0.8)
        d = r.to_dict()
        assert d["ci_low"] <= 0.8 <= d["ci_high"]
        assert d["n"] == 10


class TestProfiler:
    def test_run_probe_perfect_model(self):
        from abi_core.capabilities.probes import Probe
        from abi_core.capabilities.profiler import run_probe
        probe = Probe(id="p", dimension="reasoning", difficulty="easy",
                      prompt="2+2?", verify=lambda o: o == "4")
        res = run_probe(probe, lambda prompt, tools: "4", n_min=10, n_max=40)
        assert res.ratio == 1.0 and res.n >= 10

    def test_verifier_crash_counts_as_failure(self):
        from abi_core.capabilities.probes import Probe
        from abi_core.capabilities.profiler import run_probe
        def boom(o): raise RuntimeError("bad")
        probe = Probe(id="p", dimension="reasoning", difficulty="easy",
                      prompt="x", verify=boom)
        res = run_probe(probe, lambda prompt, tools: "x", n_min=10, n_max=10)
        assert res.successes == 0

    def test_aggregate_weights_hard_more(self):
        from abi_core.capabilities.probes import ProbeResult
        from abi_core.capabilities.profiler import aggregate_dimension
        easy = ProbeResult("e", "reasoning", "easy", successes=10, n=10)   # 1.0
        hard = ProbeResult("h", "reasoning", "hard", successes=0, n=10)    # 0.0
        # weights 1 and 3 → (1*1.0 + 3*0.0)/4 = 0.25
        assert aggregate_dimension([easy, hard]) == pytest.approx(0.25)

    def test_profile_model_builds_measured_profile(self):
        from abi_core.capabilities.probes import Probe
        from abi_core.capabilities.profiler import profile_model
        from abi_core.capabilities.profiles import SOURCE_MEASURED
        probes = [
            Probe(id="r1", dimension="reasoning", difficulty="easy",
                  prompt="2+2?", verify=lambda o: o == "4"),
            Probe(id="s1", dimension="structured_output", difficulty="easy",
                  prompt="json", verify=lambda o: o == "{}"),
        ]
        def run_fn(prompt, tools):
            return "4" if prompt == "2+2?" else "{}"
        mp = profile_model("test-model", probes, run_fn, n_min=10, n_max=10)
        assert mp.source == SOURCE_MEASURED
        assert mp.capability("reasoning") == pytest.approx(1.0)
        assert mp.capability("structured_output") == pytest.approx(1.0)
        assert "probe_results" in mp.metadata


class TestProbeSuite:
    def test_all_builtin_probes_valid(self):
        from abi_core.capabilities.probe_suite import builtin_probes
        probes = builtin_probes()
        assert len(probes) >= 7
        # each probe already validated its dimension/difficulty on construction
        dims = {p.dimension for p in probes}
        assert "instruction_following" in dims

    def test_verifiers_pass_on_correct_output(self):
        from abi_core.capabilities.probe_suite import builtin_probes
        by_id = {p.id: p for p in builtin_probes()}
        assert by_id["reason.easy.add"].verify("43") is True
        assert by_id["reason.easy.add"].verify("44") is False
        assert by_id["instr.easy.wordcap"].verify(" Banana ") is True
        assert by_id["struct.easy.json"].verify('{"ok": true}') is True
        assert by_id["tool.easy.name"].verify("write_file") is True

    def test_profile_with_builtin_battery(self):
        from abi_core.capabilities.probe_suite import builtin_probes
        from abi_core.capabilities.profiler import profile_model
        # perfect model: always returns the correct answer per probe id
        answers = {
            "struct.easy.json": '{"ok": true}',
            "struct.medium.schema": '{"name": "x", "age": 3}',
            "reason.easy.add": "43",
            "reason.medium.seq": "30",
            "instr.easy.wordcap": "banana",
            "instr.medium.noletter": "kiwi",
            "code.easy.func": "def add(a, b): return a+b",
            "plan.easy.steps": "1. boil 2. pour 3. steep",
            "ctx.medium.needle": "ZX42",
            "tool.easy.name": "write_file",
        }
        probes = builtin_probes()
        prompt_to_id = {p.prompt: p.id for p in probes}
        def run_fn(prompt, tools):
            return answers[prompt_to_id[prompt]]
        mp = profile_model("perfect", probes, run_fn, n_min=10, n_max=10)
        assert mp.capability("reasoning") == pytest.approx(1.0)
        assert mp.capability("instruction_following") == pytest.approx(1.0)
