import datetime
from django.shortcuts import render,HttpResponse
from django.http import JsonResponse
from rest_framework import views
from api.models import *

class DeepScience_bh(views.APIView):
    def get(self,request,*args,**kwargs):
        ret = []
        response = JsonResponse(ret)
        response['Access-Control-Allow-Origin'] = "*"
        return response


def create_data(request):
    title = '《Python全栈开发》书籍简介'
    article_type = 0
    brief = '本书由老男孩教育和路飞学城数位金牌Python讲师撰写而成'
    head_img = '/api/media/head_img/1.jepg'
    content = 'Hi ，小伙伴们，想知道你们即将获赠的书籍是什么样子吗？跟着我一起先睹为快吧~本书由老男孩教育和路飞学城数位金牌Python讲师撰写而成，主要包括Python开发基础、函数编程、面向对象编程、常用标准库、网络编程部分，全书有近10个项目实战，总代码量超过1万行，贴近实战，讲解深入，配合Python入门14天集训营课程视频学习，事半功倍，犹如神助。Anyway，吹了那么多，这本书到底讲些什么？长什么样子呢？'
    pub_date = datetime.datetime.now()
    offline_date = datetime.datetime.now()
    Article.objects.create(title=title,article_type=article_type, )
    return HttpResponse('...')




