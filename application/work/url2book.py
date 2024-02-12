#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#实现接收到邮件后抓取URL然后制作成电子书

import zlib, base64, io
from flask import Blueprint, request
from ..base_handler import *
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import send_to_kindle
from ..utils import local_time
from build_ebook import urls_to_book

bpUrl2Book = Blueprint('bpUrl2Book', __name__)

#抓取指定链接，转换成附件推送
@bpUrl2Book.route("/url2book")
def Url2BookRoute():
    global default_log
    log = default_log
    args = request.args
    userName = args.get('u')
    urls = args.get('urls')
    subject = args.get('subj')
    bookType = args.get("type", "epub")
    if not all((userName, urls, subject, bookType)):
        return "Some parameter missing!"
        
    urls = zlib.decompress(base64.urlsafe_b64decode(urls)).decode('utf-8')
    user = KeUser.get_or_none(KeUser.name == userName)
    if not user or not user.kindle_email:
        return "The user does not exist."
    
    to = user.kindle_email
    tz = user.timezone
    
    if bookType == 'Download': #直接下载电子书并推送
        from lib.filedownload import Download
        for url in urls.split('|'):
            result = Download(url)
            #如果标题已经给定了文件名，则使用标题文件名
            if '.' in subject and (1 < len(subject.split('.')[-1]) < 5):
                fileName = subject
            else:
                fileName = result.fileName or "NoName"
                
            if result.content:
                send_to_kindle(user, fileName, result.content)
            else:
                save_delivery_log(user, fileName, 0, status=result.status)
            log.info("{} Sent!".format(fileName))
        return "{} Sent!".format(fileName)
    elif bookType == 'Debug': #调试目的，将链接直接下载，发送到管理员邮箱
        from lib.debug_utils import debug_fetch
        #如果标题已经给定了文件名，则使用标题文件名，否则为默认文件名(page.html)
        fileName = None
        if '.' in subject and (1 < len(subject.split('.')[-1]) < 5):
            fileName = subject

        for url in urls.split('|'):
            debug_fetch(url, fileName)
        log.info('[DEBUG] debug file sent!')
        return 'Debug file sent!'
        
    book = urls_to_book(urls.split('|'), subject, user)
    if book:
        send_to_kindle(user, subject, book)
        rs = f"Sent {subject}.{user.book_type}"
    else:
        save_delivery_log(user, title, 0, status='fetch failed')
        rs = "[Url2Book]Fetch url failed."
    return rs
