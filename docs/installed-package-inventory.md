# Installed package inventory — 2026-08-03

The physical MP2000 has **83 installed package payloads across three stores,
using 7,209,706 bytes (6.88 MiB) of compressed payload data**. There are 82
distinct package identities because `Dock ZC & TCP/IP:Kallisys` is present on
both Internal and Ultimate Newton.

This is the canonical installed-package record derived from the raw `Packages`
soups, not an Extras-screen transcription. It combines the latest Internal
backup with the separately captured 4 MB Ultimate Newton card and 16 MB ATA
card. The two storage cards are alternatives in the Newton's storage-card slot
while the WaveLAN card occupies the other slot.

## Totals

| Store/content | Payloads | Compressed bytes | MiB |
|---|---:|---:|---:|
| Internal — active packages | 56 | 3,028,883 | 2.89 |
| Ultimate Newton 4 MB — active packages | 6 | 505,141 | 0.48 |
| 16 MB ATA card — active packages | 21 | 3,675,682 | 3.51 |
| **Active package locations** | **83** | **7,209,706** | **6.88** |
| Ultimate Newton — saved `BACKUP:Packages` copy | 51 | 2,415,807 | 2.30 |
| **Active plus saved backup payloads** | **134** | **9,625,513** | **9.18** |

“Compressed bytes” is the exact stored `pkgRef` large-binary payload length in
the Dock export. Newton store allocation is slightly higher because package
frames, Extras metadata, soup indexes, and flash blocks also consume space.
Built-in ROM packages are not included because they do not occupy these stores.

The Ultimate Newton backup copy contains the same payload bytes as 51 of the
Internal packages below. It predates `Dock ZC & TCP/IP:Kallisys`,
`HarnessProbe:jbfly`, `Internet Setup`, `NetHopper:ALLPEN`, and
`NetTest:Newton`; those five are therefore absent from `BACKUP:Packages`.

## Internal — 56 active payloads

| Package identity | Bytes | KiB |
|---|---:|---:|
| ` Newton Devices` | 69,246 | 67.6 |
| `3C589` | 2,368 | 2.3 |
| `ATA Support:Kallisys` | 123,527 | 120.6 |
| `Avi's Backdrop:AviD` | 48,775 | 47.6 |
| `BASIC:NSBASIC` | 129,812 | 126.8 |
| `BiggerNotes:Paul's Software` | 1,812 | 1.8 |
| `BleepMaker:KISANUKI` | 43,128 | 42.1 |
| `Calc++:MacSOS` | 57,849 | 56.5 |
| `Convert!:CLINT` | 49,828 | 48.7 |
| `Courier` | 55,576 | 54.3 |
| `DD_Dice:SDH` | 13,992 | 13.7 |
| `Dock ZC & TCP/IP:Kallisys` | 42,380 | 41.4 |
| `DopeWars Help` | 9,405 | 9.2 |
| `dopewars:NSBASIC` | 34,644 | 33.8 |
| `Earth :deepfocus` | 104,124 | 101.7 |
| `EH:PBJONES` | 29,256 | 28.6 |
| `Farallon Enet` | 8,072 | 7.9 |
| `Frogs vs. Cars:SAS` | 36,214 | 35.4 |
| `GDTPrintDriver` | 10,084 | 9.8 |
| `HarnessProbe:jbfly` | 5,240 | 5.1 |
| `HP IrDA Printers` | 4,444 | 4.3 |
| `HWR Works:SAS` | 7,909 | 7.7 |
| `HyperNewt:ATOW` | 108,668 | 106.1 |
| `Image Stationery` | 19,666 | 19.2 |
| `ImageDec:Simple` | 4,271 | 4.2 |
| `Internet Setup` | 140,890 | 137.6 |
| `ISO-8859-1:Simple` | 4,793 | 4.7 |
| `JPEGConvert:NewtsCape` | 60,997 | 59.6 |
| `LetterSpin` | 45,551 | 44.5 |
| `LucentWaveLAN:Noguchi` | 38,460 | 37.6 |
| `Minico:Scrawl` | 33,172 | 32.4 |
| `modPlayer:RSM` | 30,207 | 29.5 |
| `modplayerAsm` | 4,387 | 4.3 |
| `Monaco` | 17,208 | 16.8 |
| `Monaco9:Newton` | 4,767 | 4.7 |
| `Mystic8ball:ErikB` | 9,100 | 8.9 |
| `NanoCAD:LeeMoon` | 10,970 | 10.7 |
| `NetHopper:ALLPEN` | 401,136 | 391.7 |
| `NetTest:Newton` | 23,430 | 22.9 |
| `Newton Internet Enabler` | 257,034 | 251.0 |
| `Newton Logo Light` | 6,500 | 6.3 |
| `newtWorks` | 116,096 | 113.4 |
| `NewtWorksDraw` | 172,324 | 168.3 |
| `NIE Ethernet Module` | 62,808 | 61.3 |
| `Paint:HexDump` | 125,440 | 122.5 |
| `Register:FlaSheridn` | 39,944 | 39.0 |
| `Runtime:NSBASIC` | 97,999 | 95.7 |
| `SonyRmt:Flash` | 27,514 | 26.9 |
| `SpeakText:NEWTON` | 12,640 | 12.3 |
| `SpellWorks:ATOW` | 24,097 | 23.5 |
| `SubPatrol:iambic` | 48,731 | 47.6 |
| `Text Stationery` | 5,031 | 4.9 |
| `Web Extensions 2:ALLPEN` | 10,068 | 9.8 |
| `Works Calculations:Apple` | 159,262 | 155.5 |
| `z3ComDrv:clli` | 3,172 | 3.1 |
| `ZGIFFormat:Simple` | 14,865 | 14.5 |

