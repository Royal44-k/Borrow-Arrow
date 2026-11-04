# V1.6 whole-change independent review — final

Reviewed 2026-11-01. **PASS within the reviewed implementation and supplied final QA scope. No unresolved P0, P1 or P2 finding remains.** All three incremental spoken-copy findings are closed. No further implementation change is requested by this review. Production deployment and post-release verification are separate tasks and were not performed here.

## Scope and method

Read `spec.md`, `ledger.md`, `final-review-brief.md`, cumulative `final-review.diff`, Task 1/2/3 reports, their independent reviews and fix reviews, and current integration source. Reviewed the later frozen spoken-copy changes and their scoped fixes separately. Assessed supplied test/GUI/media reports without rerunning already-passed suites. This reviewer did not modify production source, spawn agents, access credentials, call live AI or delete workspace content; only this review document was written.

## Integration result

- Backend V1.6 is a version-gated overlay. Warning/probe/drawn bows award zero; first reception awards 50,000; turning and reloading retain 50,000; actual second volleys award 100,000. Zero-arrow outcomes distinguish early departure, unfired bows and probes falling into water. Stop/feint choices persist real consequences rather than silently awarding another volley.
- Battle metadata drives the frontend phases and releases operations after presentation. Pause, skip and low-motion completion do not call a story mutation. Preview does not become new evidence. Backdrop errors release continuation; WebGL construction failure retains a continue path. Actual per-side load reaches inspection and maneuver views independently of presentation completion.
- Model assembly uses the existing named groups and target contract. Empty assembly hides straw/cloth; cargo moves. Per-side arrows follow backend load. Maneuver raycasts change actual model headings and emit the validated range. The earlier camera clamp and hollow companion-bundle findings are fixed.
- Speaker-qualified speech preserves legacy manifest fallback, and generation tickets prevent superseded callbacks from changing active narration status. Battle presentation gates dialogue. Updated speech avoids repeated precise river receipt numbers and cause-history recitation; the north location subtitle is `江上 · 南船`.
- Earlier saves retain their stored version and earlier scene/model routing. V1.6 forks preserve learner-original precedence and inherited read-only context. No save migration is introduced.

## Findings resolved

The incremental dialogue review identified three P2 continuity defects; all were checked in current source and are **CLOSED**:

1. `C_second_rain` now says `箭越过江面`, avoiding invented fog on the clear route.
2. `C_draw_bows` now says `来船来意不明`, preserving the already audible drum calls.
3. `C_stop_signal` now orders the watch to track turning boats and guard the gate, without treating already identified clear-route straw as unknown figures.

The additional Cao Cao wording `盯紧外侧水道` preserves the concrete order. These fixes change words only, leaving node/action/state/yield contracts and legacy strings intact. The earlier detailed finding history is summarized here to avoid presenting resolved defects as open release blockers.

## Final evidence assessed

- Backend full suite: 282 passing before the final three-sentence fix; subsequent targeted narrative suite: 87 passing, including the new mist/clear copy checks. Frontend final `qa/frontend-final.txt`: 142 tests, 142 passing, zero failures. Parent reports TypeScript check and final dist build successful. These are supplied executions, not reviewer reruns.
- Exhaustive authored-state export: 130,056 states, 71 nodes, 662 role/scenario conditional edges. Earlier 15 complete real GUI routes cover 16 new nodes and 33 new incident edges. This is not exhaustive over arbitrary learner language or every browser permutation.
- Final `qa/final-routes/ui-walk-final.json`: `complete: true`, `errors: []`, two complete routes: L/mist/E3 and C/clear/E2. Independently read the clear-route sequence through drawn bows, probe, first volley, stop signal, recognition, return, muster, unloading, arrow tally and ending. The final report supersedes the earlier harness timing failure.
- Final `qa/media.json`: 606 decoded audio entries and 23 decoded images, `errors: []`. Voice-cast evidence records 97 watch-captain lines using `zh-CN-YunjianNeural`. The 606-key final speech inventory supersedes the earlier 1,349-key version after cause-recitation removal; the final media report, not the earlier count, is the closeout evidence.
- `qa/framework.json`: role filters yield L 50 / Z 49 / C 33 nodes, clear navigation true, updated copy true, zero errors.
- `qa/visual-probe.json`: actual tool drop, mouse fleet rotation to 114 degrees, frozen elapsed time while paused and unchanged persisted revision after movie presentation, zero errors. Independently viewed current fleet-drag, barrage-peak and 1024-high-workshop captures: visible controls, filled fleet bundles, water contact and unobstructed battle presentation. Static captures do not independently prove every motion or every heading threshold.

## Limits and release boundary

The model remains visibly stylized: repeated bundle spacing, regular fleet formation and patterned water are apparent. This is an aesthetic limitation, not an unresolved correctness finding. Neither test counts nor these images establish reference-image equivalence, photorealism, universal hardware FPS or learning effectiveness. Media decoding establishes browser readability, not a full independent human listening review of every line.

QA ran on isolated 8773. This review did not restart or publish production 8771. Production backup, preservation of saved rows, deployment and public-entry verification remain the root release procedure. The user's permanent working directory is preserved.
