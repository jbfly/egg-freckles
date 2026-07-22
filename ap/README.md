# ap/ — dedicated wifi AP for the Newton MP2000

Open 802.11b AP (`SSID: newton`) on wlan0 with an isolated subnet
(10.42.0.0/24). The Newton may reach **only** this host's TCP 6801 (the
harness) plus DHCP/DNS on this host. No LAN, no internet, nothing inbound.

Everything here is runtime-only: nothing is installed to /etc, no system
services are enabled, and a reboot (or `teardown.sh`) returns the machine
to its previous state.

## Prerequisites

```sh
sudo pacman -S hostapd    # the only missing piece
```

dnsmasq and nftables are already installed. hostapd 2.11 (repo version)
**removed WEP support** — `wep_*` config keys are rejected as unknown.
That's fine: the WaveLAN/Noguchi setup runs open auth, and the firewall
makes the open SSID low-risk. Verified against the actual 2.11 binary.

## Apply

```sh
cd ~/git/newton-harness/ap
sudo ./apply.sh
```

This disconnects wlan0 from the fallback uplink (THIS_HOUSE_6G), sets it
unmanaged in NetworkManager, gives it 10.42.0.1/24, loads the nftables
table, and starts dnsmasq + hostapd. Idempotent — safe to re-run.
(The wired uplink enp42s0 is untouched throughout.)

## Verify

```sh
iw dev wlan0 info                                   # type AP, channel 6
sudo hostapd_cli -p /run/newton-ap/hostapd status   # state=ENABLED
sudo ss -lunp | grep 10.42.0.1                      # dnsmasq on 53 + 67
sudo nft list table inet newton-ap                  # the isolation rules
ip addr show wlan0                                  # 10.42.0.1/24
```

With the Newton associated (`hostapd_cli ... all_sta` shows its MAC) it
should get 10.42.0.10–10.42.0.50. Then, from the Newton: `10.42.0.1:6801`
connects; DNS resolves; **everything else fails** (ping the LAN gateway,
any other host port, any internet address — all dropped).

## Teardown

```sh
sudo ./teardown.sh
```

Stops the daemons, removes the nftables table and the 10.42.0.1 address,
hands wlan0 back to NetworkManager, which reconnects the saved fallback
uplink. Idempotent.

## Newton side

- WaveLAN driver (Noguchi): SSID `newton`, encryption **None/Open**.
- Internet Enabler setup: obtain IP automatically (DHCP). No proxy.
- Then point PT100 (or the native client) at `10.42.0.1`, port `6801`.

## Notes

- Channel 6, hw_mode=b, 1/2 Mb/s basic rates for the WaveLAN. Change
  `channel` in hostapd.conf if 6 is congested (1–13 usable, regdomain PT).
- Re-apply after reboot if you want the AP back; nothing persists by design.
- If wlan0's MAC/regdomain changes (different machine), re-check
  `iw reg get` and `country_code` in hostapd.conf.
