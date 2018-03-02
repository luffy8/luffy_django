from django.shortcuts import HttpResponse
from django.http import JsonResponse
from django.conf import settings
import uuid
import datetime
import json

from rest_framework import views
from rest_framework.response import Response
from api import models
from api import series
from utils.redis_pool import CONN
from utils.auth.api_view import AuthAPIView
from utils.exception import PricePolicyDoesNotExist,CourseNotOnLine
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.versioning import URLPathVersioning


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
                token_obj.token = str(datetime.datetime.utcnow())+'_'+user.username
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
            ser = series.NewsSerializer(instance=news_list, many=True, context={'request':request})
            response = Response(ser.data)
        return response


class ShoppingCarViews(AuthAPIView, views.APIView):
    """
    获取课程 id，价格策略 id
    """
    def get(self, request, *args, **kwargs):
        """查看购物车"""
        ret = CONN.hget(settings.REDIS_SHOPPING_CAR, request.user.id)
        ret = json.loads(ret.decode('utf-8'))
        return Response(ret)

    def post(self, request, *args, **kwargs):
        """向购物车中添加商品"""
        ret = {'code': 1000, 'msg': None}
        # 拿到课程 id，价格策略 id
        try:
            course_id = request.data.get('course_id')
            policy_id = request.data.get('policy_id')
            # a. 获取当前选择课程
            course_obj = models.Course.objects.get(id=course_id)
            #    如果状态不为0的话，就代表课程未上线
            if course_obj.status:
                raise CourseNotOnLine()

            # b. 获取课程所有的有效期和价格策略
            price_policy_list = []
            #    拿到所有的价格策略
            flag = False
            price_policy_objs = course_obj.price_policy.all()
            for item in price_policy_objs:
                if item.id == int(policy_id):
                    flag = True
                price_policy_list.append({'id':item.id,'valid_period':item.get_valid_period_display(),'price':item.price})
            if not flag:
                raise PricePolicyDoesNotExist()

            # c. 将课程和价格策略存入 redis
            course_dict = {
                'id': course_id,
                'title': course_obj.name,
                'img': course_obj.course_img,
                'price_policy_list': price_policy_list,
                'default_policy_id': policy_id
            }
            # 获取当前用户购物车中的课程
            nothing = CONN.hget(settings.REDIS_SHOPPING_CAR, request.user.id)
            if not nothing:
                data = {course_id: course_dict}
            else:
                # 从 redis中拿出来的数据是 bytes 类型
                data = json.loads(nothing.decode('utf-8'))
                data[course_id] = course_dict
            CONN.hset(settings.REDIS_SHOPPING_CAR, request.user.id, json.dumps(data))

        except ObjectDoesNotExist as e:
            ret['code'] = 1001
            ret['msg'] = '课程不存在'
        except PricePolicyDoesNotExist as e:
            ret['code'] = 1002
            ret['msg'] = '价格策略不存在'
        except CourseNotOnLine as e:
            ret['code'] = 1003
            ret['msg'] = '当前选择课程未上线'
        except Exception as e  :
            ret['code'] = 1004
            ret['msg'] = '添加购物车异常'
        return Response(ret)

    def delete(self, request, *args, **kwargs):
        """删除选定的课程"""
        response = {'code': 1000}
        try:
            course_id = request.GET.get('pk')
            if not course_id:
                raise Exception('请选择要删除的课程')
            product_dict = CONN.hget(settings.REDIS_SHOPPING_CAR, request.user.id)
            if not product_dict:
                raise Exception('购物车中无课程')
            if course_id not in product_dict:
                raise Exception('购物车中无该商品')

            del product_dict[course_id]
            CONN.hset(settings.REDIS_SHOPPING_CAR, request.user.id, json.dumps(product_dict))
        except Exception as e :
            response['code'] = 1001
            response['msg'] = str(e)
        return Response(response)

    def dispatch(self, request, *args, **kwargs):
        """更新购物车中默认的价格策略"""
        response = {'code':1000, 'msg':None}
        try:
            course_id = request.GET.get('pk')
            print(request.data)
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
