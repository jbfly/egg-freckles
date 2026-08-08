NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files

.PHONY: all clean

all: tic-tac-toe-a8.pkg

tic-tac-toe-a8.pkg: Main.newt tic-tac-toe-a8.nprj
	LD_LIBRARY_PATH="$(NEWTON_DEV)/prefix/lib:$${LD_LIBRARY_PATH}" \
		"$(TNTK)" -P "$(PLATFORMS)" -c tic-tac-toe-a8.nprj

clean:
	rm -f tic-tac-toe-a8.pkg
