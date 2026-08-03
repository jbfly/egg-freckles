# downloads/ — Newton Internet Enabler distributions and study sources

```sh
./downloads/fetch-downloads.sh
```

Only the script, `SHA256SUMS`, this README, and one GPL tarball are tracked.
The eight Apple NIE archives are Apple copyright and are fetched from
[UNNA](http://www.unna.org/), then checked against `SHA256SUMS`.

| File | What it is | Source |
|---|---|---|
| `NIE_1.1_Developer.sea.hqx`, `NIE_1.1_Packages.sea.hqx`, `NIE_Developer_Goodies.sea.hqx`, `Newton_Internet_Enabler.sea.hqx` | Newton Internet Enabler 1.1, Mac BinHex self-extracting distributions | UNNA `/unna/apple/development/NIE1.x/` |
| `NIE10.ZIP`, `NIE11.EXE`, `NIEDVLPR.EXE`, `NIEGOODS.ZIP` | the same NIE 1.0/1.1 material in its Windows form; `NIEDVLPR.EXE` is also where `refs/nie11/` comes from | UNNA, same directory |
| `NIM-source.zip` | NewtonIM — a Jabber client whose NewtonScript source is the clearest working example of the NIE TCP endpoint lifecycle (`docs/unna-survey.md`, rank 3) | UNNA `/unna/internet/NewtonIM/` |
| `unixnpi-1.1.3.tar.gz` | **tracked, not fetched.** Richard C. Li's UnixNPI, GPL C source for the Newton package-upload protocol; redistributable, 21 KB, and the reference `runtime/newton_backup.py` had to match | UNNA `/unna/unix/` |

`recovery/` is a separate set with its own fetcher — see
`downloads/recovery/README.md` and `scripts/fetch-recovery-packages.sh`.

Every URL was re-checked on 2026-08-03: HTTP 200, and every downloaded file
hashed identically to the copy this repo was developed against. UNNA's HTTPS
chain does not validate against a stock Linux trust store, so the script uses
plain HTTP and relies on `SHA256SUMS` for integrity.
