import AppKit
import Darwin

let args = CommandLine.arguments
let text = args[1]
let size = CGFloat(Double(args[2])!)
let output = args[3]
let attributes: [NSAttributedString.Key: Any] = [
    .font: NSFont(name: "Devanagari Sangam MN", size: size) ?? NSFont.systemFont(ofSize: size),
    .foregroundColor: NSColor.white
]
let string = NSAttributedString(string: text, attributes: attributes)
let bounds = string.size()
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(ceil(bounds.width)) + 12,
    pixelsHigh: Int(ceil(bounds.height)) + 12, bitsPerSample: 8, samplesPerPixel: 4,
    hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
string.draw(at: NSPoint(x: 6, y: 6))
NSGraphicsContext.restoreGraphicsState()
try bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: output))
exit(0)
