from utils.auth.token_auth import LuffyTokenAuthentication

class AuthAPIView(object):
    authentication_classes = [LuffyTokenAuthentication, ]