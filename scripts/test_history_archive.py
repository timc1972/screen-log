import copy
import unittest
from sync_trakt import merge_archive


class HistoryArchiveTests(unittest.TestCase):
    def setUp(self):
        self.prior = {
            'movies': [
                {'id': 'tt10000', 'title': 'Older movie', 'watchedAt': '2026-11-10T00:00:00Z', 'watches': 2},
                {'id': 'tt20000', 'title': 'Unreported movie', 'watchedAt': '2026-11-09T00:00:00Z', 'watches': 1},
            ],
            'shows': [
                {'id': 'tt31510819', 'title': 'MobLand', 'lastWatchedAt': '2026-11-13T13:51:00Z',
                 'episodes': [
                    {'season': 2, 'episode': 8, 'title': 'We Don\'t Talk Anymore',
                     'watchedAt': '2026-11-07T15:05:00Z'},
                    {'season': 2, 'episode': 9, 'title': 'Nervous Breakdown',
                     'watchedAt': '2026-11-13T13:51:00Z'},
                 ]},
                {'id': 'tt30000', 'title': 'Missing show', 'lastWatchedAt': '2026-11-01T00:00:00Z',
                 'episodes': [{'season': 1, 'episode': 1, 'title': 'Pilot',
                               'watchedAt': '2026-11-01T00:00:00Z'}]},
            ]
        }
        self.current = {
            'movies': [{'id': 'tt10000', 'title': 'Older movie',
                        'watchedAt': '2026-11-08T00:00:00Z', 'watches': 1}],
            'shows': [{'id': 'tt31510819', 'title': 'MobLand',
                       'lastWatchedAt': '2026-11-07T15:05:00Z',
                       'episodes': [{'season': 2, 'episode': 8,
                                     'title': 'We Don\'t Talk Anymore',
                                     'watchedAt': '2026-11-07T15:05:00Z'}]}]
        }

    def test_restore_mobland_episode_from_confirmed_archive(self):
        result = merge_archive(copy.deepcopy(self.current), self.prior)
        mobland = next(show for show in result['shows'] if show['id'] == 'tt31510819')
        self.assertEqual([(ep['season'], ep['episode']) for ep in mobland['episodes']],
                         [(2, 8), (2, 9)])
        self.assertEqual(mobland['lastWatchedAt'], '2026-11-13T13:51:00Z')
        self.assertEqual(mobland['episodes'][1]['title'], 'Nervous Breakdown')

    def test_missing_movie_and_entire_show_are_preserved(self):
        result = merge_archive(copy.deepcopy(self.current), self.prior)
        self.assertEqual(len(result['movies']), 2)
        self.assertEqual(len(result['shows']), 2)
        movie = next(m for m in result['movies'] if m['id'] == 'tt10000')
        self.assertEqual(movie['watches'], 2)
        self.assertEqual(movie['watchedAt'], '2026-11-10T00:00:00Z')

    def test_repeated_sync_does_not_duplicate_episodes(self):
        result = merge_archive(copy.deepcopy(self.current), self.prior)
        again = merge_archive(result, self.prior)
        mobland = next(show for show in again['shows'] if show['id'] == 'tt31510819')
        self.assertEqual(len(mobland['episodes']), 2)

    def test_newer_trakt_watch_is_preferred(self):
        current = copy.deepcopy(self.current)
        current['shows'][0]['episodes'][0]['watchedAt'] = '2026-11-14T12:00:00Z'
        result = merge_archive(current, self.prior)
        mobland = next(show for show in result['shows'] if show['id'] == 'tt31510819')
        self.assertEqual(mobland['lastWatchedAt'], '2026-11-14T12:00:00Z')


if __name__ == '__main__':
    unittest.main()
