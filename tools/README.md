# Original-package verification

These tools never install, execute package code, modify a DEB, re-sign it, or repack it. Use Python without `-O`; assertions are release gates. Only Python's standard library and a working `dpkg-deb` are required for independent package inspection.

```sh
python3 -B tools/verify_package.py ORIGINAL.deb --report local-package-verification.json
```

The verifier reads the **original archive**, validates ar/control/data inventory with bounded decompression (including an independent LZMA memory ceiling), and requires the real Debian parser to accept those same bytes. It checks Notice-X identity, RootHide paths, the SpringBoard-only filter, the default-off Settings entry, English/Simplified Chinese resources and each shipped Mach-O. Every arm64/arm64e slice must be iPhoneOS with deployment 15.0, have a bounded signature with all code-page hashes verified, and contain defined module-specific Swift instruction symbols. The prefs binary must define `NXSettingsController`. Debug symbols are stripped but defined symbols intentionally remain (`STRIP_FLAGS = -S`).

Signature/code-page integrity is **not** signer trust, entitlement correctness, source reproducibility, installation success or device acceptance. Swift symbol evidence proves compiled Swift code is present, not that every business method executed. Source graph guards and actual host fixtures are separate gates. Parser tests use explicitly synthetic archives; none is a product build.

## CI evidence and offline readback

The sole push-to-main job uses macOS 15, Xcode 16.4/iPhoneOS SDK 18.5, recursive hash-pinned RootHide Theos, and the hash-pinned Preferences link stub. It executes `tests/run_swift_tests.py --out ci-artifacts/swift-tests` and all `test_*.py` contracts before packaging. `SDKROOT` for portable host execution is step-scoped; the device build explicitly receives the iPhoneOS sysroot. No simulator/device pass is manufactured.

`ci_evidence.py scope` records the exact checkout SHA, repository, run/attempt, source hashes/compile graph and explicit untested-device scope before setup. After a successful build, `retain` copies exactly the expected DEB and binds its hash to the raw build log before supplemental checks. `manifest` writes complete evidence checksums, even for failed jobs. A successful final gate reconciles verbose compiler commands with each target/source/architecture, pinned Theos link/sign records, the package report and the actual host assertion report/log without a hardcoded assertion total. Always-on upload retains setup/compiler/test/verifier failures and the untouched package if one was produced.

After obtaining an exact run's artifact, independently authenticate its ZIP digest against GitHub metadata and safely unpack it into a fresh directory. Then use trusted, independently retrieved run identifiers (not values merely copied from the archive):

```sh
python3 -B tools/ci_evidence.py verify --out DOWNLOADED_EVIDENCE \
  --source-sha EXACT_40_HEX_SHA --repository Tsangbaby/Notice-X \
  --run-id EXACT_RUN_ID --attempt EXACT_ATTEMPT
python3 -B tools/verify_package.py DOWNLOADED_EVIDENCE/ORIGINAL.deb \
  --report independent-package-verification.json
```

Keep the report outside `DOWNLOADED_EVIDENCE` so its original manifest inventory remains unchanged. `verify` checks source markers, source/run identity, complete file inventory and all byte hashes, plus original DEB/build-log binding. A failed/partial job remains failed/partial even if its checksums match. Compare the package reports exactly (the report includes only the package basename, not a host extraction path). The outer Actions ZIP digest and inner DEB SHA-256 are different identities.

The tools do not retrieve or dispatch a workflow. No package can be called verified until an actual original cloud DEB passes independent inspection; handset behavior is a later, separate acceptance gate.
