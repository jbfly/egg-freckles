# EF24 physical iPad one-Send result

Date: 2026-08-11. This is a curated record of the first physical iPad run of
Egg Freckles EF24. It contains no photo because none was taken and makes no
packet-level claim.

## Direct human observation

- Mars was confirmed at the pinned address with its listener active.
- The operator entered `/status`, tapped **Send once**, and did not retry.
- The operator directly observed this visible sequence:
  1. `Connecting to server... will send`
  2. `Connect error -16013`
- No HS-A, HS-B, or HS-C status was observed, and no reply arrived.
- No photo or screenshot was captured. Hardware proof failed.

## Network-record limits

An intentionally started 90-second pcap ended before the Send and contains zero
packets. It is a timing miss, not evidence that the iPad sent no packets or that
Mars received none. The pcap is not committed and is not used as network
evidence.

The authoritative Mars service journal independently records seven accepted
connections during the attempt, from 16:41:36Z through 16:41:55Z at
three-second intervals, with no harness protocol observed by the service. The
journal records connection lifecycle, not transmitted byte count. The sanitized
journal facts are in `mars-journal-summary.txt`; private addresses, client
ports, process metadata, host identifiers, absolute paths, and raw provider
logs are omitted.

## Honest comparison

EF23's earlier one-Send M4 run visibly ended at `Connect error -16005`
(`../m4-ipad-ef23-20260809/packet-summary.txt:9-10`). After EF24 restored the
primary connect request timeout from 10 seconds to 45 seconds, this run visibly
ended at `Connect error -16013`. The changed result does not establish a root
cause: EF24 still did not reach HS-A/B/C, produce service-observed harness
protocol, or receive a reply. Its transmitted byte count is unknown.
