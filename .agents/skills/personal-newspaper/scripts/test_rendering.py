"""Exercise actual compact layout and per-page artwork with the installed PDF runtime."""
from pathlib import Path
import shutil
import tempfile
import unittest

import newspaper as n


class RenderTests(unittest.TestCase):
    def test_all_four_games_fit_one_page_with_full_width_art(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            p=n.load(n.ASSETS/'full.profile.json')
            s=n.load(n.ASSETS/'full.snapshot.json')
            e=n.load(n.ASSETS/'full.edition.json')
            p['sections']=[p['sections'][0],{**next(x for x in p['sections'] if x['id']=='games-1'),'games':['crossword','jumble','sudoku','chess']}]
            p['sources']=[p['sources'][0]]
            s['sources']={'calendar':s['sources']['calendar']}
            p['members']=[p['members'][0]]
            p['artwork'].update(mode='one_per_page',comic_people=[],lesson_person_id=None)
            e['pages']=[e['pages'][0],next(x for x in e['pages'] if x['id']=='games-1')]
            e['pages'][0]['image']=dict(e['pages'][1]['image'])
            (root/'demo-art').mkdir()
            shutil.copyfile(n.ASSETS/'demo-art/back.png',root/'demo-art/back.png')
            for name,obj in [('profile',p),('snapshot',s),('edition',e)]:
                n.save(root/(name+'.json'),obj)
            result=n.render(root/'profile.json',root/'snapshot.json',root/'edition.json',root/'rendered')
            self.assertTrue(result['qa']['passed'],result['qa']['errors'])
            self.assertEqual(result['qa']['physical_pages'],2)
            self.assertEqual(len(result['qa']['images']),2)
            self.assertEqual(len(result['qa']['preview_sha256']),2)
            self.assertFalse(n.load(root/'rendered/receipt.json')['visual_review'])
            digest=n.sha256(root/'rendered/newspaper.pdf')
            with self.assertRaises(FileExistsError):
                n.render(root/'profile.json',root/'snapshot.json',root/'edition.json',root/'rendered')
            self.assertEqual(n.sha256(root/'rendered/newspaper.pdf'),digest)


if __name__=='__main__':
    unittest.main()
