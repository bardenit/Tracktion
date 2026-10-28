TRACKTION — BRAND ASSET PACK
Fuel. Maintenance. Performance.
=================================================

Generated from the Tracktion Media Pack v1.0 sheet.

NOTE ON QUALITY
---------------
These assets were rebuilt from the artwork on your media-pack sheet
(no original master file was provided). The mark has been cleaned to a
transparent matte and recolored mathematically, so the flat-color
variations (white / orange / one-color / reversed) are crisp at any size.
The full-color mark was upscaled once from the sheet, so very large uses
(e.g. print bigger than ~25cm) may look slightly soft. For razor-sharp
output at any scale, re-run this with the original vector/hi-res logo.

COLORS
------
Orange (primary) ... #FF6A00
Orange (alt) ....... #FF8C00
White .............. #FFFFFF
Dark (tile) ........ #1A1A1A
Dark (alt) ......... #2B2B2B

FONTS
-----
Primary .... Rajdhani Bold      Secondary .... Inter Regular

FOLDERS
-------
/app-icons        Dark rounded tiles: 1024, 512, 180, 120, 76, 60, 40
/logos
   /transparent   Mark on transparent bg: full-color, white, orange, one-color
   reversed       Dark mark + orange drop on white tile (1024, 512)
/favicons         16 & 32 px browser-tab icons (dark tile)
/pwa              apple-touch-icon-180, android-chrome 192/512, site.webmanifest
/brand-pattern    Tire-tread backgrounds:
                    - tracktion-tread-bg-tile.png ...... 560x560 seamless, repeats (dark)
                    - tracktion-tread-bg-tile-warm.png . 560x560 seamless, repeats (warm)
                    - tracktion-tread-bg-hero-1920.png . 1920x1080 full-bleed, orange sweep
                    - tracktion-tread-texture.png ...... 512x116 divider strip (from sheet)

USING THE BACKGROUND TILES (CSS)
--------------------------------
body{
  background-color:#161616;
  background-image:url("brand-pattern/tracktion-tread-bg-tile.png");
  background-repeat:repeat;       /* seams-free at any size */
}
/* full-bleed hero */
.hero{
  background:#0e0e0e url("brand-pattern/tracktion-tread-bg-hero-1920.png") center/cover no-repeat;
}

WEB SETUP (paste into <head>)
-----------------------------
<!-- Tracktion favicons & app icons -->
<link rel="icon" type="image/png" sizes="32x32" href="/favicons/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicons/favicon-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/pwa/apple-touch-icon-180.png">
<link rel="manifest" href="/pwa/site.webmanifest">
<meta name="theme-color" content="#FF6A00">
