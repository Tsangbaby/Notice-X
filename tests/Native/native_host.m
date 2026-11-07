// Explicit Foundation-only framework substitutes, never shipped in Notice-X.
#import "NoticeXBridge.h"
#import "OSFixture.h"
#include <stdio.h>
#include <stdlib.h>

static int starts, images, assertions;
static NSOperatingSystemVersion fixtureOS;
static int osReads;
@implementation NXFixtureProcessInfo
+ (instancetype)processInfo {
    static NXFixtureProcessInfo *value;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ value = [self new]; });
    return value;
}
- (NSOperatingSystemVersion)operatingSystemVersion { ++osReads; return fixtureOS; }
@end
void NXStart(void) { starts++; }
void NXImagesChanged(void) { images++; }
void NXDiagnosticBegin(void) {}
void NXDiagnosticRecord(int32_t code) { (void)code; }
static void Require(BOOL ok, const char *reason) {
    assertions++;
    if (!ok) { fprintf(stderr,"NOTICE_X_NATIVE_FAIL: %s\n",reason); exit(1); }
}
@implementation UIView
- (BOOL)isDescendantOfView:(UIView *)view {
    UIView *current=self;
    for (int i=0;current && i<16;i++,current=current.superview) if(current==view)return YES;
    return NO;
}
@end

static BOOL locked,unlocking,lockVisible,coverPresented,coverVisible,critical,banner=YES,throws;
@interface NXFixtureLockManager : NSObject
+ (id)sharedInstanceIfExists;
- (BOOL)isUILocked;
- (BOOL)isUIUnlocking;
- (BOOL)isLockScreenVisible;
@end
@implementation NXFixtureLockManager
+ (id)sharedInstanceIfExists { return [self new]; }
- (BOOL)isUILocked { return locked; }
- (BOOL)isUIUnlocking { return unlocking; }
- (BOOL)isLockScreenVisible { return lockVisible; }
@end
@interface NXFixtureCoverManager : NSObject
+ (id)sharedInstanceIfExists;
- (BOOL)isPresented;
- (BOOL)isVisible;
@end
@implementation NXFixtureCoverManager
+ (id)sharedInstanceIfExists { return [self new]; }
- (BOOL)isPresented { return coverPresented; }
- (BOOL)isVisible { return coverVisible; }
@end
@interface NXFixtureRequest : NSObject
- (BOOL)isCriticalAlert;
@end
@implementation NXFixtureRequest
- (BOOL)isCriticalAlert { return critical; }
@end
@interface NXFixtureWrongRequest : NSObject
- (int)isCriticalAlert;
@end
@implementation NXFixtureWrongRequest
- (int)isCriticalAlert { return 0; }
@end
@interface NXFixtureLook : UIView
@property(nonatomic,strong) UIView *material;
@property(nonatomic,strong) UIView *content;
- (BOOL)_isBanner;
- (id)backgroundMaterialView;
- (id)_notificationContentView;
@end
@implementation NXFixtureLook
- (BOOL)_isBanner { return banner; }
- (id)backgroundMaterialView {
    if(throws) @throw [NSException exceptionWithName:@"NXFixture" reason:@"test only" userInfo:nil];
    return self.material;
}
- (id)_notificationContentView { return self.content; }
@end
@interface NXFixtureShortController : NSObject
@property(nonatomic,strong) id look;
@property(nonatomic,strong) id request;
- (id)_notificationShortLookViewIfLoaded;
- (id)notificationRequest;
@end
@implementation NXFixtureShortController
- (id)_notificationShortLookViewIfLoaded { return self.look; }
- (id)notificationRequest { return self.request; }
@end
@interface NXFixturePresentable : NSObject
@property(nonatomic,strong) id controller;
- (id)notificationViewController;
@end
@implementation NXFixturePresentable
- (id)notificationViewController { return self.controller; }
@end

int main(int argc, const char *argv[]) { @autoreleasepool {
    Require(argc == 2, "exact OS lane required");
    NSString *lane = [NSString stringWithUTF8String:argv[1]];
    BOOL lifecycle = [lane isEqualToString:@"15.4.1"];
    if (lifecycle) fixtureOS = (NSOperatingSystemVersion){15,4,1};
    else if ([lane isEqualToString:@"15.4.0"]) fixtureOS = (NSOperatingSystemVersion){15,4,0};
    else { Require([lane isEqualToString:@"16.0.3"], "known legacy OS lane"); fixtureOS = (NSOperatingSystemVersion){16,0,3}; }
    Require(starts==1 && images>0,"actual native constructor activates without an explicit start call");
    Require(NXUnlockedHomeOrApp(),"positive unlocked Home/App context");
    locked=YES;Require(!NXUnlockedHomeOrApp(),"lock exclusion");locked=NO;
    unlocking=YES;Require(!NXUnlockedHomeOrApp(),"unlock transition exclusion");unlocking=NO;
    lockVisible=YES;Require(!NXUnlockedHomeOrApp(),"visible lock exclusion");lockVisible=NO;
    coverPresented=YES;Require(!NXUnlockedHomeOrApp(),"presented Cover Sheet exclusion");coverPresented=NO;
    coverVisible=YES;Require(!NXUnlockedHomeOrApp(),"visible Cover Sheet exclusion");coverVisible=NO;
    NXFixtureLook *look=[NXFixtureLook new];
    look.material=[UIView new];look.material.superview=look;
    look.content=[UIView new];look.content.superview=look;
    NXFixtureShortController *shortController=[NXFixtureShortController new];
    shortController.look=look;shortController.request=[NXFixtureRequest new];
    NXFixturePresentable *owner=[NXFixturePresentable new];owner.controller=shortController;
    NXBannerParts *parts=NXResolveBannerParts(owner,YES);
    Require(parts && parts.look==look && parts.material==look.material &&
            parts.content==look.content && parts.requestIdentity==shortController.request,
            "resolution preserves exact native view/request identities");
    Require(!NXResolveBannerParts(owner,NO),"nonbanner without live session remains excluded");
    banner=NO;
    if (lifecycle) Require(NXResolveBannerParts(owner,YES)!=nil,"lifecycle admits target banner when look flag is false");
    else Require(!NXResolveBannerParts(owner,YES),"legacy OS still requires positive look flag");
    Require(!NXResolveBannerParts(owner,NO),"negative look flag without live session rejected on every OS");
    banner=YES;
    critical=YES;Require(!NXResolveBannerParts(owner,YES),"critical alert exclusion");critical=NO;
    shortController.request=[NXFixtureWrongRequest new];
    Require(!NXResolveBannerParts(owner,YES),"wrong BOOL ABI rejected without invocation");
    shortController.request=[NSObject new];Require(!NXResolveBannerParts(owner,YES),"missing capability rejected");
    shortController.request=[NXFixtureRequest new];
    throws=YES;Require(!NXResolveBannerParts(owner,YES),"native getter exception contained");throws=NO;
    look.content.superview=look.material;
    Require(!NXResolveBannerParts(owner,YES),"material containing content must not be hidden");
    look.content.superview=look;
    owner.controller=[NSObject new];Require(!NXResolveBannerParts(owner,YES),"unrelated content controller rejected");
    owner.controller=shortController;
    Require(NXResolveBannerParts(owner,YES)!=nil,"fresh healthy resolution recovers after rejects");
    Require(!NXResolveBannerParts([NSObject new],YES),"nonnotification presentable rejected");
    Require(osReads==1,"OS authority is cached once");
    puts([[NSString stringWithFormat:@"NOTICE_X_NATIVE_PASS assertions=%d",assertions] UTF8String]);
    return 0;
} }
