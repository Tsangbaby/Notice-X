#import "RuntimeBridge.h"
static NSMutableArray<NSString *> *events;
static NSLock *eventLock;
static NSInteger installs;
static void NXFixtureSetup(void) {
    static dispatch_once_t once;dispatch_once(&once,^{events=[NSMutableArray new];eventLock=[NSLock new];});
}
void NXFixtureRecord(NSString *event) { NXFixtureSetup();[eventLock lock];[events addObject:event];[eventLock unlock]; }
NSArray<NSString *> *NXFixtureEvents(void) { NXFixtureSetup();[eventLock lock];NSArray *copy=[events copy];[eventLock unlock];return copy; }
void NXFixtureClearEvents(void) { NXFixtureSetup();[eventLock lock];[events removeAllObjects];[eventLock unlock]; }
NSInteger NXFixtureHookCount(void) { return installs; }
void MSHookMessageEx(Class cls, SEL selector, IMP replacement, IMP *original) {
    Method method=class_getInstanceMethod(cls,selector);
    *original=method_getImplementation(method);
    class_replaceMethod(cls,selector,replacement,method_getTypeEncoding(method));
    installs++;
}
@interface NXRuntimeFixturePresentable : NSObject
#if NX_WRONG_ABI
- (int)presentableWillAppearAsBanner:(id)value;
#else
- (void)presentableWillAppearAsBanner:(id)value;
#endif
- (void)presentableDidAppearAsBanner:(id)value;
- (void)presentableWillDisappearAsBanner:(id)value withReason:(id)reason;
- (void)presentableDidDisappearAsBanner:(id)value withReason:(id)reason;
- (void)presentableWillNotAppearAsBanner:(id)value withReason:(id)reason;
- (void)userInteractionWillBeginForBannerForPresentable:(id)value;
- (void)longLookWillPresentForNotificationViewController:(id)value;
- (void)viewDidLayoutSubviews;
@end
@implementation NXRuntimeFixturePresentable
#if NX_WRONG_ABI
- (int)presentableWillAppearAsBanner:(id)value { (void)value;NXFixtureRecord(@"native:will");return 0; }
#else
- (void)presentableWillAppearAsBanner:(id)value { (void)value;NXFixtureRecord(@"native:will"); }
#endif
- (void)presentableDidAppearAsBanner:(id)value { (void)value;NXFixtureRecord(@"native:did"); }
- (void)presentableWillDisappearAsBanner:(id)value withReason:(id)reason { (void)value;(void)reason;NXFixtureRecord(@"native:willClose"); }
- (void)presentableDidDisappearAsBanner:(id)value withReason:(id)reason { (void)value;(void)reason;NXFixtureRecord(@"native:didClose"); }
- (void)presentableWillNotAppearAsBanner:(id)value withReason:(id)reason { (void)value;(void)reason;NXFixtureRecord(@"native:notAppear"); }
- (void)userInteractionWillBeginForBannerForPresentable:(id)value { (void)value;NXFixtureRecord(@"native:interact"); }
- (void)longLookWillPresentForNotificationViewController:(id)value { (void)value;NXFixtureRecord(@"native:long"); }
- (void)viewDidLayoutSubviews { NXFixtureRecord(@"native:layout"); }
@end
id NXFixtureMakeOwner(void) { return [NXRuntimeFixturePresentable new]; }
