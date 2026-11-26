// Genere les icones du site (PWA + favicon + icone iOS).
//
// Usage : swift deploiement/icones.swift
// Sortie : deploiement/pages/icones/*.png
//
// Pourquoi un script plutot que des PNG sortis d'un logiciel : le dessin reste
// modifiable (couleurs du bandeau, taille du joueur, pointilles) et
// regenerable a l'identique. Il faut macOS avec Swift ; les PNG sont versionnes
// dans le depot, la publication sur Cloudflare ne depend donc pas de ce script.
//
// Le fond reprend le degrade du bandeau de la page (magenta -> indigo) et ses
// pointilles. Par-dessus : la silhouette d'un joueur en suspension, en blanc.
// La silhouette est un PNG blanc sur transparent range dans
// deploiement/sources/ : ce dossier n'est pas publie, il ne sert qu'a
// regenerer les icones.

import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

// ------------------------------------------------------------------ couleurs
func couleur(_ hex: String) -> CGColor {
    var s = hex
    if s.hasPrefix("#") { s.removeFirst() }
    let v = UInt32(s, radix: 16)!
    return CGColor(red: CGFloat((v >> 16) & 0xff) / 255,
                   green: CGFloat((v >> 8) & 0xff) / 255,
                   blue: CGFloat(v & 0xff) / 255, alpha: 1)
}

func contexte(_ largeur: Int, _ hauteur: Int, opaque: Bool = false) -> CGContext {
    CGContext(data: nil, width: largeur, height: hauteur,
              bitsPerComponent: 8, bytesPerRow: 0,
              space: CGColorSpaceCreateDeviceRGB(),
              bitmapInfo: opaque
                  ? CGImageAlphaInfo.noneSkipLast.rawValue
                  : CGImageAlphaInfo.premultipliedLast.rawValue)!
}

func ecrire(_ img: CGImage, _ chemin: String) {
    let url = URL(fileURLWithPath: chemin)
    let dest = CGImageDestinationCreateWithURL(url as CFURL,
                                               UTType.png.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(dest, img, nil)
    guard CGImageDestinationFinalize(dest) else {
        fatalError("ecriture impossible : \(chemin)")
    }
}

// ------------------------------------------------------------------ dessin
// Fond : degrade du bandeau, prolonge au-dela des extremites pour couvrir
// entierement le carre (sinon les coins restent transparents).
func fond(_ ctx: CGContext, _ S: CGFloat) {
    let cols = [couleur("e5177b"), couleur("a3208f"),
                couleur("4a2a9e"), couleur("2f3aa8")]
    let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(),
                       colors: cols as CFArray,
                       locations: [0, 0.38, 0.68, 1])!
    ctx.drawLinearGradient(g,
                           start: CGPoint(x: 0, y: S * 0.10),
                           end: CGPoint(x: S, y: S * 0.90),
                           options: [.drawsBeforeStartLocation, .drawsAfterEndLocation])
}

// Pointilles discrets, comme le fond de maillot du bandeau : des ronds blancs
// tres peu opaques, repartis a la main pour ne pas gener la silhouette.
func points(_ ctx: CGContext, _ S: CGFloat) {
    let t: [(CGFloat, CGFloat, CGFloat, CGFloat)] = [
        (0.12, 0.14, 0.030, 0.055), (0.25, 0.27, 0.017, 0.045), (0.08, 0.40, 0.013, 0.04),
        (0.35, 0.09, 0.015, 0.04), (0.87, 0.18, 0.028, 0.055), (0.75, 0.33, 0.016, 0.04),
        (0.93, 0.46, 0.012, 0.04), (0.81, 0.58, 0.010, 0.03), (0.15, 0.73, 0.019, 0.04),
        (0.08, 0.87, 0.012, 0.04), (0.29, 0.91, 0.015, 0.04), (0.44, 0.82, 0.011, 0.03),
        (0.90, 0.81, 0.017, 0.04), (0.62, 0.05, 0.011, 0.03), (0.54, 0.95, 0.019, 0.04),
    ]
    for (x, y, r, a) in t {
        ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: a))
        ctx.fillEllipse(in: CGRect(x: S * x - S * r, y: S * (1 - y) - S * r,
                                   width: 2 * S * r, height: 2 * S * r))
    }
}

