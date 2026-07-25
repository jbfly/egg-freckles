NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files

.PHONY: all check clean

all: harness-loader.pkg

harness-loader.pkg: Main.newt harness-loader.nprj
	LD_LIBRARY_PATH="$(NEWTON_DEV)/prefix/lib:$${LD_LIBRARY_PATH}" \
		"$(TNTK)" -P "$(PLATFORMS)" -c harness-loader.nprj

check: harness-loader.pkg
	test -s harness-loader.pkg

clean:
	rm -f harness-loader.pkg
