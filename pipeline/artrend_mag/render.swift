// ARTREND media renderer, built with the system toolchain only (AVFoundation, CoreGraphics, CoreText); no third-party packages.
//   artrend_render shorts spec.json   beats of image + caption + optional narration -> vertical H.264/AAC mp4
//   artrend_render cards  spec.json   slides of image + text -> card-news PNGs (one file per slide)
import AVFoundation
import AppKit
import CoreImage
import CoreText
import Foundation

func fail(_ msg: String) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(1)
}

// MARK: - shared drawing

let space = CGColorSpaceCreateDeviceRGB()
let white = CGColor(red: 1, green: 1, blue: 1, alpha: 1)
let black = CGColor(red: 0, green: 0, blue: 0, alpha: 1)
let ink = CGColor(red: 0.07, green: 0.07, blue: 0.07, alpha: 1)
let grey = CGColor(red: 0.38, green: 0.36, blue: 0.33, alpha: 1)
let red = CGColor(red: 0.784, green: 0.216, blue: 0.122, alpha: 1)
let paper = CGColor(red: 0.957, green: 0.937, blue: 0.902, alpha: 1)
let navy = CGColor(red: 0.12, green: 0.18, blue: 0.29, alpha: 1)

func loadImage(_ path: String?) -> CGImage? {
    guard let p = path, let img = NSImage(contentsOfFile: p) else { return nil }
    var r = CGRect(origin: .zero, size: img.size)
    return img.cgImage(forProposedRect: &r, context: nil, hints: nil)
}

func font(_ size: CGFloat, _ weight: String = "Heavy") -> CTFont {
    CTFontCreateWithName("AppleSDGothicNeo-\(weight)" as CFString, size, nil)
}

func textWidth(_ s: String, _ f: CTFont) -> CGFloat {
    let a = NSAttributedString(string: s, attributes: [NSAttributedString.Key(kCTFontAttributeName as String): f])
    return CGFloat(CTLineGetTypographicBounds(CTLineCreateWithAttributedString(a), nil, nil, nil))
}

// Wrap text to a width, preferring spaces; a word wider than the line is split by characters.
func wrap(_ text: String, _ f: CTFont, _ maxW: CGFloat) -> [String] {
    var out: [String] = []
    var cur = ""
    for word in text.split(separator: " ", omittingEmptySubsequences: false).map(String.init) {
        let cand = cur.isEmpty ? word : cur + " " + word
        if textWidth(cand, f) <= maxW { cur = cand; continue }
        if !cur.isEmpty && textWidth(word, f) <= maxW { out.append(cur); cur = word; continue }
        var piece = cur.isEmpty ? "" : cur + " "
        for ch in word {
            if textWidth(piece + String(ch), f) > maxW { out.append(piece.trimmingCharacters(in: .whitespaces)); piece = "" }
            piece.append(ch)
        }
        cur = piece
    }
    if !cur.isEmpty { out.append(cur) }
    return out
}

// At most `maxLines` lines; the last one gets an ellipsis when the text was cut.
func clamp(_ text: String, _ f: CTFont, _ maxW: CGFloat, _ maxLines: Int) -> [String] {
    var lines = wrap(text, f, maxW)
    if lines.count > maxLines {
        lines = Array(lines.prefix(maxLines))
        var last = lines[maxLines - 1]
        while !last.isEmpty && textWidth(last + "…", f) > maxW { last.removeLast() }
        lines[maxLines - 1] = last + "…"
    }
    return lines
}

enum Align { case left, center }

// Draw one line; `y` is the baseline in CoreGraphics coordinates (origin bottom-left).
func drawLine(_ ctx: CGContext, _ s: String, _ f: CTFont, x: CGFloat, y: CGFloat, align: Align = .left, fill: CGColor,
              stroke: CGColor? = nil, strokeW: CGFloat = 0) {
    let key = NSAttributedString.Key(kCTFontAttributeName as String)
    let fg = NSAttributedString.Key(kCTForegroundColorAttributeName as String)
    let w = textWidth(s, f)
    let origin = CGPoint(x: align == .center ? x - w / 2 : x, y: y)
    if let st = stroke {
        ctx.saveGState()
        ctx.setTextDrawingMode(.stroke)
        ctx.setLineWidth(strokeW)
        ctx.setLineJoin(.round)
        let sa = NSAttributedString(string: s, attributes: [key: f, fg: st, NSAttributedString.Key(kCTStrokeColorAttributeName as String): st,
                                                            NSAttributedString.Key(kCTStrokeWidthAttributeName as String): strokeW])
        ctx.textPosition = origin
        CTLineDraw(CTLineCreateWithAttributedString(sa), ctx)
        ctx.restoreGState()
    }
    ctx.setTextDrawingMode(.fill)
    ctx.textPosition = origin
    CTLineDraw(CTLineCreateWithAttributedString(NSAttributedString(string: s, attributes: [key: f, fg: fill])), ctx)
}

