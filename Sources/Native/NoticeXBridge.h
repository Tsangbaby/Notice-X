#pragma once
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

NS_ASSUME_NONNULL_BEGIN
extern void MSHookMessageEx(Class cls, SEL selector, IMP replacement, IMP _Nullable * _Nonnull original);

/// Typed snapshots of already-loaded native views. No notification payload is copied.
@interface NXBannerParts : NSObject
@property(nonatomic, strong, readonly) UIView *look;
@property(nonatomic, strong, readonly) UIView *material;
@property(nonatomic, strong, readonly) UIView *content;
@property(nonatomic, strong, readonly) NSObject *requestIdentity;
@end

FOUNDATION_EXPORT BOOL NXUnlockedHomeOrApp(void);
FOUNDATION_EXPORT NXBannerParts * _Nullable NXResolveBannerParts(id owner);
NS_ASSUME_NONNULL_END
