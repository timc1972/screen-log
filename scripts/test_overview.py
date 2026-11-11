import unittest
from sync_trakt import build, safe_overview


class OverviewTests(unittest.TestCase):
    def test_overview_prefers_trakt_and_normalizes_whitespace(self):
        self.assertEqual(safe_overview({'overview': '  An  exciting\\n adventure. '},
                                       {'overview': 'Older'}), 'An exciting adventure.')

    def test_preserves_previous_overview_if_trakt_missing(self):
        self.assertEqual(safe_overview({'overview': None}, {'overview': 'Old synopsis'}),
                         'Old synopsis')

    def test_movie_and_show_descriptions_added(self):
        movie = {'movie': {'ids': {'imdb': 'tt1234567'}, 'title': 'Movie',
                           'overview': 'Film story.'}, 'watched_at': '2026-11-10T00:00:00Z'}
        episode = {'show': {'ids': {'imdb': 'tt2345678'}, 'title': 'Series',
                            'overview': 'Series story.'},
                   'episode': {'season': 1, 'number': 1, 'title': 'Pilot'},
                   'watched_at': '2026-11-10T00:00:00Z'}
        data = build([movie], [episode], {'movies': [], 'shows': []})
        self.assertEqual(data['movies'][0]['overview'], 'Film story.')
        self.assertEqual(data['shows'][0]['overview'], 'Series story.')

    def test_last_known_description_survives_new_missing_metadata(self):
        movie = {'movie': {'ids': {'imdb': 'tt1234567'}, 'title': 'Movie'},
                 'watched_at': '2026-11-10T00:00:00Z'}
        data = build([movie], [], {'movies': [{'id': 'tt1234567', 'overview': 'Saved story.'}],
                                    'shows': []})
        self.assertEqual(data['movies'][0]['overview'], 'Saved story.')


if __name__ == '__main__':
    unittest.main()
