#!/usr/bin/env python3
# encoding: utf-8
import base64
import re
from urlparse import urljoin

from Crypto.Cipher import AES

from books.base import BaseComicBook
from bs4 import BeautifulSoup
from lib.autodecoder import AutoDecoder
from lib.urlopener import URLOpener


def decrypt_manhuadui(raw):
    """
    https://www.manhuadui.com/js/decrypt20180904.js
    """
    obj = AES.new('123456781234567G', AES.MODE_CBC, 'ABCDEF1G34123412')
    return obj.decrypt(base64.b64decode(raw))


class ManHuaDuiBaseBook(BaseComicBook):
    accept_domains = ("https://www.manhuadui.com/", )
    host = "https://www.manhuadui.com/"

    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host)
        chapterList = []

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn(
                "fetch comic page failed: {} (status code {}, content {})".format(
                    url, result.status_code, result.content
                )
            )
            return chapterList

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        soup = BeautifulSoup(content, "html.parser")
        ul_soup = soup.find("ul", {"id": "chapter-list-1"})

        for link in ul_soup.find_all("a"):
            chapterList.append((link.get("title"), urljoin(self.host, link.get("href"))))
        return chapterList

    def getImgList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(url)

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn(
                "fetch comic page failed: {} (status code {}, content {})".format(
                    url, result.status_code, result.content
                )
            )
            return []

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )
        images_match = re.search(r'chapterImages = "(.+?)"', content)
        if not images_match:
            self.log.warn("Can't find chapterImages from {}".format(url))
            return []
        images = re.findall('"(.+?)"', decrypt_manhuadui(images_match.group(1)))

        img_path_match = re.search(r'chapterPath = "(.+?)"', content)
        if not img_path_match:
            self.log.warn("Can't find chapterPath from {}".format(url))
            return []
        img_base_path = urljoin("https://res.333dm.com", img_path_match.group(0))
        return [urljoin(img_base_path, x) for x in images]
