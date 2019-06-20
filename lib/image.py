# -*- coding: utf-8 -*-
#
# Copyright (C) 2010  Alex Yatskov
# Copyright (C) 2011  Stanislav (proDOOMman) Kosolapov <prodoomman@gmail.com>
# Copyright (c) 2016  Alberto Planas <aplanas@gmail.com>
# Copyright (c) 2012-2014 Ciro Mattia Gonano <ciromattia@gmail.com>
# Copyright (c) 2013-2019 Pawel Jastrzebski <pawelj@iosphe.re>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# https://github.com/ciromattia/kcc/blob/master/kindlecomicconverter/image.py


try:
    from cStringIo import StringIO
except ImportError:
    from StringIO import StringIO

from PIL import Image, ImageChops, ImageFilter, ImageOps


def get_bounding_box(tmptmg):
    min_margin = [int(0.005 * i + 0.5) for i in tmptmg.size]
    max_margin = [int(0.1 * i + 0.5) for i in tmptmg.size]
    bbox = tmptmg.getbbox()
    bbox = (
        max(0, min(max_margin[0], bbox[0] - min_margin[0])),
        max(0, min(max_margin[1], bbox[1] - min_margin[1])),
        min(
            tmptmg.size[0], max(tmptmg.size[0] - max_margin[0], bbox[2] + min_margin[0])
        ),
        min(
            tmptmg.size[1], max(tmptmg.size[1] - max_margin[1], bbox[3] + min_margin[1])
        ),
    )
    return bbox


def get_image_histogram(image):
    histogram = image.histogram()
    if histogram[0] == 0:
        return -1
    elif histogram[255] == 0:
        return 1
    else:
        return 0


def fill_check(image):
    bw = image.convert("L").point(lambda x: 0 if x < 128 else 255, "1")
    imageBoxA = bw.getbbox()
    imageBoxB = ImageChops.invert(bw).getbbox()
    if imageBoxA is None or imageBoxB is None:
        surfaceB, surfaceW = 0, 0
        diff = 0
    else:
        surfaceB = (imageBoxA[2] - imageBoxA[0]) * (imageBoxA[3] - imageBoxA[1])
        surfaceW = (imageBoxB[2] - imageBoxB[0]) * (imageBoxB[3] - imageBoxB[1])
        diff = (
            (max(surfaceB, surfaceW) - min(surfaceB, surfaceW))
            / min(surfaceB, surfaceW)
        ) * 100
    if diff > 0.5:
        if surfaceW < surfaceB:
            return "white"
        elif surfaceW > surfaceB:
            return "black"
    else:
        fill = 0
        startY = 0
        while startY < bw.size[1]:
            if startY + 5 > bw.size[1]:
                startY = bw.size[1] - 5
            fill += get_image_histogram(bw.crop((0, startY, bw.size[0], startY + 5)))
            startY += 5
        startX = 0
        while startX < bw.size[0]:
            if startX + 5 > bw.size[0]:
                startX = bw.size[0] - 5
            fill += get_image_histogram(bw.crop((startX, 0, startX + 5, bw.size[1])))
            startX += 5
        if fill > 0:
            return "black"
        else:
            return "white"


def chop_image(data, page_number_power, margin_power):
    if not isinstance(data, StringIO):
        data = StringIO(data)
    image = Image.open(data)
    fill = fill_check(image)
    if fill != "white":
        tmptmg = image.convert(mode="L")
    else:
        tmptmg = ImageOps.invert(image.convert(mode="L"))
    if page_number_power:
        page_number_tmpimg = (
            tmptmg.point(lambda x: x and 255)
            .filter(ImageFilter.MinFilter(size=3))
            .filter(ImageFilter.GaussianBlur(radius=5))
            .point(lambda x: (x >= 16 * page_number_power) and x)
        )
        image = (
            image.crop(page_number_tmpimg.getbbox())
            if page_number_tmpimg.getbbox()
            else image
        )
    if margin_power:
        margin_tmping = tmptmg.filter(ImageFilter.GaussianBlur(radius=3)).point(
            lambda x: (x >= 16 * margin_power) and x
        )
        image = (
            image.crop(get_bounding_box(margin_tmping))
            if margin_tmping.getbbox()
            else image
        )
    data = StringIO()
    image.save(data, "JPEG")
    return data.getvalue()
