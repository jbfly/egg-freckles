# newton-harness — plan

Agentic AI harness for the Apple Newton MessagePad 2000 (NewtonOS 2.1),
modeled on ~/git/model100. Client/server over wifi.

## Recon facts (verified 2026-07-22)
- Prior art: github.com/jbfly/newtonGPT — asyncio telnet server, port 6801,
  Newton runs PT100 (font Minico 18, 45 cols). pt100_serial.py = PT100 keygen.
- Wifi: WaveLAN Silver→Gold PCMCIA card + Hiroshi Noguchi driver. 802.11b,
  open/WEP only. AirPort Express worked in 2023; DD-WRT did not.
- Emulator: github.com/pguyot/Einstein (active, 2026-07). Runs OS 2.1 from a
  self-dumped 717006 ROM; has NE2000 PCMCIA + TAP/usermode networking.
- Toolchain (Linux, no classic Mac): tntk + cDCL compile NewtonScript → .pkg;
  NEWT/0 runs NewtonScript on desktop; install over TCP via tntk -t or unixnpi.
  NTK platform files from UNNA. Docs: newtonscript.org.
- model100 reusables: agent backend w/ strict JSON response schema, stop-and-wait
  framed protocol (seq+checksum+ACK/NAK, GET/PUT/PATCH/RUN), ASCII sanitize/wrap,
  session state. M100-specific parts (BASIC gen, 40-col) get replaced.

## Phases
0. AP on Alpha wlan0: hostapd open SSID "newton", isolated subnet 10.42.0.0/24,
   nftables: Newton may reach ONLY Alpha:6801 (+DHCP/DNS). Prepared, human applies.
1. Telnet bootstrap: server.py on :6801, PT100 client (zero Newton-side code).
   45-col wrap, 7-bit ASCII, CRLF. Backend: agent CLI w/ JSON schema à la model100.
2. Dev env: Einstein + tntk/cDCL/NEWT0 built on Alpha; ROM dump from real MP2000;
   sample .pkg builds and installs into Einstein.
3. Native NewtonScript client app: nicer UI than PT100, framed protocol,
   GET/PUT for notes/files, installed over TCP.
4. Apps: omnigent/tmux session monitor (top priority), notes/data sync,
   Beeper/email gateway, image gen (Newton-optimized dithered grayscale 480x320),
   handwriting/AI experiments.
5. Portable networking (later): travel router w/ open SSID + WireGuard upstream.

## Constraints
- Newton screen: 480x320 grayscale. PT100: 45 cols. No TLS on device — server
  proxies everything. ASCII only.
