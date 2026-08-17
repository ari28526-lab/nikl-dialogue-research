#!/usr/bin/env python3
"""Create a hash-bound D9 approval after explicit researcher authorization."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_v1_recovery_d9_common import D9_ID, PROJECT_ROOT, load_json, validate_approval
from pipeline_common import atomic_write_json, now_iso


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PROJECT_ROOT / "outputs/releases" / D9_ID)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    pending = load_json(package / "RESEARCHER_APPROVAL_PENDING.json")
    if pending.get("status") != "pending_researcher_approval":
        raise RuntimeError("D9 pending approval template status differs")
    approval = dict(pending)
    approval.update(
        {
            "status": "approved",
            "approved_by": args.approved_by.strip(),
            "approved_at": now_iso(),
            "note": "Explicit researcher authorization recorded after the frozen D9 package was reviewed.",
        }
    )
    if not approval["approved_by"]:
        raise RuntimeError("D9 approved-by is empty")
    output = args.output.resolve()
    atomic_write_json(output, approval)
    validate_approval(
        output,
        execution_contract_path=package / "D9_EXECUTION_CONTRACT.json",
        run_shard_path=package / "D9_RUN_SHARD.json",
        config_path=package / "D9_MFA_CONFIG.json",
    )
    print(json.dumps(approval, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
