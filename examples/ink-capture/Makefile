NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files

.PHONY: all clean

all: ink-capture.pkg

ink-capture.pkg: Main.newt ink-capture.nprj
	LD_LIBRARY_PATH="$(NEWTON_DEV)/prefix/lib:$${LD_LIBRARY_PATH}" \
		"$(TNTK)" -P "$(PLATFORMS)" -c ink-capture.nprj

clean:
	rm -f ink-capture.pkg
