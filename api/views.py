from django.shortcuts import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

import datetime
import json

from rest_framework import views
from rest_framework.response import Response

from api import models
from api import series
from utils.auth.token_auth import LuffyTokenAuthentication
from utils.redis_pool import conn


def test(request):
    return HttpResponse(111)


class LoginView(views.APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        response = HttpResponse()
        return response

    def post(self, request, *args, **kwargs):

        response = {'code': 1000, 'errors': None}
        ser = series.AuthSerializer(data=request.data)
        if ser.is_valid():
            try:
                user = models.Account.objects.get(**ser.validated_data)
                token_obj, is_create = models.UserAuthToken.objects.get_or_create(user=user)
                token_obj.token = str(datetime.datetime.utcnow()) + '_' + user.username
                token_obj.save()
                response['token'] = token_obj.token
                response['username'] = user.username
                response['code'] = 1002
            except Exception as e:
                response['errors'] = '用户名密码验证异常'
                response['code'] = 1001
        else:
            response['errors'] = ser.errors

        return Response(response)

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


class CoursesView(views.APIView):
    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')  # 课程ID
        if pk:
            # todo:根据ID得到对应的课程
            course_obj = models.CourseDetail.objects.filter(course_id=pk).first()
            ret = series.CourseDetailSerializers(instance=course_obj)
        else:
            # todo:返回所有的课程
            course_list = models.Course.objects.all()
            ret = series.CourseSerializers(instance=course_list, many=True)
        response = Response(ret.data)
        return response


class NewsViews(views.APIView):
    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        if pk:
            art_obj = models.Article.objects.filter(pk=pk).first()
            ser = series.NewsSerializer(instance=art_obj, context={'request': request})
            response = Response(ser.data)
        else:
            news_list = models.Article.objects.all()
            ser = series.NewsSerializer(instance=news_list, many=True, context={'request': request})
            response = Response(ser.data)
        return response


class ShoppingCartView(views.APIView):
    authentication_classes = [LuffyTokenAuthentication, ]

    def get(self, request, *args, **kwargs):
        ret = {'code': 1000, 'data': None, 'msg': None, 'error': None}
        try:
            course_dict_bytes = conn.hget('luffyshopping_cart1', request.user.id)
            course_dict = course_dict_bytes.decode('utf-8')
            ret['code'] = 1200
            ret['data'] = course_dict
            return Response(ret)
        except Exception:
            ret['code'] = 1500
            ret['error'] = '服务端异常啦天呐'
            return ret

    def post(self, request, *args, **kwargs):
        course_id = request.data.get('course_id')
        price_policy_id = request.data.get('price_policy_id')
        ret = {'code': 1000, 'msg': None, 'error': None}
        try:
            course_obj = models.Course.objects.get(id=course_id)

            # 如果该课程不处于上线状态
            if course_obj.status != 0:
                ret['code'] = 1400
                ret['error'] = '当前课程不在上线状态'
                return Response(ret)
            price_policy_list = [price_policy_obj.id
                                 for price_policy_obj in course_obj.price_policy.all()
                                 ]
            # 如果该课程没有改价格策略
            if not int(price_policy_id) in price_policy_list:
                ret['code'] = 1400
                ret['error'] = '当前课程不存在该价格策略'
                return Response(ret)

            course_dict = {
                'price_policy_all': price_policy_list,
                'price_policy': price_policy_id,
            }
            cart = conn.hget('luffyshopping_cart1', request.user.id)   # b'{"1": {"price_policy_all": [1, 2, 3], "price_policy": 1}}'
            if not cart:
                data = {str(course_obj.id): course_dict}
            else:
                data = json.loads(cart.decode('utf-8'))
                data[str(course_id)] = course_dict
            conn.hset('luffyshopping_cart1', request.user.id, json.dumps(data))
            return Response('OK')
        except ObjectDoesNotExist:
            ret['code'] = 1404
            ret['error'] = '课程不存在'
            return Response(ret)
        except Exception:
            ret['code'] = 1500
            ret['error'] = '服务端异常啦'
            return Response(ret)
