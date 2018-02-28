from django.shortcuts import render,HttpResponse
from django.http import JsonResponse
from rest_framework import views
from rest_framework.response import Response
from api import models
from api import series
import uuid

class LoginView(views.APIView):
    def get(self, request, *args, **kwargs):
        response = HttpResponse()
        return response

    def post(self, request, *args, **kwargs):
        # 接收到的用户名和密码
        username, pwd = request.data.get('username'), request.data.get('password')

        # 验证账号，通过的话生成token并保存
        print(username, pwd)
        user_obj = models.Account.objects.filter(username=username,password=pwd).first()
        if user_obj:
            token = uuid.uuid1()
            ret = {
                'code': 1000,
                'username': username,
                'token': token,
            }
        else:
            ret = {
                'code': 403,
                'msg':'用户名或密码错误'
            }
        response = JsonResponse(ret)
        return response

    def options(self, request, *args, **kwargs):
        response = HttpResponse()
        return response




class DegreeCourse(views.APIView):
    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')  # 课程ID
        if pk:
            # todo:根据ID得到对应的课程
            dc = models.DegreeCourse.objects.get(pk=pk)
            ser = series.DegreeCourseSerializer(instance=dc)
            ret = ser.data
        else:
            dcs = models.DegreeCourse.objects.all()
            ser = series.DegreeCourseSerializer(instance=dcs, many=True)
            ret = {
                'code': 1000,
                'courseList': ser.data
            }
        response = Response(ret)
        return response






