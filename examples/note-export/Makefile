NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files

.PHONY: all clean

all: note-export.pkg

note-export.pkg: Main.newt note-export.nprj
	LD_LIBRARY_PATH="$(NEWTON_DEV)/prefix/lib:$${LD_LIBRARY_PATH}" \
		"$(TNTK)" -P "$(PLATFORMS)" -c note-export.nprj

clean:
	rm -f note-export.pkg
