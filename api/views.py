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

from utils.exception import PricePolicyDoesNotExist, CourseNotOnLine
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
            #    如果状态不为0的话，就代表课程未上线
            if course_obj.status:
                raise CourseNotOnLine()

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
        except Exception as e:
            response['code'] = 1004
            response['msg'] = '当前选择课程未上线'

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

class Settlement(views.APIView):
    """
    结算，认证已在全局中存在
    """
    def get(self,request,*args,**kwargs):
        """
        结算列表，和购物车列表写重复了。留着吧，反正也不耽误事儿。
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        response = {'code':1000}
        try:
            settlement_list = CONN.hget(settings.REDIS_SETTLEMENT_KEY,request.user.id)
            if not settlement_list:
                raise Exception()
            response['data'] = {
                'settlement_list':json.loads(settlement_list.decode('utf-8')),
                'balance':request.user.balance
            }
        except Exception as  e:
            response['code'] = 1001
            response['msg'] = '结算列表为空'

        return Response(response)

    def post(self,request,*args,**kwargs):

        response = {'code':1000}
        try:
            course_id_list = request.data.get('course_list')
            if not course_id_list:
                raise Exception('还没选择要结算的课程')
            course_dict = CONN.hget(settings.REDIS_SHOPPING_CAR_KEY,request.user.id)
            if not course_dict:
                raise Exception('购物车为空')
            """
            数据结构：
            user_id:{
                course_dict_policy{
                    course_id:{
                        'course_id': '',
                        'course_title': '',
                        'course_img': '',
                        'policy_id': '',
                        'policy_price': '',
                        'policy_period': '',
                        'coupon_list':[
                            {课程优惠券信息}，
                            {课程优惠券信息}，
                            {课程优惠券信息}，
                            ...
                        ]
                    }
                }
                global_coupon_dict:{
                    1:{通用优惠券信息}，
                    2:{通用优惠券信息}，
                    3:{通用优惠券信息}，
                    ...
                }
            }
            """
            course_dict = json.loads(course_dict.decode('utf-8'))
            course_dict_policy = {}

            for course_id in course_id_list:
                course_id = str(course_id)
                course_info = course_dict.get(course_id)
                if not course_info:
                    raise Exception('课程需先加入购物车才能购买')
                price_policy_exit = False
                for policy in course_info['price_policy_list']:
                    if policy['id'] == course_info['default_policy_id']:
                        policy_price = policy['price']
                        policy_valid_period = policy['valid_period']
                        price_policy_exit = True
                        break
                if not price_policy_exit:
                    raise Exception('价格策略错误')
                course_policy = {
                    'course_id': course_id,
                    'course_title': course_info['title'],
                    'course_img': course_info['img'],
                    'policy_id': course_info['default_policy_id'],
                    'policy_price':policy_price,
                    'policy_valid_period':policy_valid_period,
                    'coupon_list': [],
                }
                course_dict_policy[course_id] = course_policy
            user_coupon_list= models.CouponRecord.objects.filter(account=request.user,status=0)
            global_coupon_dict = {}
            current_date = datetime.datetime.now().date()
            for user_coupon in user_coupon_list:
                begin_date = user_coupon.coupon.valid_begin_date
                end_date = user_coupon.coupon.valid_end_date
                if begin_date:
                    if current_date < begin_date:
                        continue
                if end_date:
                    if current_date > end_date:
                        continue
                if user_coupon.coupon.content_type:
                    #学位课或普通课程
                    cid = user_coupon.coupon.object_id
                    if user_coupon.coupon.coupon_type == 0:
                        coupon_info = {
                            'type':0,
                            'text':'通用优惠券',
                            'id':user_coupon.id,
                            'begin_date':begin_date,
                            'end_date':end_date,
                            'money_equivalent_value':user_coupon.coupon.money_equivalent_value,
                        }
                    elif user_coupon.coupon.coupon_type == 1 and course_dict_policy[cid]['policy_price'] >= user_coupon.coupon.money_equivalent_value:
                        coupon_info = {
                            'type': 1,
                            'text': '满减券',
                            'id': user_coupon.id,
                            'begin_date': begin_date,
                            'end_date': end_date,
                            'money_equivalent_value,': user_coupon.coupon.money_equivalent_value,
                            'minimum_consume':user_coupon.coupon.minimum_consume
                        }
                    elif user_coupon.coupon.coupon_type == 2:
                        coupon_info = {
                            'type': 2,
                            'text': '折扣券',
                            'id': user_coupon.id,
                            'begin_date': begin_date,
                            'end_date': end_date,
                            'off_percent': user_coupon.coupon.off_percent,
                        }
                    else:
                        continue
                    course_dict_policy[cid]['coupon_list'].append(coupon_info)
                else:
                    #全局优惠券
                    if user_coupon.coupon.coupon_type == 0:
                        coupon_info = {
                            'type':0,
                            'text':'通用优惠券',
                            'id':user_coupon.id,
                            'begin_date':begin_date,
                            'end_date':end_date,
                            'money_equivalent_value':user_coupon.coupon.money_equivalent_value,
                        }
                    elif user_coupon.coupon.coupon_type == 1 :
                        coupon_info = {
                            'type': 1,
                            'text': '满减券',
                            'id': user_coupon.id,
                            'begin_date': begin_date,
                            'end_date': end_date,
                            'money_equivalent_value,': user_coupon.coupon.money_equivalent_value,
                            'minimum_consume':user_coupon.coupon.minimum_consume
                        }
                    elif user_coupon.coupon.coupon_type == 2:
                        coupon_info = {
                            'type': 2,
                            'text': '折扣券',
                            'id': user_coupon.id,
                            'begin_date': begin_date,
                            'end_date': end_date,
                            'off_percent': user_coupon.coupon.off_percent,
                        }
                    else:
                        continue
                    global_coupon_dict[user_coupon.id] = coupon_info
            user_settlement = {
                'course_dict_policy':course_dict_policy,
                'global_coupon_dict':global_coupon_dict
            }
            CONN.hset(settings.REDIS_SETTLEMENT_KEY,request.user.id,json.dumps(user_settlement))

        except Exception as e:
            response['code'] = 1002
            response['msg'] = str(e)

        return Response(response)













