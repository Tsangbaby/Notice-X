// Temporary, first-reach-only evidence. No request objects cross this boundary.
#import <Foundation/Foundation.h>
#import <CoreFoundation/CoreFoundation.h>
#import <dispatch/dispatch.h>
#include <pthread.h>
#include <stdint.h>

static CFStringRef const NXDiagnosticDomain = CFSTR("com.tsangbaby.noticex.diag1541");
static CFStringRef const NXSnapshotKey = CFSTR("snapshot");
static NSString *const NXDiagnosticBuild = @"banner-entry-1541-v1";
static const NSUInteger NXMaxEvents = 96;
static const NSUInteger NXMaxPending = 32;
static const NSUInteger NXMaxBytes = 16384;
static pthread_mutex_t NXDiagnosticLock = PTHREAD_MUTEX_INITIALIZER;
static dispatch_queue_t NXWriter;
static BOOL NXStarted;
static BOOL NXBeginning;
static BOOL NXDisabled;
static BOOL NXSeen[146];
static int32_t NXBufferedCodes[96];
static BOOL NXDrainScheduled;
static NSUInteger NXDrained;
static NSUInteger NXPending;
static NSUInteger NXAccepted;
// Writer-owned state, never accessed by a banner callback.
static BOOL NXResetConfirmed;
static NSUInteger NXGeneration;
static NSMutableArray<NSString *> *NXTrace;
#ifdef NX_DIAGNOSTIC_HOST_TEST
static BOOL NXHostFailPublication;
#endif

static const char *NXPhaseName(int32_t code) {
    switch (code) {
        case 1: return "native_not_main";
        case 2: return "native_managers_missing";
        case 3: return "native_state_unreadable";
        case 4: return "native_context_rejected";
        case 5: return "native_context_ready";
        case 6: return "native_resolve_not_main";
        case 7: return "native_resolve_context_rejected";
        case 8: return "resolve_classes_missing";
        case 9: return "resolve_owner_rejected";
        case 10: return "resolve_controller_rejected";
        case 11: return "resolve_look_missing";
        case 12: return "resolve_not_banner";
        case 13: return "resolve_request_rejected";
        case 14: return "resolve_critical_alert";
        case 15: return "resolve_subviews_missing";
        case 16: return "resolve_hierarchy_rejected";
        case 17: return "resolve_ready";
        case 18: return "native_exception";
        case 19: return "native_lock_unreadable";
        case 20: return "native_unlocking_unreadable";
        case 21: return "native_lock_visible_unreadable";
        case 22: return "native_cover_presented_unreadable";
        case 23: return "native_cover_visible_unreadable";
        case 24: return "native_locked";
        case 25: return "native_unlocking";
        case 26: return "native_lock_visible";
        case 27: return "native_cover_presented";
        case 28: return "native_cover_visible";
        case 29: return "resolve_banner_unreadable";
        case 30: return "resolve_critical_unreadable";
        case 100: return "runtime_start";
        case 101: return "install_class_missing";
        case 102: return "install_class_sb";
        case 103: return "install_class_nc";
        case 104: return "install_check_will_appear";
        case 105: return "install_check_did_appear";
        case 106: return "install_check_will_disappear";
        case 107: return "install_check_did_disappear";
        case 108: return "install_check_will_not_appear";
        case 109: return "install_check_interaction";
        case 110: return "install_check_long_look";
        case 111: return "install_check_layout";
        case 112: return "install_selector_missing";
        case 113: return "install_argument_count_mismatch";
        case 114: return "install_return_type_mismatch";
        case 115: return "install_argument_type_mismatch";
        case 116: return "install_abi_mismatch";
        case 117: return "install_complete";
        case 118: return "runtime_switch_on";
        case 119: return "runtime_switch_off";
        case 120: return "banner_will_appear";
        case 121: return "banner_switch_off";
        case 122: return "banner_context_rejected";
        case 123: return "banner_context_ready";
        case 124: return "banner_session_created";
        case 125: return "banner_did_appear";
        case 126: return "banner_did_appear_without_session";
        case 127: return "layout_without_session";
        case 128: return "layout_session_busy";
        case 129: return "layout_switch_off";
        case 130: return "layout_context_rejected";
        case 131: return "admission_rejected";
        case 132: return "admission_ready";
        case 133: return "visual_reused";
        case 134: return "visual_constructor_rejected";
        case 135: return "visual_installed";
        case 136: return "callback_will_appear";
        case 137: return "callback_did_appear";
        case 138: return "callback_will_disappear";
        case 139: return "callback_did_disappear";
        case 140: return "callback_will_not_appear";
        case 141: return "callback_interaction";
        case 142: return "callback_long_look";
        case 143: return "callback_layout";
        case 144: return "visual_identity_rejected";
        case 145: return "visual_session_replaced";
        default: return NULL;
    }
}