` Newton Devices` really does begin with a space; preserve that exact identity.

## Ultimate Newton 4 MB — 6 active payloads

| Package identity | Bytes | KiB |
|---|---:|---:|
| `-HarnessLoaderZC39:jbfly` | 14,752 | 14.4 |
| `-HarnessLoaderZC40:jbfly` | 14,832 | 14.5 |
| `Dock ZC & TCP/IP:Kallisys` | 42,380 | 41.4 |
| `HarnessClientA3:jbfly` | 19,344 | 18.9 |
| `NewtsCape:NewtsCape` | 238,041 | 232.5 |
| `PT100:Scrawl` | 175,792 | 171.7 |

These identities explain the Extras labels: `HarnessClientA3:jbfly` appears as
**Chat A3**, and `NewtsCape:NewtsCape` appears as **NewtScape**. ZC40 is the
current loader; ZC39 remains the fallback.

## 16 MB ATA card — 21 active payloads

| Package identity | Bytes | KiB |
|---|---:|---:|
| `1989.mod` | 173,672 | 169.6 |
| `AcesHigh.mod` | 261,199 | 255.1 |
| `ActOfImpulse.mod` | 80,689 | 78.8 |
| `Asphyxiated.mod` | 112,169 | 109.5 |
| `Can't Touch.mod` | 171,204 | 167.2 |
| `Consummation.mod` | 83,846 | 81.9 |
| `Cyber.mod` | 50,668 | 49.5 |
| `DeepGreen:JoBS` | 107,912 | 105.4 |
| `Flatland:RTP` | 221,900 | 216.7 |
| `Get Ready.mod` | 210,367 | 205.4 |
| `HighVoltage.mod` | 413,590 | 403.9 |
| `HWInstructor:Newton` | 183,348 | 179.1 |
| `MacInTalk` | 250,440 | 244.6 |
| `movie:NSBASIC` | 106,289 | 103.8 |
| `NC_HELP.htm` | 84,085 | 82.1 |
| `NetHopper:ALLPEN` | 442,520 | 432.1 |
| `NewtHack:ChrisDopp` | 239,588 | 234.0 |
| `NHSounds:CAD` | 120,196 | 117.4 |
| `Oh Yeah.mod` | 96,226 | 94.0 |
| `RainyNight.mod` | 184,720 | 180.4 |
| `Thow-Heap.mod` | 81,054 | 79.2 |

## Evidence and refresh procedure

### Emulator recovery baseline

An isolated Einstein instance named `mpclone` was initialized from a blank
8 MiB flash and restored over the ROM Dock serial path. The following physical
recovery/core packages were installed from their preserved standalone package
files and remained present after reboot:

| Emulator package | User-visible name | Source `.pkg` bytes |
|---|---|---:|
| `-HarnessLoaderZC39:jbfly` | ZC39 Loader 2.3 | 14,624 |
| `-HarnessLoaderZC40:jbfly` | ZC40 Loader 2.4 | 14,704 |
| `HarnessClientA3:jbfly` | Chat A3 / Newton Chat 2.3-a3 | 19,184 |
| `NewtsCape:NewtsCape` | NewtScape | 296,128 |
| `PT100:Scrawl` | PT100 | 174,416 |

The ignored recoverable flash is
`runtime/emulators/mp2000-core-20260803/internal.flash`: 8,388,608 bytes,
SHA-256
`259133f65e61b139fb85c2d41085d3114f49413b841f76667269303c94ef974d`.
It is a verified core baseline, not yet a byte-for-byte physical clone.

The other 78 active package locations are preserved as compressed large-binary
objects inside the Dock soup exports. They cannot be treated as standalone
`package0` files, so the full soup-level restore remains a separate test. Do not
claim that copying or renaming those `pkgRef` bytes restores a package.

A follow-up install of the five Einstein NIE/NE2000 packages completed over
serial, but that blank flash raised Newton error `-48807` after reboot. The
experiment was rolled back to the verified core flash above. Network testing
should continue from the repo's already configured Einstein baseline; adding
Dock TCP to a blank clone is not a proven shortcut.

### Backup sources

- Latest Internal and 16 MB ATA data:
  `runtime/backups/mp2000-cf32-20260803-docktcp-a1`; archive SHA-256
  `5409b5ef0171bb80d97d0ebf16b878e848dcaa926e5b91d28e26a329a9e0ba1b`.
- Ultimate Newton 4 MB data:
  `runtime/backups/mp2000-20260803-docktcp-a3`; archive SHA-256
  `b60de3710e89ea99bd202f24bf75c38b7d6071afe9a7aceab732a51d2de9fc7c`.
- The ignored exports contain personal Newton data and remain outside Git. This
  report records only package identities and payload sizes.
- Refresh this report from a new complete Dock export after installing or
  removing packages. Never infer the current inventory from Extras icons alone.
