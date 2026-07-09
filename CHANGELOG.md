# Changelog

## Unreleased

- Poll AnkiDroid's forwarded CDP endpoint until the reviewer WebView target is
  registered instead of failing when the first `/json` response is still empty.
- Accept AnkiDroid's required V2 scheduler upgrade for directly seeded legacy
  collections, and restrict fallback deck taps to actual deck rows so modal help
  links cannot divert the smoke run into Chrome.
- Make `android-smoke --clear-app-data` seed a disposable AnkiDroid collection
  directly from a single configured APKG. This avoids brittle shell-driven
  Android import intents while still testing the real AnkiDroid WebView.
- Give AnkiDroid external-storage cleanup enough time for media-heavy deck
  fixtures.
- Launch AnkiDroid through its exported intent handler instead of its
  non-exported deck picker activity.

## 0.5.0

- Add `webkit-smoke` for iOS/AnkiMobile-engine card rendering through Playwright
  WebKit, using Anki-style HTML injection and built-in deck probe card samples.
- Add opt-in `android-smoke` and `android-dockerfile` surfaces for AnkiDroid
  emulator smoke tests over adb and raw Chrome DevTools Protocol. Android SDK,
  emulator, and APK installation stay explicit environment/CI responsibilities.
- Add cross-engine card smoke config keys for WebKit/Android selectors, device,
  timeout, Android image/spec, and AnkiDroid APK source.
