import json
import unittest
from pathlib import Path
from filter_calendar import classify, filter_ics, split_ics

CFG=json.loads(Path(__file__).with_name('config.json').read_text())
class FilterTests(unittest.TestCase):
    def test_source_categories(self):
        pairs=[('Consumer Price Index (CPI)','macro_release_cpi','inflation'),('Personal Income & Outlays (PCE)','macro_release_pce','inflation'),('Employment Situation (Nonfarm Payrolls)','macro_release_employment_situation','employment'),('GDP (Second Estimate)','macro_release_gdp','gdp_retail'),('Retail Sales (Advance)','macro_release_retail_sales','gdp_retail'),('ISM Manufacturing PMI (estimated)','ism_manufacturing_pmi','ism_pmi'),('Treasury Auction: 26-Week Bill','treasury_auction','treasury_auction'),('Initial Jobless Claims','macro_release_jobless_claims','jobless_claims'),('Consumer Confidence','consumer_confidence','consumer_confidence'),('Monthly Options Expiration (OPEX)','monthly_opex','options_expiration'),('Quad Witching','quad_witching','options_expiration'),('FOMC Statement & Rate Decision','fomc_statement',None),('FOMC Chair Press Conference','fomc_press_conference',None),('Beige Book','fomc_beige_book',None),('Market Closed — Thanksgiving Day','market_holiday',None),('Early Close (1:00pm ET)','market_early_close',None),('Futures Expiration (/ES)','futures_expiration',None),('Futures Liquidity Roll (/ES)','futures_liquidity_roll',None),('Housing Starts','macro_release_housing_starts',None),('Treasury Quarterly Refunding Announcement','treasury_quarterly_refunding',None)]
        for title,cat,expected in pairs:
            with self.subTest(title=title): self.assertEqual(classify(title,[cat+',impact-high']),expected)
    def test_title_fallback(self):
        for title, expected in [('US CPI','inflation'),('US jobs report','employment'),('VIX futures and options expiration','options_expiration'),('Fed Chair Speech on CPI',None),('US stock market closes early',None),('US state employment and unemployment rate',None),('Consumer Confidence','consumer_confidence')]:
            with self.subTest(title=title): self.assertEqual(classify(title,[]),expected)
    def test_filter(self):
        def ev(title,cat,num):
            return f'BEGIN:VEVENT\r\nSUMMARY:{title}\r\nCATEGORIES:{cat}\r\nUID:original-{num}\r\nDTSTAMP:20261115T000000Z\r\nDTSTART:20261117T133000Z\r\nDESCRIPTION:one\r\n two\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:Alarm\r\nTRIGGER:-PT10M\r\nEND:VALARM\r\nEND:VEVENT\r\n'
        source='BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\nX-WR-CALNAME:Old\r\n'+ev('Retail Sales (Advance)','macro_release_retail_sales',1)+ev('Beige Book','fomc_beige_book',2)+'END:VCALENDAR\r\n'
        out,total,counts,skipped=filter_ics(source,CFG)
        text=out.decode(); self.assertEqual(total,2); self.assertEqual(sum(counts.values()),1)
        self.assertIn('UID:original-1',text); self.assertIn('DTSTART:20261117T133000Z',text)
        self.assertIn('DESCRIPTION:one\r\n two',text); self.assertIn('BEGIN:VALARM',text)
        self.assertNotIn('Beige Book',text); self.assertIn('X-WR-CALNAME:Economic Calendar',text)
        split_ics(text)
        with self.assertRaises(ValueError): filter_ics(source.replace('macro_release_retail_sales','fomc_minutes'),CFG)
    def test_bad_source(self):
        with self.assertRaises(ValueError): filter_ics('<html>Error</html>',CFG)
if __name__=='__main__': unittest.main()
