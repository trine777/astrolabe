// 星图 - 风隐式设计系统

import SwiftUI

// MARK: - 颜色扩展

extension Color {
    /// 星图主背景色
    static let xingtuBackground = Color(red: 0.08, green: 0.08, blue: 0.10)
    
    /// 星图次级背景
    static let xingtuSecondaryBackground = Color(red: 0.12, green: 0.12, blue: 0.14)
    
    /// 星图强调色 - 星辰蓝
    static let xingtuAccent = Color(red: 0.4, green: 0.6, blue: 0.95)
    
    /// 星图次级强调色
    static let xingtuSecondaryAccent = Color(red: 0.6, green: 0.5, blue: 0.9)
    
    /// 星图文本色
    static let xingtuText = Color.white.opacity(0.9)
    
    /// 星图次级文本
    static let xingtuSubtext = Color.white.opacity(0.6)
    
    /// 状态颜色
    static let xingtuSuccess = Color(red: 0.3, green: 0.8, blue: 0.5)
    static let xingtuWarning = Color(red: 0.95, green: 0.7, blue: 0.3)
    static let xingtuError = Color(red: 0.9, green: 0.4, blue: 0.4)
}

// MARK: - 视图修饰器

struct XingtuCardStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding()
            .background(Color.xingtuSecondaryBackground)
            .cornerRadius(12)
            .shadow(color: .black.opacity(0.2), radius: 4, y: 2)
    }
}

extension View {
    func xingtuCard() -> some View {
        modifier(XingtuCardStyle())
    }
}

// MARK: - 发光效果

struct GlowEffect: ViewModifier {
    let color: Color
    let radius: CGFloat
    
    func body(content: Content) -> some View {
        content
            .shadow(color: color.opacity(0.5), radius: radius)
            .shadow(color: color.opacity(0.3), radius: radius * 2)
    }
}

extension View {
    func glow(color: Color = .xingtuAccent, radius: CGFloat = 8) -> some View {
        modifier(GlowEffect(color: color, radius: radius))
    }
}

// MARK: - 渐变背景

struct XingtuGradientBackground: View {
    var body: some View {
        LinearGradient(
            colors: [
                Color.xingtuBackground,
                Color(red: 0.06, green: 0.06, blue: 0.12)
            ],
            startPoint: .top,
            endPoint: .bottom
        )
        .ignoresSafeArea()
    }
}

// MARK: - 加载指示器

struct XingtuLoadingIndicator: View {
    @State private var isAnimating = false
    
    var body: some View {
        Circle()
            .stroke(
                AngularGradient(
                    colors: [.xingtuAccent.opacity(0), .xingtuAccent],
                    center: .center
                ),
                lineWidth: 3
            )
            .frame(width: 40, height: 40)
            .rotationEffect(.degrees(isAnimating ? 360 : 0))
            .onAppear {
                withAnimation(.linear(duration: 1).repeatForever(autoreverses: false)) {
                    isAnimating = true
                }
            }
    }
}

// MARK: - 按钮样式

struct XingtuButtonStyle: ButtonStyle {
    let isProminent: Bool
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                isProminent
                    ? Color.xingtuAccent
                    : Color.xingtuSecondaryBackground
            )
            .foregroundColor(isProminent ? .white : .xingtuText)
            .cornerRadius(8)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
    }
}

extension ButtonStyle where Self == XingtuButtonStyle {
    static var xingtu: XingtuButtonStyle { XingtuButtonStyle(isProminent: false) }
    static var xingtuProminent: XingtuButtonStyle { XingtuButtonStyle(isProminent: true) }
}

// MARK: - 输入框样式

struct XingtuTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .padding(12)
            .background(Color.xingtuSecondaryBackground)
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.xingtuAccent.opacity(0.3), lineWidth: 1)
            )
    }
}

// MARK: - 动画

extension Animation {
    static let xingtuSpring = Animation.spring(response: 0.4, dampingFraction: 0.8)
    static let xingtuEase = Animation.easeInOut(duration: 0.25)
}

// MARK: - 图标扩展

extension Image {
    static func xingtu(_ name: String) -> Image {
        Image(systemName: name)
    }
}