static void NXDisableDiagnostic(void) {
    pthread_mutex_lock(&NXDiagnosticLock);
    NXDisabled = YES;
    pthread_mutex_unlock(&NXDiagnosticLock);
}

static void NXReleaseReservation(void) {
    pthread_mutex_lock(&NXDiagnosticLock);
    --NXPending;
    pthread_mutex_unlock(&NXDiagnosticLock);
}

// Called only on the serial writer. Whole-wrapper serialization also bounds the
// actual preferences representation, not merely the phase array's element count.
static BOOL NXPublish(void) {
#ifdef NX_DIAGNOSTIC_HOST_TEST
    if (NXHostFailPublication) [NSException raise:@"NXDiagnosticHostFailure" format:@"fixed_failure"];
#endif
    NSDictionary *snapshot = @{
        @"schema": @1, @"build": NXDiagnosticBuild,
        @"generation": @(NXGeneration), @"sequence": @(NXTrace.count),
        @"resetConfirmed": @((BOOL)NXResetConfirmed),
        @"trace": [NXTrace copy]
    };
    NSDictionary *wrapper = @{@"snapshot": snapshot};
    CFDataRef encoded = CFPropertyListCreateData(kCFAllocatorDefault,
        (__bridge CFPropertyListRef)wrapper, kCFPropertyListBinaryFormat_v1_0, 0, NULL);
    if (!encoded) return NO;
    BOOL bounded = CFDataGetLength(encoded) <= (CFIndex)NXMaxBytes;
    CFRelease(encoded);
    if (!bounded) return NO;
    CFPreferencesSetAppValue(NXSnapshotKey, (__bridge CFPropertyListRef)snapshot, NXDiagnosticDomain);
    if (!CFPreferencesAppSynchronize(NXDiagnosticDomain)) return NO;
    CFPropertyListRef readback = CFPreferencesCopyAppValue(NXSnapshotKey, NXDiagnosticDomain);
    if (!readback) return NO;
    BOOL equal = CFEqual(readback, (__bridge CFTypeRef)snapshot);
    CFRelease(readback);
    return equal;
}

static void NXDrain(void) {
    for (;;) {
        int32_t batch[96];
        NSUInteger count = 0;
        pthread_mutex_lock(&NXDiagnosticLock);
        if (NXDisabled || NXDrained == NXAccepted) {
            NXDrainScheduled = NO;
            pthread_mutex_unlock(&NXDiagnosticLock);
            return;
        }
        while (NXDrained < NXAccepted) batch[count++] = NXBufferedCodes[NXDrained++];
        pthread_mutex_unlock(&NXDiagnosticLock);
        if (!NXResetConfirmed) { NXDisableDiagnostic(); continue; }
        for (NSUInteger index = 0; index < count; ++index) {
            [NXTrace addObject:[NSString stringWithUTF8String:NXPhaseName(batch[index])]];
        }
        if (!NXPublish()) NXDisableDiagnostic();
    }
}

