# DB v1 active annotation view contract v1

RC0 is the default for every utterance. Join this exception table on `(year, utt_id)`. If `active_annotation_source=curated`, use the curated transcript, orthographic Roman, and TextGrid pointer. Otherwise preserve RC0. Diagnostic evidence is never promoted to an active annotation. D9 phones remain reference-only and pending morph/phoneme fields are not synthesized.
