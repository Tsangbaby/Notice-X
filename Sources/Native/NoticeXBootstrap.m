// Only loader and verified Objective-C ABI boundaries live here. UI/state are Swift.
#import "NoticeXBridge.h"
#import <objc/message.h>
#import <mach-o/dyld.h>
#import <string.h>
#import <stdlib.h>

extern void NXStart(void);
extern void NXImagesChanged(void);

// Declaration-only vocabulary; every call below additionally validates the live ABI.
@interface NSObject (NXPrivateSelectorDeclarations)
+ (id)sharedInstanceIfExists;
- (BOOL)isUILocked;
- (BOOL)isUIUnlocking;
- (BOOL)isLockScreenVisible;
- (BOOL)isPresented;
- (BOOL)isVisible;
- (BOOL)_isBanner;
- (BOOL)isCriticalAlert;
- (id)notificationViewController;
- (id)_notificationShortLookViewIfLoaded;
- (id)_lookViewIfLoaded;
- (id)notificationRequest;
- (id)backgroundMaterialView;
- (id)_notificationContentView;
@end

@interface NXBannerParts ()
@property(nonatomic, strong, readwrite) UIView *look;
@property(nonatomic, strong, readwrite) UIView *material;
@property(nonatomic, strong, readwrite) UIView *content;
@property(nonatomic, strong, readwrite) NSObject *requestIdentity;
@end
@implementation NXBannerParts
@end

static const char *NXUnqualified(const char *type) {
    while (type && *type && strchr("rnNoORV", *type)) ++type;
    return type;
}

static BOOL NXGetterMatches(id object, SEL selector, const char *expected) {
    if (!object) return NO;
    Method method = class_getInstanceMethod(object_getClass(object), selector);
    if (!method || method_getNumberOfArguments(method) != 2) return NO;
    char *raw = method_copyReturnType(method);
    const char *type = NXUnqualified(raw);
    BOOL matches = type && (expected[0] == '@' ? type[0] == '@' : strcmp(type, expected) == 0);
    free(raw);
    return matches;
}

static id NXObjectGetter(id object, SEL selector) {
    if (!NXGetterMatches(object, selector, @encode(id))) return nil;
    return ((id (*)(id, SEL))objc_msgSend)(object, selector);
}

static BOOL NXReadBool(id object, SEL selector, BOOL *value) {
    if (!NXGetterMatches(object, selector, @encode(BOOL))) return NO;
    *value = ((BOOL (*)(id, SEL))objc_msgSend)(object, selector);
    return YES;
}

BOOL NXUnlockedHomeOrApp(void) {
    if (!NSThread.isMainThread) { NXDiagnosticRecord(NXDiagnosticNativeCodeNotMain); return NO; }
    @try {
        Class lockClass = NSClassFromString(@"SBLockScreenManager");
        Class coverClass = NSClassFromString(@"SBCoverSheetPresentationManager");
        id lock = NXObjectGetter(lockClass, @selector(sharedInstanceIfExists));
        id cover = NXObjectGetter(coverClass, @selector(sharedInstanceIfExists));
        if (!lock || !cover) { NXDiagnosticRecord(NXDiagnosticNativeCodeManagersMissing); return NO; }
        BOOL locked = YES, unlocking = YES, visible = YES, presented = YES, coverVisible = YES;
        if (!NXReadBool(lock, @selector(isUILocked), &locked)) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeLockUnreadable); return NO;
        }
        if (!NXReadBool(lock, @selector(isUIUnlocking), &unlocking)) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeUnlockingUnreadable); return NO;
        }
        if (!NXReadBool(lock, @selector(isLockScreenVisible), &visible)) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeLockVisibleUnreadable); return NO;
        }
        if (!NXReadBool(cover, @selector(isPresented), &presented)) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeCoverPresentedUnreadable); return NO;
        }
        if (!NXReadBool(cover, @selector(isVisible), &coverVisible)) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeCoverVisibleUnreadable); return NO;
        }
        if (locked) { NXDiagnosticRecord(NXDiagnosticNativeCodeLocked); return NO; }
        if (unlocking) { NXDiagnosticRecord(NXDiagnosticNativeCodeUnlocking); return NO; }
        if (visible) { NXDiagnosticRecord(NXDiagnosticNativeCodeLockVisible); return NO; }
        if (presented) { NXDiagnosticRecord(NXDiagnosticNativeCodeCoverPresented); return NO; }
        if (coverVisible) { NXDiagnosticRecord(NXDiagnosticNativeCodeCoverVisible); return NO; }
        NXDiagnosticRecord(NXDiagnosticNativeCodeContextReady);
        return YES;
    } @catch (__unused NSException *exception) {
        NXDiagnosticRecord(NXDiagnosticNativeCodeException);
        return NO;
    }
}

