import AppKit
import Foundation

let args = CommandLine.arguments
if args.count < 7 {
    fputs("usage: shape_text TEXT SIZE MAX_WIDTH MAX_HEIGHT ALIGN OUTPUT\n", stderr)
    exit(2)
}
let text = args[1]
let size = CGFloat(Double(args[2]) ?? 0)
let maxWidth = CGFloat(Double(args[3]) ?? 0)
let maxHeight = CGFloat(Double(args[4]) ?? 0)
let alignName = args[5]
let output = args[6]
guard size > 0, maxWidth > 0, maxHeight > 0 else {
    fputs("Invalid text box\n", stderr)
    exit(2)
}
guard let font = NSFont(name: "Devanagari Sangam MN", size: size) else {
    fputs("Devanagari Sangam MN is not installed\n", stderr)
    exit(2)
}
let style = NSMutableParagraphStyle()
style.lineBreakMode = .byWordWrapping
style.alignment = alignName == "left" ? .left : .center
let attributes: [NSAttributedString.Key: Any] = [
    .font: font,
    .foregroundColor: NSColor.white,
    .paragraphStyle: style,
]
let string = NSAttributedString(string: text, attributes: attributes)
let bounds = string.boundingRect(
    with: NSSize(width: maxWidth, height: 10000),
    options: [.usesLineFragmentOrigin, .usesFontLeading]
)
if bounds.height > maxHeight + 0.5 {
    fputs("Text exceeds the measured box (\(Int(ceil(bounds.height))) > \(Int(maxHeight)))\n", stderr)
    exit(3)
}
let width = Int(ceil(maxWidth)) + 8
let height = max(1, Int(ceil(bounds.height)) + 8)
guard let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: width,
    pixelsHigh: height,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
) else {
    fputs("Could not allocate text bitmap\n", stderr)
    exit(2)
}
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
string.draw(
    with: NSRect(x: 4, y: 4, width: maxWidth, height: bounds.height + 2),
    options: [.usesLineFragmentOrigin, .usesFontLeading]
)
NSGraphicsContext.restoreGraphicsState()
guard let data = bitmap.representation(using: .png, properties: [:]) else {
    fputs("Could not encode text\n", stderr)
    exit(2)
}
do {
    try data.write(to: URL(fileURLWithPath: output))
} catch {
    fputs("Could not write text\n", stderr)
    exit(2)
}
print("\(width) \(height)")
exit(0)
