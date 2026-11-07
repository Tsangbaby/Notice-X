import Foundation
import ObjectiveC

// Explicit test-only coordinator; production hook slot and callback bodies remain unchanged.
final class NXBannerCoordinator {
    static let shared = NXBannerCoordinator()
    private var sessions = Set<ObjectIdentifier>()
    func start() { NXFixtureRecord("swift:start") }
    func willAppear(_ owner:AnyObject) {
        sessions.insert(ObjectIdentifier(owner));NXFixtureRecord("swift:will")
    }
    func didAppear(_ owner:AnyObject) { NXFixtureRecord("swift:did") }
    func willDisappear(_ owner:AnyObject) { NXFixtureRecord("swift:willClose") }
    func retire(_ owner:AnyObject) {
        sessions.remove(ObjectIdentifier(owner));NXFixtureRecord("swift:retire")
    }
    func layout(_ owner:AnyObject) { NXFixtureRecord("swift:layout") }
    func hasSession(_ owner:AnyObject) -> Bool { sessions.contains(ObjectIdentifier(owner)) }
}
private typealias One = @convention(c)(AnyObject,Selector,AnyObject?) -> Void
private typealias Two = @convention(c)(AnyObject,Selector,AnyObject?,AnyObject?) -> Void
private typealias Zero = @convention(c)(AnyObject,Selector) -> Void
var assertions = 0
func require(_ condition:@autoclosure () -> Bool,_ reason:String) {
    assertions += 1
    if !condition() { FileHandle.standardError.write(Data(("NOTICE_X_RUNTIME_FAIL: "+reason+"\n").utf8));exit(1) }
}
let owner: AnyObject = NXFixtureMakeOwner()! as AnyObject
func invoke(_ selector:String,_ count:Int) {
    let sel=NSSelectorFromString(selector)
    guard let cls=object_getClass(owner),let method=class_getInstanceMethod(cls,sel) else { fatalError("fixture selector missing") }
    let imp=method_getImplementation(method)
    if count==0 { unsafeBitCast(imp,to:Zero.self)(owner,sel) }
    else if count==1 { unsafeBitCast(imp,to:One.self)(owner,sel,owner) }
    else { unsafeBitCast(imp,to:Two.self)(owner,sel,owner,owner) }
}
func events() -> [String] { NXFixtureEvents() ?? [] }
let invalid=CommandLine.arguments.contains("wrong-abi")
NXStart()
DispatchQueue.main.async {
    DispatchQueue.main.async {
        require(Thread.isMainThread,"fixture executes on real main thread")
        if invalid {
            require(NXFixtureHookCount()==0,"one wrong return ABI rejects entire hook group")
            NXFixtureClearEvents()
            invoke("presentableDidAppearAsBanner:",1)
            require(events()==["native:did"],"unsupported group keeps native behavior untouched")
        } else {
            require(NXFixtureHookCount()==8,"all eight hooks installed once")
            let cases:[(String,Int,[String])] = [
                ("presentableWillAppearAsBanner:",1,["swift:will","native:will","swift:layout"]),
                ("presentableDidAppearAsBanner:",1,["native:did","swift:did"]),
                ("presentableWillDisappearAsBanner:withReason:",2,["swift:willClose","native:willClose"]),
                ("presentableDidDisappearAsBanner:withReason:",2,["swift:retire","native:didClose"]),
                ("presentableWillNotAppearAsBanner:withReason:",2,["swift:retire","native:notAppear"]),
                ("userInteractionWillBeginForBannerForPresentable:",1,["swift:retire","native:interact"]),
                ("longLookWillPresentForNotificationViewController:",1,["swift:retire","native:long"]),
                ("viewDidLayoutSubviews",0,["native:layout","swift:layout"])
            ]
            for (selector,count,expected) in cases {
                NXFixtureClearEvents();invoke(selector,count)
                require(events()==expected,"exactly-once native forwarding and owner ordering: "+selector)
            }
            invoke("presentableWillAppearAsBanner:",1)
            NXFixtureReenterOnNextDisappear()
            NXFixtureClearEvents()
            invoke("presentableDidDisappearAsBanner:withReason:",2)
            require(NXBannerCoordinator.shared.hasSession(owner),
                    "native disappearance reentry preserves replacement session")
            require(events()==["swift:retire","native:didClose","swift:will","native:will","swift:layout"],
                    "old retirement completes before native reentrant appearance")
            NXFixtureClearEvents()
            let finished=DispatchSemaphore(value:0)
            DispatchQueue.global().async { invoke("presentableDidAppearAsBanner:",1);finished.signal() }
            require(finished.wait(timeout:.now()+5) == .success,"off-main predecessor completes")
            require(events()==["native:did"],"off-main native call does not mutate UIKit coordinator")
        }
        NXStart();NXImagesChanged()
        DispatchQueue.main.async {
            DispatchQueue.main.async {
                require(NXFixtureHookCount()==(invalid ? 0 : 8),"duplicate startup does not install twice")
                print("NOTICE_X_RUNTIME_PASS mode=\(invalid ? "wrong-abi" : "healthy") assertions=\(assertions)")
                fflush(stdout)
                exit(0)
            }
        }
    }
}
RunLoop.main.run(until:Date(timeIntervalSinceNow:15))
fputs("NOTICE_X_RUNTIME_FAIL: main-queue completion missing\n",stderr)
exit(1)
