#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from config import *

class LogsTestCase(BaseTestCase):
    login_required = 'admin'

    def setUp(self):
        super().setUp()
        #测试数据库跨次运行会保留数据，先清理本模块用到的数据，保证用例可重复运行
        DeliverLog.delete().execute()
        KeUser.delete().where(KeUser.name != 'admin').execute()

    def test_logs(self):
        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        self.assertIn('There is nothing here.', text) #还没有任何推送记录

        data = {'user': 'admin', 'to': 'test@test.com', 'size': 1024, 'time_str': '2024-01-01',
            'datetime': datetime.datetime.utcnow(), 'book': 'test', 'status': 'ok'}
        DeliverLog.create(**data)
        DeliverLog.create(**data)
        DeliverLog.create(**data)

        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Only display last 20 logs', resp.text)

        data['user'] = 'other'
        DeliverLog.create(**data)
        KeUser.create(name='other', passwd_hash='pwd')
        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Logs of other users', resp.text)

    def test_remove_logs(self):
        resp = self.client.get('/removelogs')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('lines of delivery log.', resp.text)

        KeUser.create(name='other', passwd_hash='pwd', expiration_days=7,
                expires=datetime.datetime.utcnow() - datetime.timedelta(days=30),
                base_config={'enable_send': 'all'})
        resp = self.client.get('/removelogs')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('lines of delivery log.', resp.text)
        user = KeUser.get(KeUser.name == 'other')
        self.assertFalse(user.cfg('enable_send'))
