#!/usr/bin/env python
# -*- coding:utf-8 -*-
# KindleEar: A GAE web application to aggregate rss and send it to your kindle.
# Visit https://github.com/cdhigh/KindleEar for the latest version
# Author:
# cdhigh <https://github.com/cdhigh>
# Contributors:
# rexdf <https://github.com/rexdf>

import os, datetime, logging, __builtin__, hashlib, time, base64, urlparse, imghdr

import web
import jinja2
from bs4 import BeautifulSoup
from utils import *
from config import *
from apps.dbModels import *
from google.appengine.api import mail
from google.appengine.api import urlfetch
import sendgrid
from sendgrid.helpers.mail import Email, Content, Mail, Attachment
from google.appengine.api.mail_errors import (
    InvalidSenderError,
    InvalidAttachmentTypeError,
)
from google.appengine.runtime.apiproxy_errors import (
    OverQuotaError,
    DeadlineExceededError,
)

# import main

# URL请求处理类的基类，实现一些共同的工具函数
class BaseHandler:
    def __init__(self):
        if not main.session.get("lang"):
            main.session.lang = self.browerlang()
        set_lang(main.session.lang)

    @classmethod
    def logined(self):
        return True if main.session.get("login") == 1 else False

    @classmethod
    def login_required(self, username=None):
        if (main.session.get("login") != 1) or (
            username and username != main.session.get("username")
        ):
            raise web.seeother(r"/login")

    @classmethod
    def getcurrentuser(self):
        self.login_required()
        u = KeUser.all().filter("name = ", main.session.username).get()
        if not u:
            raise web.seeother(r"/login")
        return u

    @classmethod
    def getsgapikey(self, name):
        user = KeUser.all().filter("name = ", name).get()
        return user.sgenable, user.sgapikey

    def browerlang(self):
        lang = web.ctx.env.get("HTTP_ACCEPT_LANGUAGE", "en")
        # 分析浏览器支持那些语种，为了效率考虑就不用全功能的分析语种和排序了
        # 此字符串类似：zh-cn,en;q=0.8,ko;q=0.5,zh-tw;q=0.3
        langs = lang.lower().replace(";", ",").replace("_", "-").split(",")
        langs = [c.strip() for c in langs if "=" not in c]
        baselangs = {c.split("-")[0] for c in langs if "-" in c}
        langs.extend(baselangs)

        for c in langs:  # 浏览器直接支持的语种
            if c in main.supported_languages:
                return c
        for c in langs:  # 同一语种的其他可选语言
            for sl in main.supported_languages:
                if sl.startswith(c):
                    return sl
        return main.supported_languages[0]

    @classmethod
    def deliverlog(self, name, to, book, size, status="ok", tz=TIMEZONE):
        try:
            dl = DeliverLog(
                username=name,
                to=to,
                size=size,
                time=local_time(tz=tz),
                datetime=datetime.datetime.utcnow(),
                book=book,
                status=status,
            )
            dl.put()
        except Exception as e:
            default_log.exception("DeliverLog failed to save.")

    @classmethod
    def sendgrid_sendmail(self, _apikey, _from, _to, _subject, _body, attachments=[]):
        file_name, data = attachments[0]
        sg = sendgrid.SendGridAPIClient(apikey=_apikey)
        from_email = Email(_from)
        subject = _subject
        to_email = Email(_to)
        content = Content("text/plain", _body)
        encoded = base64.b64encode(data).decode()

        attachment = Attachment()
        attachment.content = encoded
        attachment.type = "application/x-mobipocket-ebook"
        attachment.filename = file_name
        attachment.disposition = "attachment"
        attachment.content_id = "kindleear"

        mail = Mail(from_email, subject, to_email, content)
        mail.add_attachment(attachment)
        response = sg.client.mail.send.post(request_body=mail.get())
        if response.status_code == 202:
            default_log.info("Sendgrid succeed send mail : %s", file_name)
        else:
            default_log.warn(
                "Sendgrid send mail failed, error code: %s", str(response.status_code)
            )
        return response.status_code

    # TO可以是一个单独的字符串，或一个字符串列表，对应发送到多个地址
    @classmethod
    def SendToKindle(
        self, name, to, title, booktype, attachment, tz=TIMEZONE, filewithtime=True
    ):
        urlfetch.set_default_fetch_deadline(60)
        if PINYIN_FILENAME:  # 将中文文件名转换为拼音
            from calibre.ebooks.unihandecode.unidecoder import Unidecoder

            decoder = Unidecoder()
            basename = decoder.decode(title)
        else:
            basename = title

        lctime = local_time("%Y-%m-%d_%H-%M", tz)
        if booktype:
            if filewithtime:
                filename = "%s(%s).%s" % (basename, lctime, booktype)
            else:
                filename = "%s.%s" % (basename, booktype)
        else:
            filename = basename

        sgenable, sgapikey = self.getsgapikey(name)
        status = []
        if SENDMAIL_ALL_POSTFIX:
            filename = filename.replace(".", "_")
            title = title.replace(".", "_")
        for i in range(SENDMAIL_RETRY_CNT + 1):
            using_sendmail = False
            try:
                if i < SENDMAIL_RETRY_CNT and sgenable and sgapikey:
                    using_sendmail = True
                    self.sendgrid_sendmail(
                        sgapikey,
                        SRC_EMAIL,
                        to,
                        "KindleEar %s" % lctime,
                        "Deliver from KindleEar",
                        attachments=[(filename, attachment)],
                    )
                else:
                    mail.send_mail(
                        SRC_EMAIL,
                        to,
                        "KindleEar %s" % lctime,
                        "Deliver from KindleEar",
                        attachments=[(filename, attachment)],
                    )
            except OverQuotaError as e:
                if using_sendmail:
                    default_log.warn(
                        "overquota when sendmail to %s:%s, use gae mail" % (to, str(e))
                    )
                    sgenable = sgapikey = None
                    status.append("sendmail over quota")
                else:
                    default_log.warn("overquota when sendmail to %s:%s" % (to, str(e)))
                    status.append("over quota")
                    break
            except InvalidSenderError as e:
                default_log.warn(
                    "UNAUTHORIZED_SENDER when sendmail to %s:%s" % (to, str(e))
                )
                status.append("wrong SRC_EMAIL")
                break
            except InvalidAttachmentTypeError as e:  # 继续发送一次
                default_log.warn(
                    "InvalidAttachmentTypeError when sendmail to %s:%s" % (to, str(e))
                )
                status.append("invalid postfix")
                break
            except DeadlineExceededError as e:
                if using_sendmail:
                    default_log.warn(
                        "timeout when sendmail to %s:%s, retry!" % (to, str(e))
                    )
                    status.append("sendgrid timeout")
                    time.sleep(5)
                else:
                    default_log.warn(
                        "timeout when sendmail to %s:%s, abort!" % (to, str(e))
                    )
                    status.append("timeout")
                    break
            except Exception as e:
                if using_sendmail:
                    default_log.exception("sendgrid sendmail to %s failed. Retry." % to)
                    status.append("sendgrid failed")
                else:
                    default_log.exception("sendmail to %s failed. " % to)
                    status.append("send failed")
                    break
            else:
                if using_sendmail:
                    status.append("sendgrid ok")
                else:
                    status.append("gae mail ok")
                break
        self.deliverlog(
            name, str(to), title, len(attachment), tz=tz, status="\n".join(status)
        )

    # TO可以是一个单独的字符串，或一个字符串列表，对应发送到多个地址
    @classmethod
    def SendHtmlMail(
        self, name, to, title, html, attachments, tz=TIMEZONE, textcontent=None
    ):
        if not textcontent or not isinstance(textcontent, basestring):
            textcontent = "Deliver from KindlerEar, refers to html part."

        for i in range(SENDMAIL_RETRY_CNT + 1):
            try:
                if attachments:
                    if html:
                        mail.send_mail(
                            SRC_EMAIL,
                            to,
                            title,
                            textcontent,
                            html=html,
                            attachments=attachments,
                        )
                    else:
                        mail.send_mail(
                            SRC_EMAIL, to, title, textcontent, attachments=attachments
                        )
                else:
                    if html:
                        mail.send_mail(SRC_EMAIL, to, title, textcontent, html=html)
                    else:
                        mail.send_mail(SRC_EMAIL, to, title, textcontent)
            except OverQuotaError as e:
                default_log.warn("overquota when sendmail to %s:%s" % (to, str(e)))
                self.deliverlog(name, str(to), title, 0, tz=tz, status="over quota")
                break
            except InvalidSenderError as e:
                default_log.warn(
                    "UNAUTHORIZED_SENDER when sendmail to %s:%s" % (to, str(e))
                )
                self.deliverlog(
                    name, str(to), title, 0, tz=tz, status="wrong SRC_EMAIL"
                )
                break
            except InvalidAttachmentTypeError as e:
                default_log.warn(
                    "InvalidAttachmentTypeError when sendmail to %s:%s" % (to, str(e))
                )
                self.deliverlog(
                    name, str(to), title, 0, tz=tz, status="invalid postfix"
                )
                break
            except DeadlineExceededError as e:
                if i < SENDMAIL_RETRY_CNT:
                    default_log.warn(
                        "timeout when sendmail to %s:%s, retry!" % (to, str(e))
                    )
                    time.sleep(5)
                else:
                    default_log.warn(
                        "timeout when sendmail to %s:%s, abort!" % (to, str(e))
                    )
                    self.deliverlog(name, str(to), title, 0, tz=tz, status="timeout")
                    break
            except Exception as e:
                default_log.warn(
                    "sendmail to %s failed:%s.<%s>" % (to, str(e), type(e))
                )
                self.deliverlog(name, str(to), title, 0, tz=tz, status="send failed")
                break
            else:
                if attachments:
                    size = len(html or textcontent) + sum(
                        [len(c) for f, c in attachments]
                    )
                else:
                    size = len(html or textcontent)
                self.deliverlog(name, str(to), title, size, tz=tz)
                break

    def render(self, templatefile, title="KindleEar", **kwargs):
        kwargs.setdefault("nickname", main.session.get("username"))
        kwargs.setdefault("lang", main.session.get("lang", "en"))
        kwargs.setdefault("version", main.__Version__)
        return main.jjenv.get_template(templatefile).render(title=title, **kwargs)
