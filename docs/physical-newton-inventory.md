# Physical MP2000 inventory — 2026-08-02

The photographed Newton already has the working network stack, the current
harness, and both recovery applications. **Dock TCP was not visible**, which
explains why the ROM Dock application did not offer TCP/IP even though normal
WiFi applications worked.

This is a transcription of four user-supplied photographs taken at the Mars
hardware bench. Extras labels are user-visible captions, not verified package
identities. The Storage view lists soups and application data, not installed
packages. Line-wrapped labels are joined below; a question mark marks text that
the photograph does not resolve confidently.

The later Dock backups supersede this photo transcription for exact identities
and sizes. See [Installed package inventory](installed-package-inventory.md),
which includes Internal, the Ultimate Newton 4 MB card, and the 16 MB ATA card.

## Operationally important state

| Item | Photographic evidence | Meaning |
|---|---|---|
| ZC40 Loader 2.4 | Extras page 3 | Current WiFi package installer is present. |
| ZC39 Loader 2.3 | Extras page 3 | Unchanged loader fallback is present. |
| Chat A3 | Extras page 1 | Current `HarnessClientA3:jbfly` client is present. |
| NewtScape | Extras page 2 | The non-demo recovery browser is present. |
| Newton Devices, Newton Internet, NIE Ethernet, Internet Setup, 802.11b WaveLAN | Extras pages 1–2 | NIE and the WaveLAN path are installed; reinstalling the NIE quartet is not the fix for Dock. |
| `Internet Setups` | Storage | Saved NIE configuration data exists. |
| `DEMO.BAS:NSBASIC` | Storage | The NS Basic REPLACE DEMO bootstrap soup still exists and must be preserved. |
| `TEMPHTML:NewtsCap` | Storage | Newt's Cape has working data on the device. |
| Dock TCP/IP | Not visible in Extras | Install the separate Dock TCP transport before expecting Dock's TCP/IP menu item. |

## Extras — All Icons

### Page 1

| Row | Column 1 | Column 2 | Column 3 | Column 4 | Column 5 |
|---:|---|---|---|---|---|
| 1 | 3C589 | 802.11b WaveLAN | ATA Support | Bigger Notes | BleepMaker |
| 2 | Calc++ | Calculator | Calls | Card | Chat A3 |
| 3 | Clock | Convert! | Courier | Dates | DD_Dice |
| 4 | Demo BASIC | Dock | dopewars | DopeWars Manual | Earth |
| 5 | ElectroHelp | Farallon Enet | Formulas | Frogs vs. Cars | GDTPrintDriver |
| 6 | GIF Format | Harness Probe | Help | HexPaint | HP IrDA Printer |
| 7 | HWRWorks By SAI | Hyper Newt | Image Decoder | Image Stationery | In/Out |

Evidence: [Extras page 1](../runtime/evidence/hardware-20260802-extras-1.jpg).

### Page 2

| Row | Column 1 | Column 2 | Column 3 | Column 4 | Column 5 |
|---:|---|---|---|---|---|
| 1 | Internet Setup | ISO-8859-1 Encoding | JPEGConvert:NewtsCa? | LetterSpin | Logo Lite |
| 2 | Minico:Scrawl | modPlayer | modplayer Asm | Monaco | Monaco9:Newton |
| 3 | Mystic | Names | NanoCAD | Net Hopper | NetTest |
| 4 | Newton Devices | Newton Internet | NewtScape | NewtWorksDraw | NIE Ethernet |
| 5 | Owner Info | Prefs | PT100 | Register | Runtime:NSBASIC |
| 6 | Setup | Sony Remote | SpeakText:NEWTON | SpellWorks | Sub Patrol Demo |
| 7 | Text Stationery | Time Zones | Web Extensions | Works | Works Calculations |

Evidence: [Extras page 2](../runtime/evidence/hardware-20260802-extras-2.jpg).

### Page 3

| Column 1 | Column 2 | Column 3 | Column 4 |
|---|---|---|---|
| Writing Practice | z3ComDrv:clli? | ZC39 Loader 2.3 | ZC40 Loader 2.4 |

Evidence: [Extras page 3](../runtime/evidence/hardware-20260802-extras-3.jpg).

## Storage soups and data

| Row | Column 1 | Column 2 | Column 3 | Column 4 | Column 5 |
|---:|---|---|---|---|---|
| 1 | Calls | Dates | In/Out Items | Names | Notes |
| 2 | To do Tasks | SpellWorks | NewtHack | AcctSoup:PocketQui? | Time Zones |
| 3 | convert:CLINT | Courier:40 Hz | DELLCW:BRANDO? | DopeData | Internet DNS Cache |
| 4 | Internet Setups | modPlayer Soup:RSM | NewtWorks | NetHopper Cache | Paintings |
| 5 | SCRATCH.BAS:NSBASIC | ToDo:ATO | TxnSoup:PocketQuic? | WSH5:WordSquare:G? | DEMO.BAS:NSBASIC |
| 6 | TEMPHTML:NewtsCap |  |  |  |  |

Evidence: [Storage](../runtime/evidence/hardware-20260802-storage.jpg). The
header appears to show `51%` and `232.4`, but the photograph does not make the
units or exact meaning reliable enough to record as a measured free-space
value.

## Limits of this inventory

- The photos do not prove package identities, versions, signatures, or whether
  each item lives on internal memory or a card.
- Some Extras icons are built-in applications or stationery, not third-party
  packages.
- A hidden extension without an Extras icon cannot be ruled out solely from
  All Icons. In this case the missing TCP/IP choice in Dock is the functional
  confirmation that the transport was not active.
