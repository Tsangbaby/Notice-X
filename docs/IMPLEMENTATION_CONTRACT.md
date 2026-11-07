# Notice-X first functional candidate

## Identity and authorization
- Product: Notice-X; author and maintainer: Tsangbaby.
- Debian ID/preferences domain: com.tsangbaby.noticex.
- Canonical public repository: https://github.com/Tsangbaby/Notice-X (explicitly authorized).
- First candidate version: 0.1.0-beta1. Populate the empty repository's main branch; no tag or GitHub Release.
- Cloud macOS/iPhoneOS build using pinned https://github.com/roothide/theos. First package lane: RootHide only; compile arm64 and arm64e with minimum iOS 15.0. No claim of compatibility beyond device evidence.

## Product boundary
- Independent SpringBoard tweak; Glint remains byte-for-byte unchanged and is not a runtime dependency.
- Swift + UIKit owns visuals, animation, configuration and lifecycle state. Minimal native bootstrap/typed compatibility boundary allowed. No Orion, Logos or SwiftUI.
- Reuse/adapt the card shell and accepted motion from Glint commit 9b07183cd428b9b385c989377d25ca5595fcf424: opening 0.6s/damping 0.72/velocity 0.4; content 0.55s/delay 0.1/damping 0.8; closing 0.6s/damping 1/velocity 0; close radius reaches half compact height.
- First candidate applies only to unlocked ordinary banners. Leave lock-screen and Notification Center presentation unchanged. Preserve native notification payload, default action, authentication, long press, reply and withdrawal. Never substitute a bundle-only App launch, recreate a notification response, or intercept APNs.
- Prefer the native notification host/controller and modify a local visual surface. Preserve original method receiver/arguments/return and exactly-once forwarding. Missing class/selector, wrong ABI, unavailable host or unsupported context means native pass-through.
- One animation owner per banner session. New presentation, interruption, reversal, layout, lock and disable invalidate old completion authority before visual cleanup. A stale callback must not mutate/remove a newer session.
- No full-screen dismissal/touch-blocking window, no polling timer/display link, no notification-content logging or network calls.
- One default-off enable switch, live preference reload, Chinese/English Settings. No speculative catalog of options.

## Components and integration authority
- Parent owns Sources/Core, Sources/Runtime, Sources/UI, Sources/Support and prefs implementation, all public interfaces and integration.
- Build/verification worker, if assigned, may write only Makefile, control, NoticeX.plist, .gitignore, prefs/Makefile, .github/workflows, tools and tests/test_build_contract.py. It must not change Sources, any prefs file other than prefs/Makefile, core tests, README or this contract, and must not commit/push/dispatch.
- Runtime boundary details must be source-evidenced before production hook code; declarations are not handset proof.

## Verification
- Test-first vertical slices, named expected RED, focused GREEN and complete discovery.
- Execute actual Foundation Swift policy/lifecycle tests on cloud Mac; source text checks are not Swift execution.
- Apple compiler builds every shipped Swift/native target and both requested slices. Retain raw compiler/test/setup failures.
- Independently verify original DEB metadata, filter, settings resources, runtime dependencies, iPhoneOS deployment/slices and code-page signatures. Bind source SHA, run/attempt and checksums.
- Deliver original cloud package with install/enable instructions and a concise device matrix. Device acceptance remains pending until the user tests it.
