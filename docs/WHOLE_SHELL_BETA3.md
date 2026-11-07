# Whole-shell entry functional candidate

## Frozen identities and scope

- User approved replacing the device-rejected mask reveal with Glint-like whole-shell entry.
- Source predecessor: `8328ac1720189a4eb382cf1495712fcec004394e` (beta2); its admission repair remains required. Its visual result is rejected, not an accepted animation baseline.
- Reference: `Tsangbaby/Glint` `9b07183cd428b9b385c989377d25ca5595fcf424`, `GLTController.m:595–692` and `GLTPlatterView.m`. Glint remains unchanged and is not a dependency.
- Candidate: `0.1.0-beta3`, RootHide only, branch `fix/whole-shell-reveal-beta3`; formal main, tags and releases remain untouched; no PR or review gate.

## Mechanism and protected boundaries

Replace the animated mask with one actual rounded, clipping shell whose frame and live blur layout expand together. Keep content measured at its final width, then reveal its local pose with the accepted Glint timings. Do not reparent native content, modify native banner frame/transform, install another window, replace BannerKit animators, or reconstruct notification actions.

Separate preparation from opening. Preparation hides only the already-resolved native material/content, leaves the owned shell hidden, and tolerates pre-appearance bounds updates. Native `presentableDidAppearAsBanner:` completion is the opening frontier. Start on a subsequent main-queue turn after revalidating the same owner/session and native views, so native ingress and the visible custom reveal do not run concurrently. If preparation or a ready frontier cannot complete, restore native appearance; do not leave content hidden indefinitely.

For the visible reveal, render the existing native content once into a bounded, memory-only image; never save, log or transmit notification pixels. Keep the original native content in its original hierarchy and use the image only while the shell is changing size. At reveal completion, atomically restore live native content and release the image. Native content/request, hit targets, actions, authentication, long press, reply, withdrawal and scheduling remain system-owned. First interaction restores the native surface before forwarding. Native disappearance cancels our reveal and uses native dismissal; do not overlap another compact/close animator with native egress.

The expanded shell uses the actual native look bounds, preserving final native touch geometry. The compact local shell is centered at the look's top. This copies Glint's whole-shell mechanism and content-width policy, not Glint's status-clock owner, notification-delivery interception, full-screen dismissal layer or window.

Images are capped at 2,000,000 physical pixels; only one image per active reveal, released at completion/restore. No per-frame captures, polling/display link, disk logging additions, new private selectors or payload parsing. Layout, lock, disabling, identity changes and interruption invalidate completion authority before restoring original native appearance.

## Implementation ownership

Parent owns production, metadata, docs, source contracts and integration. A delegated executable-fixture owner may write only `tests/Visual/*` and `tests/run_visual_tests.py`, using the interface below; it must not alter production, existing tests, workflows, version metadata or Git refs. It must not commit, push or dispatch CI.

Public production seam remains `NXCardAnimator(parts:)`, `matches(_:)`, `open()`, `layout()`, `close()`, `restore()`. `open()` is invoked only after the native did-appear frontier by the coordinator. Init prepares but does not show or start the shell. Native content hierarchy and transform remain unchanged. Completion/restore release image ownership. `close()` restores immediately, leaving native dismissal authoritative.

## Verification and limits

Write focused rejection tests before implementation. Preserve all native runtime/bootstrap/preferences bytes from beta2, including the exact 15.4.1 admission gate. Execute production animator text using explicit UIKit doubles on the cloud Mac to test state, geometry, resource release and stale callbacks; doubles are not UIKit rendering or handset timing proof. Retain all existing portable/core/native/hook/diagnostic fixtures, compile real iPhoneOS UIKit code for arm64 and arm64e, and independently verify the original cloud DEB and exact-SHA artifact. No new diagnostic package and no claim of measured FPS, reduced memory usage or visual parity before handset acceptance.
