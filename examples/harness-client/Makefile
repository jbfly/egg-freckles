NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files

.PHONY: all check clean

all: harness-client.pkg

harness-client.pkg: Main.newt harness-client.nprj
	LD_LIBRARY_PATH="$(NEWTON_DEV)/prefix/lib:$${LD_LIBRARY_PATH}" \
		"$(TNTK)" -P "$(PLATFORMS)" -c harness-client.nprj

check: harness-client.pkg
	test -s harness-client.pkg

clean:
	rm -f harness-client.pkg
