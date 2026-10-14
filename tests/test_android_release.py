import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class AndroidReleaseTest(unittest.TestCase):
    def test_update_metadata_matches_signed_apk_and_manifest(self):
        downloads=ROOT/'camp_ledger/static/downloads'
        meta=json.loads((downloads/'android-version.json').read_text())
        manifest=ET.parse(ROOT/'android/AndroidManifest.xml').getroot()
        android='{http://schemas.android.com/apk/res/android}'
        self.assertEqual(meta['version_code'],int(manifest.attrib[android+'versionCode']))
        self.assertEqual(meta['version_name'],manifest.attrib[android+'versionName'])
        self.assertEqual(meta['sha256'],hashlib.sha256((downloads/'camp-ledger.apk').read_bytes()).hexdigest())
        provider=manifest.find('application/provider')
        self.assertEqual(provider.attrib[android+'exported'],'false')
        self.assertEqual(provider.attrib[android+'grantUriPermissions'],'true')
