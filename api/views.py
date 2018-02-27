from django.shortcuts import render,HttpResponse
from django.http import JsonResponse
from rest_framework import views

class LoginView(views.APIView):
    def get(self, request, *args, **kwargs):
        response = HttpResponse()
        return response

    def post(self, request, *args, **kwargs):
        # 接收到的用户名和密码
        username, pwd = request.data.get('username'), request.data.get('password')
        # 返回token
        ret = {
            'code': 1000,
            'username': username,
            'token': '71ksdf7913knaksdasd7',
        }
        response = JsonResponse(ret)
        return response

    def options(self, request, *args, **kwargs):
        response = HttpResponse()
        return response


class CoursesView(views.APIView):
    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')  # 课程ID
        if pk:
            # todo:根据ID得到对应的课程
            ret = {
                'title': "课程标题",
                'summary': '这是课程'+pk
            }
        else:
            # todo:返回所有的课程
            ret = {
                'code': 1000,
                'courseList': [
                     {"name": '课程1', 'id': 1},
                     {"name": '课程2', 'id': 2},
                     {"name": '课程3', 'id': 3},
                ]
            }
        response = JsonResponse(ret)
        return response









