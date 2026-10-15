#!/usr/bin/env bash
set -euo pipefail
src_dir="$(cd "$(dirname "$0")" && pwd)"
sdk_dir="${ANDROID_SDK_ROOT:?Set ANDROID_SDK_ROOT}"
build_dir="${CAMP_APK_BUILD_DIR:?Set CAMP_APK_BUILD_DIR outside the source checkout}"
build_tools="$sdk_dir/build-tools/36.1.0"
android_jar="$sdk_dir/platforms/android-36/android.jar"
mkdir -p "$build_dir/classes" "$build_dir/generated" "$build_dir/dex"
"$build_tools/aapt2" compile --dir "$src_dir/res" -o "$build_dir/resources.zip"
"$build_tools/aapt2" link -o "$build_dir/unsigned.apk" --manifest "$src_dir/AndroidManifest.xml" -I "$android_jar" --java "$build_dir/generated" "$build_dir/resources.zip"
find "$src_dir/src" "$build_dir/generated" -name '*.java' > "$build_dir/sources.txt"
javac --release 8 -classpath "$android_jar" -d "$build_dir/classes" @"$build_dir/sources.txt"
jar cf "$build_dir/classes.jar" -C "$build_dir/classes" .
"$build_tools/d8" --min-api 29 --lib "$android_jar" --output "$build_dir/dex" "$build_dir/classes.jar"
(cd "$build_dir/dex" && zip -q "$build_dir/unsigned.apk" classes.dex)
"$build_tools/zipalign" -p -f 4 "$build_dir/unsigned.apk" "$build_dir/aligned.apk"
"$build_tools/apksigner" sign --ks "${CAMP_APK_KEYSTORE:?Set CAMP_APK_KEYSTORE}" --ks-key-alias campsite-journal --ks-pass env:CAMP_APK_STOREPASS --key-pass env:CAMP_APK_STOREPASS --out "$build_dir/campsite-journal.apk" "$build_dir/aligned.apk"
"$build_tools/apksigner" verify --verbose "$build_dir/campsite-journal.apk"
python3 - "$src_dir/AndroidManifest.xml" "$build_dir/campsite-journal.apk" "$build_dir/android-version.json" <<'PY'
import hashlib,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
manifest=ET.parse(sys.argv[1]).getroot();android='{http://schemas.android.com/apk/res/android}'
metadata={'version_code':int(manifest.attrib[android+'versionCode']),'version_name':manifest.attrib[android+'versionName'],'sha256':hashlib.sha256(Path(sys.argv[2]).read_bytes()).hexdigest()}
Path(sys.argv[3]).write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
PY
