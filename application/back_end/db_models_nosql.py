#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#datastore数据库结构定义，使用经过修改的datastorm ODM库管理
#datastorm 源 <https://github.com/JavierLuna/datastorm>
#datastorm 文档 <https://datastorm.readthedocs.io/en/latest/>
#cloud datastore 文档 <https://cloud.google.com/datastore/docs/concepts/queries>
#使用的datastorm是自己修改过的，接口尽量和peewee保持一致，并且尽量不要使用peewee的高级特性
#可以使用Key实例的 to_legacy_urlsafe().decode()/from_legacy_urlsafe() 来模拟SQL的外键
#根据以前的经验，经常出现有网友部署时没有成功建立数据库索引，所以现在排序在应用内处理，数据量不大
#Author: cdhigh <https://github.com/cdhigh/KindleEar>
import os, json, datetime
from config import APP_ID, DATABASE_ENGINE, DATABASE_HOST, DATABASE_PORT, DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_NAME

if DATABASE_ENGINE == "datastore":
    from weedata import *
    dbInstance = DatastoreClient(project=APP_ID)
elif DATABASE_ENGINE == "mongodb":
    from weedata import *
    dbInstance = MongoDbClient(APP_ID, "mongodb://localhost:27017/")
else:
    raise Exception("database engine '{}' not supported yet".format(DATABASE_ENGINE))

#调用此函数正式连接到数据库（打开数据库）
def ConnectToDatabase():
    pass

#关闭数据库连接
def CloseDatabase():
    pass

#数据表的共同基类
class MyBaseModel(Model):
    class Meta:
        client = dbInstance
        useIDInsteadOfKey = True
    
    @classmethod
    def get_all(cls, *query):
        if query:
            return cls.select().where(*query).execute()
        else:
            return cls.select().execute()

    #如果取不到，返回None
    @classmethod
    def get_by_id_or_none(cls, id_):
        try:
            return cls.get_by_key(id_)
        except:
            return None

    #将当前行数据转换为一个字典结构，由子类使用，将外键转换为ID，日期转换为字符串
    #可以传入 only=[Book.title, ...]，或 exclude=[]
    def to_dict(self, **kwargs):
        ret = self.dicts(**kwargs)
        ret.pop('key', None)
        ret.pop('_id', None)
        for key in ret:
            data = ret[key]
            if isinstance(data, datetime.datetime):
                ret[key] = data.strftime('%Y-%m-%d %H:%M:%S')
        return ret
        