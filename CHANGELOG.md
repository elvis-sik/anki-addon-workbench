# Changelog

## 0.5.0

- Add `webkit-smoke` for iOS/AnkiMobile-engine card rendering through Playwright
  WebKit, using Anki-style HTML injection and built-in deck probe card samples.
- Add opt-in `android-smoke` and `android-dockerfile` surfaces for AnkiDroid
  emulator smoke tests over adb and raw Chrome DevTools Protocol.
- Add cross-engine card smoke config keys for WebKit/Android selectors, device,
  timeout, Android image/spec, and AnkiDroid APK source.
