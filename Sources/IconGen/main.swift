import CoreGraphics
import Foundation
import ImageIO

// Erzeugt das App-Icon als vollständiges .iconset.
// Rein CoreGraphics + ImageIO — keine Abhängigkeit über die Command Line Tools
// hinaus, damit `./build.sh` auf jedem Mac ohne Homebrew durchläuft.
//
// Aufruf: IconGen <ausgabe-verzeichnis.iconset>

// MARK: - Entwurf
//
// Alle Maße in Entwurfseinheiten auf einer 1024er-Fläche, beim Rendern skaliert.
//
// Motiv: drei aufsteigende Balken (Verbrauchsstatistik) plus ein Funke
// (Claude) auf warmem Verlauf. Bei 16 und 32 px werden die Balken zu dünn,
// um lesbar zu bleiben — dort nur der große Funke, passend zum Symbol in
// der Menüleiste.

private enum Design {
    static let canvas: CGFloat = 1024

    /// Rand um den Icon-Körper, wie in Apples Icon-Raster für macOS.
    static let bodyInset: CGFloat = 96
    /// Exponent der Superellipse — ergibt die typische „Squircle"-Form.
    static let squircleExponent: CGFloat = 4.6

    // Balken. Die Position ist bewusst fest gesetzt und nicht zentriert:
    // Balken und Funke bilden zusammen die Komposition, und die wird als
    // Ganzes ausgemittelt.
    static let barStartX: CGFloat = 290
    static let barWidth: CGFloat = 130
    static let barGap: CGFloat = 58
    static let barBaseline: CGFloat = 214
    static let barHeights: [CGFloat] = [250, 390, 530]

    // Funke, sitzt über dem kürzesten Balken.
    static let sparkCenter = CGPoint(x: 330, y: 750)
    static let sparkRadius: CGFloat = 112
    static let sparkWaist: CGFloat = 0.19

    /// Ab dieser Größe (in px) wird das vollständige Motiv gezeichnet.
    static let fullDetailMinimum = 64
}

private func rgb(_ r: Int, _ g: Int, _ b: Int, _ a: CGFloat = 1) -> CGColor {
    CGColor(
        srgbRed: CGFloat(r) / 255, green: CGFloat(g) / 255,
        blue: CGFloat(b) / 255, alpha: a
    )
}

// MARK: - Pfade

/// Superellipse: |x/a|^n + |y/b|^n = 1. Als Polygon mit vielen Punkten
/// abgetastet — bei 1024 px optisch nicht von einer Kurve zu unterscheiden.
private func squirclePath(in rect: CGRect, exponent n: CGFloat, samples: Int = 1440) -> CGPath {
    let a = rect.width / 2, b = rect.height / 2
    let cx = rect.midX, cy = rect.midY
    let path = CGMutablePath()
    for i in 0..<samples {
        let t = 2 * CGFloat.pi * CGFloat(i) / CGFloat(samples)
        let ct = cos(t), st = sin(t)
        let x = cx + a * copysign(pow(abs(ct), 2 / n), ct)
        let y = cy + b * copysign(pow(abs(st), 2 / n), st)
        if i == 0 { path.move(to: CGPoint(x: x, y: y)) } else { path.addLine(to: CGPoint(x: x, y: y)) }
    }
    path.closeSubpath()
    return path
}

/// Vierzackiger Funke: vier Spitzen, dazwischen mit Quadratkurven eingezogen.
private func sparkPath(center c: CGPoint, radius r: CGFloat, waist: CGFloat) -> CGPath {
    let path = CGMutablePath()
    let tips = [
        CGPoint(x: c.x, y: c.y + r),
        CGPoint(x: c.x + r, y: c.y),
        CGPoint(x: c.x, y: c.y - r),
        CGPoint(x: c.x - r, y: c.y),
    ]
    let inner = r * waist
    let controls = [
        CGPoint(x: c.x + inner, y: c.y + inner),
        CGPoint(x: c.x + inner, y: c.y - inner),
        CGPoint(x: c.x - inner, y: c.y - inner),
        CGPoint(x: c.x - inner, y: c.y + inner),
    ]
    path.move(to: tips[0])
    for i in 0..<4 {
        path.addQuadCurve(to: tips[(i + 1) % 4], control: controls[i])
    }
    path.closeSubpath()
    return path
}

private func pillPath(x: CGFloat, baseline: CGFloat, width: CGFloat, height: CGFloat) -> CGPath {
    CGPath(
        roundedRect: CGRect(x: x, y: baseline, width: width, height: height),
        cornerWidth: width / 2, cornerHeight: width / 2, transform: nil
    )
}

