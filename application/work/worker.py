#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#后台实际的推送任务，由任务队列触发

from collections import defaultdict
import datetime, time, imghdr, io, logging
from flask import Blueprint, request
from ..base_handler import *
from ..back_end.send_mail_adpt import send_to_kindle
from ..back_end.db_models import *
from ..utils import local_time
from calibre.web.feeds.recipes import compile_recipe
from ..lib.recipe_helper import *
from ..lib.build_ebook import recipes_to_ebook

bpWorker = Blueprint('bpWorker', __name__)

#<https://cloud.google.com/tasks/docs/creating-appengine-handlers>
#如果是Task触发的，则环境变量会包含以下一些变量
#X-AppEngine-QueueName/X-AppEngine-TaskName/X-AppEngine-TaskRetryCount/X-AppEngine-TaskExecutionCount/X-AppEngine-TaskETA

#在已订阅的Recipe或自定义RSS列表创建Recipe源码列表，最重要的作用是合并自定义RSS
#返回一个字典，键名为title，元素为 [BookedRecipe, recipe, src]
def GetAllRecipeSrc(user, idList):
    srcDict = {}
    rssList = []
    ftRssList = []
    for bked in filter(bool, [BookedRecipe.get_or_none(BookedRecipe.recipe_id == id_) for id_ in idList]):
        recipeId = bked.recipe_id
        recipeType, dbId = Recipe.type_and_id(recipeId)
        if recipeType == 'builtin':
            bnInfo = GetBuiltinRecipeInfo(recipeId)
            src = GetBuiltinRecipeSource(recipeId)
            if bnInfo and src:
                srcDict[bnInfo.get('title', '')] = [bked, bnInfo, src]
            continue
        
        recipe = Recipe.get_by_id_or_none(dbId)
        if recipe:
            if recipeType == 'upload': #上传的Recipe
                srcDict[recipe.title] = [bked, recipe, recipe.src]
            elif recipe.isfulltext: #全文自定义RSS
                ftRssList.append((bked, recipe))
            else: #摘要自定义RSS
                rssList.append((bked, recipe))

    #全文和概要rss各建一个源码
    title = user.book_title
    if ftRssList:
        feeds = [(item.title, item.url) for bked, item in ftRssList]
        srcDict[title + '_f'] = [*ftRssList[0], GenerateRecipeSource(title, feeds, user, isfulltext=True)]

    if rssList:
        feeds = [(item.title, item.url) for bked, item in rssList]
        srcDict[title] = [*rssList[0], GenerateRecipeSource(title, feeds, user, isfulltext=False)]
    return srcDict

# 实际下载文章和生成电子书并且发送邮件
@bpWorker.route("/worker")
def Worker():
    global default_log
    log = default_log
    args = request.args
    userName = args.get('userName', '')
    recipeId = args.get('recipeId', '')  #如果有多个Recipe，使用','分隔
    
    return WorkerImpl(userName, recipeId, log)

#执行实际抓取网页生成电子书任务
#userName: 需要执行任务的账号名
#idList: 需要投递的Recipe ID列表
#返回执行结果字符串
def WorkerImpl(userName: str, idList: list, log=None):
    if not userName:
        return "Parameters invalid."

    user = KeUser.get_or_none(KeUser.name == userName)
    if not user:
        return "The user does not exist."

    if not log:
        log = logging.getLogger('WorkerImpl')
        log.setLevel(logging.WARN)
    
    if not idList:
        idList = [item.recipe_id for item in user.get_booked_recipe()]
    elif not isinstance(idList, list):
        idList = idList.replace('__', ':').split(',')
    
    if not idList:
        log.warning('There are nothing to push.')
        return 'There are nothing to push.'

    #编译recipe
    srcDict = GetAllRecipeSrc(user, idList)
    recipes = defaultdict(list) #编译好的recipe代码对象
    for title, (bked, recipeDb, src) in srcDict.items():
        try:
            ro = compile_recipe(src)
            assert(ro.title)
        except Exception as e:
            log.warning('Failed to compile recipe {}: {}'.format(title, e))

        if not ro.language or ro.language == 'und':
            ro.language = user.book_language

        #合并自定义css
        if user.css_content:
            ro.extra_css = ro.extra_css + '\n\n' + user.css_content if ro.extra_css else user.css_content

        #如果需要登录网站
        if ro.needs_subscription:
            ro.username = bked.account
            ro.password = bked.password

        if bked.separated:
            recipes[ro.title].append(ro)
        else:
            recipes[user.book_title].append(ro)
    
    #逐个生成电子书推送
    lastSendTime = 0
    bookType = user.book_type
    ret = []
    for title, ro in recipes.items():
        book = recipes_to_ebook(ro, user)
        if book:
            #避免触发垃圾邮件机制，最短10s发送一次
            now = time.time() #单位为s
            if lastSendTime and (now - lastSendTime < 10):
                time.sleep(10)

            send_to_kindle(user, title, book)
            lastSendTime = time.time()
            ret.append(f"Sent {title}.{bookType}")
        else:
            save_delivery_log(user, title, 0, status='nonews')

    return '\n'.join(ret) if ret else "There are no new feeds available."
