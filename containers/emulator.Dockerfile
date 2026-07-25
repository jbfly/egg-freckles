FROM debian:trixie-slim AS builder

ARG EINSTEIN_COMMIT=f5544a039fc3964e18b217ccffa030c6bf1e4044
ARG CDCL_COMMIT=46aef5750e0275380c7b9488626a3294643d8504
ARG TNTK_COMMIT=f9f3f5dd2444997f1febd5648f60ec71a3a08afd
ARG NEWT0_COMMIT=025bc268742c493fb1ce2dcea10ebeb4846652cf

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        autoconf \
        bison \
        build-essential \
        ca-certificates \
        cmake \
        flex \
        git \
        libasound2-dev \
        libexpat1-dev \
        libffi-dev \
        libglu1-mesa-dev \
        libpango1.0-dev \
        libpulse-dev \
        libreadline-dev \
        libx11-dev \
        libxcursor-dev \
        libxext-dev \
        libxfixes-dev \
        libxft-dev \
        libxinerama-dev \
        ninja-build \
    && rm -rf /var/lib/apt/lists/*

COPY containers/patches /patches

RUN git clone https://github.com/pguyot/Einstein.git /src/Einstein \
    && git -C /src/Einstein checkout "${EINSTEIN_COMMIT}" \
    && git -C /src/Einstein apply /patches/einstein-gcc.patch \
    && git -C /src/Einstein apply /patches/einstein-dns.patch \
    && git -C /src/Einstein apply /patches/einstein-tcp-send-after-ack.patch \
    && git -C /src/Einstein apply /patches/einstein-tcp-newton-payload.patch \
    && git -C /src/Einstein apply /patches/einstein-tcp-native-diag.patch \
    && git -C /src/Einstein apply /patches/einstein-tcp-inbound-diag.patch \
    && git -C /src/Einstein apply /patches/einstein-nie-rom-trace.patch \
    && git -C /src/Einstein apply /patches/einstein-control-socket.patch \
    && cmake -S /src/Einstein -B /build/Einstein -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DEINSTEIN_FLTK_FRONTEND=ON \
        -DFLTK_BACKEND_WAYLAND=OFF \
    && cmake --build /build/Einstein --target Einstein --parallel 4

RUN git clone https://github.com/ekoeppen/cDCL.git /src/cDCL \
    && git -C /src/cDCL checkout "${CDCL_COMMIT}" \
    && cmake -S /src/cDCL -B /build/cDCL -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
    && cmake --build /build/cDCL --parallel 2 \
    && cmake --install /build/cDCL

RUN git clone https://github.com/ekoeppen/NEWT0.git /src/NEWT0 \
    && git -C /src/NEWT0 checkout "${NEWT0_COMMIT}" \
    && git clone https://github.com/ekoeppen/tntk.git /src/tntk \
    && git -C /src/tntk checkout "${TNTK_COMMIT}" \
    && git -C /src/tntk apply /patches/tntk-gcc.patch \
    && cmake -S /src/tntk -B /build/tntk -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_FLAGS="-DHAS_C99_LONGLONG=1 -DTARGET_RT_BIG_ENDIAN=0 -DTARGET_RT_LITTLE_ENDIAN=1" \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DCMAKE_PREFIX_PATH=/usr/local \
        -DFETCHCONTENT_SOURCE_DIR_NEWT0=/src/NEWT0 \
    && cmake --build /build/tntk --parallel 2 \
    && cmake --install /build/tntk


FROM debian:trixie-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        imagemagick \
        libasound2 \
        libcairo2 \
        libffi8 \
        libfontconfig1 \
        libfreetype6 \
        libice6 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpulse0 \
        libreadline8t64 \
        libsm6 \
        libx11-6 \
        libxcursor1 \
        libxext6 \
        libxfixes3 \
        libxft2 \
        libxinerama1 \
        libxrender1 \
        make \
        novnc \
        openbox \
        pulseaudio \
        python3 \
        tini \
        websockify \
        x11-utils \
        x11vnc \
        xdotool \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/Einstein/Einstein /usr/local/bin/einstein
COPY --from=builder /usr/local/bin/tntk /usr/local/bin/tntk
COPY --from=builder /usr/local/lib/libDCL.so /usr/local/lib/libDCL.so
COPY containers/einstein.prefs /opt/newton/config/einstein.prefs
COPY containers/emulator-entrypoint.sh /opt/newton/bin/emulator-entrypoint
COPY emulator/control.py /opt/newton/bin/emulator-control

RUN useradd --create-home --uid 1000 newton \
    && mkdir -p /state /rom /packages /platforms \
    && chown newton:newton /state \
    && chmod 0755 /opt/newton/bin/emulator-entrypoint \
    && ldconfig

USER newton

ENV DISPLAY=:99 \
    HOME=/state/home \
    LD_LIBRARY_PATH=/usr/local/lib \
    NEWTON_SCREEN_WIDTH=320 \
    NEWTON_SCREEN_HEIGHT=480 \
    NEWTON_SCREEN_TOP=78 \
    PYTHONUNBUFFERED=1 \
    XDG_RUNTIME_DIR=/tmp/newton-runtime

EXPOSE 6080 8080

ENTRYPOINT ["/usr/bin/tini", "--", "/opt/newton/bin/emulator-entrypoint"]
