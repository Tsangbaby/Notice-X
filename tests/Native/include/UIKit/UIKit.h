#pragma once
#import <Foundation/Foundation.h>
@interface UIView : NSObject
@property(nonatomic, weak) UIView *superview;
- (BOOL)isDescendantOfView:(UIView *)view;
@end
