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

    def test_live_rt_series_score_percent_format(self):
        # Actual field names from a Nov 12 RT series page response.
        html = ('<script id="media-scorecard-json" type="application/json">'
                '{"audienceScore":{"scorePercent":"97%"},'
                '"criticsScore":{"scorePercent":"96%","reviewCount":250,'
                '"title":"Avg. Tomatometer"},'
                '"overlay":{"mediaType":"TvSeries"}}'
                '</script>')
        self.assertEqual(parse_tv_critic_score(html), (True, '96%'))

    def test_does_not_confuse_audience_for_critic_score(self):
        html = ('<script id="media-scorecard-json">'
                '{"audienceScore":{"scorePercent":"97%"},'
                '"criticsScore":{"scorePercent":""},'
                '"overlay":{"mediaType":"TvSeries"}}'
                '</script>')
        self.assertEqual(parse_tv_critic_score(html), (True, None))

    def test_zero_and_out_of_range_scores(self):
        for score, expected in [('0%', '0%'), ('100%', '100%'),
                                ('101%', None), ('abc', None)]:
            html = ('<script id="media-scorecard-json">'
                    '{"criticsScore":{"scorePercent":"' + score + '"},'
                    '"overlay":{"mediaType":"TvSeries"}}'
                    '</script>')
            self.assertEqual(parse_tv_critic_score(html), (True, expected))

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
