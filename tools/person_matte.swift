// Person segmentation mattes with Apple Vision (macOS 12+, offline, no installs).
//   swift tools/person_matte.swift <frames_dir> <out_dir>
// Reads every *.png in frames_dir (sorted) and writes a same-size 8-bit grey matte
// (white = person) with the same name to out_dir. One request object is reused across
// frames so Vision's .accurate mode can keep the matte temporally stable.
// Driven by tools/person_matte.py.
import CoreImage
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count == 3 else {
    FileHandle.standardError.write("usage: person_matte.swift <frames_dir> <out_dir>\n".data(using: .utf8)!)
    exit(2)
}
let inDir = URL(fileURLWithPath: args[1])
let outDir = URL(fileURLWithPath: args[2])
try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
let files = try FileManager.default.contentsOfDirectory(atPath: inDir.path).filter { $0.hasSuffix(".png") }.sorted()

let ctx = CIContext()
let grey = CGColorSpaceCreateDeviceGray()
let req = VNGeneratePersonSegmentationRequest()
req.qualityLevel = .accurate
req.outputPixelFormat = kCVPixelFormatType_OneComponent8

for f in files {
    let url = inDir.appendingPathComponent(f)
    guard let src = CIImage(contentsOf: url) else { continue }
    try VNImageRequestHandler(ciImage: src).perform([req])
    var mask = CIImage(color: .black).cropped(to: src.extent)
    if let buf = req.results?.first?.pixelBuffer {
        let m = CIImage(cvPixelBuffer: buf)
        mask = m.transformed(by: CGAffineTransform(scaleX: src.extent.width / m.extent.width,
                                                   y: src.extent.height / m.extent.height))
    }
    try ctx.writePNGRepresentation(of: mask, to: outDir.appendingPathComponent(f), format: .L8, colorSpace: grey)
}
print("mattes: \(files.count) frames → \(outDir.path)")
