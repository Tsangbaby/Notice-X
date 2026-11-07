#pragma once
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
void MSHookMessageEx(Class cls, SEL selector, IMP replacement, IMP *original);
void NXFixtureRecord(NSString *event);
NSArray<NSString *> *NXFixtureEvents(void);
void NXFixtureClearEvents(void);
id NXFixtureMakeOwner(void);
NSInteger NXFixtureHookCount(void);
