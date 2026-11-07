// Explicit host doubles. Foundation/CoreGraphics geometry is real; UIKit is not.
@_exported import Foundation
@_exported import CoreGraphics

public enum UIUserInterfaceStyle { case unspecified, light, dark }
public enum CALayerCornerCurve { case circular, continuous }
public enum UIViewContentMode { case scaleToFill, scaleAspectFit, scaleAspectFill, center }
public struct UIViewAutoresizing: OptionSet {
    public let rawValue: Int
    public init(rawValue: Int) { self.rawValue = rawValue }
    public static let flexibleWidth = UIViewAutoresizing(rawValue: 1)
    public static let flexibleHeight = UIViewAutoresizing(rawValue: 2)
}

public final class UIColor: NSObject {
    public static let black = UIColor(white: 0, alpha: 1)
    public static let clear = UIColor(white: 0, alpha: 0)
    public let white: CGFloat
    public let alpha: CGFloat
    public init(white: CGFloat, alpha: CGFloat) { self.white = white; self.alpha = alpha }
}
public enum UIAccessibility {
    public static var isReduceMotionEnabled = false
    public static var isReduceTransparencyEnabled = false
}
public final class UIScreen {
    public static let main = UIScreen()
    public var scale: CGFloat = 3
    public var nativeScale: CGFloat { scale }
}
public final class UITraitCollection {
    public var displayScale: CGFloat { UIScreen.main.scale }
}

// Only the affine surface needed by the frozen beta2 negative control.
public struct CATransform3D {
    public var affine: CGAffineTransform
    public init(_ affine: CGAffineTransform = .identity) { self.affine = affine }
}
public let CATransform3DIdentity = CATransform3D()
public func CATransform3DIsAffine(_ value: CATransform3D) -> Bool { true }
public func CATransform3DGetAffineTransform(_ value: CATransform3D) -> CGAffineTransform { value.affine }

public struct VisualMutation {
    public let view: ObjectIdentifier
    public let property: String
}
public struct VisualDraw {
    public let view: ObjectIdentifier
    public let alpha: CGFloat
    public let hidden: Bool
    public let bounds: CGRect
}
public struct VisualRender {
    public let bounds: CGRect
    public let scale: CGFloat
    public var physicalPixels: Double {
        Double(ceil(bounds.width * scale)) * Double(ceil(bounds.height * scale))
    }
}
public enum VisualTrace {
    public static var mutations: [VisualMutation] = []
    public static var draws: [VisualDraw] = []
    public static var renders: [VisualRender] = []
    public static var imagesCreated = 0
    public static var imagesReleased = 0
    public static var liveImages: Int { imagesCreated - imagesReleased }
    public static var drawSucceeds = true
    public static func changed(_ view: UIView, _ property: String) {
        mutations.append(VisualMutation(view: ObjectIdentifier(view), property: property))
    }
    public static func draw(_ view: UIView) {
        draws.append(VisualDraw(view: ObjectIdentifier(view), alpha: view.alpha,
                                hidden: view.isHidden, bounds: view.bounds))
    }
    public static func reset() {
        precondition(liveImages == 0, "previous case leaked a rendered image")
        mutations = []; draws = []; renders = []
        imagesCreated = 0; imagesReleased = 0; drawSucceeds = true
        UIViewPropertyAnimator.scheduled = []
        UIAccessibility.isReduceMotionEnabled = false
        UIAccessibility.isReduceTransparencyEnabled = false
        UIScreen.main.scale = 3
    }
}

open class CALayer: NSObject {
    public weak var owner: UIView?
    public var frame: CGRect = .zero
    public var bounds: CGRect = .zero
    public var cornerRadius: CGFloat = 0
    public var cornerCurve: CALayerCornerCurve = .circular
    public var masksToBounds = false
    public var opacity: Float = 1
    public var transform = CATransform3DIdentity
    public var presentationLayer: CALayer?
    public func presentation() -> CALayer? { presentationLayer }
    public func render(in context: CGContext) {
        if let owner = owner { VisualTrace.draw(owner) }
    }
}