// MARK: - Zeichnen

/// Wie der Hintergrund behandelt wird.
enum IconStyle: String {
    /// Eigene Squircle-Platte mit Rand und Schatten (klassisch, macOS 14/15).
    case plate
    /// Verlauf randlos über die ganze Fläche, ohne eigene Rundung.
    case fullBleed
    /// Nur das Motiv auf Transparenz — macOS 26 stellt die Platte.
    case glyph
    /// Squircle randlos über die ganze Fläche: macOS 26 maskiert deckungsgleich,
    /// älteres macOS zeigt die mitgelieferte Rundung. Das ist der Standard.
    case rounded
}

/// Standard ist `fullBleed`: macOS 26 maskiert nur vollständig deckende
/// Legacy-Icons auf die native Squircle-Form. Sobald das Bild irgendwo
/// transparent ist, setzt das System es stattdessen auf eine dunkle Platte —
/// was bei einem Icon mit eigener Platte doppelt gerahmt aussieht.
/// Für macOS 14/15 ist `plate` die passende Wahl (dort maskiert das System nicht).
var iconStyle: IconStyle = .fullBleed

private func drawIcon(into ctx: CGContext, pixelSize: Int) {
    let scale = CGFloat(pixelSize) / Design.canvas
    ctx.scaleBy(x: scale, y: scale)
    ctx.setAllowsAntialiasing(true)
    ctx.interpolationQuality = .high

    // Bei `rounded` füllt die Form die ganze Fläche; das System legt seine
    // eigene Maske und seinen Schatten darüber.
    let inset = iconStyle == .rounded ? 0 : Design.bodyInset
    let body = CGRect(
        x: inset, y: inset,
        width: Design.canvas - 2 * inset,
        height: Design.canvas - 2 * inset
    )
    let shape = squirclePath(in: body, exponent: Design.squircleExponent)

    // Weicher Schatten unter dem Körper — nur bei größeren Größen, sonst
    // verschmiert er das kleine Bild.
    //
    // Der Schatten wird über eine Transparenzschicht gelegt: der Körper wird
    // darin fertig gezeichnet und als Ganzes geworfen. Würde man stattdessen
    // erst eine schwarze Form füllen und den Verlauf darüber legen, bliebe die
    // antialiasierte Kante des schwarzen Grunds als dunkler Saum sichtbar.
    let castsShadow = pixelSize >= 128 && iconStyle == .plate
    ctx.saveGState()
    if castsShadow {
        ctx.setShadow(
            offset: CGSize(width: 0, height: -10),
            blur: 26,
            color: rgb(90, 30, 0, 0.28)
        )
        ctx.beginTransparencyLayer(auxiliaryInfo: nil)
    }

    // Ab hier alles auf die Körperform beschnitten.
    ctx.saveGState()
    switch iconStyle {
    case .plate:
        ctx.addPath(shape)
        ctx.clip()
    case .fullBleed:
        ctx.clip(to: CGRect(x: 0, y: 0, width: Design.canvas, height: Design.canvas))
    case .rounded:
        ctx.addPath(shape)
        ctx.clip()
    case .glyph:
        break // kein Hintergrund
    }

    // Hintergrundverlauf: helles Amber oben, tiefes Orange unten.
    let space = CGColorSpace(name: CGColorSpace.sRGB)!
    let paintsBackground = iconStyle != .glyph
    let background = CGGradient(
        colorsSpace: space,
        colors: [rgb(255, 196, 106), rgb(255, 138, 61), rgb(226, 88, 18)] as CFArray,
        locations: [0, 0.52, 1]
    )!
    if paintsBackground { ctx.drawLinearGradient(
        background,
        start: CGPoint(x: body.minX, y: body.maxY),
        end: CGPoint(x: body.maxX, y: body.minY),
        options: [.drawsBeforeStartLocation, .drawsAfterEndLocation]
    ) }

    // Lichtschein oben links für Tiefe.
    let sheen = CGGradient(
        colorsSpace: space,
        colors: [rgb(255, 255, 255, 0.30), rgb(255, 255, 255, 0)] as CFArray,
        locations: [0, 1]
    )!
    if paintsBackground { ctx.drawRadialGradient(
        sheen,
        startCenter: CGPoint(x: body.minX + body.width * 0.28, y: body.maxY - body.height * 0.1),
        startRadius: 0,
        endCenter: CGPoint(x: body.minX + body.width * 0.28, y: body.maxY - body.height * 0.1),
        endRadius: body.width * 0.72,
        options: []
    ) }

    // Motiv
    let cream = iconStyle == .glyph ? rgb(240, 108, 26) : rgb(255, 252, 246)
    if pixelSize >= Design.fullDetailMinimum {
        // Balken
        ctx.setFillColor(cream)
        var x = Design.barStartX
        for height in Design.barHeights {
            ctx.addPath(pillPath(
                x: x, baseline: Design.barBaseline,
                width: Design.barWidth, height: height
            ))
            ctx.fillPath()
            x += Design.barWidth + Design.barGap
        }
        // Funke
        ctx.addPath(sparkPath(
            center: Design.sparkCenter,
            radius: Design.sparkRadius,
            waist: Design.sparkWaist
        ))
        ctx.setFillColor(cream)
        ctx.fillPath()
    } else {
        // Kleine Größen: nur der Funke, groß und mittig.
        ctx.addPath(sparkPath(
            center: CGPoint(x: Design.canvas / 2, y: Design.canvas / 2),
            radius: 322,
            waist: 0.2
        ))
        ctx.setFillColor(cream)
        ctx.fillPath()
    }

    // Feine Innenkante — lässt die Form auf hellem Hintergrund sauber abschließen.
    if pixelSize >= 64 && iconStyle == .plate {
        ctx.addPath(squirclePath(
            in: body.insetBy(dx: 3, dy: 3), exponent: Design.squircleExponent
        ))
        ctx.setStrokeColor(rgb(255, 255, 255, 0.26))
        ctx.setLineWidth(5)
        ctx.strokePath()
    }

    ctx.restoreGState() // Beschnitt auf die Körperform

    if castsShadow { ctx.endTransparencyLayer() }
    ctx.restoreGState()
}

