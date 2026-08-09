# S12 Android Vehicle Sound Controller v0.8

This is a minimal Debug-signed APK that sends C/synthetic vehicle-state JSON to the PC runtime WebSocket. It has only Start, Stop and Send Vehicle State controls. It does not render audio, read vehicle data, access CAN/OBD, use ESP32/I2S, store secrets, or claim vehicle deployment.

## Local PC simulation endpoint

Start the PC server on the host loopback interface:

    python tools/sound_sim/s12/acoustic_demo/run_runtime_server.py --port 8765

For an Android Emulator, use `ws://10.0.2.2:8765/state`; this maps to the PC loopback interface. Physical Android-device networking is intentionally out of scope.

## Offline debug build

    set ANDROID_HOME=C:\Users\Admin\AppData\Local\Android\Sdk
    C:\Users\Admin\.gradle\wrapper\dists\gradle-8.9-bin\90cnw93cvbtalezasaz0blq0a\gradle-8.9\bin\gradle.bat --offline :app:assembleDebug

The generated `app-debug.apk` is a standard Android Debug-signed artifact. It is not committed, and no project signing key is included.