open class UIView: NSObject {
    private var storedFrame: CGRect
    private var storedBounds: CGRect
    public let layer = CALayer()
    public private(set) weak var superview: UIView?
    public private(set) var subviews: [UIView] = []
    open var frame: CGRect {
        get { storedFrame }
        set {
            VisualTrace.changed(self, "frame")
            storedFrame = newValue; storedBounds.size = newValue.size
            layer.frame = newValue; layer.bounds = storedBounds
        }
    }
    open var bounds: CGRect {
        get { storedBounds }
        set {
            VisualTrace.changed(self, "bounds")
            storedBounds = newValue; storedFrame.size = newValue.size
            layer.bounds = newValue; layer.frame = storedFrame
        }
    }
    public var alpha: CGFloat = 1 {
        didSet { layer.opacity = Float(alpha); VisualTrace.changed(self, "alpha") }
    }
    public var transform: CGAffineTransform = .identity {
        didSet { layer.transform = CATransform3D(transform); VisualTrace.changed(self, "transform") }
    }
    public var isHidden = false { didSet { VisualTrace.changed(self, "hidden") } }
    public var mask: UIView? { didSet { VisualTrace.changed(self, "mask") } }
    public var isUserInteractionEnabled = true
    public var accessibilityElementsHidden = false
    public var clipsToBounds = false { didSet { layer.masksToBounds = clipsToBounds } }
    public var backgroundColor: UIColor?
    public var overrideUserInterfaceStyle: UIUserInterfaceStyle = .unspecified
    public var autoresizingMask: UIViewAutoresizing = []
    public var contentMode: UIViewContentMode = .scaleToFill
    public let traitCollection = UITraitCollection()
    public var window: UIWindow? { (self as? UIWindow) ?? superview?.window }
    public init(frame: CGRect) {
        storedFrame = frame; storedBounds = CGRect(origin: .zero, size: frame.size)
        super.init()
        layer.owner = self; layer.frame = frame; layer.bounds = storedBounds
    }
    public override convenience init() { self.init(frame: .zero) }
    public required init?(coder: NSCoder) {
        storedFrame = .zero; storedBounds = .zero
        super.init(); layer.owner = self
    }
    public func addSubview(_ view: UIView) { insertSubview(view, at: subviews.count) }
    public func insertSubview(_ view: UIView, at index: Int) {
        view.removeFromSuperview()
        subviews.insert(view, at: min(index, subviews.count)); view.superview = self
        VisualTrace.changed(view, "superview")
    }
    public func removeFromSuperview() {
        guard let parent = superview else { return }
        parent.subviews.removeAll { $0 === self }; superview = nil
        VisualTrace.changed(self, "superview")
    }
    public func isDescendant(of view: UIView) -> Bool {
        self === view || (superview?.isDescendant(of: view) ?? false)
    }
    public func convert(_ rect: CGRect, from view: UIView?) -> CGRect {
        // All fixture ancestors have identity transforms; CoreGraphics still owns the geometry.
        func offset(_ view: UIView?) -> CGPoint {
            var result = CGPoint.zero, cursor = view
            while let current = cursor {
                precondition(current.transform == .identity, "fixture conversion only admits identity ancestors")
                result.x += current.frame.minX - current.bounds.minX
                result.y += current.frame.minY - current.bounds.minY
                cursor = current.superview
            }
            return result
        }
        let source = offset(view), destination = offset(self)
        return rect.offsetBy(dx: source.x - destination.x, dy: source.y - destination.y)
    }
    open func layoutSubviews() {}
    public func setNeedsLayout() {}
    public func layoutIfNeeded() {
        layoutSubviews()
        for view in subviews { view.layoutIfNeeded() }
    }
    public func drawHierarchy(in rect: CGRect, afterScreenUpdates: Bool) -> Bool {
        VisualTrace.draw(self); return VisualTrace.drawSucceeds
    }
    public static func performWithoutAnimation(_ actions: () -> Void) { actions() }
}

open class UIWindow: UIView { public let screen = UIScreen.main }

open class UIVisualEffect: NSObject {}
public final class UIBlurEffect: UIVisualEffect {
    public enum Style { case systemThickMaterialDark }
    public let style: Style
    public init(style: Style) { self.style = style; super.init() }
}
open class UIVisualEffectView: UIView {
    public var effect: UIVisualEffect?
    public let contentView = UIView(frame: .zero)
    public init(effect: UIVisualEffect?) {
        self.effect = effect; super.init(frame: .zero); addSubview(contentView)
    }
    public required init?(coder: NSCoder) { effect = nil; super.init(coder: coder) }
    open override func layoutSubviews() { super.layoutSubviews(); contentView.frame = bounds }
}