// Cover-fit an image into a rect (with optional zoom and horizontal drift for motion).
func drawCover(_ ctx: CGContext, _ img: CGImage, in rect: CGRect, zoom: CGFloat = 1, drift: CGFloat = 0) {
    let iw = CGFloat(img.width), ih = CGFloat(img.height)
    let s = max(rect.width / iw, rect.height / ih) * zoom
    let dw = iw * s, dh = ih * s
    let x = rect.minX + (rect.width - dw) / 2 + drift * max(0, (dw - rect.width) / 2)
    let y = rect.minY + (rect.height - dh) / 2
    ctx.saveGState()
    ctx.clip(to: rect)
    ctx.interpolationQuality = .high
    ctx.draw(img, in: CGRect(x: x, y: y, width: dw, height: dh))
    ctx.restoreGState()
}

func bitmap(_ w: Int, _ h: Int) -> CGContext {
    CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0, space: space,
              bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
}

func writePNG(_ ctx: CGContext, _ path: String) {
    let rep = NSBitmapImageRep(cgImage: ctx.makeImage()!)
    guard let png = rep.representation(using: .png, properties: [:]) else { fail("png encode") }
    do { try png.write(to: URL(fileURLWithPath: path)) } catch { fail("write \(path): \(error)") }
}

// MARK: - shorts

// One beat = one screen of the video. Layouts:
//   hook  full-bleed image, big serif title          info  image panel + label/value rows
//   list  image panel + numbered item                fact  image panel + one big figure
//   text  image panel (or type only) + bullet lines  end   brand card
struct Beat: Decodable {
    let layout: String
    let image: String?
    let kicker: String?
    let title: String
    let sub: [String]?
    let rows: [[String]]?
    let big: String?
    let bigLabel: String?
    let num: String?
    let credit: String?
    let duration: Double
    let audio: String?
}

struct ShortsSpec: Decodable {
    let out: String
    let width: Int
    let height: Int
    let fps: Int
    let brand: String
    let date: String
    let music: String?
    let musicVolume: Double?
    let beats: [Beat]
}

func serif(_ size: CGFloat) -> CTFont { CTFontCreateWithName("NanumMyeongjoExtraBold" as CFString, size, nil) }

func ease(_ x: Double) -> Double { let c = max(0, min(1, x)); return 1 - pow(1 - c, 3) }

func alpha(_ c: CGColor, _ a: CGFloat) -> CGColor { c.copy(alpha: a) ?? c }

// A small, heavily blurred copy used as the backdrop behind images that do not fill the frame.
func blurred(_ img: CGImage) -> CGImage? {
    let s = 320 / CGFloat(img.width)
    let small = CIImage(cgImage: img).transformed(by: CGAffineTransform(scaleX: s, y: s))
    guard let f = CIFilter(name: "CIGaussianBlur") else { return nil }
    f.setValue(small.clampedToExtent(), forKey: kCIInputImageKey)
    f.setValue(16, forKey: kCIInputRadiusKey)
    guard let out = f.outputImage?.cropped(to: small.extent) else { return nil }
    return CIContext().createCGImage(out, from: small.extent)
}

func drawFit(_ ctx: CGContext, _ img: CGImage, in rect: CGRect, zoom: CGFloat = 1) {
    let iw = CGFloat(img.width), ih = CGFloat(img.height)
    let s = min(rect.width / iw, rect.height / ih) * zoom
    let dw = iw * s, dh = ih * s
    ctx.saveGState()
    ctx.clip(to: rect)
    ctx.interpolationQuality = .high
    ctx.draw(img, in: CGRect(x: rect.midX - dw / 2, y: rect.midY - dh / 2, width: dw, height: dh))
    ctx.restoreGState()
}

