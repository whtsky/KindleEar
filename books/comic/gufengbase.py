# -*- coding:utf-8 -*-

# https://github.com/insert0003/zkindlerss/commit/0e7e95e96dc94763ac39bc435b32e89e4da3c03b#diff-56bed09c78e61b0fb43a5bfeab12d3ec

import re
import json

from urlparse import urljoin
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from bs4 import BeautifulSoup


class GuFengBaseBook(BaseComicBook):
    accept_domains = ("https://m.gufengmh8.com", "https://www.gufengmh8.com")
    host = "https://m.gufengmh8.com"

    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        chapterList = []

        url = url.replace("https://www.gufengmh8.com", "https://m.gufengmh8.com")

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn("fetch comic page failed: %s" % result.status_code)
            return chapterList

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        soup = BeautifulSoup(content, "html.parser")
        # <ul class="Drama autoHeight" data-sort="asc" id="chapter-list-1">
        soup = soup.find("ul", {"id": "chapter-list-1"})
        if not soup:
            self.log.warn("chapter-list is not exist.")
            return chapterList

        lias = soup.findAll("a")
        if not lias:
            self.log.warn("chapterList href is not exist.")
            return chapterList

        for li in lias:
            href = urljoin("https://m.gufengmh8.com", li.get("href"))
            chapterList.append((li.get_text().strip(), href))

        return chapterList

    # 获取漫画图片列表
    def getImgList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        imgList = []

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn("fetch comic page failed: %s" % url)
            return imgList

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        # var chapterPath = "images/comic/31/61188/";
        chapter_match = re.search(r'var chapterPath = "(.+?)";', content)
        if not chapter_match:
            self.log.warn("var chapterPath is not exist.")
            return imgList
        chapter_path = chapter_match.group(1)

        # var pageImage = "http://res.gufengmh.com/images/";
        prefix_match = re.search(r'var pageImage = "(.+?)/images/', content)
        if not prefix_match:
            self.log.warn("var chapterImages is not exist.")
            return imgList
        img_prefix = urljoin(prefix_match.group(1), chapter_path)

        # var chapterImages = ["",""];
        images_match = re.search(r"var chapterImages = (\[.+?\]);", content)
        if not images_match:
            self.log.warn("var chapterImages is not exist.")
            return imgList
        content = images_match.group(1)
        images = json.loads(content)

        for img in images:
            imgList.append(urljoin(img_prefix, img))

        return imgList
