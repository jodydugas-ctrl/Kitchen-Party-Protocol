"""KPP ports for model-independent Anchor decision batching and optional Decider AI boost."""
from __future__ import annotations

from pathlib import Path

from ..anchor_decision_boost import (
    DEFAULT_BOOST_PROVIDER,
    DEFAULT_CONFIDENCE_THRESHOLD,
    GeminiDecisionBoostAdapter,
    OpenRouterDecisionBoostAdapter,
    SUPPORTED_BOOST_PROVIDERS,
    build_decode_batch,
    build_encode_batch,
    create_decision_boost_adapter,
    decode_through_anchor,
    encode_to_anchor,
    involves_anchor_coding,
    recipe_boost_status,
    to_gemini_decisions_request,
    to_openrouter_decisions_request,
)
from .core import KPPError, parse_json, read_json

MAX_INPUT_BYTES = 1_048_576


def _read_source_or_json(path: Path):
    target = Path(path)
    if not target.is_file() or target.is_symlink():
        raise KPPError(f"Input must be a regular file: {target}")
    raw = target.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise KPPError(f"Input exceeds {MAX_INPUT_BYTES}-byte limit: {target}")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise KPPError(f"Input must be UTF-8: {target}") from exc
    if target.suffix.lower() == ".json":
        return parse_json(text)
    return text


def _provider_from_responses(
    responses_path: Path | None,
    confidence_threshold: float,
    *,
    provider: str = DEFAULT_BOOST_PROVIDER,
    model: str | None = None,
):
    if responses_path is None:
        return None
    payload = read_json(responses_path)
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
        raise KPPError("Responses JSON must be an object containing an 'answers' map")
    return create_decision_boost_adapter(
        provider=provider,
        model=model,
        transport=lambda _request: payload,
        confidence_threshold=confidence_threshold,
    )


def boost_status(recipe_path: Path) -> dict:
    """Report whether the pinned recipe selects ``anchor-decision-boost``."""
    try:
        return recipe_boost_status(read_json(recipe_path))
    except ValueError as exc:
        raise KPPError(str(exc)) from exc


def export_batch(
    input_path: Path,
    *,
    mode: str = "encode",
    design_id: str = "anchor-system",
    goal: str = "Encode Anchor design",
    stimulus_path: Path | None = None,
    openrouter_request: bool = False,
    gemini_request: bool = False,
    model: str | None = None,
) -> dict:
    """Build an ``anchor.decision-batch/1`` (or OpenRouter / Gemini Decisions request) from files."""
    if openrouter_request and gemini_request:
        raise KPPError("Choose at most one of --openrouter-request or --gemini-request")
    try:
        if mode == "encode":
            batch = build_encode_batch(_read_source_or_json(input_path), design_id=design_id, goal=goal)
        elif mode == "decode":
            if stimulus_path is None:
                raise KPPError("decode mode requires --stimulus FILE")
            contract = read_json(input_path)
            stimulus = _read_source_or_json(stimulus_path)
            batch = build_decode_batch(contract, stimulus)
        else:
            raise KPPError("Batch mode must be encode or decode")
        if openrouter_request:
            return to_openrouter_decisions_request(batch, **({"model": model} if model else {}))
        if gemini_request:
            return to_gemini_decisions_request(batch, **({"model": model} if model else {}))
        return batch
    except ValueError as exc:
        raise KPPError(str(exc)) from exc


def encode_file(
    input_path: Path,
    *,
    design_id: str,
    goal: str,
    recipe_path: Path | None = None,
    responses_path: Path | None = None,
    provider: str = DEFAULT_BOOST_PROVIDER,
    model: str | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict:
    """Encode a file (source, spec, or scan JSON) into an Anchor design packet."""
    try:
        recipe = read_json(recipe_path) if recipe_path is not None else None
        decision_provider = _provider_from_responses(
            responses_path,
            confidence_threshold,
            provider=provider,
            model=model,
        )
        return encode_to_anchor(
            _read_source_or_json(input_path),
            design_id=design_id,
            goal=goal,
            recipe=recipe,
            decision_provider=decision_provider,
            confidence_threshold=confidence_threshold,
        )
    except ValueError as exc:
        raise KPPError(str(exc)) from exc


def decode_file(
    contract_path: Path,
    stimulus_path: Path,
    *,
    recipe_path: Path | None = None,
    responses_path: Path | None = None,
    provider: str = DEFAULT_BOOST_PROVIDER,
    model: str | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict:
    """Decode and route a stimulus file through an Anchor design or KPP recipe contract."""
    try:
        contract = read_json(contract_path)
        recipe = read_json(recipe_path) if recipe_path is not None else None
        decision_provider = _provider_from_responses(
            responses_path,
            confidence_threshold,
            provider=provider,
            model=model,
        )
        stimulus = _read_source_or_json(stimulus_path)
        return decode_through_anchor(
            contract,
            stimulus,
            recipe=recipe,
            decision_provider=decision_provider,
            confidence_threshold=confidence_threshold,
        )
    except ValueError as exc:
        raise KPPError(str(exc)) from exc
