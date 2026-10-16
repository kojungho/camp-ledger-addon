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

    def test_unified_camp_note_metadata_and_capture_asset(self):
        import zipfile
        downloads=ROOT/'camp_ledger/journal/static/downloads'
        meta=json.loads((downloads/'android-version.json').read_text())
        manifest=ET.parse(ROOT/'android/camp-note/AndroidManifest.xml').getroot()
        android='{http://schemas.android.com/apk/res/android}'
        self.assertEqual(meta['version_code'],int(manifest.attrib[android+'versionCode']))
        self.assertEqual(meta['version_name'],manifest.attrib[android+'versionName'])
        apk=(downloads/'camp-note.apk').read_bytes()
        self.assertEqual(meta['sha256'],hashlib.sha256(apk).hexdigest())
        self.assertEqual(apk,(downloads/'campsite-journal.apk').read_bytes())
        activity=next(a for a in manifest.findall('application/activity') if a.attrib[android+'name'].endswith('PlatformActivity'))
        self.assertEqual(activity.attrib[android+'exported'],'false')
        application=manifest.find('application');self.assertEqual(application.attrib[android+'name'],'.CampNoteApplication')
        profiles=[a for a in manifest.findall('application/activity') if a.attrib[android+'name'] in ('.PlatformAccountOneActivity','.PlatformAccountTwoActivity')]
        self.assertEqual(len(profiles),2);self.assertEqual(len({a.attrib[android+'process'] for a in profiles}),2)
        self.assertTrue(all(a.attrib[android+'exported']=='false' for a in profiles))
        with zipfile.ZipFile(downloads/'camp-note.apk') as archive:
            for asset in ('platform-capture.js','platform-scroll.js'):
                self.assertEqual(archive.read('assets/'+asset),(ROOT/'android/camp-note/assets'/asset).read_bytes())
