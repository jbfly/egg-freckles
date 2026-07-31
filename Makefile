PODMAN ?= podman
COMPOSE ?= podman-compose
NEWTON_SOURCE_DATE_EPOCH ?= 1767225600
NEWTON_PACKAGE_DIRS := examples/harness-loader examples/harness-client
NEWTON_STAGING_DIR := runtime/staging

.PHONY: check-rootless images server-login server-up server-test emulator-up \
	emulator-stop emulator-instance-up emulator-instance-down emulator-instances \
	toolchain-hello newton-packages status down test

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

status: check-rootless
	$(COMPOSE) --profile emulator --profile tools ps

down: check-rootless
	$(COMPOSE) --profile emulator --profile tools down

test:
	uv run --with pytest pytest -q
