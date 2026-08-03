PODMAN ?= podman
COMPOSE ?= podman-compose
NEWTON_SOURCE_DATE_EPOCH ?= 1767225600
NEWTON_PACKAGE_DIRS := examples/harness-loader examples/harness-client
NEWTON_STAGING_DIR := runtime/staging
NEWTON_HW_STAGING_DIR := runtime/staging/hardware

.PHONY: check-rootless images server-login server-mcp server-up server-test emulator-up \
	emulator-stop emulator-instance-up emulator-instance-down emulator-instances \
	toolchain-hello newton-packages stage-hw status down test

check-rootless:
	@command -v "$(PODMAN)" >/dev/null || { \
		echo "Podman is not installed. See README.md."; exit 1; \
	}
	@command -v "$(COMPOSE)" >/dev/null || { \
		echo "podman-compose is not installed. See README.md."; exit 1; \
	}
	@test "$$("$(PODMAN)" info --format '{{.Host.Security.Rootless}}')" = true || { \
		echo "Refusing to run: Podman is not rootless."; exit 1; \
	}

images: check-rootless
	$(COMPOSE) build server
	$(COMPOSE) --profile emulator build emulator

server-login: check-rootless
	$(COMPOSE) run --rm server codex login --device-auth

# Registers newton_mcp.py with the codex inside the server container. Writes
# [mcp_servers.newton] into the `codex-home` volume, the same place
# server-login writes auth.json -- run it once per volume, and again after a
# `podman volume rm newton-harness_codex-home`. docs/agent-tools.md.
server-mcp: check-rootless
	$(COMPOSE) run --rm server codex mcp add newton -- python3 /app/newton_mcp.py
	$(COMPOSE) run --rm server codex mcp get newton

server-up: check-rootless
	$(COMPOSE) up -d server

server-test: check-rootless
	NEWTON_FAKE_BACKEND=1 $(COMPOSE) up server

emulator-up: check-rootless
	$(COMPOSE) --profile emulator up -d --build emulator

emulator-stop: check-rootless
	$(COMPOSE) --profile emulator stop emulator

emulator-instance-up: check-rootless
	@COMPOSE="$(COMPOSE)" scripts/emulator-instance.sh up "$(INSTANCE)"

emulator-instance-down: check-rootless
	@COMPOSE="$(COMPOSE)" scripts/emulator-instance.sh down "$(INSTANCE)"

emulator-instances: check-rootless
	@scripts/emulator-instance.sh list

toolchain-hello: check-rootless
	$(COMPOSE) --profile tools run --rm toolchain \
		make -C examples/hello TNTK=/usr/local/bin/tntk PLATFORMS=/platforms

newton-packages:
	@set -eu; \
	for dir in $(NEWTON_PACKAGE_DIRS); do $(MAKE) -B -C "$$dir"; done; \
	mkdir -p "$(NEWTON_STAGING_DIR)"; \
	for pkg in examples/harness-loader/harness-loader.pkg examples/harness-client/harness-client.pkg; do \
		python3 -c 'import pathlib, struct, sys; p=pathlib.Path(sys.argv[1]); d=bytearray(p.read_bytes()); assert len(d) >= 36 and d[:8] == b"package0", "not a Newton package"; d[32:36]=struct.pack(">I", int(sys.argv[2]) + 2082844800); p.write_bytes(d)' "$$pkg" "$(NEWTON_SOURCE_DATE_EPOCH)"; \
		cp "$$pkg" "$(NEWTON_STAGING_DIR)/$${pkg##*/}"; \
	done; \
	cd "$(NEWTON_STAGING_DIR)"; \
	sha256sum harness-loader.pkg harness-client.pkg > SHA256SUMS

# Builds one example dir the same way newton-packages does (forced rebuild,
# same reproducible-build header stamp) and stages it for the ZC40 loader.
# docs/install-paths.md is the row-2 write-up; keep this in sync with it.
# Needs ~/newton-dev/prefix/bin/tntk built with tools/tntk-project-version.patch
# applied out-of-tree -- that is a one-time host setup step, not done here
# (docs/START-HERE.md:96-98: without it every rebuild silently regresses to
# package version 1).
stage-hw:
	@set -eu; \
	test -n "$(PKG)" || { echo "Usage: make stage-hw PKG=examples/<name>"; exit 1; }; \
	dir="$(PKG)"; \
	test -d "$$dir" || { echo "stage-hw: no such directory: $$dir"; exit 1; }; \
	name=$$(basename "$$dir"); \
	pkg="$$dir/$$name.pkg"; \
	$(MAKE) -B -C "$$dir"; \
	test -s "$$pkg" || { echo "stage-hw: build did not produce $$pkg"; exit 1; }; \
	python3 -c 'import pathlib, struct, sys; p=pathlib.Path(sys.argv[1]); d=bytearray(p.read_bytes()); assert len(d) >= 36 and d[:8] == b"package0", "not a Newton package"; d[32:36]=struct.pack(">I", int(sys.argv[2]) + 2082844800); p.write_bytes(d)' "$$pkg" "$(NEWTON_SOURCE_DATE_EPOCH)"; \
	mkdir -p "$(NEWTON_HW_STAGING_DIR)"; \
	cp "$$pkg" "$(NEWTON_HW_STAGING_DIR)/$$name.pkg"; \
	python3 -c 'import hashlib, pathlib, sys; staging = pathlib.Path(sys.argv[1]); name = sys.argv[2]; digest = hashlib.sha256((staging / name).read_bytes()).hexdigest(); sums = staging / "SHA256SUMS"; lines = [l for l in sums.read_text().splitlines() if l.split()[-1] != name] if sums.exists() else []; lines.append(digest + "  " + name); lines.sort(key=lambda l: l.split()[-1]); sums.write_text("\n".join(lines) + "\n")' "$(NEWTON_HW_STAGING_DIR)" "$$name.pkg"; \
	echo "Staged $(NEWTON_HW_STAGING_DIR)/$$name.pkg -- type '$$name.pkg' into the ZC40 loader"

status: check-rootless
	$(COMPOSE) --profile emulator --profile tools ps

down: check-rootless
	$(COMPOSE) --profile emulator --profile tools down

test:
	uv run --with pytest pytest -q
