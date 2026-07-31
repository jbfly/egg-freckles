# Newton recovery packages

Fetched 2026-07-31. These packages restore networking to a hard-reset Newton
MessagePad 2000/2100 and then provide a browser that can install other Newton
packages from HTTP URLs.

| File | Bytes | Why it is here | Source |
|---|---:|---|---|
| `Enetsup.pkg` | 74,888 | Apple NIE 2.0 Ethernet support; required for every Ethernet card. | [Archive.org](https://archive.org/download/newton_ethernet_drivers/Enetsup.pkg) |
| `Inetenbl.pkg` | 318,276 | Apple Newton Internet Enabler 2.0 core networking stack. | [Archive.org](https://archive.org/download/newton_ethernet_drivers/Inetenbl.pkg) |
| `Newtdev.pkg` | 86,316 | Apple Newton Devices support required by Ethernet and WaveLAN drivers. | [Archive.org](https://archive.org/download/newton_ethernet_drivers/Newtdev.pkg) |
| `Inetstup.pkg` | 192,156 | Apple Internet Setup application used to configure TCP/IP and DHCP. | [Archive.org](https://archive.org/download/newton_ethernet_drivers/Inetstup.pkg) |
| `LucentWaveLAN.pkg` | 37,524 | Hiroshi Noguchi's driver for the Lucent WaveLAN PCMCIA card used by the recovery network. | [UNNA source ZIP](http://www.unna.org/unna/drivers/ethernet/WiFi/NewtonWaveLAN_source.zip) |
| `nwcp21e2.pkg` | 296,128 | Newt's Cape 2.1e-2 freeware/unexpiring build; downloads and installs `.pkg` files from HTTP URLs after NIE is running. | [Communicrossings registered/freeware path](https://communicrossings.com/html/newton/regnewtscape/pkg/nwcp21e2.pkg) |

Run `scripts/fetch-recovery-packages.sh` from anywhere to replace all package
files with fresh downloads and verify them against `SHA256SUMS`. The WaveLAN
package is extracted from UNNA's source ZIP. Archive.org's item description
also names `NewtonWaveLAN_source.zip`, but its corresponding download URL
returned HTTP 404 on 2026-07-31.

The `.pkg` binaries are intentionally ignored by git and must remain mirrored
on local/recovery storage. This README, the checksums, and the fetch script are
tracked so the set can be reproduced while the source sites remain available.
