"""
A wrapper of goproxy
"""
import json
import logging
import socket
import time
import traceback
from os import getcwd
from os.path import join
from platform import platform
from subprocess import Popen, TimeoutExpired
from threading import Lock, Thread
from typing import Dict, List
from util import MutexLock

log = logging.getLogger(__file__)

if platform().startswith("Darwin"):
    proxy_bin = join(getcwd(), "bin", "proxy.mac64")
elif platform().startswith("Linux"):
    proxy_bin = join(getcwd(), "bin", "proxy.amd64")
else:
    # fixme Add win platform here
    # fixme Identify the arch of PC/Server
    raise Exception("Platform not support: " + platform())


def _expand_parameters(parameters: dict) -> list:
    """
    Turn dict to commandline parameter
    Like {"a":1,"b":2,"c":None}-->["a","1","b","2","c"]
    :param parameters:
    :return:
    """
    return [str(e) for l in ([k, v] for k, v in parameters.items()) for e in l if e is not None]


def apply_ports(port_count: int):
    """
    Get k socket list
    :param port_count:
    :return:
    """
    socket_list = []
    port_list = []
    try:
        for i in range(port_count):
            sock = socket.socket()
            sock.bind(('', 0))
            _, port = sock.getsockname()
            socket_list.append(sock)
            port_list.append(port)
    finally:
        [sock.close() for sock in socket_list]
    return port_list


class ExposeConfig:
    def __init__(
            self,
            innet_port: int,
            expose_port: int = None,
    ):
        self.expose_port = expose_port
        self.innet_port = innet_port

    @property
    def json(self):
        return dict(
            expose_port=self.expose_port,
            innet_port=self.innet_port,
        )


class MultiTunnel:
    def __init__(
            self,
            exposes: List[ExposeConfig],
            bridge_port: int = None,
            comment: str = "",
            expired: float = 60
    ):
        self.exposes = exposes
        if len(exposes) <= 0:
            log.warning("Do not have expose configuration, only bridge created.")
        self.comment = comment
        self.bridge_port = bridge_port
        self.last_check_time = time.time()
        self.expire_time = expired
        self.bridge_process = None
        self.client_processes = []

    def check(self):
        """
        Reset last check time
        :return:
        """
        self.last_check_time = time.time()

    @property
    def valid(self):
        """
        If over timeout second during last check, then invalid
        :param timeout:
        :return:
        """
        if self.expire_time >= 0:
            return (time.time() - self.last_check_time) < self.expire_time
        else:
            return True

    def start(self):
        # Apply ports
        port_need_to_apply = 0
        if self.bridge_port is None:
            port_need_to_apply += 1
        for expose_config in self.exposes:
            if expose_config.expose_port is None:
                port_need_to_apply += 1
        ports = apply_ports(port_need_to_apply)
        if self.bridge_port is None:
            self.bridge_port = ports.pop(0)
        for expose_config in self.exposes:
            if expose_config.expose_port is None:
                expose_config.expose_port = ports.pop(0)

        log.info("Starting bridge server at port: {}".format(self.bridge_port))
        self.bridge_process = Popen(
            [proxy_bin, "bridge", "--forever"] + _expand_parameters({
                "-C": "certification/proxy.crt",
                "-K": "certification/proxy.key",
                "-p": ":{}".format(self.bridge_port)
            })
        )
        log.info("Bridge started in PID: {}".format(self.bridge_process.pid))

        for expose_config in self.exposes:
            log.info("Starting client server at port: {}".format(self.bridge_port))
            client_process = Popen(
                [proxy_bin, "server", "--forever"] + _expand_parameters({
                    "-C": "certification/proxy.crt",
                    "-K": "certification/proxy.key",
                    "-P": "127.0.0.1:{}".format(self.bridge_port),
                    "-r": ":{}@:{}".format(expose_config.expose_port, expose_config.innet_port)
                })
            )
            self.client_processes.append(client_process)
            log.info("Client started in PID: {}".format(client_process.pid))

    @staticmethod
    def __stop_process(process: Popen, timeout: float = 5):
        try:
            pid = process.pid
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except TimeoutExpired:
                process.kill()
                print("Kill {}".format(pid))
        except:
            log.error("Other exception caughted during stopping PID {} caused by {}.".format(
                process.pid,
                traceback.format_exc()
            ))

    def stop(self):
        log.info("Stopping the client process...")
        for client_process in self.client_processes:
            log.info("Stopping the PID: {}".format(client_process.pid))
            self.__stop_process(client_process)
        log.info("Stopping the bridge process...")
        self.__stop_process(self.bridge_process)
        return self

    @property
    def json(self):
        """
        Return the properties
        :return:
        """
        return {
            "bridge_port": self.bridge_port,
            "exposes": [
                expose.json for expose in self.exposes
            ],
            "comment": self.comment,
            "expire_time": self.expire_time,
            "last_check_time": self.last_check_time,
            "from_last_check": time.time() - self.last_check_time
        }


class Tunnel(MultiTunnel):
    def __init__(
            self,
            innet_port: int,
            expose_port: int = None,
            bridge_port: int = None,
            comment: str = "",
            expired: float = 60
    ):
        """
        Manage a tunnel program
        :param innet_port: the tunnel proxy port to expose
        :param expose_port: expose for client connect
        :param bridge_port: bridge connection port
        """
        log.warning("Tunnel is deprecated, please use MultiTunnel instead.")
        super().__init__(
            [ExposeConfig(
                innet_port, expose_port
            )],
            bridge_port=bridge_port,
            comment=comment,
            expired=expired
        )


class TunnelsCheckThread(Thread):
    def __init__(self, tunnels: Dict[int, MultiTunnel], op_lock: Lock, interval: float = 2):
        """
        A thread to check invalid tunnels and shut them
        :param tunnels: tunnels list
        :param op_lock: operation lock
        :param interval: interval between check
        """
        super(TunnelsCheckThread, self).__init__()
        self.tunnels = tunnels
        self.op_lock = op_lock
        self.is_stop = False
        self.interval = interval
        self.daemon = True

    def run(self) -> None:
        while not self.is_stop:
            with MutexLock(self.op_lock) as _:
                log.debug("Checking the tunnels status.")
                for tid in [x for x, tunnel in self.tunnels.items() if not tunnel.valid]:
                    tunnel = self.tunnels.pop(tid).stop()
                    log.info("Tunnel {} closed caused by expired: {}".format(
                        tid,
                        json.dumps(tunnel.json)
                    ))
            time.sleep(self.interval)

    def stop(self):
        self.is_stop = True
