# coding=utf-8

"""
Http Response related functions
"""

import json
import os
import sys
import time
import traceback
from typing import Iterable, Union, Callable

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpRequest

# Auto load authorize key
from tunnel_manager.settings import DEBUG

_auth_key = set(os.environ.get("AUTHORIZE_KEYS").split(",")) if os.environ.get("AUTHORIZE_KEYS") is not None else None


def get_request_with_default(request, key, default_value):
    """
    Try to get value by specific key in request object, if can't find key in keySet, return default value.
    :param request: request object created by django
    :param key: key
    :param default_value: default value
    :return:
    """
    try:
        return request.GET[key]
    except:
        return default_value


def get_request_get(request, key):
    """
    Try to get value by specific key in request object, if can't find key in keySet, return None.
    :param request: request object created by django
    :param key: key
    :return:
    """
    return get_request_with_default(request, key, None)


def get_json_response(obj, status_code: int = 200):
    """
    Create a http response
    :param status_code: Http status code
    :param obj: object which json serializable
    :return:
    """
    response = HttpResponse(
        json.dumps(obj),
        content_type="application/json",
        status=status_code
    )
    return response


def get_host(request):
    """
    Get host info from request META
    :param request:
    :return:
    """
    return request.META["HTTP_HOST"].split(":")[0]


def response_json_error_info(func):
    """
    Trying to run function, if exception caught, return error details with json format
    :param func:
    :return:
    """

    def wrapper(request):
        try:
            return func(request)
        except Exception as ex:
            print("Error:" + str(ex), file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return get_json_response({
                "status": "error",
                "error_info": str(ex),
                "trace_back": traceback.format_exc()
            }, status_code=500)

    return wrapper


def response_json(func):
    """
    Trying to run function, if exception caught, return error details with json format, else return json formatted object
    :param func:
    :return:
    """

    def wrapper(request):
        try:
            return get_json_response(func(request))
        except Exception as ex:
            print("Error:" + str(ex), file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            resp = {
                "status": "error",
                "error_info": str(ex)
            }
            if DEBUG:
                resp["trace_back"] = traceback.format_exc()
            return get_json_response(resp, status_code=500)

    return wrapper


def response_figure_image(func):
    """
    Turn the returned figure into png file
    :param func:
    :return:
    """

    def wrapper(request):
        try:
            fn = "%d.png" % int(time.time() * 1000 * 1000)
            fig = func(request)
            fig.savefig(fn)
            with open(fn, "rb") as fp:
                image_data = fp.read()
            os.remove(fn)
            return HttpResponse(image_data, content_type="image/png")
        except Exception as ex:
            print("Error:" + str(ex), file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return get_json_response({
                "status": "error",
                "error_info": str(ex),
                "trace_back": traceback.format_exc()
            }, status_code=500)

    return wrapper


def method_verify(request: HttpRequest, methods: Union[str, Iterable[str]]):
    """
    Verify is method right
    :param request: Django request
    :param methods: Method(s)
    :return:
    """
    current_method = request.method.upper()
    if type(methods) == str:
        method_check_pass = current_method == methods.upper()
        assert method_check_pass, \
            "Interface should be call by {} method, you're using {}.".format(methods, current_method)
    else:
        method_check_pass = current_method in {m.upper() for m in methods}
        assert method_check_pass, \
            "Interface should be call by {} method, you're using {}.".format("/".join(methods), current_method)


def _authorize(request: HttpRequest) -> None:
    """
    Check the authorization key for request
    :param request:
    :return:
    """
    if _auth_key is None or len(_auth_key) <= 0:
        pass
    elif "key" in request.POST:
        if request.POST["key"] not in _auth_key:
            raise Exception("Authorization failed caused by incorrect key")
    elif "key" in request.GET:
        if request.GET["key"] not in _auth_key:
            raise Exception("Authorization failed caused by incorrect key")
    else:
        raise Exception("Authorization failed caused by key not found.")


def is_browser(request: HttpRequest) -> bool:
    """
    Classify the client type by user agent
    :param request:
    :return:
    """
    if "User-Agent" not in request.headers:
        return False
    else:
        return request.headers.get("User-Agent").startswith("Mozilla")


def check_authorization(func) -> Callable:
    """
    Auto check the authorization
    If authorization is not set, pass
    If key is correct pass
    If cookies is login, pass
    If above all failed, then fail
    :param func:
    :return:
    """

    def wrapper(request: HttpRequest) -> HttpResponse:
        try:
            _authorize(request)
            return func(request)
        except:
            # Different behavior between curl/postman/wget/... and browser
            time.sleep(0.5)
            if is_browser(request):
                return login_required(func)(request)
            else:
                return get_json_response({
                    "status": "error",
                    "error_info": "Authorization failed."
                }, status_code=401)

    return wrapper
