# -*- coding: utf-8 -*-
import logging
from scrapy.http import Request
from scrapy.selector import Selector
from scrapy.spider import Spider
import urlparse
from raw.scraper.items import LibraryAgenda, LibraryHansard, LibraryResultPage


logger = logging.getLogger('legcowatch')


class LegcoLibrarySpider(Spider):
    """
    Common methods for library archive pages
    """
    def pagination_links(self, response):
        # Get the pagination links
        # There are two pagination sections, so use only the first one
        sel = Selector(response)
        more_pages = sel.xpath('//td[@class="browsePager"]')[0]
        page_links = more_pages.xpath('./a[@href]/@href').extract()
        for link in page_links:
            absolute_url = urlparse.urljoin(response.url, link.strip())
            # Expects self.parse to be the main parsing loop for browse index pages
            req = Request(absolute_url, callback=self.parse)
            yield req


class LibraryAgendaSpider(LegcoLibrarySpider):
    name = "library_agenda"
    # allowed_domains = ["library.legco.gov.hk"]
    start_urls = [
        # Older agendas are in HTML
        # Newer agendas are in doc format.
        # The break happens on 2004.10.06 (entry 299)- this is the first doc agenda.
        # http://library.legco.gov.hk:1080/search~S10?/tAgenda+for+the+meeting+of+the+Legislative+Council/tagenda+for+the+meeting+of+the+legislative+council/289%2C670%2C670%2CB/frameset&FF=tagenda+for+the+meeting+of+the+legislative+council+2004+++10+++06&1%2C1%2C
        # Thus the last old HTML agenda is on 2004.07.13
        # http://library.legco.gov.hk:1080/search~S10?/tAgenda+for+the+meeting+of+the+Legislative+Council/tagenda+for+the+meeting+of+the+legislative+council/289%2C670%2C670%2CB/frameset&FF=tagenda+for+the+meeting+of+the+legislative+council+2004+++07+++13&1%2C1%2C
        # Some even newer doc agendas has an "Internet version" as well - cannot see what the differences are compared to its normal version.
        
        # below is an old link - only covers the period up to the end of 2014
        #"http://library.legco.gov.hk:1080/search~S10?/tAgenda+for+the+meeting+of+the+Legislative+Council/tagenda+for+the+meeting+of+the+legislative+council/1%2C670%2C670%2CB/browse",
        # new link. Covers up to current date.
        "http://library.legco.gov.hk:1080/search~S10/?searchtype=t&searcharg=Agenda+for+the+meeting+of+the+Legislative+Council"
    ]

    def parse(self, response):
        sel = Selector(response)
        entries = sel.xpath('//tr[@class="browseEntry"]')
        for entry in entries:
            agenda_link = entry.xpath('./td[@class="browseEntryData"]/a[@href]')
            if len(agenda_link) != 1:
                # Should have exactly one link.  Log it if not.
                pass
            link_url = agenda_link.xpath('./@href').extract()[0]
            link_title = agenda_link.xpath('./text()').extract()[0]
            absolute_url = urlparse.urljoin(response.url, link_url.strip())
            # Log the individual result page
            page = LibraryResultPage(
                title=link_title,
                link=absolute_url,
                browse_url=response.url,
                document_type="Agenda"
            )
            yield page

            # Then follow through the request
            req = Request(absolute_url, callback=self.parse_agenda_page)
            yield req

        for link in self.pagination_links(response):
            yield link

    def parse_agenda_page(self, response):
        sel = Selector(response)

        bib_info = sel.xpath('//td[@class="bibInfoData"]/node()/text()').extract()
        title_en = bib_info[2].strip()
        title_cn = bib_info[3].strip()
        links = sel.xpath('//table[@class="bibLinks"]//a')
        links_href = links.xpath('./@href').extract()
        file_urls = [urlparse.urljoin(response.url, l.strip()) for l in links_href]
        links_title = [xx.strip() for xx in links.xpath('.//text()').extract()]
        # Sometimes there are more than just two records, such as for appendices
        # See http://library.legco.gov.hk:1080/search~S10?/tAgenda+for+the+meeting+of+the+Legislative+Council/tagenda+for+the+meeting+of+the+legislative+council/565%2C670%2C670%2CB/frameset&FF=tagenda+for+the+meeting+of+the+legislative+council+2012+++02+++29&1%2C1%2C
        links = zip(links_title, file_urls)

        item = LibraryAgenda(
            title_en=title_en,
            title_cn=title_cn,
            links=links,
            file_urls=file_urls,
            source_url=response.url
        )
        logger.info('Scraped {}'.format(title_en))
        yield item


