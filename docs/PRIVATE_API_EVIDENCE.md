# Private API evidence and visual ownership

## Immutable references

Header corpus: `donato-fiore/iOS-Runtime-Headers` at `031ec3a8b25d1751646143551d2ea630bbb04cf9`.

The following Contents API payloads were base64-decoded and independently checked against their Git blob SHA-1 before implementation:

- `15.0/PrivateFrameworks/UserNotificationsUIKit.framework/Headers/NCNotificationPresentableViewController.h` — blob `6d01204674c1024b1f31a53424f2124a01283c0d`.
- `15.0/PrivateFrameworks/UserNotificationsUIKit.framework/Headers/NCNotificationShortLookView.h` — blob `3bd272fe87d5f5d26cccf5c4b8daa9a9af024cc1`.
- `16.0/PrivateFrameworks/UserNotificationsUIKit.framework/Headers/NCNotificationShortLookView.h` — blob `a08391a234282fc11367f56422973ea986b79633`.
- `15.0/PrivateFrameworks/UserNotificationsKit.framework/Headers/NCNotificationRequest.h` — blob `2669811b70893c3b9b90fbd4680e5f3562ec862c`.
- `15.0/PrivateFrameworks/SpringBoard.framework/Headers/SBLockScreenManager.h` — blob `858a5a2f2d743bd99c4e64dd5e69ea9b550481a9`.
- `15.0/PrivateFrameworks/SpringBoard.framework/Headers/SBCoverSheetPresentationManager.h` — blob `9282d4a68374a309fe41bcb17bea55650a1030de`.
- `15.0/PrivateFrameworks/SpringBoard.framework/Headers/SBNotificationPresentableViewController.h` — blob `346799c22544c13e41f3cd56d43d67e1073c300e`.
- `16.0/PrivateFrameworks/SpringBoard.framework/Headers/SBNotificationPresentableViewController.h` — blob `a3ae81b4d1f0dc3ff0ba6ba060b6aee5bde827e6`.

Reference URL form: `https://github.com/donato-fiore/iOS-Runtime-Headers/blob/031ec3a8b25d1751646143551d2ea630bbb04cf9/<path>`.

These are dumped declarations, not method implementations or proof of a target handset's callback ordering.

## Selected seam

Observe banner-specific lifecycle callbacks on `SBNotificationPresentableViewController`, with `NCNotificationPresentableViewController` as the capability-checked fallback. Install only when the complete needed method group matches `void` returns and exact object argument shapes.

Resolve `notificationViewController` → loaded short-look view → existing `backgroundMaterialView` and `_notificationContentView`. Require a non-ending banner session for the same owner, created only by the native banner lifecycle. The iOS 15.4.1 device trace reached that lifecycle with `_isBanner == NO`, so only that exact OS tuple uses lifecycle/session identity instead of the look flag. Other versions retain the original ABI-checked `_isBanner` filter. Preserve exact native request and view identities. Exclude nonbanners without an active session, critical alerts, locked/unlocking/lock-visible state and visible/presented Cover Sheet. An unknown required capability is native pass-through. This admission repair is a functional verification candidate, not device-proven styling.

The action chain is untouched: no Hook of notification delivery, tap handling, action execution or response sending. Native user-interaction and long-look callbacks retire our visual session before forwarding, so the system takes full visual ownership.

## Ownership

BannerKit keeps its window, outer frame/transform, scheduling and interactive dismissal. Beta3 removes the device-rejected animated mask. Notice-X prepares a hidden noninteractive clipping shell, then waits for the same owner's native did-appear callback and one subsequent main-queue turn before whole-shell entry. Preparation may adopt native pre-entry bounds changes; a bounded 1.5-second fallback restores native appearance if opening was not scheduled. Active geometry changes, native interaction, lock, Settings changes and disappearance retire the reveal. Generation checks precede animation/completion mutation; current native view/request identities are rechecked on layout. Foreign masks and unsupported hierarchies are not adopted.

The shell's expanded frame is the real native look bounds, not Glint's separate status-clock window geometry. Native content stays in its original hierarchy and keeps its frame/transform. During entry only, its pixels are rendered once into a memory-only, standard-range image capped at 2,000,000 physical pixels. The image keeps its final native content rectangle while the shell and live material grow; both animation completions must finish before live content is restored and image ownership released. No notification image is persisted or transmitted. Native egress restores the original surface rather than running a second close animator. These are source-level preservation properties, not device-proven touch/presentation equivalence.

Beta3 does not globally replace `BNBannerAnimator` or a BannerKit transitioning delegate. A full native-animator substitution remains a separate capability requiring cancellation, retargeting and completion proof on the target systems.

## Visual reference

Glint accepted source: `Tsangbaby/Glint` commit `9b07183cd428b9b385c989377d25ca5595fcf424`.

`reconstructed/Sources/GLTController.m:595–692` supplies the whole-shell frame expansion and timing/pose vocabulary. `GLTPlatterView.m:81–90` keeps content at its measured open width while its clipped material container grows. Beta3 applies this mechanism to its own shell using cancellable `UIViewPropertyAnimator` handles and `UISpringTimingParameters`; the frozen beta2 mask test is historical regression evidence only. The native content hierarchy and outer BannerKit animation remain separate and untouched. See `WHOLE_SHELL_BETA3.md` for the approved integration boundary and device-proof limits.

Private Preferences declarations were checked against `theos/headers` commit `13c1f17176d7efe6871551cd69a75b71ac4eeaf1` (`PSListController.h`, `PSViewController.h`, `PSSpecifier.h`). A narrow declaration header avoids importing an obsolete superclass initializer into Swift. The Swift subclass owns the optional `initForContentSize:` factory adapter and routes it through the public UIKit initializer.

## Acceptance still required

Home/light/dark App banners; native default action to exact destination; native long press/reply; continuous notifications; dismissal/interruption; rotation and layout; Reduce Motion/Transparency; no changes to lock screen or Notification Center. No header, fixture, binary signature or cloud compiler result establishes these handset rows.
