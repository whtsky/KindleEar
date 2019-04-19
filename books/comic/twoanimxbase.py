#!/usr/bin/env python2
# encoding: utf-8

import re

from bs4 import BeautifulSoup
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook


class TwoAniMxBaseBook(BaseComicBook):
    accept_domains = ("http://www.2animx.com",)

    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(addreferer=False, timeout=60)
        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn("fetch comic page failed: %s" % result.status_code)
            return []

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        # try get chapters from html
        soup = BeautifulSoup(content, "lxml")
        chapter_wrapper_soup = soup.find("div", attrs={"id": "oneCon1"})
        if not chapter_wrapper_soup:
            self.log.warn("Can't find chapter wrapper.")
            return []

        chapterList = []
        for chapter_anchor in chapter_wrapper_soup.find_all("a", {"target": "_blank"}):
            chapterList.append(
                (unicode(chapter_anchor.string).strip(), chapter_anchor.get("href"))
            )

        return chapterList

    # 获取漫画图片列表
    def getImgList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(addreferer=False, timeout=60)
        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn("fetch comic page failed: %s" % result.status_code)
            return []

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        # try get chapters from html
        soup = BeautifulSoup(content, "lxml")
        img_soup = soup.find("img", {"id": "ComicPic"})
        if not img_soup:
            self.log.warn("Can't find img")
            return []
        jpg_url = img_soup.get("src")  # type: str
        if not jpg_url.endswith("1.jpg"):
            self.log.warn("Invalid img src: %s" % jpg_url)
            return []

        select_soup = soup.find("select", {"name": "select1"})
        if not select_soup:
            self.log.warn("Can't find page info.")
            return []
        options = select_soup.find_all("option")
        total_page = int(options[-1].get("value"))
        return [jpg_url.replace("1.jpg", "%s.jpg" % (x + 1)) for x in range(total_page)]
