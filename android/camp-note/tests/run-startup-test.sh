#!/usr/bin/env bash
set -euo pipefail
src_dir="$(cd "$(dirname "$0")" && pwd)"
sdk_dir="${ANDROID_SDK_ROOT:?Set ANDROID_SDK_ROOT}"
build_dir="${CAMP_ANDROID_TEST_DIR:?Set CAMP_ANDROID_TEST_DIR outside the checkout}"
serial="${CAMP_ANDROID_TEST_SERIAL:?Select a test emulator explicitly}"
build_tools="$sdk_dir/build-tools/36.1.0"
android_jar="$sdk_dir/platforms/android-36/android.jar"
mkdir -p "$build_dir/classes" "$build_dir/dex"
"$build_tools/aapt2" link -o "$build_dir/unsigned.apk" --manifest "$src_dir/AndroidManifest.xml" -I "$android_jar"
javac --release 8 -classpath "$android_jar" -d "$build_dir/classes" "$src_dir/"*.java
jar cf "$build_dir/classes.jar" -C "$build_dir/classes" .
"$build_tools/d8" --min-api 29 --lib "$android_jar" --output "$build_dir/dex" "$build_dir/classes.jar"
(cd "$build_dir/dex" && zip -q "$build_dir/unsigned.apk" classes.dex)
"$build_tools/zipalign" -p -f 4 "$build_dir/unsigned.apk" "$build_dir/aligned.apk"
"$build_tools/apksigner" sign --ks "${CAMP_APK_KEYSTORE:?Set CAMP_APK_KEYSTORE}" --ks-key-alias campsite-journal --ks-pass env:CAMP_APK_STOREPASS --key-pass env:CAMP_APK_STOREPASS --out "$build_dir/test.apk" "$build_dir/aligned.apk"
"$sdk_dir/platform-tools/adb" -s "$serial" install -r "$build_dir/test.apk"
for runner in StartupTest ScanTest ProfileOneTest ProfileTwoTest ProfileOneTest; do
  "$sdk_dir/platform-tools/adb" -s "$serial" shell am instrument -w "co.kr.badara.campsitejournal.test/co.kr.badara.campsitejournal.test.$runner" | tee "$build_dir/$runner-result.txt"
  rg -q 'INSTRUMENTATION_RESULT: result=PASS' "$build_dir/$runner-result.txt"
done
