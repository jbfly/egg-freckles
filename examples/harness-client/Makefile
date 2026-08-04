NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files

.PHONY: all check clean

all: egg-freckles.pkg

egg-freckles.pkg: Main.newt egg-freckles.nprj
	LD_LIBRARY_PATH="$(NEWTON_DEV)/prefix/lib:$${LD_LIBRARY_PATH}" \
		"$(TNTK)" -P "$(PLATFORMS)" -c egg-freckles.nprj

check: egg-freckles.pkg
	test -s egg-freckles.pkg

clean:
	rm -f egg-freckles.pkg
