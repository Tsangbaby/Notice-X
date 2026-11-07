#!/usr/bin/env python3
"""Strictly validate an untouched, payload-free Notice-X diag1541 preferences plist."""
import argparse
import json
from pathlib import Path
import plistlib

MAX_BYTES = 16384
BUILD = "banner-entry-1541-v1"
ALLOWED_PHASES = frozenset("""
native_not_main native_managers_missing native_state_unreadable
native_context_rejected native_context_ready native_resolve_not_main
native_resolve_context_rejected resolve_classes_missing resolve_owner_rejected
resolve_controller_rejected resolve_look_missing resolve_not_banner
resolve_request_rejected resolve_critical_alert resolve_subviews_missing
resolve_hierarchy_rejected resolve_ready native_exception native_lock_unreadable
native_unlocking_unreadable native_lock_visible_unreadable
native_cover_presented_unreadable native_cover_visible_unreadable native_locked
native_unlocking native_lock_visible native_cover_presented native_cover_visible
resolve_banner_unreadable resolve_critical_unreadable runtime_start
install_class_missing install_class_sb install_class_nc install_check_will_appear
install_check_did_appear install_check_will_disappear install_check_did_disappear
install_check_will_not_appear install_check_interaction install_check_long_look
install_check_layout install_selector_missing install_argument_count_mismatch
install_return_type_mismatch install_argument_type_mismatch install_abi_mismatch
install_complete runtime_switch_on runtime_switch_off banner_will_appear
banner_switch_off banner_context_rejected banner_context_ready
banner_session_created banner_did_appear banner_did_appear_without_session
layout_without_session layout_session_busy layout_switch_off
layout_context_rejected admission_rejected admission_ready visual_reused
visual_constructor_rejected visual_installed callback_will_appear
callback_did_appear callback_will_disappear callback_did_disappear
callback_will_not_appear callback_interaction callback_long_look callback_layout
visual_identity_rejected visual_session_replaced
""".split())


def validate(raw):
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("invalid_diagnostic_size")
    try:
        wrapper = plistlib.loads(raw)
    except Exception:
        raise ValueError("invalid_diagnostic_plist") from None
    if type(wrapper) is not dict or set(wrapper) != {"snapshot"}:
        raise ValueError("invalid_diagnostic_wrapper")
    snapshot = wrapper["snapshot"]
    fields = {"schema", "build", "generation", "sequence", "resetConfirmed", "trace"}
    if type(snapshot) is not dict or set(snapshot) != fields:
        raise ValueError("invalid_diagnostic_fields")
    if type(snapshot["schema"]) is not int or snapshot["schema"] != 1 or snapshot["build"] != BUILD:
        raise ValueError("wrong_diagnostic_generation")
    generation = snapshot["generation"]
    if type(generation) is not int or not 1 <= generation <= 2147483647:
        raise ValueError("invalid_diagnostic_generation")
    if type(snapshot["resetConfirmed"]) is not bool or snapshot["resetConfirmed"] is not True:
        raise ValueError("diagnostic_reset_unconfirmed")
    trace, sequence = snapshot["trace"], snapshot["sequence"]
    if type(trace) is not list or type(sequence) is not int or not 1 <= sequence <= 96 or len(trace) != sequence:
        raise ValueError("invalid_diagnostic_sequence")
    if any(type(phase) is not str or phase not in ALLOWED_PHASES for phase in trace):
        raise ValueError("invalid_diagnostic_phase")
    if trace[0] != "runtime_start" or len(set(trace)) != len(trace):
        raise ValueError("invalid_first_reach_trace")
    return {"schema": 1, "build": BUILD, "generation": generation, "sequence": sequence,
            "resetConfirmed": True, "trace": list(trace)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plist", type=Path)
    args = parser.parse_args()
    try:
        if args.plist.stat().st_size > MAX_BYTES:
            raise ValueError("invalid_diagnostic_size")
        result = validate(args.plist.read_bytes())
    except (ValueError, OSError):
        parser.exit(1, "DIAGNOSTIC_INVALID: fixed-schema validation failed\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
