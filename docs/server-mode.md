# 服务器模式

浏览器公开版的账号是本机演示身份。需要真正跨设备班级、账号和数据权限时，使用原 FastAPI 服务器实现，并在正式部署前完成身份管理、HTTPS、备份及新的非公开试卷配置。

1. Python 3.12 创建独立虚拟环境，安装 `backend/requirements.txt`。
2. 使用 Node/pnpm 安装前端依赖。PowerShell 中执行 `$env:LST_SERVER='1'; pnpm build`；bash 使用 `LST_SERVER=1 pnpm build`。这会将 API 切回服务器请求。
3. 在项目目录按 `backend/create_account.py --help` 为自己的环境创建账号。也可运行 `backend/seed_demo.py` 创建其明示的演示账号；演示账号不可用于公网课堂。数据库由本机首次运行生成，不在 Git 中。
4. 从 `backend/` 运行 `python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8771`，访问 `http://127.0.0.1:8771/`。
5. 服务器版的教师端包含模型建议接口；真实 DeepSeek 验收仍暂缓。默认不配置模型，不在前端或 Git 中写 Key，不将规则或预写文本称为真实模型输出。

本次发布验证集中在公共浏览器版和离线包；服务器逻辑保留历史版本，其生产安全与真实模型接入不因公开打包而被宣称完成。
