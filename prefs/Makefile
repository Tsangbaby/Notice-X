THEOS_PACKAGE_SCHEME = roothide
TARGET = iphone:clang:18.5:15.0
ARCHS = arm64 arm64e

include $(THEOS)/makefiles/common.mk

BUNDLE_NAME = NoticeXPrefs
NoticeXPrefs_FILES = NoticeXPreferences.swift ../Sources/Core/NoticePolicy.swift \
    ../Sources/Support/NoticePreferences.swift
NoticeXPrefs_FRAMEWORKS = Foundation UIKit
NoticeXPrefs_PRIVATE_FRAMEWORKS = Preferences
NoticeXPrefs_SWIFT_VERSION = 5
NoticeXPrefs_SWIFT_BRIDGING_HEADER = NoticeXPreferencesBridge.h
NoticeXPrefs_SWIFTFLAGS = -O
NoticeXPrefs_STRIP_FLAGS = -S
NoticeXPrefs_INSTALL_PATH = /Library/PreferenceBundles
NoticeXPrefs_RESOURCE_DIRS = Resources

include $(THEOS_MAKE_PATH)/bundle.mk
