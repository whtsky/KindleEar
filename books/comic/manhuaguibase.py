#!/usr/bin/env python3
# encoding: utf-8
# https://www.manhuagui.com或者https://m.manhuagui.com网站的免费漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
# Author: insert0003 <https://github.com/insert0003>
import re, json
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from urlparse import urljoin
from books.base import BaseComicBook
from bs4 import BeautifulSoup
import urllib, urllib2, imghdr
from google.appengine.api import images
from lib.userdecompress import decompressFromBase64
from packer import decode_packed_codes
from itertools import cycle


class ManHuaGuiBaseBook(BaseComicBook):
    accept_domains = (
        "https://www.manhuagui.com",
        "https://m.manhuagui.com",
        "https://tw.manhuagui.com",
    )
    host = "https://tw.manhuagui.com"

    # 获取漫画章节列表
    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host)
        chapterList = []

        url = url.replace("https://m.manhuagui.com", "https://tw.manhuagui.com")
        url = url.replace("https://www.manhuagui.com", "https://tw.manhuagui.com")

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
        invisible_input = soup.find("input", {"id": "__VIEWSTATE"})
        if invisible_input:
            lz_encoded = invisible_input.get("value")
            lz_decoded = decompressFromBase64(lz_encoded)
            soup = BeautifulSoup(lz_decoded, "html.parser")

        if not soup:
            self.log.warn("chapterList is not exist.")
            return chapterList

        chapter_datas = []
        for chapter_list in soup.find_all("div", {"class": "chapter-list"}):
            for link in chapter_list.find_all("a"):
                chapter_datas.append(
                    {
                        "chapter_id": int(
                            re.search("\/(\d+)\.html", link.get("href")).group(1)
                        ),
                        "chapter_title": unicode(link.get("title")),
                    }
                )
        chapter_datas.sort(key=lambda d: d["chapter_id"])
        for chapter in chapter_datas:
            chapter_url = urljoin(
                url, "{chapter_id}.html".format(chapter_id=chapter["chapter_id"])
            )
            chapterList.append((chapter["chapter_title"], chapter_url))
        return chapterList

    # 获取漫画图片列表
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
        packed_match = re.search(r'(window\["\\x65\\x76\\x61\\x6c"\].*\))', content)
        if not packed_match:
            self.log.warn("Can't find res")
            return []
        codes = decode_packed_codes(packed_match.group(1))

        pages_opts = json.loads(re.search("\(({.+})\)", codes).group(1))

        corejsurl_match = re.search(r'src="(https?://[^"]+?/core_\w+?\.js)"', content)
        if not corejsurl_match:
            self.log.warn("Can't find corejs url from {}".format(url))
            return []

        corejsurl = corejsurl_match.group(1)
        result = opener.open(corejsurl)
        if result.status_code != 200 or not result.content:
            self.log.warn("fetch corejs: %s" % result.status_code)
            return []
        servs = re.search(r"var servs=(.+?),pfuncs=", result.content).group(1)
        servs = re.findall('h:"(.+?)"', servs)
        servers = cycle(servs)

        cid = self.getChapterId(url)
        md5 = pages_opts["sl"]["md5"]
        images = pages_opts["files"]

        if not images:
            self.log.warn("image list is not exist.")
            return []

        imgList = []
        for img in images:
            base_path = urljoin(
                "http://{}.hamreus.com".format(next(servers)),
                urllib.quote(pages_opts["path"].encode("utf8")),
            )
            img_url = urljoin(
                base_path, "{}?cid={}&md5={}".format(img.rstrip(".webp"), cid, md5)
            )
            imgList.append(img_url)

        return imgList

    def getChapterId(self, url):
        section = url.split("/")
        fName = section[len(section) - 1]
        return fName.split(".")[0]
