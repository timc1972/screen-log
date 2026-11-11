import unittest
from ratings import parse_tv_critic_score


class TVScoreParsingTests(unittest.TestCase):
    def test_multiline_json_script_and_series_critics(self):
        html = '''<html><script
          type="application/json"
          id="media-scorecard-json"
          >{"criticsScore":{"score":"96"},"audienceScore":{"score":"97"},
          "overlay":{"mediaType":"TvSeries"}}</script></html>'''
        self.assertEqual(parse_tv_critic_score(html), (True, '96%'))

    def test_no_reviews_is_not_zero(self):
        html = '<script id="media-scorecard-json">{"criticsScore":{"reviewCount":0},"overlay":{"mediaType":"TvSeries"}}</script>'
        self.assertEqual(parse_tv_critic_score(html), (True, None))

    def test_ignore_season_score(self):
        html = '<script id="media-scorecard-json">{"criticsScore":{"score":"99"},"overlay":{"mediaType":"TvSeason"}}</script>'
        self.assertEqual(parse_tv_critic_score(html), (True, None))

    def test_ignore_audience_score(self):
        html = '<script id="media-scorecard-json">{"audienceScore":{"score":"88"}}</script>'
        self.assertEqual(parse_tv_critic_score(html), (True, None))

    def test_reject_missing_or_invalid_markup(self):
        self.assertEqual(parse_tv_critic_score('<html>None</html>'), (False, None))
        self.assertEqual(parse_tv_critic_score('<script id="media-scorecard-json">{"criticsScore":{"score":"105"}}</script>'), (True, None))


if __name__ == '__main__':
    unittest.main()
