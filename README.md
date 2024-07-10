## QuickNC

本程序是一个端口监听和接收服务，开立在公网服务器上，可允许连入的用户在没有公网IP的情况下共享公网服务器IP，轻松地监听端口和接收数据。

## 部署流程

1. 找一个安装好 Docker 和 Docker-Compose 的主机，执行如下命令，拉取代码。

```
git clone https://github.com/glzjin/QuickNC
cd QuickNC
```

2. 编辑 docker-compose.yml，进行设置。

```
version: '3.8'

services:
  quicknc:
    build: .
    network_mode: host
    restart: always
    environment:
      - PASSWORD=114514 # 用户开启端口监听的时候的密码
      - PORT_MIN=10000 # 监听端口范围下限
      - PORT_MAX=20000 # 监听端口范围上限
      - MAIN_PORT=19999 # 监听主端口，用户连接到这个来获取
      - SOLVER_URL=https://buuoj.cn/files/312e52f8ec473c9d4f4f18581aa3c37c/pow.py # 下载验证码脚本的地址，会返回给用户让用户去下载执行，自己 Host 的话改这里
      - CHALLENGE_DIFFICULTY=5000 # 验证码强度，越大要的时间越久
```

3. 启动。

```
docker compose up -d
```

## 用户侧使用方法

1. 使用 nc 连接上这个服务。

```
nc <ip> <main_port>
```

比如  

```
nc 114.51.4.19 19999
```

![](https://c.img.dasctf.com/LightPicture/2024/07/7fdc676d81778743.png)

2. 连接上之后，会看到一串要求执行的命令，本地执行获得结果。

注意：可执行下面的命令安装 gmpy2 库来加速。

```
pip3 install gmpy2
```

然后执行，获得验证码结果。

![](https://c.img.dasctf.com/LightPicture/2024/07/469e68c4e83a99ca.png)

3. 然后把结果贴回去，再提示输入密码，输入完密码就会开启监听端口，给出端口号。

![](https://c.img.dasctf.com/LightPicture/2024/07/f85349769a8b0ace.png)


4. 这时就可以监听端口，接收数据了。

- 案例-Curl：

![](https://c.img.dasctf.com/LightPicture/2024/07/4d0d0c6c5877e4e5.png)


![](https://c.img.dasctf.com/LightPicture/2024/07/13f1fba31addc8a1.png)

- 案例-反弹 Shell：

![](https://c.img.dasctf.com/LightPicture/2024/07/6502274bafdf87af.png)

![](https://c.img.dasctf.com/LightPicture/2024/07/dee73dc5976c0a97.png)