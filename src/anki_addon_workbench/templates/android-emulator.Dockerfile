FROM ubuntu:24.04

ARG ANDROID_COMMANDLINE_TOOLS_URL=https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
ARG ANDROID_API_LEVEL=34
ARG ANDROID_SYSTEM_IMAGE_ARCH=x86_64
ARG ANDROID_AVD_NAME=aaw_test
ARG ANKIDROID_APK_URL={{ANKIDROID_APK_URL}}
ARG ANKI_ADDON_WORKBENCH_SPEC={{WORKBENCH_SPEC}}

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=/opt/android-sdk
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/emulator:/usr/lib/jvm/java-17-openjdk-amd64/bin:${PATH}
ENV ANKIDROID_APK=/opt/ankidroid/AnkiDroid.apk
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        openjdk-17-jdk-headless \
        python3 \
        python3-pip \
        unzip \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p "${ANDROID_SDK_ROOT}/cmdline-tools" /tmp/android-tools \
    && curl -fsSL "${ANDROID_COMMANDLINE_TOOLS_URL}" -o /tmp/android-tools/tools.zip \
    && unzip -q /tmp/android-tools/tools.zip -d /tmp/android-tools \
    && mv /tmp/android-tools/cmdline-tools "${ANDROID_SDK_ROOT}/cmdline-tools/latest" \
    && rm -rf /tmp/android-tools

RUN yes | sdkmanager --licenses >/dev/null \
    && sdkmanager \
        "platform-tools" \
        "emulator" \
        "platforms;android-${ANDROID_API_LEVEL}" \
        "system-images;android-${ANDROID_API_LEVEL};google_apis;${ANDROID_SYSTEM_IMAGE_ARCH}" \
    && echo "no" | avdmanager create avd \
        -n "${ANDROID_AVD_NAME}" \
        -k "system-images;android-${ANDROID_API_LEVEL};google_apis;${ANDROID_SYSTEM_IMAGE_ARCH}" \
        -d pixel_6

RUN pip3 install --break-system-packages --no-cache-dir "${ANKI_ADDON_WORKBENCH_SPEC}"

RUN mkdir -p /opt/ankidroid \
    && if [ -n "${ANKIDROID_APK_URL}" ]; then \
        curl -fsSL "${ANKIDROID_APK_URL}" -o "${ANKIDROID_APK}"; \
    fi

WORKDIR /workspace

CMD ["sh", "-lc", "python3 -m anki_addon_workbench android-smoke --start-emulator --avd-name \"${ANDROID_AVD_NAME}\""]
