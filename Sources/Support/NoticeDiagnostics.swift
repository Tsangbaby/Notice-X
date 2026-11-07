import Foundation

/// Fixed numeric bridge only. The exception-contained native sink owns bounded I/O.
enum NXDiagnostic {
    enum Phase: Int32 {
        case runtimeStart = 100
        case installClassMissing = 101
        case installClassSB = 102
        case installClassNC = 103
        case installCheckWillAppear = 104
        case installCheckDidAppear = 105
        case installCheckWillDisappear = 106
        case installCheckDidDisappear = 107
        case installCheckWillNotAppear = 108
        case installCheckInteraction = 109
        case installCheckLongLook = 110
        case installCheckLayout = 111
        case installSelectorMissing = 112
        case installArgumentCountMismatch = 113
        case installReturnTypeMismatch = 114
        case installArgumentTypeMismatch = 115
        case installABIMismatch = 116
        case installComplete = 117
        case runtimeSwitchOn = 118
        case runtimeSwitchOff = 119
        case bannerWillAppear = 120
        case bannerSwitchOff = 121
        case bannerContextRejected = 122
        case bannerContextReady = 123
        case bannerSessionCreated = 124
        case bannerDidAppear = 125
        case bannerDidAppearWithoutSession = 126
        case layoutWithoutSession = 127
        case layoutSessionBusy = 128
        case layoutSwitchOff = 129
        case layoutContextRejected = 130
        case admissionRejected = 131
        case admissionReady = 132
        case visualReused = 133
        case visualConstructorRejected = 134
        case visualInstalled = 135
        case callbackWillAppear = 136
        case callbackDidAppear = 137
        case callbackWillDisappear = 138
        case callbackDidDisappear = 139
        case callbackWillNotAppear = 140
        case callbackInteraction = 141
        case callbackLongLook = 142
        case callbackLayout = 143
        case visualIdentityRejected = 144
        case visualSessionReplaced = 145
    }

    static func begin() { NXDiagnosticBegin() }
    static func record(_ phase: Phase) { NXDiagnosticRecord(phase.rawValue) }
}