class LibraryHansardSpider(LegcoLibrarySpider):
    name = "library_hansard"
    start_urls = [
                  #Link to all hansards date back to 1858.01.05, a few hundred pages
                  #Almost all hansards are in DOC format, but the structure inside can be very different
                  #Takes a long time to scrape just a few hansards, so watch out.
                  
                  #All hansards
                  #'http://library.legco.gov.hk:1080/search~S10/?searchtype=t&searcharg=Hong+Kong+Hansard'
                  
                  #Limit to post-20xx for quick test
                  'http://library.legco.gov.hk:1080/search~S10?/tHong+Kong+Hansard/thong+kong+hansard;Ya=2010/1%2C105%2C0%2CB/browse'
                  ]
    def parse(self, response):
        sel = Selector(response)
        entries = sel.xpath('//tr[@class="browseEntry"]')
        for entry in entries:
            hansard_link = entry.xpath('./td[@class="browseEntryData"]/a[@href]')
            if len(hansard_link) != 1:
                # Should have exactly one link.  Log it if not.
                pass
            #e.g. '/search~S10?/tHong+Kong+Hansard/thong+kong+hansard;Ya=2013;M=5;T=Hong+Kong+Hansard/1%2C105%2C0%2CB/frameset&FF=thong+kong+hansard;Ya=2013;M=5;T=Hong+Kong+Hansard&1%2C105%2C'
            link_url = hansard_link.xpath('./@href').extract()[0]
            # can be 'Official Record of Proceedings, yyyy.mm.dd.',
            # or 'Hong Kong Hansard, yyyy.mm.dd.'
            # depending on search string
            link_title = hansard_link.xpath('./text()').extract()[0] 
            absolute_url = urlparse.urljoin(response.url, link_url.strip())
            # Log the individual result page
            page = LibraryResultPage(
                title=link_title,
                link=absolute_url,
                browse_url=response.url,
                document_type="Hansard"
            )
            yield page

            # Then follow through the request
            req = Request(absolute_url, callback=self.parse_hansard_page)
            yield req

        for link in self.pagination_links(response):
            yield link
    
    def parse_hansard_page(self, response):
        sel = Selector(response)

        bib_info = sel.xpath('//td[@class="bibInfoData"]/node()/text()').extract()
        title_en = bib_info[2].strip()
        title_cn = bib_info[3].strip()
        links = sel.xpath('//table[@class="bibLinks"]//a')
        links_href = links.xpath('./@href').extract()
        file_urls = [urlparse.urljoin(response.url, l.strip()) for l in links_href]
        links_title = [xx.strip() for xx in links.xpath('.//text()').extract()]
        # Normally there are 3 links: Floor, English and Chinese(中文版), in DOC format
        # But a lot of exceptions, especially for older records
        # Some longer records spread more that one DOC,
        # newer records may only have floor version available (sometimes the name floor is omitted),
        # some hansard may have appendix (image in DOC file)
        # and in a rare case on 2006.08.05 all links link to PDFs, probably a mistake
        links = zip(links_title, file_urls)

        item = LibraryHansard(
            title_en=title_en,
            title_cn=title_cn,
            links=links,
            file_urls=file_urls,
            source_url=response.url
        )
        logger.info(u'Scraped {}'.format(title_en))
        yield item