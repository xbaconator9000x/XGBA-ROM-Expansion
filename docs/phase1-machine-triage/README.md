# Phase 1 bulk machine triage — not semantic approval

This pipeline consumes the 14,834-entry pinned semantic queue and SHA-256-bound dossier snapshot. It checks every dossier digest and pinned source identity, excludes the 113 existing analyst-prepared whole-file candidates, and orders remaining files deterministically by P0–P3 risk, incoming include candidates, lexical hits and identity. Use --offset and --limit for bounded batches. Before changing offsets, reconcile earlier batch identities to prevent double counting.

With --source-root, the generator verifies each selected file's exact pinned Git tree identity and recomputes the Git blob SHA-1 from canonical bytes. It produces whole-blob SHA-256, all-lines digest, complete line count, include and conditional compilation anchors, and lexical risk flags. These are structural records, **not** source-backed whole-file semantic understanding. Generated records explicitly say MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW; no prepared or independent approval is granted.

The workflow runs negative controls, pins all five upstream repositories, rehashes 200 selected blobs, saves an artifact and commits one coherent checkpoint to the existing Phase 1 branch. The push is non-forcing. The authoritative gate is never written or advanced. CI success cannot certify independent semantic review.

Baseline: inventory 14,834/14,834 (100%); substantively prepared 113/14,834 (0.7618%); independently approved 0/14,834 (0.0000%); gate FAIL_INCOMPLETE. Machine-triaged count is separate.