public final class UIImage: NSObject {
    public let size: CGSize
    public let scale: CGFloat
    public init(size: CGSize, scale: CGFloat) {
        self.size = size; self.scale = scale
        super.init(); VisualTrace.imagesCreated += 1
    }
    deinit { VisualTrace.imagesReleased += 1 }
}
open class UIImageView: UIView {
    public var image: UIImage?
    public init(image: UIImage?) {
        self.image = image
        super.init(frame: CGRect(origin: .zero, size: image?.size ?? .zero))
    }
    public override init(frame: CGRect) { super.init(frame: frame) }
    public required init?(coder: NSCoder) { super.init(coder: coder) }
}
public final class UIGraphicsImageRendererFormat {
    public var scale = UIScreen.main.scale
    public var opaque = false
    public enum Range { case automatic, extended, standard }
    public var preferredRange: Range = .automatic
    public init() {}
    public static func `default`() -> UIGraphicsImageRendererFormat { UIGraphicsImageRendererFormat() }
    public static func preferred() -> UIGraphicsImageRendererFormat { UIGraphicsImageRendererFormat() }
}
public final class UIGraphicsImageRendererContext {
    // A real tiny CGContext is sufficient: we record calls, not notification pixels.
    public let cgContext = CGContext(data: nil, width: 1, height: 1, bitsPerComponent: 8,
        bytesPerRow: 4, space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
}
public final class UIGraphicsImageRenderer {
    public let bounds: CGRect
    public let format: UIGraphicsImageRendererFormat
    public init(bounds: CGRect, format: UIGraphicsImageRendererFormat) {
        self.bounds = bounds; self.format = format
    }
    public convenience init(size: CGSize, format: UIGraphicsImageRendererFormat) {
        self.init(bounds: CGRect(origin: .zero, size: size), format: format)
    }
    public convenience init(size: CGSize) { self.init(size: size, format: .default()) }
    public func image(actions: (UIGraphicsImageRendererContext) -> Void) -> UIImage {
        VisualTrace.renders.append(VisualRender(bounds: bounds, scale: format.scale))
        actions(UIGraphicsImageRendererContext())
        return UIImage(size: bounds.size, scale: format.scale)
    }
}

public protocol UITimingCurveProvider {}
public final class UISpringTimingParameters: UITimingCurveProvider {
    public let dampingRatio: CGFloat
    public let initialVelocity: CGVector
    public init(dampingRatio: CGFloat, initialVelocity: CGVector = .zero) {
        self.dampingRatio = dampingRatio; self.initialVelocity = initialVelocity
    }
}
public enum UIViewAnimatingState { case inactive, active, stopped }
public enum UIViewAnimatingPosition { case start, end, current }
public final class UIViewPropertyAnimator {
    public static var scheduled: [UIViewPropertyAnimator] = []
    public let duration: TimeInterval
    public let timingParameters: UITimingCurveProvider?
    public private(set) var state: UIViewAnimatingState = .inactive
    public private(set) var delay: TimeInterval = 0
    public private(set) var stoppedWithoutFinishing: Bool?
    public private(set) var animationRuns = 0
    public private(set) var completionRuns = 0
    private var animations: [() -> Void] = []
    private var completions: [(UIViewAnimatingPosition) -> Void] = []
    public init(duration: TimeInterval, timingParameters: UITimingCurveProvider) {
        self.duration = duration; self.timingParameters = timingParameters
    }
    public func addAnimations(_ animation: @escaping () -> Void) { animations.append(animation) }
    public func addCompletion(_ completion: @escaping (UIViewAnimatingPosition) -> Void) {
        completions.append(completion)
    }
    public func startAnimation() { startAnimation(afterDelay: 0) }
    public func startAnimation(afterDelay delay: TimeInterval) {
        self.delay = delay; state = .active; Self.scheduled.append(self)
    }
    public func stopAnimation(_ withoutFinishing: Bool) {
        state = .stopped; stoppedWithoutFinishing = withoutFinishing
    }
    public func finishAnimation(at position: UIViewAnimatingPosition) { replayCompletion(position) }
    // Intentionally callable even after stop, repeatedly, to deliver stale work.
    public func replayAnimations() { animationRuns += 1; for action in animations { action() } }
    public func replayCompletion(_ position: UIViewAnimatingPosition) {
        completionRuns += 1; state = .stopped
        for completion in completions { completion(position) }
    }
}
