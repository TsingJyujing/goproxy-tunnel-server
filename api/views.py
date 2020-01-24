import atexit
import json
import logging
import sys
import time
from threading import Lock
from typing import Dict, Mapping

from django.http import HttpRequest
# Create your views here.
from django.views.decorators.csrf import csrf_exempt

from tunnel_manager.settings import DEBUG
from util import MutexLock, TunnelsCheckThread, response_json, check_authorization
# Initialize
from util.goproxy import ExposeConfig, MultiTunnel

tunnels: Dict[int, MultiTunnel] = dict()

tunnels_op_lock = Lock()
_check_thread = TunnelsCheckThread(tunnels, tunnels_op_lock)
_check_thread.start()

tunnel_id = 0

log = logging.getLogger(__file__)


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


def _create_from_dict(config: Mapping):
    exposes = []
    if "exposes" in config:
        for pair_strs in (s.split("-") for s in config["exposes"].split(",")):
            if len(pair_strs) == 2:
                exposes.append(ExposeConfig(
                    int(pair_strs[0]),
                    int(pair_strs[1])
                ))
            elif len(pair_strs) == 1:
                exposes.append(ExposeConfig(
                    int(pair_strs[0]),
                    None
                ))
            else:
                log.error("Wrong expose configuration: {}".format(repr(pair_strs)))

    elif "innet" in config:
        exposes.append(
            ExposeConfig(
                int(config["innet"]),
                int(config["expose"]) if "expose" in config else None
            )
        )
    else:
        raise ValueError("Can't find innet or exposes in configuration")

    tunnel = MultiTunnel(
        exposes,
        bridge_port=int(config["bridge"]) if "bridge" in config else None,
        comment=config.get("comment", ""),
        expired=config.get("expire", 60)
    )

    return tunnel


def _add_permanent_proxy():
    try:
        with open("permanent.json", "r") as fp:
            with MutexLock(tunnels_op_lock) as _:
                for item in json.load(fp):
                    if "expire" not in item:
                        item["expire"] = -1
                    tid = _new_tunnel_id()
                    tunnels[tid] = _create_from_dict(item)
                    tunnels[tid].start()
    except Exception as ex:
        log.error("Error while initialize permanent tunnels.", exc_info=ex)


if sys.argv[1] == "runserver":
    _add_permanent_proxy()
else:
    log.info("Not `runserver` mode, permanent proxy will not started.")


def _close_all_tunnel():
    """
    Acquire the lock and release the tunnel
    :return:
    """
    _check_thread.stop()
    tunnels_op_lock.acquire()
    for tid, tunnel in tunnels.items():
        log.info("Releasing tunnel {}...".format(tid))
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
                "tunnel": tunnel.json
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

    with MutexLock(tunnels_op_lock) as _:
        tid = _new_tunnel_id()
        # noinspection PyTypeChecker
        tunnels[tid] = _create_from_dict(request.POST)
        tunnels[tid].start()
        log.info("Tunnel {} created by API.".format(tid))
        return {
            "status": "success",
            "id": tid,
            "tunnel": tunnels[tid].json
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
            log.info("Tunnel {} removed by API.".format(tid))
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
                "tunnel": tunnels[tid].json
            }
    else:
        raise Exception("ID {} not found".format(tid))