void NXDiagnosticBegin(void) {
    BOOL reserved = NO;
    BOOL submitted = NO;
    @try {
#ifndef NX_DIAGNOSTIC_HOST_TEST
        NSOperatingSystemVersion os = NSProcessInfo.processInfo.operatingSystemVersion;
        if (os.majorVersion != 15 || os.minorVersion != 4 || os.patchVersion != 1) return;
#endif
        static dispatch_once_t queueOnce;
        dispatch_once(&queueOnce, ^{
            NXWriter = dispatch_queue_create("com.tsangbaby.noticex.diag1541.writer", DISPATCH_QUEUE_SERIAL);
        });
        pthread_mutex_lock(&NXDiagnosticLock);
        if (NXStarted || NXBeginning) { pthread_mutex_unlock(&NXDiagnosticLock); return; }
        NXBeginning = YES;
        NXPending = 1;
        NXAccepted = 1;
        NXSeen[100] = YES;
        NXBufferedCodes[0] = 100;
        NXDrained = 1;
        pthread_mutex_unlock(&NXDiagnosticLock);
        reserved = YES;
        dispatch_async(NXWriter, ^{
            @autoreleasepool {
                @try {
                    CFPreferencesAppSynchronize(NXDiagnosticDomain);
                    CFPropertyListRef prior = CFPreferencesCopyAppValue(NXSnapshotKey, NXDiagnosticDomain);
                    NSDictionary *previous = CFBridgingRelease(prior);
                    NSNumber *generation = [previous isKindOfClass:NSDictionary.class] ? previous[@"generation"] : nil;
                    NSInteger old = [generation isKindOfClass:NSNumber.class] ? generation.integerValue : 0;
                    NXGeneration = (old >= 0 && old < INT32_MAX) ? (NSUInteger)old + 1 : 1;
                    NXTrace = [NSMutableArray new];
                    NXResetConfirmed = NO;
                    if (!NXPublish()) { NXDisableDiagnostic(); return; }
                    NXResetConfirmed = YES;
                    [NXTrace addObject:@"runtime_start"];
                    if (!NXPublish()) NXDisableDiagnostic();
                } @catch (__unused NSException *exception) {
                    NXDisableDiagnostic();
                } @finally {
                    NXReleaseReservation();
                }
            }
        });
        submitted = YES;
        pthread_mutex_lock(&NXDiagnosticLock);
        NXStarted = YES;
        NXBeginning = NO;
        pthread_mutex_unlock(&NXDiagnosticLock);
    } @catch (__unused NSException *exception) {
        NXDisableDiagnostic();
        if (reserved && !submitted) NXReleaseReservation();
    }
}

void NXDiagnosticRecord(int32_t code) {
    // Only closed numeric codes are accepted. No caller strings/objects are retained.
    const char *literal = NXPhaseName(code);
    if (!literal) return;
    BOOL reserved = NO;
    BOOL submitted = NO;
    @try {
        pthread_mutex_lock(&NXDiagnosticLock);
        if (!NXStarted || NXDisabled || NXSeen[code] || NXAccepted >= NXMaxEvents) {
            pthread_mutex_unlock(&NXDiagnosticLock);
            return;
        }
        NXSeen[code] = YES;
        NXBufferedCodes[NXAccepted++] = code;
        if (NXDrainScheduled) { pthread_mutex_unlock(&NXDiagnosticLock); return; }
        // Markers share a fixed buffer and coalesced drains, not one job each.
        if (NXPending >= NXMaxPending) {
            NXDisabled = YES;
            pthread_mutex_unlock(&NXDiagnosticLock);
            return;
        }
        NXDrainScheduled = YES;
        ++NXPending;
        pthread_mutex_unlock(&NXDiagnosticLock);
        reserved = YES;
        dispatch_async(NXWriter, ^{
            @autoreleasepool {
                @try {
                    NXDrain();
                } @catch (__unused NSException *exception) {
                    NXDisableDiagnostic();
                } @finally {
                    NXReleaseReservation();
                }
            }
        });
        submitted = YES;
    } @catch (__unused NSException *exception) {
        NXDisableDiagnostic();
        if (reserved && !submitted) NXReleaseReservation();
    }
}

#ifdef NX_DIAGNOSTIC_HOST_TEST
// Test-only synchronization of the real writer; never compiled into the package.
void NXDiagnosticHostDrain(void) { dispatch_sync(NXWriter, ^{}); }
void NXDiagnosticHostFailPublication(void) {
    if (NXWriter) dispatch_sync(NXWriter, ^{ NXHostFailPublication = YES; });
    else NXHostFailPublication = YES;
}
NSUInteger NXDiagnosticHostPending(void) {
    pthread_mutex_lock(&NXDiagnosticLock);
    NSUInteger result = NXPending;
    pthread_mutex_unlock(&NXDiagnosticLock);
    return result;
}
#endif
