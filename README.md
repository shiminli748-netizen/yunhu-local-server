# 云湖(YHChat) 本地模拟服务器

单机版云湖模拟服务器，配合修改后的APK使用，实现本地化运行。

## 功能

- 完整模拟云湖所有API端点
- 任意手机号/邮箱自动注册登录
- 极光一键登录直接通过
- 消息收发（通过WebSocket实时推送）
- 好友/群组管理
- 机器人管理
- Admin后台管理界面

## 快速开始

### 1. 安装依赖

```bash
pip install aiohttp
```

### 2. 生成SSL证书

```bash
python3 gen_cert.py
```

### 3. 启动服务器

```bash
python3 server.py
```

或使用启动脚本：

```bash
bash start.sh
```

### 4. 访问

- API服务器: `https://127.0.0.1:8443`
- WebSocket: `wss://127.0.0.1:8444/ws`
- Admin后台: `https://127.0.0.1:8443/admin/`

### 5. 默认管理员

- 账号: `admin`
- 密码: `admin123`

## Admin后台功能

- 用户管理（设置VIP、管理员、封禁/解封）
- 群组管理（查看、解散）
- 消息记录查看
- 机器人列表查看
- 统计面板

## 目录结构

```
yunhu_server/
├── server.py          # 主服务器（包含所有API逻辑）
├── gen_cert.py        # SSL证书生成
├── start.sh           # 启动脚本
├── admin/
│   └── index.html     # Admin管理界面
├── data/              # 数据库目录（运行时创建）
├── static/uploads/    # 文件上传目录
└── cert/              # SSL证书目录
```

## 注意事项

- 本项目仅供学习交流使用
- 服务器使用自签名SSL证书，客户端需要信任该证书
- 数据库使用SQLite，数据存储在 `data/yunhu.db`

## 许可证

MIT License
