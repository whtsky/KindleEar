#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from flask import session
from application.view.settings import get_locale

class SettingTestCase(BaseTestCase):
    login_required = 'admin'

    def test_setting_page(self):
        resp = self.client.get('/settings')
        self.assertEqual(resp.status_code, 200)
        data = resp.text
        self.assertTrue(('Base' in data) and ('Oldest article' in data))

    def test_set_post(self):
        data = {'kindle_email': '', 'rss_title': '', 'sm_service': 'sendgrid', 'sm_apikey': '', 'sm_host': '',
            'sm_port': '', 'sm_username': '', 'sm_password': '', 'sm_save_path': '',
            'enable_send': 'all', 'timezone': 8, 'send_time': 7, 'book_type': 'epub', 'device_type': 'kindle',
            'title_fmt': '', 'Monday': 1, 'book_mode': '', 'remove_hyperlinks': 'all', 'author_format': '',
            'book_language': 'zh', 'oldest': 7, 'time_fmt': ''
            }
        resp = self.client.post('/settings', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)

        data['kindle_email'] = 'test@gmail.com'
        data['rss_title'] = 'Test'
        resp = self.client.post('/settings', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)

        #检查配置确实保存了
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        self.assertEqual(user.cfg('kindle_email'), 'test@gmail.com')
        self.assertEqual(user.book_cfg('title'), 'Test')
        self.assertEqual(user.cfg('enable_send'), 'all')
        self.assertEqual(user.send_time, 7)

        data['enable_send'] = 'recipes'
        resp = self.client.post('/settings', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)

        data['enable_send'] = ''
        resp = self.client.post('/settings', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)

    def test_set_locale(self):
        with self.client:
            #POST方式设置语种，返回json
            resp = self.client.post('/setlocale', data={'lang': 'zh'})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json['status'], 'ok')
            self.assertEqual(resp.json['lang'], 'zh')

            with self.client.session_transaction() as sess:
                self.assertEqual(sess['langCode'], 'zh')

            #GET方式设置语种，重定向刷新页面
            resp = self.client.get('/setlocale', query_string={'lang': 'zh', 'next': '/'})
            self.assertEqual(resp.status_code, 302)

            #不支持的语种回落到en
            resp = self.client.post('/setlocale', data={'lang': 'unknown'})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json['lang'], 'en')

            with self.client.session_transaction() as sess:
                self.assertEqual(sess['langCode'], 'en')

        #get_locale()在请求上下文内读取会话中的语种设置
        with self.app.test_request_context():
            session['langCode'] = 'zh'
            self.assertEqual(get_locale(), 'zh')
            session['langCode'] = 'en'
            self.assertEqual(get_locale(), 'en')
            session['langCode'] = None
            self.assertEqual(get_locale(), 'en')
