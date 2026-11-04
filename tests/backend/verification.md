# 本地平台后端验证记录

2026-10-27，合成账号/合成剧情与试卷作答；未启动HTTP监听服务，未做浏览器体验或课堂实验。

## 红测与实现

- 先建立 `test_platform.py` 六项权限/考试行为测试，首次运行6项因 `create_app` 尚无 `platform_database_url` 参数失败。平台功能不存在是预期红测原因。
- 完成独立平台SQLite模型、账号认证、课程归属守卫、固定100分考试、人工短文复核与发布、教师评语后：6项通过，13.37秒。
- 追加沈砚剧情回应与作品归属测试，先得到明确断言失败：仍返回旧“作为你的作品留下”等技术文案；替换新版 `service.py` 台词后通过。
- 累加模型禁用、密码哈希/认证持久性、跨班教师拒绝测试，整文件10项通过，19.21秒。
- 最后新增一项24路线回归：三角色×八终场全部经过新Bearer登录/课程会话归属校验与旧动作事务，通过；该测试1项，9.92秒。此后仅追加本报告，无产品修改。测试总计11项覆盖，最后的矩阵项为单独运行，未说最后一次整套11项同跑。

## 实际命令

```powershell
& 'D:/Codex-chat-II/thesis-courseware/.venv/Scripts/python.exe' -m pytest tests/backend/test_platform.py -q
& 'D:/Codex-chat-II/thesis-courseware/.venv/Scripts/python.exe' -m pytest tests/backend/test_platform.py::test_authenticated_three_roles_eight_endings_keep_world_contract -q
```

沙箱内TestClient首次初始化在Windows asyncio `socketpair` 的 `accept` 阻塞，15秒faulthandler给出此栈；停止该进程后，经工具自动审批以相同本地测试命令在沙箱外成功运行。没有把环境阻塞称为产品逻辑失败，没有跳过权限断言。两次通过均有1条既有Starlette/httpx兼容层弃用警告。

## 覆盖和边界

覆盖：无公开教师注册；错误密码/退出令牌失效；PBKDF2密码哈希、8小时令牌、重开库可认令牌；登录姓名与个人会话绑定；拿到他人会话token仍不能进入；旧feedback端点须教师；跨班教师不能查详情/评分/发布；公开题面不含键；11题6种题型总分100；完成完整故事后提交；主观待评总分null；教师复核并发布后学生只获总分；幂等与冲突；非法题型结构拒绝；未知路线404；有表达才出现目标记录；组内/个人证据标识接口；模型禁用且不读取继承密钥配置；24条路线完成与曹营库存隔离。

题型计数：single、multi、order、match、scenario、short。客观70分，两个短表达共30分，由认证教师人工复核，不存在关键词自动判分。共同通关不会生成个人素养分。

24路线夹具来自既有v3 `reachability-witnesses.json`，本次复制到tests/backend/fixtures/legacy-route-witnesses.json，SHA-256：`bd43cb6b2094192558120014b7585cc818b2981edbab44fdf0a7d68f1e45aeb7`。夹具是软件验证路线，不是真实学生数据，也不是新增教学研究样本。

未覆盖：真实课堂、真实AI三层输出、浏览器全屏与影音、跨设备/公网部署、学校统一认证、负载/攻击压力、评分信效度。当前是本科可控的本地平台切片，不宜直接公网部署演示账号。旧草船工程与凭据均未改；默认数据库固定在新项目data下，不沿用旧COURSEWARE_DATABASE_URL。`seed_demo.py`和`create_account.py`需本机显式运行，不因导入应用自动创建教师。

## 窄接口与独立审查修复后的完整回归

后续新增3项接口红测首先实际失败：A_SAY的goal_id被旧白名单拒绝、presentation_state尚不存在。修复为可选且经过白名单的目标，仅存入唯一Artifact；世界canonical参数中移除goal_id，幂等指纹仍包含目标。缺省目标为空。A_SAY之后增一份合法快照，测试实际换诸葛亮得到原句且不把旧句复制成新作品。表现投影供刷新恢复草束/空甲、初始面/另一面、当前火态，曹营保持未观察字段为空，浓雾下不泄露真正接触。

独立代理查出P2：每件作品先前使用全路支持总数，后来求助被算进早期表达。新增真实API时序 `expression(before)→help(H1)→expression(after)` 红测，确实得到早期support_count=1的错误。修复后仅取提交前支持，按原始来源去重并给support_ids；红测转绿，0/1区分保留。该记录只表示此前呈现，不声称学生采用。

最终同一文件**15项完整通过，34.39秒，1条既有弃用警告**，包括24条三角色八终场路线。与上文历史分次检查不同，这次确实是整套15项同次运行。只改新项目后端和相应测试/API文档，未启服务、未读凭据、未改旧草船。

## 终场镜头状态补丁

新增未出发/已出发/曹营终场测试，字段缺失时两项相关测试实际失败。随后为船方投影实际 `presentation_state.launched`，船方完整终场提供 `ending_code`；曹营两字段保持null，不把对方借箭/归营结果泄漏给曹营视角。2026-10-27按受影响范围运行 `-k 'terminal_presentation or presentation_state_survives or cao_reveals or authenticated_three'`：**4项通过、12项未选，11.51秒，1条既有弃用警告**。其中一项仍包含三角色×八终场24条动作路线。未把本次子集称为16项全套同跑；服务重启和画面复验由root另行执行。