// --------------------------------------------------------------- silhouette
// Charge le PNG et renvoie l'image ainsi que sa boite utile (pixels non
// transparents) : le cadrage ne depend pas des marges eventuelles du fichier.
func charger(_ chemin: String) -> (CGImage, CGRect) {
    let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: chemin) as CFURL, nil)!
    let img = CGImageSourceCreateImageAtIndex(src, 0, nil)!
    let ctx = contexte(img.width, img.height)
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: img.width, height: img.height))
    let d = ctx.data!.assumingMemoryBound(to: UInt8.self)
    let pas = ctx.bytesPerRow
    var x0 = img.width, y0 = img.height, x1 = -1, y1 = -1
    for y in 0..<img.height {
        for x in 0..<img.width where d[y * pas + x * 4 + 3] > 8 {
            x0 = min(x0, x); x1 = max(x1, x)
            y0 = min(y0, y); y1 = max(y1, y)
        }
    }
    return (ctx.makeImage()!,
            CGRect(x: x0, y: y0, width: x1 - x0 + 1, height: y1 - y0 + 1))
}

// ---------------------------------------------------------------- composition
func icone(_ pose: CGImage, _ boite: CGRect, _ cote: Int, hauteur: CGFloat) -> CGImage {
    // Rendu a 4x puis moyenne 4x4 : le tramage du degrade disparait, les bords
    // de la silhouette sont lisses, et le PNG se compresse dix fois mieux
    // qu'en direct.
    let facteur = 4
    let S = cote * facteur
    let sf = CGFloat(S)
    let ctx = contexte(S, S, opaque: true)
    fond(ctx, sf)
    points(ctx, sf)

    let h = sf * hauteur
    let echelle = h / boite.height
    let w = boite.width * echelle
    let cible = CGRect(x: (sf - w) / 2, y: (sf - h) / 2, width: w, height: h)
    // boite en coordonnees haut-gauche, dessin CG en bas-gauche
    let morceau = CGRect(x: boite.minX, y: CGFloat(pose.height) - boite.maxY,
                         width: boite.width, height: boite.height)
    ctx.draw(pose.cropping(to: morceau)!, in: cible)

    let src = ctx.data!.assumingMemoryBound(to: UInt8.self)
    let pas = ctx.bytesPerRow
    let dst = UnsafeMutablePointer<UInt8>.allocate(capacity: cote * cote * 4)
    let n = facteur * facteur
    for y in 0..<cote {
        for x in 0..<cote {
            var r = 0, v = 0, b = 0
            for dy in 0..<facteur {
                let ligne = (y * facteur + dy) * pas
                for dx in 0..<facteur {
                    let p = ligne + (x * facteur + dx) * 4
                    r += Int(src[p]); v += Int(src[p + 1]); b += Int(src[p + 2])
                }
            }
            let q = (y * cote + x) * 4
            dst[q] = UInt8((r + n / 2) / n)
            dst[q + 1] = UInt8((v + n / 2) / n)
            dst[q + 2] = UInt8((b + n / 2) / n)
            dst[q + 3] = 255
        }
    }

    let out = CGContext(data: dst, width: cote, height: cote,
                        bitsPerComponent: 8, bytesPerRow: cote * 4,
                        space: CGColorSpaceCreateDeviceRGB(),
                        bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    return out.makeImage()!
}

// ------------------------------------------------------------------ sortie
let (pose, boite) = charger("deploiement/sources/silhouette.png")
print("silhouette source \(Int(boite.width))x\(Int(boite.height))")

let dossier = "deploiement/pages/icones"
try? FileManager.default.createDirectory(atPath: dossier,
                                         withIntermediateDirectories: true)

// 0,755 : la silhouette occupe les trois quarts du carre sans toucher les bords.
// maskable : le systeme rogne jusqu'a un cercle de 80 % du cote ; a 62 % la
// silhouette tient entierement dans la zone sure.
let fichiers: [(String, Int, CGFloat)] = [
    ("favicon-32.png", 32, 0.755),
    ("apple-touch-icon.png", 180, 0.755),
    ("icone-192.png", 192, 0.755),
    ("icone-512.png", 512, 0.755),
    ("icone-maskable-512.png", 512, 0.62),
]

for (nom, cote, hauteur) in fichiers {
    let img = icone(pose, boite, cote, hauteur: hauteur)
    let chemin = "\(dossier)/\(nom)"
    ecrire(img, chemin)
    let attrs = try? FileManager.default.attributesOfItem(atPath: chemin)
    let octets = (attrs?[.size] as? Int) ?? 0
    print("\(nom) : \(cote)x\(cote), \(octets) octets")
}