func vgradient(_ ctx: CGContext, from y0: CGFloat, _ a0: CGFloat, to y1: CGFloat, _ a1: CGFloat, width: CGFloat, color: CGColor = black) {
    let g = CGGradient(colorsSpace: space, colors: [alpha(color, a0), alpha(color, a1)] as CFArray, locations: [0, 1])!
    ctx.saveGState()
    ctx.clip(to: CGRect(x: 0, y: min(y0, y1), width: width, height: abs(y1 - y0)))
    ctx.drawLinearGradient(g, start: CGPoint(x: 0, y: y0), end: CGPoint(x: 0, y: y1), options: [])
    ctx.restoreGState()
}

func renderShorts(_ spec: ShortsSpec) {
    let W = spec.width, H = spec.height, FPS = Int32(spec.fps)
    let Wf = CGFloat(W), Hf = CGFloat(H)
    let M: CGFloat = 84
    let textW = Wf - M - 150  // right edge stays clear of the Reels/Shorts side buttons
    let floorY: CGFloat = 300  // bottom captions/UI of the apps cover what is below
    let panelY = Hf * 0.42
    let images = spec.beats.map { loadImage($0.image) }
    let backs = images.map { $0.flatMap(blurred) }
    let totalD = spec.beats.reduce(0) { $0 + $1.duration }
    let ink2 = CGColor(red: 0.055, green: 0.055, blue: 0.06, alpha: 1)
    let soft = CGColor(red: 0.86, green: 0.84, blue: 0.80, alpha: 1)

    // staggered entrance: element k fades in and rises a little
    func show(_ ctx: CGContext, _ t: Double, _ k: Int, _ draw: (CGFloat) -> Void) {
        let a = ease((t - 0.1 - 0.13 * Double(k)) / 0.45)
        ctx.saveGState()
        ctx.setAlpha(CGFloat(a))
        draw(CGFloat(1 - a) * 34)
        ctx.restoreGState()
    }

    func picture(_ ctx: CGContext, _ i: Int, _ rect: CGRect, _ p: Double) {
        guard let img = images[i] else { return }
        let zoom = CGFloat(1.03 + 0.09 * p)
        let drift = (i % 2 == 0 ? 1 : -1) * CGFloat(p - 0.5) * 0.6
        let coverScale = max(rect.width / CGFloat(img.width), rect.height / CGFloat(img.height))
        if coverScale > 1.7 {
            // a small image would be blown up into mush: show it whole over its own blurred colours
            if let b = backs[i] { drawCover(ctx, b, in: rect, zoom: 1.1) }
            ctx.setFillColor(alpha(black, 0.25))
            ctx.fill(rect)
            drawFit(ctx, img, in: rect.insetBy(dx: 60, dy: 70), zoom: zoom)
        } else {
            drawCover(ctx, img, in: rect, zoom: zoom, drift: drift)
        }
    }

    func titleBlock(_ ctx: CGContext, _ b: Beat, _ t: Double, top: CGFloat, size: CGFloat, maxLines: Int, k0: Int) -> CGFloat {
        var y = top
        var k = k0
        if let kk = b.kicker, !kk.isEmpty {
            let kf = font(28, "Bold")
            show(ctx, t, k) { dy in
                ctx.setFillColor(red)
                ctx.fill(CGRect(x: M, y: y + 9 - dy, width: 36, height: 5))
                drawLine(ctx, kk, kf, x: M + 52, y: y - dy, fill: red)
            }
            y -= 76
            k += 1
        }
        var f = serif(size)
        var lines = clamp(b.title, f, textW, maxLines)
        if lines.count == maxLines && maxLines > 2 {
            f = serif(size * 0.84)
            lines = clamp(b.title, f, textW, maxLines)
        }
        let lh = CTFontGetSize(f) * 1.3
        let yy = y
        show(ctx, t, k) { dy in
            var ly = yy - CTFontGetSize(f) * 0.72
            for l in lines { drawLine(ctx, l, f, x: M, y: ly - dy, fill: white); ly -= lh }
        }
        return y - CTFontGetSize(f) * 0.72 - CGFloat(lines.count - 1) * lh - 44
    }

    func details(_ ctx: CGContext, _ b: Beat, _ t: Double, top: CGFloat, k0: Int) {
        var y = top
        var k = k0
        if let big = b.big {
            let bf = serif(150)
            show(ctx, t, k) { dy in
                drawLine(ctx, big, bf, x: M, y: y - 120 - dy, fill: red)
                if let l = b.bigLabel { drawLine(ctx, l, font(36, "Medium"), x: M, y: y - 190 - dy, fill: soft) }
            }
            y -= 250
            k += 1
        }
        if let rows = b.rows {
            for r in rows where r.count == 2 {
                let vf = font(36, "Medium")
                let vals = clamp(r[1], vf, textW - 170, 2)
                let h = CGFloat(vals.count) * 48 + 34
                if y - h < floorY { break }
                let yy = y
                show(ctx, t, k) { dy in
                    ctx.setFillColor(alpha(white, 0.22))
                    ctx.fill(CGRect(x: M, y: yy - dy, width: textW, height: 1.5))
                    drawLine(ctx, r[0], font(26, "Bold"), x: M, y: yy - 52 - dy, fill: alpha(white, 0.55))
                    var vy = yy - 52
                    for v in vals { drawLine(ctx, v, vf, x: M + 170, y: vy - dy, fill: white); vy -= 48 }
                }
                y -= h
                k += 1
            }
        }
        if let sub = b.sub {
            let sf = font(37, "Medium")
            for s in sub.prefix(4) {
                let ls = clamp(s, sf, textW - 34, 3)
                let h = CGFloat(ls.count) * 54 + 22
                if y - h < floorY - 20 { break }
                let yy = y
                show(ctx, t, k) { dy in
                    if sub.count > 1 {
                        ctx.setFillColor(red)
                        ctx.fill(CGRect(x: M, y: yy - 36 - dy, width: 10, height: 10))
                    }
                    var ly = yy - 50
                    for l in ls { drawLine(ctx, l, sf, x: M + (sub.count > 1 ? 30 : 0), y: ly - dy, fill: soft); ly -= 54 }
                }
                y -= h
                k += 1
            }
        }
    }

    func drawBeat(_ ctx: CGContext, _ i: Int, _ t: Double) {
        let b = spec.beats[i]
        let p = max(0, min(1, t / b.duration))
        let full = CGRect(x: 0, y: 0, width: Wf, height: Hf)
        ctx.setFillColor(ink2)
        ctx.fill(full)
        switch b.layout {
        case "hook":
            if images[i] != nil {
                picture(ctx, i, full, p)
                vgradient(ctx, from: 0, 0.94, to: Hf * 0.66, 0, width: Wf)
            }
            // measure bottom-up so the block always sits just above the app UI
            var f = serif(118)
            var lines = clamp(b.title, f, textW, 3)
            if lines.count > 2 { f = serif(96); lines = clamp(b.title, f, textW, 3) }
            let lh = CTFontGetSize(f) * 1.22
            let subs = (b.sub ?? []).prefix(2).flatMap { clamp($0, font(42, "Medium"), textW, 2) }
            var y = floorY + 40 + CGFloat(subs.count) * 60 + CGFloat(lines.count) * lh + 96
            if let kk = b.kicker {
                let kf = font(30, "Bold")
                show(ctx, t, 0) { dy in
                    ctx.setFillColor(red)
                    ctx.fill(CGRect(x: M, y: y - 14 - dy, width: textWidth(kk, kf) + 40, height: 58))
                    drawLine(ctx, kk, kf, x: M + 20, y: y + 3 - dy, fill: white)
                }
            }
            y -= 50 + CTFontGetSize(f) * 0.8
            let ty = y
            show(ctx, t, 1) { dy in
                var ly = ty
                for l in lines { drawLine(ctx, l, f, x: M, y: ly - dy, fill: white); ly -= lh }
            }
            y -= CGFloat(lines.count - 1) * lh + 76
            let sy = y
            show(ctx, t, 2) { dy in
                var ly = sy
                for s in subs { drawLine(ctx, s, font(42, "Medium"), x: M, y: ly - dy, fill: soft); ly -= 60 }
            }
        case "end":
            if let bk = backs[i] {
                drawCover(ctx, bk, in: full, zoom: 1.2)
                ctx.setFillColor(alpha(ink2, 0.82))
                ctx.fill(full)
            }
            show(ctx, t, 0) { dy in
                drawLine(ctx, spec.brand, serif(150), x: Wf / 2, y: Hf * 0.55 - dy, align: .center, fill: white)
                ctx.setFillColor(red)
                ctx.fill(CGRect(x: Wf / 2 - 45, y: Hf * 0.55 - 70 - dy, width: 90, height: 6))
            }
            show(ctx, t, 1) { dy in
                drawLine(ctx, b.title, font(46, "Bold"), x: Wf / 2, y: Hf * 0.55 - 170 - dy, align: .center, fill: white)
                var y = Hf * 0.55 - 250
                for s in b.sub ?? [] {
                    drawLine(ctx, s, font(32, "Medium"), x: Wf / 2, y: y - dy, align: .center, fill: alpha(white, 0.7)); y -= 52
                }
            }
        default:
            let hasImg = images[i] != nil
            var top: CGFloat
            if hasImg {
                if let bk = backs[i] { drawCover(ctx, bk, in: full, zoom: 1.15) }
                ctx.setFillColor(alpha(ink2, 0.9))
                ctx.fill(CGRect(x: 0, y: 0, width: Wf, height: panelY))
                picture(ctx, i, CGRect(x: 0, y: panelY, width: Wf, height: Hf - panelY), p)
                vgradient(ctx, from: panelY, 1, to: panelY + 330, 0, width: Wf, color: ink2)
                top = panelY + 95
            } else {
                // type-only screen: a big faint numeral or brand mark carries the composition
                let mark = b.num ?? "A"
                drawLine(ctx, mark, serif(520), x: Wf - 60 - textWidth(mark, serif(520)), y: Hf - 760, fill: alpha(white, 0.06))
                ctx.setFillColor(red)
                ctx.fill(CGRect(x: M, y: Hf * 0.62 + 40, width: 120, height: 8))
                top = Hf * 0.62
            }
            var k = 0
            if let n = b.num, hasImg {
                let nf = serif(120)
                let yy = top
                show(ctx, t, 0) { dy in drawLine(ctx, n, nf, x: M, y: yy - 96 - dy, fill: red) }
                top -= 135
                k = 1
            }
            let size: CGFloat = b.layout == "list" || b.layout == "info" ? 66 : 70
            let after = titleBlock(ctx, b, t, top: top, size: size, maxLines: 3, k0: k)
            details(ctx, b, t, top: after, k0: k + 2)
        }
    }

    func frame(_ ctx: CGContext, beat i: Int, t: Double) {
        drawBeat(ctx, i, t)
        let fade = 0.35
        if i > 0 && t < fade {
            ctx.saveGState()
            ctx.setAlpha(CGFloat(1 - t / fade))
            ctx.beginTransparencyLayer(auxiliaryInfo: nil)
            drawBeat(ctx, i - 1, spec.beats[i - 1].duration)
            ctx.endTransparencyLayer()
            ctx.restoreGState()
        }
        let b = spec.beats[i]
        if b.layout != "end" {
            vgradient(ctx, from: Hf, 0.55, to: Hf - 300, 0, width: Wf)
            drawLine(ctx, spec.brand, serif(42), x: M, y: Hf - 140, fill: white)
            let df = font(28, "Medium")
            drawLine(ctx, spec.date, df, x: Wf - M - textWidth(spec.date, df), y: Hf - 136, fill: alpha(white, 0.85))
            if let c = b.credit, images[i] != nil {
                let cf = font(22, "Medium")
                drawLine(ctx, c, cf, x: Wf - M - textWidth(c, cf), y: Hf - 180, fill: alpha(white, 0.7))
            }
        }
        // story-style segmented progress
        let n = spec.beats.count
        let gap: CGFloat = 8, x0: CGFloat = 40
        let segW = (Wf - 2 * x0 - gap * CGFloat(n - 1)) / CGFloat(n)
        for j in 0..<n {
            let x = x0 + CGFloat(j) * (segW + gap)
            ctx.setFillColor(alpha(white, 0.28))
            ctx.fill(CGRect(x: x, y: Hf - 62, width: segW, height: 6))
            let f: CGFloat = j < i ? 1 : (j == i ? CGFloat(min(1, t / spec.beats[j].duration)) : 0)
            ctx.setFillColor(white)
            ctx.fill(CGRect(x: x, y: Hf - 62, width: segW * f, height: 6))
        }
        _ = totalD
    }

    // 1) video track
    let tmpVideo = URL(fileURLWithPath: spec.out + ".video.mov")
    try? FileManager.default.removeItem(at: tmpVideo)
    let writer = try! AVAssetWriter(outputURL: tmpVideo, fileType: .mov)
    let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
        AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: W, AVVideoHeightKey: H,
        AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 8_000_000, AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel],
    ])
    let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB, kCVPixelBufferWidthKey as String: W,
        kCVPixelBufferHeightKey as String: H,
    ])
    writer.add(input)
    writer.startWriting()
    writer.startSession(atSourceTime: .zero)
    var n: Int64 = 0
    for (i, b) in spec.beats.enumerated() {
        for k in 0..<Int(b.duration * Double(FPS)) {
            while !input.isReadyForMoreMediaData { usleep(2000) }
            var pb: CVPixelBuffer?
            CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &pb)
            guard let buf = pb else { fail("pixel buffer") }
            CVPixelBufferLockBaseAddress(buf, [])
            let ctx = CGContext(data: CVPixelBufferGetBaseAddress(buf), width: W, height: H, bitsPerComponent: 8,
                                bytesPerRow: CVPixelBufferGetBytesPerRow(buf), space: space, bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue)!
            frame(ctx, beat: i, t: Double(k) / Double(FPS))
            CVPixelBufferUnlockBaseAddress(buf, [])
            adaptor.append(buf, withPresentationTime: CMTime(value: n, timescale: FPS))
            n += 1
        }
    }
    input.markAsFinished()
    let sem = DispatchSemaphore(value: 0)
    writer.finishWriting { sem.signal() }
    sem.wait()
    if writer.status != .completed { fail("video write failed: \(String(describing: writer.error))") }

    // 2) mux narration (each beat's audio at its start time) + the music bed -> mp4
    let comp = AVMutableComposition()
    let vAsset = AVURLAsset(url: tmpVideo)
    let total = vAsset.duration
    let cv = comp.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid)!
    try! cv.insertTimeRange(CMTimeRange(start: .zero, duration: total), of: vAsset.tracks(withMediaType: .video)[0], at: .zero)
    let ca = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)!
    var start = 0.0
    var hasAudio = false
    for b in spec.beats {
        if let a = b.audio, FileManager.default.fileExists(atPath: a) {
            let aa = AVURLAsset(url: URL(fileURLWithPath: a))
            if let at = aa.tracks(withMediaType: .audio).first {
                let dur = CMTimeMinimum(aa.duration, CMTime(seconds: b.duration, preferredTimescale: 600))
                try? ca.insertTimeRange(CMTimeRange(start: .zero, duration: dur), of: at, at: CMTime(seconds: start + 0.2, preferredTimescale: 600))
                hasAudio = true
            }
        }
        start += b.duration
    }
    if !hasAudio { comp.removeTrack(ca) }
    var mix: AVMutableAudioMix?
    if let m = spec.music, FileManager.default.fileExists(atPath: m) {
        let ma = AVURLAsset(url: URL(fileURLWithPath: m))
        if let mt = ma.tracks(withMediaType: .audio).first,
           let cm = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) {
            try? cm.insertTimeRange(CMTimeRange(start: .zero, duration: CMTimeMinimum(ma.duration, total)), of: mt, at: .zero)
            let prm = AVMutableAudioMixInputParameters(track: cm)
            let vol = Float(spec.musicVolume ?? 0.2)
            prm.setVolume(vol, at: .zero)
            let fadeStart = CMTimeSubtract(total, CMTime(seconds: 1.6, preferredTimescale: 600))
            prm.setVolumeRamp(fromStartVolume: vol, toEndVolume: 0, timeRange: CMTimeRange(start: fadeStart, duration: CMTime(seconds: 1.6, preferredTimescale: 600)))
            let am = AVMutableAudioMix()
            am.inputParameters = [prm]
            mix = am
        }
    }
    let outURL = URL(fileURLWithPath: spec.out)
    try? FileManager.default.removeItem(at: outURL)
    guard let ex = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetHighestQuality) else { fail("export session") }
    ex.outputURL = outURL
    ex.outputFileType = .mp4
    ex.shouldOptimizeForNetworkUse = true
    ex.audioMix = mix
    let sem2 = DispatchSemaphore(value: 0)
    ex.exportAsynchronously { sem2.signal() }
    sem2.wait()
    try? FileManager.default.removeItem(at: tmpVideo)
    if ex.status != .completed { fail("export failed: \(String(describing: ex.error))") }
    print(spec.out)
}

