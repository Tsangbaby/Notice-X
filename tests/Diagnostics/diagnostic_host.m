// Execute the actual diagnostic producer with real Foundation/CFPreferences.
#import <Foundation/Foundation.h>
#import <CoreFoundation/CoreFoundation.h>
#import <dispatch/dispatch.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
extern void NXDiagnosticBegin(void);
extern void NXDiagnosticRecord(int32_t code);
extern void NXDiagnosticHostDrain(void);
extern NSUInteger NXDiagnosticHostPending(void);
extern void NXDiagnosticHostFailPublication(void);
static int assertions;
static CFStringRef const domain = CFSTR("com.tsangbaby.noticex.diag1541");
static void Require(BOOL condition) {
    ++assertions;
    if (!condition) { fputs("NOTICE_X_DIAGNOSTIC_FAIL\n", stderr); exit(1); }
}
static NSDictionary *Snapshot(void) {
    CFPreferencesAppSynchronize(domain);
    return CFBridgingRelease(CFPreferencesCopyAppValue(CFSTR("snapshot"), domain));
}
int main(int argc, const char *argv[]) { @autoreleasepool {
    Require(argc == 3);
    NSString *mode = [NSString stringWithUTF8String:argv[1]];
    CFPreferencesSetAppValue(CFSTR("snapshot"), NULL, domain);
    Require(CFPreferencesAppSynchronize(domain));
    if ([mode isEqualToString:@"reset-failure"]) NXDiagnosticHostFailPublication();
    NXDiagnosticBegin();
    NXDiagnosticHostDrain();
    Require(NXDiagnosticHostPending() == 0);
    if ([mode isEqualToString:@"reset-failure"]) {
        Require(Snapshot() == nil);
        NXDiagnosticRecord(1); NXDiagnosticHostDrain();
        Require(Snapshot() == nil && NXDiagnosticHostPending() == 0);
    } else {
        NSDictionary *initial = Snapshot();
        Require([initial isKindOfClass:NSDictionary.class]);
        Require([initial[@"build"] isEqual:@"banner-entry-1541-v1"]);
        Require(CFGetTypeID((__bridge CFTypeRef)initial[@"resetConfirmed"]) == CFBooleanGetTypeID());
        Require([initial[@"resetConfirmed"] boolValue]);
        Require([initial[@"trace"] isEqual:@[@"runtime_start"]]);
        NXDiagnosticBegin(); NXDiagnosticHostDrain();
        Require([Snapshot() isEqual:initial]);
        if ([mode isEqualToString:@"write-failure"]) {
            NXDiagnosticHostFailPublication();
            NXDiagnosticRecord(1); NXDiagnosticHostDrain();
            Require([Snapshot() isEqual:initial]);
            NXDiagnosticRecord(2); NXDiagnosticHostDrain();
            Require([Snapshot() isEqual:initial] && NXDiagnosticHostPending() == 0);
        } else {
            Require([mode isEqualToString:@"healthy"]);
            dispatch_apply(5000, dispatch_get_global_queue(QOS_CLASS_DEFAULT, 0), ^(size_t index) {
                NXDiagnosticRecord((int32_t)(index % 180));
            });
            NXDiagnosticRecord(-1); NXDiagnosticRecord(INT32_MAX);
            NXDiagnosticHostDrain();
            NSDictionary *snapshot = Snapshot();
            NSArray *trace = snapshot[@"trace"];
            Require(trace.count > 70 && trace.count <= 96);
            Require([NSSet setWithArray:trace].count == trace.count);
            Require([snapshot[@"sequence"] unsignedIntegerValue] == trace.count);
            Require(NXDiagnosticHostPending() == 0);
            NSDictionary *wrapper = @{@"snapshot": snapshot};
            NSData *raw = [NSPropertyListSerialization dataWithPropertyList:wrapper
                format:NSPropertyListBinaryFormat_v1_0 options:0 error:NULL];
            Require(raw != nil && raw.length <= 16384);
            NSString *path = [NSString stringWithUTF8String:argv[2]];
            Require([raw writeToFile:path options:NSDataWritingAtomic error:NULL]);
        }
    }
    CFPreferencesSetAppValue(CFSTR("snapshot"), NULL, domain);
    Require(CFPreferencesAppSynchronize(domain));
    printf("NOTICE_X_DIAGNOSTIC_PASS assertions=%d\n", assertions);
    return 0;
} }