NXBannerParts *NXResolveBannerParts(id owner) {
    if (!NSThread.isMainThread) { NXDiagnosticRecord(NXDiagnosticNativeCodeResolveNotMain); return nil; }
    if (!NXUnlockedHomeOrApp()) { NXDiagnosticRecord(NXDiagnosticNativeCodeResolveContextRejected); return nil; }
    @try {
        Class presentableClass = NSClassFromString(@"NCNotificationPresentableViewController");
        Class shortControllerClass = NSClassFromString(@"NCNotificationShortLookViewController");
        Class lookClass = NSClassFromString(@"NCNotificationShortLookView");
        if (!presentableClass || !shortControllerClass || !lookClass) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeResolveClassesMissing); return nil;
        }
        if (![owner isKindOfClass:presentableClass]) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeResolveOwnerRejected); return nil;
        }
        id controller = NXObjectGetter(owner, @selector(notificationViewController));
        if (![controller isKindOfClass:shortControllerClass]) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeResolveControllerRejected); return nil;
        }
        id look = NXObjectGetter(controller, @selector(_notificationShortLookViewIfLoaded));
        if (!look) look = NXObjectGetter(controller, @selector(_lookViewIfLoaded));
        if (![look isKindOfClass:lookClass] || ![look isKindOfClass:UIView.class]) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeResolveLookMissing); return nil;
        }
        BOOL banner = NO;
        if (!NXReadBool(look, @selector(_isBanner), &banner)) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeBannerUnreadable); return nil;
        }
        if (!banner) { NXDiagnosticRecord(NXDiagnosticNativeCodeResolveNotBanner); return nil; }
        id request = NXObjectGetter(controller, @selector(notificationRequest));
        BOOL critical = YES;
        if (![request isKindOfClass:NSObject.class]) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeResolveRequestRejected); return nil;
        }
        if (!NXReadBool(request, @selector(isCriticalAlert), &critical)) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeCriticalUnreadable); return nil;
        }
        if (critical) { NXDiagnosticRecord(NXDiagnosticNativeCodeResolveCriticalAlert); return nil; }
        id material = NXObjectGetter(look, @selector(backgroundMaterialView));
        id content = NXObjectGetter(look, @selector(_notificationContentView));
        if (![material isKindOfClass:UIView.class] || ![content isKindOfClass:UIView.class] ||
            material == look || content == look || material == content ||
            [(UIView *)content isDescendantOfView:material] ||
            ![(UIView *)material isDescendantOfView:look] ||
            ![(UIView *)content isDescendantOfView:look]) {
            NXDiagnosticRecord(NXDiagnosticNativeCodeResolveHierarchyRejected); return nil;
        }
        NXBannerParts *parts = [NXBannerParts new];
        parts.look = look;
        parts.material = material;
        parts.content = content;
        parts.requestIdentity = request;
        NXDiagnosticRecord(NXDiagnosticNativeCodeResolveReady);
        return parts;
    } @catch (__unused NSException *exception) {
        NXDiagnosticRecord(NXDiagnosticNativeCodeException);
        return nil;
    }
}

static void NXImageAdded(const struct mach_header *header, intptr_t slide) {
    (void)header; (void)slide;
    NXImagesChanged();
}

__attribute__((constructor, used)) static void NXLoad(void) {
    NXStart();
    _dyld_register_func_for_add_image(NXImageAdded);
}
