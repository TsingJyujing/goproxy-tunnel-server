"""
A wrapper of goproxy
"""
import json
import socket
import time
from os import getcwd
from os.path import join
from platform import platform
from subprocess import Popen, TimeoutExpired
from threading import Lock, Thread
from typing import Dict

from tunnel_manager.settings import DEBUG
from util import MutexLock

if platform().startswith("Darwin"):
    proxy_bin = join(getcwd(), "bin", "proxy.mac64")
elif platform().startswith("Linux"):
    proxy_bin = join(getcwd(), "bin", "proxy.amd64")
else:
    raise Exception("Platform not support: " + platform())


def _expand_parameters(parameters: dict) -> list:
    """
    Turn dict to commandline parameter
    Like {"a":1,"b":2,"c":None}-->["a","1","b","2","c"]
    :param parameters:
    :return:
    """
    return [str(e) for l in ([k, v] for k, v in parameters.items()) for e in l if e is not None]


class Tunnel:
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
        self.innet_port = innet_port
        self.expose_port = expose_port
        self.bridge_port = bridge_port
        self.bridge_process = None
        self.client_process = None
        self.comment = comment
        self.last_check_time = time.time()
        self.expire_time = expired

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

    @property
    def invalid(self):
        return not self.valid

    def start(self):
        socket_list = []
        if self.expose_port is None:
            sock = socket.socket()
            sock.bind(('', 0))
            _, port = sock.getsockname()
            socket_list.append(sock)
            self.expose_port = port
        if self.bridge_port is None:
            sock = socket.socket()
            sock.bind(('', 0))
            _, port = sock.getsockname()
            socket_list.append(sock)
            self.bridge_port = port

        [sock.close() for sock in socket_list]

        self.bridge_process = Popen(
            [proxy_bin, "bridge", "--forever"] + _expand_parameters({
                "-C": "certification/proxy.crt",
                "-K": "certification/proxy.key",
                "-p": ":{}".format(self.bridge_port)
            })
        )

        self.client_process = Popen(
            [proxy_bin, "server", "--forever"] + _expand_parameters({
                "-C": "certification/proxy.crt",
                "-K": "certification/proxy.key",
                "-P": "127.0.0.1:{}".format(self.bridge_port),
                "-r": ":{}@:{}".format(self.expose_port, self.innet_port)
            })
        )
        print("Starting proxy bridge {}-{}-{} at pid {} and {}".format(
            self.innet_port,
            self.bridge_port,
            self.expose_port,
            self.bridge_process.pid,
            self.client_process.pid
        ))
        return self

    @classmethod
    def __stop_process(cls, process: Popen, timeout: float = 5):
        try:
            pid = process.pid
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except TimeoutExpired:
                process.kill()
                print("Kill {}".format(pid))
        except:
            pass

    def stop(self):
        print("Stopping tunnel {}-{}-{} at pid {} and {}".format(
            self.innet_port,
            self.bridge_port,
            self.expose_port,
            self.bridge_process.pid,
            self.client_process.pid
        ))
        self.__stop_process(
            self.client_process
        )
        self.__stop_process(
            self.bridge_process
        )
        return self

    def properties_dict(self):
        """
        Return the properties
        :return:
        """
        return {
            "innet_port": self.innet_port,
            "bridge_port": self.bridge_port,
            "expose_port": self.expose_port,
            "comment": self.comment,
            "expire_time": self.expire_time,
            "last_check_time": self.last_check_time,
            "from_last_check": time.time() - self.last_check_time
        }


class TunnelsCheckThread(Thread):
    def __init__(self, tunnels: Dict[int, Tunnel], op_lock: Lock, interval: float = 2):
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
                if DEBUG:
                    print("Checking timeout tunnels")
                for tid in [x for x, tunnel in self.tunnels.items() if tunnel.invalid]:
                    tunnel = self.tunnels.pop(tid).stop()
                    print("Tunnel {} closed caused by timeout: {}".format(
                        tid,
                        json.dumps(tunnel.properties_dict())
                    ))
            time.sleep(self.interval)

    def stop(self):
        self.is_stop = True
