"""
Capability profiling commands for ABI-Core CLI.

Capability matching selects models by comparing what a task *requires* against
what a model *provides*, over 7 dimensions. Model profiling is a **dev-time**
step: profile candidate models once, export JSON, load it into the agentic
system, and let runtime refine it with real data.

Subcommands:
    abi-core capabilities list                 List models in a profile source
    abi-core capabilities show <model>         Show a model's profile (bars or radar PNG)
    abi-core capabilities profile <model>      (pending) Run probes to measure a model

``list`` and ``show`` work today against the built-in seed catalog or a loaded
JSON file. ``profile`` (running the probe battery) is pending the profiling
methodology sub-spec (see .abi/specs/capability-profiling-methodology.md).
"""

import click

from abi_core.capabilities import (
    get_seed_profile,
    seed_catalog,
    load_catalog,
    render_bars,
    render_radar_png,
)


def _resolve_catalog(source: str | None):
    """Return a {model: ModelProfile} dict from a JSON file or the seed catalog."""
    if source:
        return load_catalog(source)
    return {p.model: p for p in seed_catalog()}


@click.group("capabilities")
def capabilities():
    """Inspect and (soon) measure model capability profiles."""
    pass


@capabilities.command("list")
@click.option("--source", type=click.Path(exists=True), default=None,
              help="JSON profile file to read (default: built-in seed catalog).")
def list_models(source):
    """List models available in a profile source with their provenance."""
    try:
        catalog = _resolve_catalog(source)
    except Exception as e:
        click.echo(f"❌ Could not load profiles: {e}")
        return 1

    if not catalog:
        click.echo("No model profiles found.")
        return 0

    origin = source or "built-in seed catalog"
    click.echo(f"📚 Model profiles ({origin}):")
    click.echo("")
    for name, profile in sorted(catalog.items()):
        click.echo(f"  • {name}  [{profile.source}, samples={profile.samples}]")
    return 0


@capabilities.command("show")
@click.argument("model")
@click.option("--source", type=click.Path(exists=True), default=None,
              help="JSON profile file to read (default: built-in seed catalog).")
@click.option("--radar", "radar_path", type=click.Path(), default=None,
              help="Write a radar chart PNG to this path (requires matplotlib).")
def show_model(model, source, radar_path):
    """Show MODEL's capability profile as terminal bars (and optionally a radar PNG)."""
    try:
        catalog = _resolve_catalog(source)
    except Exception as e:
        click.echo(f"❌ Could not load profiles: {e}")
        return 1

    profile = catalog.get(model) or (get_seed_profile(model) if source is None else None)
    if profile is None:
        click.echo(f"❌ Model '{model}' not found in {source or 'seed catalog'}.")
        click.echo("💡 Use 'abi-core capabilities list' to see available models.")
        return 1

    click.echo(f"🧬 {model}  [{profile.source}, samples={profile.samples}]")
    click.echo("")
    click.echo(render_bars(profile.capabilities, primary_label=model))

    if radar_path:
        try:
            render_radar_png(profile.capabilities, radar_path, primary_label=model,
                             title=f"Capability Profile — {model}")
            click.echo("")
            click.echo(f"🖼️  Radar chart written to {radar_path}")
        except RuntimeError as e:
            click.echo(f"⚠️  {e}")
            return 1
    return 0


class ProfilingError(click.ClickException):
    """Fatal profiling error that should stop the run immediately."""


def _check_ollama_model(model: str, host: str) -> None:
    """Verify Ollama is reachable and the model is pulled; fail fast otherwise."""
    import httpx

    try:
        resp = httpx.get(f"{host}/api/tags", timeout=10.0)
        resp.raise_for_status()
    except Exception as e:
        raise ProfilingError(
            f"Cannot reach Ollama at {host}: {e}\n"
            f"   Is Ollama running? Try: curl {host}/api/tags"
        )

    available = [m.get("name", "") for m in resp.json().get("models", [])]
    # Ollama tags are like "qwen2.5:3b"; accept an exact match or a bare name.
    if model not in available and f"{model}:latest" not in available:
        listing = "\n     ".join(available) if available else "(none pulled)"
        raise ProfilingError(
            f"Model '{model}' is not available on {host}.\n"
            f"   Pulled models:\n     {listing}\n"
            f"   Pull it with: ollama pull {model}"
        )


def _ollama_run_fn(model: str, host: str, timeout: float = 120.0):
    """Build a (prompt, tools) -> output function backed by Ollama's HTTP API."""
    import httpx

    def run_fn(prompt: str, tools) -> str:
        try:
            resp = httpx.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0}},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except httpx.HTTPStatusError as e:
            # 404 mid-run means the model vanished (unloaded/removed) — abort,
            # don't keep hammering N times against a dead model.
            if e.response.status_code == 404:
                raise ProfilingError(f"Model '{model}' not found at {host} (404). Aborting.")
            click.echo(f"⚠️  generation failed: {e}")
            return ""
        except Exception as e:
            click.echo(f"⚠️  generation failed: {e}")
            return ""

    return run_fn


@capabilities.command("profile")
@click.argument("model")
@click.option("--host", default="http://localhost:11434", help="Ollama host URL.")
@click.option("--output", type=click.Path(), default=None, help="Write the measured profile JSON here.")
@click.option("--reps", "n_min", default=10, help="Repetitions per probe at each level.")
@click.option("--timeout", default=300.0, help="Per-generation timeout in seconds (raise for big models on modest hardware).")
def profile_model(model, host, output, n_min, timeout):
    """Measure MODEL's operational envelopes (v2) and export its profile."""
    from abi_core.capabilities.probe_suite import (
        LEVELED_PROBES, LEVELED_SUITE_VERSION, leveled_dimensions,
    )
    from abi_core.capabilities.profiler import profile_model_envelope
    from abi_core.capabilities import save_profiles, render_bars

    click.echo(f"🔬 Profiling '{model}' via {host} (envelope suite v{LEVELED_SUITE_VERSION})...")
    click.echo(f"   Measuring dimensions: {', '.join(leveled_dimensions())}")
    _check_ollama_model(model, host)  # fail fast if unreachable / not pulled

    run_fn = _ollama_run_fn(model, host, timeout=timeout)

    # Warm up: the first call loads the model into memory (slow for big models).
    # Do it once, outside the timed probes, so model load doesn't trip a timeout.
    click.echo("⏳ Warming up (loading model into memory)...")
    run_fn("Reply with: ok", [])

    mp = profile_model_envelope(
        model, LEVELED_PROBES, run_fn, reps=n_min,
        metadata={"suite_version": LEVELED_SUITE_VERSION, "host": host, "temperature": 0},
    )

    click.echo("")
    click.echo(render_bars(mp.capabilities, primary_label=model))
    click.echo(f"\n  [envelope score = highest reliable level / max; measured over {mp.samples} runs]")
    unmeasured = mp.metadata.get("unmeasured_dimensions", [])
    if unmeasured:
        click.echo(f"  [not measured (needs execution sandbox): {', '.join(unmeasured)}]")

    if output:
        save_profiles([mp], output, generator=f"abi-core capabilities profile (envelope suite v{LEVELED_SUITE_VERSION})")
        click.echo(f"💾 Profile written to {output}")
    else:
        click.echo("💡 Pass --output profiles.json to save this profile.")
    return 0
