# Ticket 001: Adopt wellmanifest new-project governance

- **ID**: ticket-001
- **Owner**: tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21

## Goal and scope

Adopt `wellmanifest/new-project` (`0.20.166`, revision `c9bb73ce5ce861e78c26619e36e5b016fda56e2d`) and register baseline/deployment `wellman` standards (`wellmanifest/docs`, `wellmanifest/logs`, `wellmanifest/poa`, `wellmanifest/authority-lifecycle`, `wellmanifest/new-project`) for `semcod/archpat`.

## Acceptance criteria

- [x] AC-01: `wellmanifest/new-project` adoption lock (`.governance/manifest.lock.json`) and host hooks (`.githooks/`) are installed and active via `./scripts/install-agent-hosts.sh`.
- [x] AC-02: `./project/governance-check.sh --base main` passes with 0 errors and 0 warnings.
- [x] AC-03: `wellman check` passes with 0 errors and 0 warnings.
- [x] AC-04: All `archpat` unit and integration tests pass inside the ticket worktree.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
