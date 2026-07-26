NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files

.PHONY: all clean

all: harness-tools-persistent.pkg

harness-tools-persistent.pkg: Main.newt harness-tools-persistent.nprj
	LD_LIBRARY_PATH="$(NEWTON_DEV)/prefix/lib:$${LD_LIBRARY_PATH}" \
		"$(TNTK)" -P "$(PLATFORMS)" -c harness-tools-persistent.nprj

clean:
	rm -f harness-tools-persistent.pkg
