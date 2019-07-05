import atexit
from threading import Lock
from typing import Dict

from django.http import HttpRequest
# Create your views here.
from django.views.decorators.csrf import csrf_exempt

from tunnel_manager.settings import DEBUG
from util import MutexLock
from util.goproxy import Tunnel, TunnelsCheckThread
from util.http_response import response_json

# Initialize
tunnel_id = 0
tunnels: Dict[int, Tunnel] = {
    # Data
}
tunnels_op_lock = Lock()
_check_thread = TunnelsCheckThread(tunnels, tunnels_op_lock, timeout=60)
_check_thread.start()


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
@response_json
def create_tunnel(request: HttpRequest):
    """
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
    with MutexLock(tunnels_op_lock) as _:
        global tunnel_id
        tunnel_id += 1
        tunnels[tunnel_id] = Tunnel(
            innet_port=innet_port,
            bridge_port=bridge_port,
            expose_port=expose_port,
            comment=comment
        ).start()
        print("Tunnel {} created by API.".format(tunnel_id))
        return {
            "status": "success",
            "id": tunnel_id,
            "tunnel": tunnels[tunnel_id].properties_dict()
        }


@csrf_exempt
@response_json
def remove_tunnel(request: HttpRequest):
    """
    :param request:
    :return:
    """
    tid = int(request.GET["id"])
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
@response_json
def tunnel_heartbeat(request: HttpRequest):
    """
    :param request:
    :return:
    """
    tid = int(request.GET["id"])
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
