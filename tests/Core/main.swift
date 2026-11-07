import Foundation

var assertions = 0
func require(_ condition: @autoclosure () -> Bool, _ reason: String) {
    assertions += 1
    if !condition() {
        FileHandle.standardError.write(Data(("NOTICE_X_CORE_FAIL: " + reason + "\n").utf8))
        exit(1)
    }
}

for bits in 0..<64 {
    let flags = (0..<6).map { bits & (1 << $0) != 0 }
    let input = NXAdmission(enabled: flags[0], unlocked: flags[1], banner: flags[2],
                            onMainThread: flags[3], attached: flags[4], hasForeignMask: flags[5],
                            width: 360, height: 100)
    require(input.allowed == (bits == 31), "only enabled/unlocked/attached banner on main without a foreign mask")
}
for invalid in [Double.nan, Double.infinity, -Double.infinity, -1, 0, 23, 601] {
    require(!NXAdmission(enabled:true, unlocked:true, banner:true, onMainThread:true,
                         attached:true, hasForeignMask:false, width:360, height:invalid).allowed,
            "invalid height rejected before visual mutation")
}
for invalid in [Double.nan, Double.infinity, -Double.infinity, -1, 0, 79, 1401] {
    require(!NXAdmission(enabled:true, unlocked:true, banner:true, onMainThread:true,
                         attached:true, hasForeignMask:false, width:invalid, height:100).allowed,
            "invalid width rejected before visual mutation")
}
var state = NXSession()
require(state.phase == .idle, "initial session idle")
let opening = state.begin(.opening)
require(state.phase == .opening, "opening admission owns phase")
let closing = state.begin(.closing)
require(!state.finish(opening, from:.opening, to:.visible), "old opening completion cannot reopen closing card")
require(state.phase == .closing, "stale callback did not mutate phase")
require(state.finish(closing, from:.closing, to:.idle), "current closing retires")
require(!state.finish(closing, from:.closing, to:.idle), "duplicate completion rejected")
let old = state.begin(.opening)
state.invalidate()
let fresh = state.begin(.opening)
require(!state.finish(old, from:.opening, to:.visible), "old ABA generation rejected")
require(state.finish(fresh, from:.opening, to:.visible), "fresh reopening finishes")
require(!state.finish(fresh, from:.closing, to:.idle), "wrong-phase finisher rejected")
state.invalidate()
require(state.phase == .idle, "disable/lock invalidates current state")
require(!state.finish(fresh, from:.opening, to:.visible), "late callback after disable rejected")
var peer = NXSession()
let peerToken = peer.begin(.opening)
state.invalidate()
require(peer.finish(peerToken, from:.opening, to:.visible), "independent banner owns independent generation")
require(NXMotion.openDuration == 0.6 && NXMotion.openDamping == 0.72 && NXMotion.openVelocity == 0.4, "accepted shell opening")
require(NXMotion.closeDuration == 0.6 && NXMotion.closeDamping == 1, "accepted critical close")
require(NXMotion.contentDuration == 0.55 && NXMotion.contentDelay == 0.1 && NXMotion.contentDamping == 0.8, "accepted content clock")
require(NXMotion.contentOffsetY == -14 && NXMotion.contentScale == 0.94, "accepted content pose")
require(!NXConfiguration(enabledValue:nil).enabled, "default off")
require(NXConfiguration(enabledValue: true).enabled, "real boolean true enables")
require(!NXConfiguration(enabledValue: false).enabled, "real boolean false disables")
for value: Any in [NSNumber(value:1), NSNumber(value:0), "true", [true]] {
    require(!NXConfiguration(enabledValue:value).enabled, "malformed or numeric value does not enable")
}
var stored: Any? = NSNumber(value:false)
var effects: [String] = []
let saved = NXPreferenceTransaction.save(true, read:{ stored },
    write:{ stored=$0; effects.append("write") },
    synchronize:{ effects.append("sync"); return true },
    notify:{ effects.append("notify") })
require(saved && NXConfiguration(enabledValue:stored).enabled, "fresh snapshot consumes saved true")
require(effects == ["write","sync","notify"], "save before exactly one notification")
effects=[]
let failed = NXPreferenceTransaction.save(false, read:{ stored },
    write:{ stored=$0; effects.append("write") },
    synchronize:{ effects.append("sync"); return false },
    notify:{ effects.append("notify") })
require(!failed && NXConfiguration(enabledValue:stored).enabled, "failed save restores previous value")
require(effects == ["write","sync","write","sync"], "failed save does not notify")
print("NOTICE_X_CORE_PASS assertions=\(assertions)")
