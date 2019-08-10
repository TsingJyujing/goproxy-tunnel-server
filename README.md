# goproxy-tunnel-server

## Introduction

A server to manage goproxy tunnel. You can start a tunnel quickly. 
After start it, you may "check" it periodically, if heartbeat timeout, the tunnel will auto-close 
to reduce the connection leakage.

The core is snail007's [goproxy](https://github.com/snail007/goproxy)

## Quick Start

### Start


#### With Docker

```bash
docker run -it --net host \
    -e EXPOSE_PORT=8080 \
    -v {your certification dir}:/app/cerfitication \
    tsingjyujing/goproxy-tunnel-server:latest
```

**Build by youself:** `docker build -t tsingjyujing/goproxy-tunnel-server .`

#### Manually

```bash
pip3 install django
python3 manage.py runserver --noreload 0.0.0.0:8000
```

### Use UI

Visit: `http://{your IP}:{service port}/ui/manager` to use the UI.
With UI, you can create a proxy tunnel easily, strongly recommend set expire time is "-1" (means will not expire).
Because we do not allow users to check manually, the interface(`/api/heartbeat`) is not designed for human.

### Use API

Use API is a more profession way to utilize this manager and it's strongly recommended.
Please follow the API document below to creare/remove/check/list your tunnels!

## API document

### List all the tunnels

#### Function

Return all the living tunnels.

#### Urls

- GET: `/api/list`

#### Parameters

None

#### Response
```json
{
    "status": "success",
    "data": [
        {
            "id": 0,
            "tunnel": {
                "innet_port": 22,
                "bridge_port": 33022,
                "expose_port": 22022,
                "comment": "iMac SSH Proxy",
                "expire_time": -1,
                "last_check_time": 1562416269.695682,
                "from_last_check": 130.42161107063293
            }
        },
        {
            "id": 1,
            "tunnel": {
                "innet_port": 22,
                "bridge_port": 20101,
                "expose_port": 22001,
                "comment": "RaspberryPi SSH Proxy",
                "expire_time": -1,
                "last_check_time": 1562416269.7007701,
                "from_last_check": 130.41652488708496
            }
        }
    ]
}
```


### Query data from one tunnel

#### Function

Query tunnel by tunnel ID

#### Urls

- GET: `/api/query`

#### Parameters

|Name|Value Example|Necessary|Method|Comment|
|-|-|-|-|-|
|id|1|yes|GET|Tunnel ID|

#### Response
```json
{
    "status": "success",
    "id": 2,
    "tunnel": {
        "innet_port": "22",
        "bridge_port": 53417,
        "expose_port": 53416,
        "comment": "",
        "expire_time": 60,
        "last_check_time": 1562416336.350801,
        "from_last_check": 20.38416600227356
    }
}
```


### Create a new tunnel

#### Function

Crate a new tunnel in server.

#### Urls

- POST: `/api/create`

#### Parameters

If expose and bridge not specified, system will find 2 free port for proxy.

|Name|Value Example|Necessary|Method|Comment|
|-|-|-|-|-|
|innet|22|yes|POST|Innet port in target server machine|
|expose|30001|no|POST|Expose port for client to connect|
|bridge|30002|no|POST|Bridge port for target server machine |
|comment|jupyter proxy|no|POST|Some attach information to tunnel|
|expire|120|no|POST|Timeout of proxy tunnel monitor, if less than/equal 0 will not expire|

#### Response
```json
{
    "status": "success",
    "id": 2,
    "tunnel": {
        "innet_port": "22",
        "bridge_port": 53417,
        "expose_port": 53416,
        "comment": "",
        "expire_time": 60,
        "last_check_time": 1562416336.350801,
        "from_last_check": 0.006495952606201172
    }
}
```

### Remove a new tunnel

#### Function

Remove a existed tunnel in server.

#### Urls

- POST: `/api/remove`

#### Parameters

|Name|Value Example|Necessary|Method|Comment|
|-|-|-|-|-|
|id|10|yes|POST|The tunnel ID to remove|


#### Response
```json
{
    "status": "success",
    "id": 1
}
```

### Recheck a new tunnel

#### Function

Recheck a tunnel to reset the last check time (like heartbeat)

#### Urls

- POST: `/api/heartbeat`

#### Parameters

|Name|Value Example|Necessary|Method|Comment|
|-|-|-|-|-|
|id|10|yes|POST|The tunnel ID to check|


#### Response
```json
{
    "status": "success",
    "id": 1
}
```