private func renderIcon(pixelSize: Int) -> CGImage? {
    let space = CGColorSpace(name: CGColorSpace.sRGB)!
    guard let ctx = CGContext(
        data: nil, width: pixelSize, height: pixelSize,
        bitsPerComponent: 8, bytesPerRow: 0, space: space,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else { return nil }
    drawIcon(into: ctx, pixelSize: pixelSize)
    return ctx.makeImage()
}

private func writePNG(_ image: CGImage, to url: URL) throws {
    guard let destination = CGImageDestinationCreateWithURL(
        url as CFURL, "public.png" as CFString, 1, nil
    ) else {
        throw NSError(domain: "IconGen", code: 1, userInfo: [
            NSLocalizedDescriptionKey: "PNG-Ziel konnte nicht erstellt werden: \(url.path)"
        ])
    }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else {
        throw NSError(domain: "IconGen", code: 2, userInfo: [
            NSLocalizedDescriptionKey: "PNG konnte nicht geschrieben werden: \(url.path)"
        ])
    }
}

// MARK: - Ablauf

/// Die von iconutil erwarteten Dateien: (Dateiname, Kantenlänge in Pixel).
private let iconsetFiles: [(name: String, pixels: Int)] = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]

let arguments = CommandLine.arguments
guard arguments.count >= 2 else {
    FileHandle.standardError.write(
        Data("Aufruf: IconGen <ausgabe.iconset> [--preview datei.png]\n".utf8)
    )
    exit(2)
}

let outputDirectory = URL(fileURLWithPath: arguments[1], isDirectory: true)

if let index = arguments.firstIndex(of: "--style"), index + 1 < arguments.count,
   let parsed = IconStyle(rawValue: arguments[index + 1]) {
    iconStyle = parsed
}

do {
    try FileManager.default.createDirectory(
        at: outputDirectory, withIntermediateDirectories: true
    )

    // Gleiche Größe nur einmal rendern, dann für beide Dateinamen schreiben.
    var rendered: [Int: CGImage] = [:]
    for entry in iconsetFiles {
        let image: CGImage
        if let cached = rendered[entry.pixels] {
            image = cached
        } else {
            guard let fresh = renderIcon(pixelSize: entry.pixels) else {
                throw NSError(domain: "IconGen", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "Rendern bei \(entry.pixels) px fehlgeschlagen"
                ])
            }
            rendered[entry.pixels] = fresh
            image = fresh
        }
        try writePNG(image, to: outputDirectory.appendingPathComponent(entry.name))
    }

    print("IconGen: \(iconsetFiles.count) Dateien in \(outputDirectory.path)")
} catch {
    FileHandle.standardError.write(Data("IconGen: \(error.localizedDescription)\n".utf8))
    exit(1)
}
