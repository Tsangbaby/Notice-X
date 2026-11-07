#pragma once
#import <Foundation/Foundation.h>

// Explicit public-OS provider substitute for production-extracted host tests.
@interface NXFixtureProcessInfo : NSObject
+ (instancetype)processInfo;
@property(nonatomic, readonly) NSOperatingSystemVersion operatingSystemVersion;
@end
