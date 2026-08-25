"""Pinned, fail-closed wav2vec2 phone-candidate runner for stage-2 PV-B."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from pathlib import Path
from typing import Callable, Sequence

from pv_b_aux_common import (
    input_summary,
    load_input_manifest,
    now_iso,
    promote_partial,
    public_input_records,
    require_new_output_root,
    sha256_file,
    write_json_new,
    write_jsonl_new,
)


MODEL_ID = "slplab/wav2vec2-xls-r-300m_phone-mfa_korean"
MODEL_REVISION = "e26ff9dfb62169acf445d0060ef56863c018b20e"


def collapse_ctc_ids(
    token_ids: Sequence[int],
    frame_scores: Sequence[float],
    *,
    blank_id: int,
    frame_seconds: float,
    token_for_id: Callable[[int], str],
) -> list[dict]:
    if len(token_ids) != len(frame_scores):
        raise ValueError("token_ids and frame_scores length mismatch")
    spans: list[dict] = []
    current: int | None = None
    start = 0
    scores: list[float] = []

    def flush(end: int) -> None:
        nonlocal current, start, scores
        if current is not None and current != blank_id:
            spans.append(
                {
                    "token_id": current,
                    "token": token_for_id(current),
                    "start_seconds": round(start * frame_seconds, 6),
                    "end_seconds": round(end * frame_seconds, 6),
                    "mean_frame_probability": round(sum(scores) / len(scores), 8),
                }
            )

    for index, (token_id, score) in enumerate(zip(token_ids, frame_scores)):
        token_id = int(token_id)
        if current is None:
            current, start, scores = token_id, index, [float(score)]
        elif token_id == current:
            scores.append(float(score))
        else:
            flush(index)
            current, start, scores = token_id, index, [float(score)]
    flush(len(token_ids))
    return spans


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=70)
    parser.add_argument("--max-per-phenomenon", type=int, default=10)
    parser.add_argument("--max-duration-seconds", type=float, default=30.0)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--allow-pickle-weights", action="store_true")
    return parser


def preflight(args: argparse.Namespace) -> tuple[list[dict], dict]:
    rows = load_input_manifest(
        args.input_manifest.resolve(),
        limit=args.limit,
        max_per_phenomenon=args.max_per_phenomenon,
    )
    for row in rows:
        duration = float(row["_wav_metadata"]["duration_seconds"])
        if duration > args.max_duration_seconds:
            raise RuntimeError(
                f"duration cap exceeded for {row['pv_id']}: {duration:.3f}s"
            )
    partial = require_new_output_root(args.output_dir)
    dependencies = {
        name: importlib.util.find_spec(name) is not None
        for name in ("torch", "transformers", "huggingface_hub", "soundfile")
    }
    report = {
        "schema_version": "stage2_pv_b_wav2vec2_preflight.v1",
        "status": "preflight_passed",
        "execution_requested": bool(args.execute),
        "python": platform.python_version(),
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "trust_remote_code": False,
        "allow_download": bool(args.allow_download),
        "pickle_weight_acknowledged": bool(args.allow_pickle_weights),
        "dependencies_available": dependencies,
        "input": input_summary(rows),
        "output_target_exists": args.output_dir.resolve().exists(),
        "partial_target_exists": partial.exists(),
        "constraints": {
            "machine_candidate_only": True,
            "canonical_textgrid_write": False,
            "canonical_mfa_write": False,
            "source_wav_write": False,
            "automatic_realization_judgement": False,
        },
    }
    return rows, report


def execute(args: argparse.Namespace, rows: list[dict], report: dict) -> None:
    if not args.allow_pickle_weights:
        raise RuntimeError(
            "model uses pytorch_model.bin; execution requires --allow-pickle-weights"
        )
    missing = [
        key for key, available in report["dependencies_available"].items() if not available
    ]
    if missing:
        raise RuntimeError(f"missing runtime dependencies: {missing}")

    target = args.output_dir.resolve()
    partial = require_new_output_root(target)
    partial.mkdir(parents=True)
    write_json_new(
        partial / "RUN_START.json",
        {
            "schema_version": "stage2_pv_b_wav2vec2_run_start.v1",
            "status": "running_machine_candidate_only",
            "started_at": now_iso(),
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "input": public_input_records(rows),
            "preflight": report,
        },
    )
    try:
        import soundfile as sf
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForCTC, AutoProcessor

        if args.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        snapshot = Path(
            snapshot_download(
                repo_id=MODEL_ID,
                revision=MODEL_REVISION,
                local_files_only=not args.allow_download,
            )
        )
        model_files = []
        for path in sorted(snapshot.iterdir()):
            if path.is_file():
                model_files.append(
                    {
                        "name": path.name,
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
        write_json_new(
            partial / "MODEL_RESOLUTION.json",
            {
                "schema_version": "stage2_pv_b_wav2vec2_model_resolution.v1",
                "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "model_files": model_files,
            },
        )
        processor = AutoProcessor.from_pretrained(
            snapshot, trust_remote_code=False, local_files_only=True
        )
        model = AutoModelForCTC.from_pretrained(
            snapshot, trust_remote_code=False, local_files_only=True
        )
        device = torch.device(args.device)
        model.to(device)
        model.eval()
        sample_rate = int(processor.feature_extractor.sampling_rate)
        ratio = float(getattr(model.config, "inputs_to_logits_ratio", 0))
        if ratio <= 0:
            raise RuntimeError("model inputs_to_logits_ratio is unavailable")
        frame_seconds = ratio / sample_rate
        blank_id = processor.tokenizer.pad_token_id
        if blank_id is None:
            blank_id = model.config.pad_token_id
        if blank_id is None:
            raise RuntimeError("CTC blank token id is unavailable")

        outputs = []
        for row in rows:
            audio, rate = sf.read(
                str(row["_wav_path"]), dtype="float32", always_2d=True
            )
            if int(rate) != sample_rate:
                raise RuntimeError(
                    f"sample rate mismatch for {row['pv_id']}: "
                    f"{rate} != {sample_rate}; silent resampling is forbidden"
                )
            waveform = audio.mean(axis=1)
            inputs = processor(
                waveform, sampling_rate=sample_rate, return_tensors="pt"
            ).input_values.to(device)
            with torch.no_grad():
                logits = model(inputs).logits[0]
                probabilities = torch.softmax(logits, dim=-1)
                scores, predicted = torch.max(probabilities, dim=-1)
            ids = predicted.detach().cpu().tolist()
            frame_scores = scores.detach().cpu().tolist()
            spans = collapse_ctc_ids(
                ids,
                frame_scores,
                blank_id=int(blank_id),
                frame_seconds=frame_seconds,
                token_for_id=lambda value: str(
                    processor.tokenizer.convert_ids_to_tokens(value)
                ),
            )
            outputs.append(
                {
                    "schema_version": "stage2_pv_b_wav2vec2_candidate.v1",
                    "result_status": "machine_candidate_not_realization",
                    "pv_id": row["pv_id"],
                    "phenomenon_code": row["phenomenon_code"],
                    "occurrence_id": row["occurrence_id"],
                    "utt_id": row["utt_id"],
                    "source_wav_sha256": row["_wav_sha256"],
                    "model_id": MODEL_ID,
                    "model_revision": MODEL_REVISION,
                    "sample_rate": sample_rate,
                    "frame_seconds": round(frame_seconds, 9),
                    "decoded_sequence": processor.batch_decode([ids])[0],
                    "phone_candidates": spans,
                    "human_verification_required": True,
                    "canonical_assets_modified": False,
                }
            )
        write_jsonl_new(partial / "acoustic_phone_candidates.jsonl", outputs)
        write_json_new(
            partial / "RUN_RESULT.json",
            {
                "schema_version": "stage2_pv_b_wav2vec2_result.v1",
                "status": "completed_machine_candidate_not_realization",
                "finished_at": now_iso(),
                "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "input_count": len(rows),
                "output_count": len(outputs),
                "candidate_jsonl_sha256": sha256_file(
                    partial / "acoustic_phone_candidates.jsonl"
                ),
                "canonical_assets_modified": False,
            },
        )
    except Exception as exc:
        if not (partial / "RUN_FAILURE.json").exists():
            write_json_new(
                partial / "RUN_FAILURE.json",
                {
                    "schema_version": "stage2_pv_b_wav2vec2_failure.v1",
                    "status": "failed_partial_preserved",
                    "finished_at": now_iso(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
        raise
    promote_partial(partial, target)
    print(json.dumps({"status": "completed", "output_dir": str(target)}))


def main() -> None:
    args = build_parser().parse_args()
    rows, report = preflight(args)
    if not args.execute:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    execute(args, rows, report)


if __name__ == "__main__":
    main()
