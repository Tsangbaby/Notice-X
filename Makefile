THEOS_PACKAGE_SCHEME = roothide
TARGET = iphone:clang:18.5:15.0
ARCHS = arm64 arm64e
INSTALL_TARGET_PROCESSES = SpringBoard

ifneq ($(THEOS_PACKAGE_SCHEME),roothide)
$(error Notice-X first candidate supports only THEOS_PACKAGE_SCHEME=roothide)
endif

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = NoticeX
NoticeX_FILES = Sources/Core/NoticePolicy.swift Sources/Support/NoticePreferences.swift \
    Sources/Support/NoticeDiagnostics.swift Sources/Native/NoticeXDiagnostics.m \
    Sources/Runtime/NoticeRuntime.swift Sources/UI/NoticeCardAnimator.swift \
    Sources/UI/NoticeBannerCoordinator.swift Sources/Native/NoticeXBootstrap.m
NoticeX_FRAMEWORKS = Foundation UIKit QuartzCore
NoticeX_LIBRARIES = substrate
NoticeX_CFLAGS = -fobjc-arc
NoticeX_SWIFT_VERSION = 5
NoticeX_SWIFT_BRIDGING_HEADER = Sources/Native/NoticeXBridge.h
NoticeX_SWIFTFLAGS = -O
# Retain defined Swift symbol evidence; remove debug symbols only.
NoticeX_STRIP_FLAGS = -S

include $(THEOS_MAKE_PATH)/tweak.mk

SUBPROJECTS = prefs
include $(THEOS_MAKE_PATH)/aggregate.mk
