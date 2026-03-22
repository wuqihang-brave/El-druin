import unittest
from news_aggregator import NewsAggregator
from event_extractor import EventExtractor

class TestNewsExtraction(unittest.TestCase):

    def setUp(self):
        self.aggregator = NewsAggregator()
        self.extractor = EventExtractor()

    def test_news_aggregation(self):
        # Test case for news aggregation
        news = self.aggregator.aggregate_news(sources=['source1', 'source2'])
        self.assertGreater(len(news), 0, "No news aggregated!")
        self.assertIn('expected_headline', [item['headline'] for item in news], "Expected headline not found!")

    def test_event_extraction(self):
        # Test case for event extraction
        sample_text = "Breaking: a significant event has occurred..."
        events = self.extractor.extract_events(sample_text)
        self.assertGreater(len(events), 0, "No events extracted!")
        self.assertIn('expected_event', events, "Expected event not found!")

if __name__ == '__main__':
    unittest.main()