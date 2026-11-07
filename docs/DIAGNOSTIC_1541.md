# Notice-X iOS 15.4.1 one-reproduction diagnostic

- Rejected functional baseline: `f7d5dd37582b86a928c631d14b763865268a5e50`.
- Diagnostic package version: `0.1.0-beta1+diag1`, RootHide only.
- Candidate branch: `diag/banner-entry-1541`; do not merge this branch into formal main.
- This is observational evidence, not a notification-style fix.

## Scope and privacy

The eight existing hooks and their native forwarding/order remain unchanged.
No notification actions, request contents, routes, private eligibility rules,
UI geometry, animation timings or product preference values are modified.
The private getter order/count is preserved. The diagnostic lifecycle itself
is restricted to the exact OS tuple 15.4.1 before queue or preferences setup.

Only fixed numeric codes enter the sink. It accepts a closed vocabulary of
first-reach phases, once per phase per SpringBoard lifetime. It retains at most
96 codes and 32 queued/executing reservations; coalesced drains avoid a job or
preferences write per layout callback. Whole-wrapper binary-plist serialization
is capped at 16 KiB. Reset must synchronize and match readback before runtime
records are published. I/O, reset/readback or Objective-C failures disable only
the diagnostic. The formal native path is not changed or suppressed.

There are no timestamps, app identifiers, notification titles/bodies/senders,
object descriptions, URLs, payload values or device identifiers in the export.
`generation` distinguishes resets, not devices. The trace is first-reach-only,
not a complete event timeline or a per-notification correlation record.

## Device procedure

1. Install the diagnostic original DEB and reload SpringBoard once.
2. Confirm the Notice-X switch remains enabled. Unlock and stay on Home or in
   an app; do not open Notification Center/Cover Sheet during the reproduction.
3. Receive one ordinary notification banner, leave it untouched, and allow it
   to disappear. No repeated toggling, reinstalling or respring loop is needed.
4. Export the untouched `com.tsangbaby.noticex.diag1541.plist` from the mobile
   user's preferences directory using Filza, normally:
   `/var/mobile/Library/Preferences/com.tsangbaby.noticex.diag1541.plist`.
   Send the original plist, not a screenshot or converted text.
5. If absent, report absence. Absence does not prove injection failed: it could
   also mean the diagnostic was unsupported, not started, or could not persist.
   Do not reinstall/respring repeatedly; obtain the relevant loader/crash
   evidence before another candidate.

Validate with `python3 -B tools/read_diagnostic.py ORIGINAL.plist`. Unknown keys,
phases, build, integer-as-Boolean fields, malformed values and oversized input
are rejected; unvalidated contents are never printed by the reader.

## Interpretation

- `runtime_start`: native constructor reached Swift installation scheduling and
  diagnostic reset/persistence succeeded. It is not hook reachability proof.
- `install_check_*` followed by a fixed mismatch: the existing hook group was
  rejected. Class, missing selector, count, return ABI and argument ABI outcomes
  are separate. Later image loads can retry; first-reach markers are not a last-
  failure timeline, so check whether `install_complete` was reached afterward.
- `install_complete` without any callback marker: registration ran but banner
  entry is unproven. Do not infer that the setting was off.
- `runtime_switch_on/off`: a value was actually consumed in SpringBoard, not
  inferred from the Settings screen. Both may occur after a settings change.
- Native lock/context/readability, controller/look/request, critical-alert,
  hierarchy, admission and visual-constructor phases localize later returns.
- `visual_installed` is not rendering proof; only the device can establish the
  intended appearance.

## Build evidence

Run source contracts and the portable core locally. On the pinned cloud Mac,
execute the unchanged native-provider and hook-forwarding fixtures plus the
actual diagnostic producer with real Foundation/CFPreferences. Stress all fixed
codes, verify a strict raw binary-plist decode, duplicate-start idempotence,
reservation release, and reset/write exception suppression. Bind the original
DEB and all logs to one committed SHA, run, attempt and checksum. Keep host,
compiler/package and device evidence separate.
