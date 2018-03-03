from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import HttpResponse, redirect
from django.core.exceptions import ObjectDoesNotExist

import datetime
import json
import time

from rest_framework import views
from rest_framework.response import Response

from api import models
from api import series
from utils.auth.token_auth import LuffyTokenAuthentication

from utils.exception import PricePolicyDoesNotExist, CourseNotOnLine
from django.conf import settings
from utils.alipay import AliPay

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
        except CourseNotOnLine as e:
            response['code'] = 1004
            response['msg'] = '当前选择课程未上线'
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


class Settlement(views.APIView):
    """
    结算，认证已在全局中存在
    """

    def get(self, request, *args, **kwargs):
        """
        结算列表，和购物车列表写重复了。留着吧，反正也不耽误事儿。
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        response = {'code': 1000}
        try:
            settlement_list = CONN.hget(settings.REDIS_SETTLEMENT_KEY, request.user.id)
            if not settlement_list:
                raise Exception()
            response['data'] = {
                'settlement_list': json.loads(settlement_list.decode('utf-8')),
                'balance': request.user.balance
            }
        except Exception as  e:
            response['code'] = 1001
            response['msg'] = '结算列表为空'

        return Response(response)

    def post(self, request, *args, **kwargs):

        response = {'code': 1000}
        try:
            course_id_list = request.data.get('course_list')
            if not course_id_list:
                raise Exception('还没选择要结算的课程')
            course_dict = CONN.hget(settings.REDIS_SHOPPING_CAR_KEY, request.user.id)
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
                    'policy_price': policy_price,
                    'policy_valid_period': policy_valid_period,
                    'coupon_list': [],
                }
                course_dict_policy[course_id] = course_policy
            user_coupon_list = models.CouponRecord.objects.filter(account=request.user, status=0)
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
                    # 学位课或普通课程
                    cid = user_coupon.coupon.object_id
                    if user_coupon.coupon.coupon_type == 0:
                        coupon_info = {
                            'type': 0,
                            'text': '通用优惠券',
                            'id': user_coupon.id,
                            'begin_date': begin_date,
                            'end_date': end_date,
                            'money_equivalent_value': user_coupon.coupon.money_equivalent_value,
                        }
                    elif user_coupon.coupon.coupon_type == 1 and course_dict_policy[cid][
                        'policy_price'] >= user_coupon.coupon.money_equivalent_value:
                        coupon_info = {
                            'type': 1,
                            'text': '满减券',
                            'id': user_coupon.id,
                            'begin_date': begin_date,
                            'end_date': end_date,
                            'money_equivalent_value,': user_coupon.coupon.money_equivalent_value,
                            'minimum_consume': user_coupon.coupon.minimum_consume
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
                    # 全局优惠券
                    if user_coupon.coupon.coupon_type == 0:
                        coupon_info = {
                            'type': 0,
                            'text': '通用优惠券',
                            'id': user_coupon.id,
                            'begin_date': begin_date,
                            'end_date': end_date,
                            'money_equivalent_value': user_coupon.coupon.money_equivalent_value,
                        }
                    elif user_coupon.coupon.coupon_type == 1:
                        coupon_info = {
                            'type': 1,
                            'text': '满减券',
                            'id': user_coupon.id,
                            'begin_date': begin_date,
                            'end_date': end_date,
                            'money_equivalent_value,': user_coupon.coupon.money_equivalent_value,
                            'minimum_consume': user_coupon.coupon.minimum_consume
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
                'course_dict_policy': course_dict_policy,
                'global_coupon_dict': global_coupon_dict
            }
            CONN.hset(settings.REDIS_SETTLEMENT_KEY, request.user.id, json.dumps(user_settlement))

        except Exception as e:
            response['code'] = 1002
            response['msg'] = str(e)

        return Response(response)


class Payment(views.APIView):
    def post(self, request, *args, **kwargs):
        '''
            {
                course_list : {
                    5: {
                        "course_id": 5,
                        "course_type": 13,
                        "course_original_price": 100
                        "course_price": 80
                        "policy_id"：shopping_car_key[user_id]（自己从redis中获取）
                        "coupon_id"：选择的绑定课程优惠券id
                    },
                    6: {
                        "course_id": 6,
                        "course_type": 20,
                        "course_original_price": 200
                        "course_price": 180
                        "policy_id"：shopping_car_key[user_id]（自己从redis中获取）
                        "coupon_id"：选择的绑定课程优惠券id
                    },
                }
                global_coupon: 15,
                actual_amount:408,
            }

        Order
            ForeignKey： account
        OrderDetail
            ForeignKey: Order
            ForeignKey: content_type
                普通课程/学位
        CouponRecord
            ForeignKey: account
            ForeignKey: coupon
            ForeignKey: Order
        '''

        temp_data = {
            'course_list': {
                '5': {
                    "course_id": 5,
                    "course_type": 13,
                    "course_original_price": 100,
                    "course_price": 80,
                    "policy_id": 'shopping_car_key[user_id]（自己从redis中获取）',
                    "coupon_id": '选择的绑定课程优惠券id'
                },
            },
            'global_coupon': 15,
            'actual_amount': 408,
        }
        # 创建订单记录
        ret = {'code': 1000, 'msg': None, 'error': None}
        try:
            order_obj = models.Order.objects.create(
                payment_type=1,
                order_number='order' + str(time.time()),
                account=request.user,
                actual_amount=temp_data['actual_amount'],
                status=1,  # todo 支付宝支付完成之后，修改状态
                date=datetime.datetime.now()
            )
            shopping_car_bytes = CONN.hget(settings.REDIS_SHOPPING_CAR_KEY, request.user.id)
            shopping_car = json.loads(shopping_car_bytes.decode())
            # 创建多条订单详细
            dict_for_validate = {}      # 支付成功之后用于更新数据库表
            dict_for_validate['order_id'] = order_obj.id
            dict_for_validate['global_coupon_id'] = temp_data['global_coupon']
            for _, item in temp_data['course_list'].items():
                course_obj = models.Course.objects.get(id=item['course_id'])
                price_policy_obj = models.PricePolicy.objects.get(id=temp_data['course_list'][str(course_obj.id)]['policy_id'])
                order_detail_obj = models.OrderDetail.objects.create(
                    order=order_obj,
                    content_object=course_obj,
                    original_price=temp_data['course_list'][str(course_obj.id)]['course_original_price'],
                    price=temp_data['course_list'][str(course_obj.id)]['course_price'],
                    valid_period_display=price_policy_obj.get_valid_period_display(),
                    valid_period=price_policy_obj.valid_period
                )
                temp = {
                    'coupon_id': temp_data['course_list'][str(course_obj.id)]['coupon_id'],
                    'order_detail_id': order_detail_obj.id,
                    'valid_period': price_policy_obj.valid_period
                }
                dict_for_validate['course_list'][str(course_obj.id)] = temp
            CONN.hset('dict_for_validate', request.user.id, json.dumps(dict_for_validate))

            # -------------------- 开始支付 -------------------------
            money = float(temp_data['actual_amount'])
            alipay = get_alipay()
            # 生成支付的url
            query_params = alipay.direct_pay(
                subject="充气式韩红",  # 商品简单描述
                out_trade_no="x2" + str(time.time()),  # 商户订单号
                total_amount=money,  # 交易金额(单位: 元 保留俩位小数)
            )

            pay_url = "https://openapi.alipaydev.com/gateway.do?{}".format(query_params)

            return redirect(pay_url)

        except ObjectDoesNotExist as e:
            ret['code'] = 1404
            ret['msg'] = str(e)
            ret['error'] = '课程/价格策略不存在，获取对象失败(创建多条订单详细)'
        except Exception as e:
            ret['code'] = 1500
            ret['msg'] = str(e)
            ret['error'] = '服务端异常'


def get_alipay():
    """ 用于初始化Alipay对象，包含用户的AppID，公钥，私钥等
    Return:
        返回初始化之后的Alipay对象
    """

    app_id = "2016091100483121"

    # POST请求，用于最后的检测
    notify_url = "http://172.96.203.6:8804/payment/validation/"

    # GET请求，用于页面的跳转展示
    return_url = "http://172.96.203.6:8804/payment/validation/"

    merchant_private_key_path = "keys/app_private_2048.txt"     # 个人密钥
    alipay_public_key_path = "keys/alipay_public_2048.txt"      # 支付宝公钥

    alipay = AliPay(
        appid=app_id,
        app_notify_url=notify_url,
        return_url=return_url,
        app_private_key_path=merchant_private_key_path,
        alipay_public_key_path=alipay_public_key_path,  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥
        debug=True,  # 默认False,
    )
    return alipay


def validation(request):
    alipay = get_alipay()
    if request.method == "POST":
        # 检测是否支付成功
        # 去请求体中获取所有返回的数据：状态/订单号
        from urllib.parse import parse_qs
        body_str = request.body.decode('utf-8')
        post_data = parse_qs(body_str)

        post_dict = {}
        for k, v in post_data.items():
            post_dict[k] = v[0]

        sign = post_dict.pop('sign', None)
        alipay.verify(post_dict, sign)
        return Response('POST返回')

    else:
        params = request.GET.dict()
        sign = params.pop('sign', None)
        alipay.verify(params, sign)

        # todo 支付成功之后更新数据库表
        # 更新order表
        bytes_for_validate = CONN.hget('dict_for_validate', request.user.id)
        dict_for_validate = json.loads(bytes_for_validate.decode('utf-8'))
        order_obj = models.Order.objects.filter(id=dict_for_validate['order_id']).first()
        order_obj.statue = 0
        order_obj.pay_time = datetime.datetime.now()
        order_obj.save()

        # 更新优惠券表
        global_coupon_obj = models.CouponRecord.objects.filter(coupon_id=dict_for_validate['global_coupon_id']).first()
        global_coupon_obj.order = order_obj
        global_coupon_obj.used_time = datetime.datetime.now()
        global_coupon_obj.status = 1

        # 更新 EnrolledCourse
        for course_id, item in dict_for_validate['course_list'].items():
            course_obj = models.Course.objects.filter(id=course_id).first()
            models.EnrolledCourse.objects.create(
                account=request.user,
                course=course_obj,
                valid_begin_date=datetime.datetime.now().date(),
                valid_end_date=datetime.datetime.now().date() + item['valid_period'],
                status=0,
                order_detail_id=item['order_detail_id']
            )
        return Response('支付成功')