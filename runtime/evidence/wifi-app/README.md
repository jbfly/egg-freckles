# WiFi/network app emulator proof

## Result

**PASS.** `WifiProof0808R2:jbfly` made an outbound HTTP/1.0 request from NewtonOS in a named Einstein instance to the host listener at `10.42.0.1:18099`, received `WIFI ROUND TRIP WORKS`, and rendered that body on screen.

## Evidence

- Final app source: `Main.newt`.
- Built package: `wifi-proof-0808-r2.pkg`.
- Host listener source: `server.py`.
- Host wire evidence: `server.log` contains peer `10.42.0.1`, `GET /wifi-proof HTTP/1.0`, and the exact sent body.
- Screen proof: `final-network-reply.png`.
- OCR proof: `final-network-reply.txt` contains `WIFI ROUND TRIP WORKS`.
- Build/tool stages: `dev-loop-build-r2.log`, `dev-loop-emulator-r2-after-restart.log`.
- Repository verification: `pytest.log` records `128 passed`.
- Bounded detached emulator stages: `seed-instance.sh` + `emulator-seed.log`, then `restart-instance.sh` + `emulator-restart.log`. Every Compose/Podman stage has a timeout and health has a 90-second deadline.

## Self-correction record

R1 completed the HTTP round trip, but the peer-close exception overwrote the reply with `Endpoint error -16005` (`02-network-reply.png`, `02-network-reply.txt`, `server-r1.log`). R2 added one `done` guard in the endpoint exception handler. After the isolated-instance restart required by a poisoned `ns_eval` probe, R2 rendered the reply and left the emulator healthy with zero restarts.

No physical Newton, Mars host, radio/AP configuration, model override, or secret was used. A canned local endpoint was sufficient; swapping in an LLM relay changes the host endpoint behavior, not the proven Newton TCP/HTTP path.