// MARK: - card news

struct Slide: Decodable {
    let kind: String  // "cover" | "item" | "end"
    let image: String?
    let kicker: String?
    let title: String
    let body: [String]?
    let chips: [String]?
    let foot: String?
    let num: String?
}

struct CardsSpec: Decodable {
    let outDir: String
    let width: Int
    let height: Int
    let brand: String
    let date: String
    let slides: [Slide]
}

func renderCards(_ spec: CardsSpec) {
    let W = CGFloat(spec.width), H = CGFloat(spec.height), M: CGFloat = 84
    try? FileManager.default.createDirectory(atPath: spec.outDir, withIntermediateDirectories: true)
    let total = spec.slides.count
    for (i, s) in spec.slides.enumerated() {
        let ctx = bitmap(spec.width, spec.height)
        let full = CGRect(x: 0, y: 0, width: W, height: H)
        let img = loadImage(s.image)
        let page = "\(i + 1) / \(total)"
        switch s.kind {
        case "cover":
            ctx.setFillColor(ink)
            ctx.fill(full)
            if let im = img {
                drawCover(ctx, im, in: full)
                // bottom-heavy gradient for the headline
                let g = CGGradient(colorsSpace: space, colors: [CGColor(red: 0, green: 0, blue: 0, alpha: 0.05), CGColor(red: 0, green: 0, blue: 0, alpha: 0.85)] as CFArray,
                                   locations: [0, 1])!
                ctx.drawLinearGradient(g, start: CGPoint(x: 0, y: H * 0.75), end: CGPoint(x: 0, y: 0), options: [])
            }
            drawLine(ctx, spec.brand, font(54), x: M, y: H - 120, fill: white)
            drawLine(ctx, spec.date, font(32, "Medium"), x: W - M - textWidth(spec.date, font(32, "Medium")), y: H - 116, fill: white)
            var y: CGFloat = 520
            if let k = s.kicker {
                ctx.setFillColor(red)
                let kf = font(32, "Bold")
                ctx.fill(CGRect(x: M, y: y + 150, width: textWidth(k, kf) + 36, height: 56))
                drawLine(ctx, k, kf, x: M + 18, y: y + 166, fill: white)
            }
            let tf = font(88)
            let lines = clamp(s.title, tf, W - 2 * M, 3)
            y = 560 - CGFloat(lines.count - 1) * 0  // anchor
            var ty: CGFloat = 600
            for l in lines { drawLine(ctx, l, tf, x: M, y: ty, fill: white); ty -= 106 }
            var by = ty - 10
            for b in (s.body ?? []).prefix(2) {
                for l in clamp(b, font(38, "Medium"), W - 2 * M, 2) { drawLine(ctx, l, font(38, "Medium"), x: M, y: by, fill: paper); by -= 52 }
            }
            drawLine(ctx, "옆으로 넘겨 보기  →", font(30, "Bold"), x: W - M - textWidth("옆으로 넘겨 보기  →", font(30, "Bold")), y: 70, fill: white)
            if let f = s.foot { drawLine(ctx, f, font(22, "Medium"), x: M, y: 70, fill: paper) }
        case "end":
            ctx.setFillColor(red)
            ctx.fill(full)
            drawLine(ctx, spec.brand, font(120), x: W / 2, y: H / 2 + 120, align: .center, fill: white)
            drawLine(ctx, s.title, font(46, "Bold"), x: W / 2, y: H / 2 + 20, align: .center, fill: white)
            if let chips = s.chips, !chips.isEmpty {
                let cf = font(32, "Bold")
                var rows: [[String]] = [[]]
                var rw: CGFloat = 0
                for c in chips.prefix(8) {
                    let w = textWidth("#" + c, cf) + 44
                    if rw + w > W - 2 * M { rows.append([]); rw = 0 }
                    rows[rows.count - 1].append(c)
                    rw += w + 14
                }
                var cy = H / 2 - 110
                for r in rows {
                    let widths = r.map { textWidth("#" + $0, cf) + 44 }
                    var cx = (W - (widths.reduce(0, +) + CGFloat(max(0, r.count - 1)) * 14)) / 2
                    for (c, w) in zip(r, widths) {
                        ctx.setStrokeColor(white)
                        ctx.setLineWidth(3)
                        ctx.stroke(CGRect(x: cx, y: cy - 18, width: w, height: 62))
                        drawLine(ctx, "#" + c, cf, x: cx + 22, y: cy, fill: white)
                        cx += w + 14
                    }
                    cy -= 84
                }
            }
            for (j, l) in (s.body ?? []).enumerated() {
                drawLine(ctx, l, font(28, "Medium"), x: W / 2, y: 150 - CGFloat(j) * 44, align: .center, fill: white)
            }
        default:  // item
            ctx.setFillColor(paper)
            ctx.fill(full)
            // text-only slides get a short colour band instead of an empty picture frame
            let imgH: CGFloat = img != nil ? 610 : 230
            let imgRect = CGRect(x: 0, y: H - imgH, width: W, height: imgH)
            if let im = img {
                drawCover(ctx, im, in: imgRect)
            } else {
                ctx.setFillColor(i % 2 == 0 ? navy : ink)
                ctx.fill(imgRect)
                drawLine(ctx, s.num ?? "", font(170), x: W - M - textWidth(s.num ?? "", font(170)), y: H - imgH + 30, fill: CGColor(red: 1, green: 1, blue: 1, alpha: 0.14))
            }
            drawLine(ctx, spec.brand, font(34), x: M, y: H - 80, fill: white, stroke: black, strokeW: 4)
            var y = H - imgH - 92
            if let n = s.num { drawLine(ctx, n, font(64), x: M, y: y - 6, fill: red) }
            if let k = s.kicker {
                let kf = font(28, "Bold")
                let kx = M + (s.num != nil ? 110 : 0)
                ctx.setStrokeColor(ink)
                ctx.setLineWidth(2.5)
                ctx.stroke(CGRect(x: kx, y: y - 4, width: textWidth(k, kf) + 28, height: 48))
                drawLine(ctx, k, kf, x: kx + 14, y: y + 8, fill: ink)
            }
            y -= 92
            let tf = font(img != nil ? 58 : 70)
            for l in clamp(s.title, tf, W - 2 * M, img != nil ? 3 : 4) { drawLine(ctx, l, tf, x: M, y: y, fill: ink); y -= img != nil ? 72 : 86 }
            y -= 14
            ctx.setFillColor(red)
            ctx.fill(CGRect(x: M, y: y + 20, width: 64, height: 6))
            y -= 34
            let bf = font(34, "Medium")
            for b in (s.body ?? []).prefix(img != nil ? 4 : 6) {
                let ls = clamp(b, bf, W - 2 * M - 34, 2)
                if y - CGFloat(ls.count) * 48 < 120 { break }
                ctx.setFillColor(red)
                ctx.fill(CGRect(x: M, y: y + 10, width: 12, height: 12))
                for l in ls { drawLine(ctx, l, bf, x: M + 34, y: y, fill: ink); y -= 48 }
                y -= 12
            }
            if let f = s.foot { drawLine(ctx, f, font(22, "Medium"), x: M, y: 64, fill: grey) }
        }
        if s.kind != "end" {
            let pf = font(26, "Bold")
            drawLine(ctx, page, pf, x: W - M - textWidth(page, pf), y: s.kind == "cover" ? H - 170 : 64, fill: s.kind == "cover" ? white : grey)
        }
        let path = (spec.outDir as NSString).appendingPathComponent(String(format: "%02d.png", i + 1))
        writePNG(ctx, path)
        print(path)
    }
}

// MARK: - main

let args = CommandLine.arguments
guard args.count == 3, let data = FileManager.default.contents(atPath: args[2]) else { fail("usage: artrend_render shorts|cards spec.json") }
do {
    switch args[1] {
    case "shorts": renderShorts(try JSONDecoder().decode(ShortsSpec.self, from: data))
    case "cards": renderCards(try JSONDecoder().decode(CardsSpec.self, from: data))
    default: fail("unknown mode \(args[1])")
    }
} catch {
    fail("bad spec: \(error)")
}
