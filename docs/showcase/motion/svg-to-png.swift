#!/usr/bin/env swift
// Render the editable architecture SVG to a pixel-sharp PNG with macOS AppKit.
import AppKit
let args = CommandLine.arguments
if args.count != 3 { fputs("Usage: swift svg-to-png.swift input.svg output.png\n", stderr); exit(2) }
guard let image = NSImage(contentsOfFile: args[1]) else { fatalError("Cannot read SVG") }
let width = Int(image.size.width), height = Int(image.size.height)
guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: width, pixelsHigh: height,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
    let context = NSGraphicsContext(bitmapImageRep: bitmap) else { fatalError("Cannot make bitmap") }
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
image.draw(in: NSRect(x: 0, y: 0, width: width, height: height))
context.flushGraphics()
NSGraphicsContext.restoreGraphicsState()
guard let png = bitmap.representation(using: .png, properties: [:]) else { fatalError("PNG encoding failed") }
try png.write(to: URL(fileURLWithPath: args[2]))
