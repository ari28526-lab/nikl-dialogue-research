# D0–D4 recovery planning methods

This package partitions the 817,310 follow-up utterances left outside the frozen
2020–2025 r3 body. It preserves the A–C accounting identity and does not alter
the 4,286,046 aligned utterances, their databases, or their 6-tier TextGrids.

## D0 — frozen input contract

The A–C output manifest, base manifest, QA report, pronunciation type catalog,
and post-QC storage cleanup result are SHA-bound. D: remains the canonical data
drive. No recovery directory on D: was created by this stage.

## D1 — reason-specific exact-ID ledger

Every follow-up utterance occurs exactly once, with year, session, source CSV,
primary status, reason code, recovery family, priority, and shard identifier.
The partition is 95,860 pre-MFA technical + 3,086 post-MFA technical + 718,364
pronunciation follow-up = 817,310. This is routing, not final exclusion.

## D2 — technical recoverability audit

The 98,946 technical rows were joined back to the frozen search-master CSV and
checked read-only against canonical source WAV paths and, for post-MFA cases,
the already materialized r3 WAV/LAB pair. Filename existence alone is not
treated as proof of audio identity; audio-pairing cases therefore remain review
or remapping work rather than automatic recovery.

## D3 — pronunciation-type compression

The 718,364 pronunciation follow-up utterances were compressed by token role
(hold/policy/unknown), token, and year frequency, then linked to the frozen
pronunciation type catalog. Dictionary, rule, and G2P values are reference
evidence only. No candidate was declared the observed realization and no
linguistic decision was automatically approved.

## D4 — first bounded diagnostic shard

The first shard contains all 25 feature-generation failures and five
unique-session alignment-missing cases per year. It is a recovery-path
diagnostic cohort, not a repeated generic pilot. The gate is closed before any
file is copied or MFA is started.

Build status: `passed_stopped_before_materialization_and_mfa`.
