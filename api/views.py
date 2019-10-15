import atexit
import json
import sys
import time
import traceback
from threading import Lock
from typing import Dict
from warnings import warn

from django.http import HttpRequest
# Create your views here.
from django.views.decorators.csrf import csrf_exempt

from tunnel_manager.settings import DEBUG
from util import MutexLock, Tunnel, TunnelsCheckThread, response_json, check_authorization

# Initialize

tunnels: Dict[int, Tunnel] = {
    # Data
}
tunnels_op_lock = Lock()
_check_thread = TunnelsCheckThread(tunnels, tunnels_op_lock)
_check_thread.start()

tunnel_id = 0

def _new_tunnel_id():
    """
    UNSAFE! Use it in mutex lock
    :return:
    """
    global tunnel_id
    current_tick = int(time.time() * 1000)
    if tunnel_id < current_tick:
        tunnel_id = current_tick
    else:
        tunnel_id += 1
    return tunnel_id


def _add_permanent_proxy():
    try:
        with open("permanent.json", "r") as fp:
            with MutexLock(tunnels_op_lock) as _:
                for item in json.load(fp):
                    tid = _new_tunnel_id()
                    tunnels[tid] = Tunnel(
                        innet_port=int(item["innet"]),
                        expose_port=int(item["expose"]),
                        bridge_port=int(item["bridge"]),
                        comment=str(item["comment"]),
                        expired=-1
                    )
                    tunnels[tid].start()
    except Exception as _:
        print("Error while initialize permanent tunnels.")
        if DEBUG:
            print(traceback.format_exc())


if sys.argv[1] == "runserver":
    _add_permanent_proxy()
else:
    warn("Not runserver mode, permanent proxy will not started.")


def _close_all_tunnel():
    """
    Acquire the lock and release the tunnel
    :return:
    """
    _check_thread.stop()
    tunnels_op_lock.acquire()
    for tid, tunnel in tunnels.items():
        print("Releasing tunnel {}...".format(tid))
        tunnel.stop()


atexit.register(_close_all_tunnel)


@check_authorization
@response_json
def get_proxy_list(request: HttpRequest):
    """
    Get proxy list
    :param request:
    :return:
    """
    return {
        "status": "success",
        "data": [
            {
                "id": tid,
                "tunnel": tunnel.properties_dict()
            }
            for tid, tunnel in tunnels.items()
        ]
    }


@csrf_exempt
@check_authorization
@response_json
def create_tunnel(request: HttpRequest):
    """
    Create a tunnel
    :param request:
    :return:
    """
    innet_port = request.POST["innet"]
    if "expose" in request.POST:
        expose_port = request.POST["expose"]
    else:
        expose_port = None

    if "bridge" in request.POST:
        bridge_port = request.POST["bridge"]
    else:
        bridge_port = None

    if "comment" in request.POST:
        comment = request.POST["comment"]
    else:
        comment = ""

    if "expire" in request.POST:
        expire_time = float(request.POST["expire"])
    else:
        expire_time = 60.0

    with MutexLock(tunnels_op_lock) as _:
        tid = _new_tunnel_id()
        tunnels[tid] = Tunnel(
            innet_port=innet_port,
            bridge_port=bridge_port,
            expose_port=expose_port,
            comment=comment,
            expired=expire_time
        ).start()
        print("Tunnel {} created by API.".format(tid))
        return {
            "status": "success",
            "id": tid,
            "tunnel": tunnels[tid].properties_dict()
        }


@csrf_exempt
@check_authorization
@response_json
def remove_tunnel(request: HttpRequest):
    """
    :param request:
    :return:
    """
    tid = int(request.POST["id"])
    if tid in tunnels:
        with MutexLock(tunnels_op_lock) as _:
            tunnel = tunnels.pop(tid)
            tunnel.stop()
            print("Tunnel {} removed by API.".format(tid))
            return {
                "status": "success",
                "id": tid
            }
    else:
        raise Exception("ID {} not found".format(tid))


@csrf_exempt
@check_authorization
@response_json
def tunnel_heartbeat(request: HttpRequest):
    """
    :param request:
    :return:
    """
    tid = int(request.POST["id"])
    if tid in tunnels:
        with MutexLock(tunnels_op_lock) as _:
            tunnels[tid].check()
            if DEBUG:
                print("Tunnel {} re-check heartbeat by API.".format(tid))
            return {
                "status": "success",
                "id": tid
            }
    else:
        raise Exception("ID {} not found".format(tid))


@csrf_exempt
@check_authorization
@response_json
def query_tunnel(request: HttpRequest):
    """
    :param request:
    :return:
    """
    tid = int(request.GET["id"])
    if tid in tunnels:
        with MutexLock(tunnels_op_lock) as _:
            return {
                "status": "success",
                "id": tid,
                "tunnel": tunnels[tid].properties_dict()
            }
    else:
        raise Exception("ID {} not found".format(tid))
