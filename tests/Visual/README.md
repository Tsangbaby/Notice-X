# Actual-source animator host replay

Integration API (macOS, same compiler/SDK arguments as the runtime host):

```python
from run_visual_tests import run_visual
run_visual(root, out, compiler, sdk)
```

Standalone:

```sh
python3 tests/run_visual_tests.py --out "$OUT"
# Optional explicit compiler: --swiftc /path/to/swiftc
```

The runner builds an explicit Swift `UIKit` double module, then compiles **the actual**
`Sources/UI/NoticeCardAnimator.swift`, `Sources/Core/NoticePolicy.swift`, and `main.swift`.
It never copies, translates or reconstructs the candidate animator. The only native
resolver replacement is a fixture `NXBannerParts` containing the resolved identities.
It also compiles the frozen beta2 animator from
`8328ac1720189a4eb382cf1495712fcec004394e` against the same doubles and executable.
That executable must exit 1 at exactly `prepare/no-native-mask`; missing mock APIs,
compiler/linker errors, crashes, and other assertions are **not** expected RED.

## Deterministic scenarios

Eight named cases cover:

- hidden preparation, no mask/capture/animation before `open`, resolved identity matching;
- compact top-centered real shell before queued animation closures, expanded actual look
  bounds afterward, blur relayout, original-width image and independent image pose;
- unchanged native frames, bounds, transforms, parents, child identities/order, including
  transient geometry/reparent writes, not just final values;
- pending native resize without teardown; active resize safely restores;
- both completions required, shell-first and content-first ordering, one render, live-content
  handoff and weak-reference/creation/release accounting;
- interrupted `.start`/`.current` completions and immediate close without a close animator;
- forced old animations/completions and repeated restore against an **actively animating**
  replacement, plus preservation of newer native alpha/style after restore;
- reduced motion retaining live content at the open frontier, with no image or animator;
- physical-pixel cap, permitting a safe live-native fallback instead of an oversized image.

`UIViewPropertyAnimator` records starts without executing anything. Its explicit
`replayAnimations()` / `replayCompletion(_:)` methods deliberately permit repeated,
post-stop callbacks. Image references are never held strongly by the trace.

## Output and proof boundary

Successful candidate output is exactly:

```text
NOTICE_X_VISUAL_PASS assertions=N
```

The separately verified predecessor emits
`NOTICE_X_VISUAL_EXPECTED_RED baseline=8328ac1 assertion=no-native-mask` from Python.
`out/visual-tests.json` records `executed`, assertion/case counts, exact source hashes,
negative-control evidence, `kind=production_swift_uikit_double_replay`, and
`device_tested=false`. Compile/run logs and host artifacts live under `out/visual-host/`.
No successful report is written if either executable fails validation.

Foundation/CoreGraphics and the tiny renderer CGContext are real macOS APIs. UIView,
CALayer, UIKit image ownership, screen, renderer and animator behavior are explicit
framework doubles. A double's view frame is its pre-transform layout rectangle, not a
claim about UIKit's transformed bounding rectangle. Coordinate conversion admits only
identity-transform fixture ancestors. No notification pixels are rendered, saved or
logged; renderer events contain only geometry/scale and counts. This proves bounded
state/geometry/resource behavior, not real UIKit timing, blur/pixel rendering,
coordinator ingress scheduling, or handset appearance.

On a non-macOS machine the runner fails closed, rather than returning a skipped PASS.
Portable runner-contract unit checks (synthetic subprocess results, **not Swift proof**):

```sh
python3 tests/Visual/test_runner.py
python3 -m py_compile tests/run_visual_tests.py tests/Visual/test_runner.py
```
