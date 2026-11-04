# STRICT CONSTRAINT: NO LOCAL GRADLE BUILDS

Per explicit user instruction:
1. **DO NOT run `./gradlew assemble*` or any local Gradle builds on this host.**
2. All compilation and APK builds are strictly handled via **GitHub Actions** CI/CD (`.github/workflows/build.yml`) or pre-built APKs.
3. `/tmp` must remain untouched.
4. Testing and verification must be done via ADB inspecting live events, logcat, and UI dumps on `192.168.1.40:5555`.
