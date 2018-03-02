from django.core.exceptions import ObjectDoesNotExist
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



from utils.auth.token_auth import LuffyTokenAuthentication
from utils.exception import PricePolicyDoesNotExist
from django.conf import settings

from utils.redis_pool import conn as CONN

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

class Cart(views.APIView):
    # authentication_classes = [LuffyTokenAuthentication,]
    def post(self, request, *args, **kwargs):
        """
        添加购物车
        """
        response = {'code': 1000, 'msg': None}
        try:
            course_id = int(request.data.get('course_id'))
            policy_id = int(request.data.get('policy_id'))

            # 1. 获取课程
            course_obj = models.Course.objects.get(id=course_id)

            # 2. 获取当前课程的所有价格策略: id, 有效期，价格
            price_policy_list = []
            flag = False
            price_policy_objs = course_obj.price_policy.all()
            for item in price_policy_objs:
                if item.id == policy_id:
                    flag = True
                price_policy_list.append(
                    {'id': item.id, 'valid_period': item.get_valid_period_display(), 'price': item.price})
            if not flag:
                raise PricePolicyDoesNotExist()

            # 3. 课程和价格策略均没有问题，将课程和价格策略放到redis中
            # 课程id,课程图片地址,课程标题，所有价格策略，默认价格策略
            course_dict = {
                'id': course_obj.id,
                'img': course_obj.course_img,
                'title': course_obj.name,
                'price_policy_list': price_policy_list,
                'default_policy_id': policy_id
            }

            # a. 获取当前用户购物车中的课程 car = {1: {,,,}, 2:{....}}
            # b. car[course_obj.id] = course_dict
            # c. conn.hset('luffy_shopping_car',request.user.id,car)
            nothing = CONN.hget(settings.REDIS_SHOPPING_CAR_KEY, request.user.id)
            if not nothing:
                data = {course_obj.id: course_dict}
            else:
                data = json.loads(nothing.decode('utf-8'))
                data[course_obj.id] = course_dict

            print(data)

            CONN.hset(settings.REDIS_SHOPPING_CAR_KEY, request.user.id, json.dumps(data))

        except ObjectDoesNotExist as e:
            response['code'] = 1001
            response['msg'] = '视频不存在'
        except PricePolicyDoesNotExist as e:
            response['code'] = 1002
            response['msg'] = '价格策略不存在'
        except Exception as e:
            print(e)
            response['code'] = 1003
            response['msg'] = '添加购物车失败'

        return Response(response)

    def get(self, request, *args, **kwargs):
        """
        查看购物车
        """
        course = CONN.hget(settings.REDIS_SHOPPING_CAR_KEY, request.user.id)
        course_dict = json.loads(course.decode('utf-8'))
        return Response(course_dict)

    def delete(self, request, *args, **kwargs):
        """
        删除购物车中的课程
        """
        response = {'code': 1000}
        try:
            course_id = request.GET.get('pk')
            print(course_id, '------')
            if not course_id:
                raise Exception('请选择要删除的课程')
            product_dict = CONN.hget(settings.REDIS_SHOPPING_CAR_KEY, request.user.id)

            if not product_dict:
                raise Exception('购物车中无课程')
            product_dict = json.loads(product_dict.decode('utf-8'))
            if course_id not in product_dict:
                raise Exception('购物车中无该商品')

            del product_dict[course_id]
            CONN.hset(settings.REDIS_SHOPPING_CAR_KEY, request.user.id, json.dumps(product_dict))
            print(CONN.hget(settings.REDIS_SHOPPING_CAR_KEY, request.user.id))
        except Exception as e:
            response['code'] = 1001
            response['msg'] = str(e)
        return Response(response)

    def put(self, request, *args, **kwargs):
        """
        更新购物车中的课程的默认的价格策略
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        response = {'code': 1000}
        try:
            course_id = request.GET.get('pk')
            policy_id = request.data.get('policy_id')
            product_dict = CONN.hget(settings.REDIS_SHOPPING_CAR_KEY, request.user.id)
            if not product_dict:
                raise Exception('购物车清单不存在')
            product_dict = json.loads(product_dict.decode('utf-8'))
            if course_id not in product_dict:
                raise Exception('购物车清单中商品不存在')

            policy_exist = False
            for policy in product_dict[course_id]['price_policy_list']:
                if policy['id'] == policy_id:
                    policy_exist = True
                    break
            if not policy_exist:
                raise PricePolicyDoesNotExist()

            product_dict[course_id]['choice_policy_id'] = policy_id
            CONN.hset(settings.REDIS_SHOPPING_CAR_KEY, request.user.id, json.dumps(product_dict))
        except PricePolicyDoesNotExist as e:
            response['code'] = 1001
            response['msg'] = '价格策略不存在'
        except Exception as e:
            response['code'] = 1002
            response['msg'] = str(e)

        return Response(response)