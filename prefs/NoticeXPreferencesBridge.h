#pragma once
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>

// Declaration-only subset verified against theos/headers 13c1f17 Preferences headers.
// Do not import unsupported legacy initializers into Swift's automatic inheritance.
@interface PSSpecifier : NSObject
- (id)propertyForKey:(NSString *)key;
- (void)setProperty:(id)value forKey:(NSString *)key;
@end
@interface PSViewController : UIViewController
- (id)readPreferenceValue:(PSSpecifier *)specifier;
- (void)setPreferenceValue:(id)value specifier:(PSSpecifier *)specifier;
@end
@interface PSListController : PSViewController
@property(nonatomic, retain) NSMutableArray *specifiers;
- (NSMutableArray *)loadSpecifiersFromPlistName:(NSString *)name target:(PSListController *)target;
- (void)reloadSpecifier:(PSSpecifier *)specifier;
@end
