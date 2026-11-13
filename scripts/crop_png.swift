import AppKit

let args = CommandLine.arguments
if args.count != 5 { fatalError("Usage: crop_png.swift input.png output.png width height") }
guard let width = Int(args[3]), let height = Int(args[4]), width > 0, height > 0,
      let data = NSData(contentsOfFile: args[1]),
      let bitmap = NSBitmapImageRep(data: data as Data),
      let image = bitmap.cgImage,
      let cropped = image.cropping(to: CGRect(x: 0, y: 0, width: width, height: height))
else { fatalError("Cannot crop input PNG") }
let output = NSBitmapImageRep(cgImage: cropped)
guard let png = output.representation(using: .png, properties: [:]) else { fatalError("Cannot encode PNG") }
try png.write(to: URL(fileURLWithPath: args[2]))
