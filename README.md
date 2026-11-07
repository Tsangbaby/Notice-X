# Notice-X

**Glint 风格的通知卡片展开效果。** Swift + UIKit 实现，保留系统通知内容和操作。

- 插件名：Notice-X
- 作者与维护者：Tsangbaby
- 包名：`com.tsangbaby.noticex`
- 当前候选：`0.1.0-beta3`，RootHide 功能验证候选
- 源码与构建：<https://github.com/Tsangbaby/Notice-X>

## 当前候选做什么

为**解锁状态下、桌面或 App 内的普通通知横幅**添加深色毛玻璃卡片与整壳展开效果。

- 保留系统的通知视图、请求、点击动作与手势；不按 Bundle ID 另行启动 App，不重建通知响应。
- 卡片动画参考已实测通过的 Glint：真实圆角外壳与模糊背景一起展开，内容保持完整宽度、稍后进入。
- 不依赖 Glint，不改状态栏时钟，不添加全屏窗口或点击遮罩。
- 默认关闭；一个设置开关，保存后从下一条横幅生效，无需为了改开关再次注销。
- 减弱动态效果时取消插件的局部形变；降低透明度时使用不透明背景。

**重要边界：beta2 的遮罩展开已被实机否决，beta3 不再使用这条路线。** beta3 在原生入场期间准备并隐藏本地视觉，收到原生 did-appear 后再展开一张真实外壳；不修改原生横幅的 frame/transform，也不替换 BannerKit 动画器。展开期间只临时保留一张有像素上限的内容图像，完成后立即释放并交回原来的实时通知内容；图像不写入磁盘。点击、长按、回复和关闭仍交给系统；收起不再叠加插件自己的第二套动画。整壳展开不是整套系统转场替换，流畅度、交接和通知操作仍需实机验收。

## 安装与测试

1. 使用适合设备越狱环境的 RootHide 原始 DEB 安装。
2. 安装后注销一次 SpringBoard。
3. 打开「设置 → Notice-X → 启用 Notice-X」。
4. 保持手机解锁，让另一台设备发送真实通知；不要把 App 自绘的站内提示当成系统横幅。
5. 检查展开与文字可读性、连续通知、点击精准跳转、长按／回复、上滑关闭。

锁屏、解锁过渡、已展示的通知中心／Cover Sheet、严重警报以及不支持的私有接口均保持原生。不要同时开启其他插件的通知横幅替换；Glint 可继续使用，但其 `replaceBanners` 应保持关闭。安装候选包并不意味着所有通知类型已经兼容。

## 实现结构

- `Sources/Core`：准入、每条横幅的 generation/phase、严格 Boolean 设置与保存事务。
- `Sources/UI`：Swift/UIKit 整壳展开、短期内容图像与原生交接、上下文所有权。
- `Sources/Runtime`：Swift Objective-C runtime Hook，检查 ABI 后安装，原方法按原参数调用一次。
- `Sources/Native`：最小加载入口和有类型、异常边界明确的系统视图／锁定状态读取。
- `prefs`：Swift PreferenceLoader 页面，中文／英文。

没有 Orion、Logos、SwiftUI、后台轮询、网络服务或通知正文日志。手写原生代码只承担加载／私有 ABI 边界，并非把旧 Objective-C 控制器包装成 Swift。

## 构建与验证

GitHub Actions 使用 cloud macOS + Apple iPhoneOS SDK，固定 RootHide Theos 提交，同时编译 arm64 / arm64e；最低部署版本 iOS 15.0。最低版本与成功编译不是各 iOS 版本已实测的证明。

本地源代码检查：

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

真实 Swift 核心执行（需要已有 Swift 编译器）：

```sh
python3 -B tests/run_swift_tests.py --out /path/to/test-evidence
```

Mac 上还运行实际原生 ABI 提供者和实际 Swift 动画所有者的显式替身测试。替身验证签名、身份、退回、初始化、异常、动画状态与资源释放，不进入安装包，不代表真实 UIKit 渲染或 SpringBoard 实机行为。

构建产物保留源提交、工具链、执行日志、包校验报告和 SHA-256。交付的是云端生成的原始 DEB，不二次打包、重签，也不自动发布 GitHub Release。

## 参考来源与验证边界

卡片视觉参考 Glint 重建工程，固定版本 `9b07183cd428b9b385c989377d25ca5595fcf424`；仅移植所需视觉行为和参数，未搬入其通知分流、天气、媒体或时钟状态机。私有接口依据与版本范围见 [PRIVATE_API_EVIDENCE](docs/PRIVATE_API_EVIDENCE.md)。

**当前是整壳展开的实机验证候选，不是已验收版本。** beta2 实机已能显示卡片，但入场分段、闪变与 Glint 效果不符。beta3 替换其视觉路线；源码检查、Swift 执行、Apple 编译、包完整性和实机验收仍是不同证据层。
