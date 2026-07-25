NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files

.PHONY: all check clean

all: network-probe.pkg

network-probe.pkg: Main.newt network-probe.nprj
	LD_LIBRARY_PATH="$(NEWTON_DEV)/prefix/lib:$${LD_LIBRARY_PATH}" \
		"$(TNTK)" -P "$(PLATFORMS)" -c network-probe.nprj

check: network-probe.pkg
	test -s network-probe.pkg

clean:
	rm -f network-probe.pkg
