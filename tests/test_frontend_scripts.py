import unittest
from pathlib import Path
from html.parser import HTMLParser
class Scripts(HTMLParser):
 def __init__(self):super().__init__();self.sources=[];self.in_script=False;self.bad=[]
 def handle_starttag(self,tag,attrs):
  if tag=='script':self.in_script=True;self.sources.append(dict(attrs).get('src'))
 def handle_endtag(self,tag):
  if tag=='script':self.in_script=False
 def handle_data(self,text):
  if self.in_script and '<script' in text:self.bad.append(text)
class FrontendScriptsTest(unittest.TestCase):
 def test_external_modules_are_real_script_elements(self):
  for folder in ['static','journal/static']:
   source=(Path(__file__).resolve().parents[1]/'camp_ledger'/folder/'index.html').read_text();parsed=Scripts();parsed.feed(source);self.assertEqual(parsed.bad,[],folder)
   required=['static/app.js','static/hub-controls.js']+(['static/mobile-display.js','static/list-preferences.js'] if folder=='static' else ['static/clipboard-reservation.js'])
   for script in required:self.assertIn(script,parsed.sources)
   self.assertEqual(len(parsed.sources),len(set(parsed.sources)))
 def test_selection_controls_are_static_and_first_in_settings(self):
  source=(Path(__file__).resolve().parents[1]/'camp_ledger/static/index.html').read_text();self.assertEqual(source.count('id="selection-pc-enabled"'),1);self.assertEqual(source.count('id="selection-mobile-enabled"'),1);self.assertLess(source.index('id="ledger-selection-settings"'),source.index('id="main-display-settings"'))
