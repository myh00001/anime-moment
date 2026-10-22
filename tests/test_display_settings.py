import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from display_settings import DEFAULT_SETTINGS,cover_geometry,load_settings,save_settings,validate_settings,output_dimensions


class DisplaySettingsTests(unittest.TestCase):
    def test_default_and_missing_file_use_highest_supported_output(self):
        self.assertEqual(max(DEFAULT_SETTINGS['width'],DEFAULT_SETTINGS['height']),1920)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_settings(Path(directory)/'missing.json'),DEFAULT_SETTINGS)

    def test_resolution_keeps_source_field_of_view(self):
        for width,height in [(1920,1080),(1080,1920),(1600,1200)]:
            for edge in [640,960,1280,1920]:
                out_width,out_height=output_dimensions(width,height,edge)
                self.assertEqual(max(out_width,out_height),edge)
                self.assertAlmostEqual(out_width/out_height,width/height,delta=.01)
                # The same normalized source coordinates remain visible after
                # display cover regardless of the output pixel count.
                x,y,scale=cover_geometry(1080,1920,out_width,out_height)
                visible_fraction_x=1080/(out_width*scale)
                expected=min(1,(1080/1920)/(width/height))
                self.assertAlmostEqual(visible_fraction_x,expected,delta=.002)

    def test_cover_landscape_and_portrait_without_borders(self):
        for screen in [(1920,1080),(1080,1920),(1024,768),(540,960),(3840,1080)]:
            x,y,scale=cover_geometry(*screen,960,540)
            self.assertLessEqual(x,0)
            self.assertLessEqual(y,0)
            self.assertGreaterEqual(960*scale+1e-8,screen[0])
            self.assertGreaterEqual(540*scale+1e-8,screen[1])
            self.assertTrue(abs(x)<1e-8 or abs(y)<1e-8)

    def test_cover_rejects_zero_sized_drawable(self):
        with self.assertRaises(ValueError):cover_geometry(0,1920,960,540)

    def test_settings_survive_restart(self):
        settings={'width':540,'height':960,'rotation':90,'mirror':False}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            self.assertEqual(save_settings(path,settings),settings)
            self.assertEqual(load_settings(path),settings)
            self.assertFalse(path.with_name(path.name+'.tmp').exists())

    def test_reject_invalid_sizes_angles_and_types(self):
        for key,value in [('width',0),('width',961),('height',1924),('rotation',45),('rotation',True),('mirror','false')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                validate_settings(dict(DEFAULT_SETTINGS,**{key:value}))

    def test_invalid_file_falls_back_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            for contents in ['{bad json',json.dumps({'width':0}),json.dumps(['invalid'])]:
                path.write_text(contents,encoding='utf-8')
                self.assertEqual(load_settings(path),DEFAULT_SETTINGS)
                self.assertEqual(path.read_text(encoding='utf-8'),contents)

    def test_invalid_apply_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json';save_settings(path,DEFAULT_SETTINGS)
            with self.assertRaises(ValueError):save_settings(path,{'height':0})
            self.assertEqual(load_settings(path),DEFAULT_SETTINGS)


if __name__=='__main__':unittest.main()
