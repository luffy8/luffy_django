#!/usr/bin/env python
# -*- coding:utf-8 -*-
from django_redis import get_redis_connection
CONN = get_redis_connection()
