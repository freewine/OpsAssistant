## 一、功能规划

### 1.1 分析WAF日志

1. 自然语言查询

> 请分析2024年5月14日04:00:00 到 05:00:00的waf 日志
> 巡检2024年6月18日全天的WAF日志

2. 安全日报、周报

### 1.2 分析GuardDuty日志

请巡检2024年6月18日全天的guardduty日志

### 1.3 设置安全组规则

设置安全组，规则为禁止i-07220fb7255216ed0和i-0b55858b2dc145198的SSH端口，给出AWS cli

### 1.4 查询CloudTrail事件

查询近一个月创建EC2的事件

### 1.5 告警分析

客户告警太多，分析告警，提炼出关键信息。

### 1.6 研发知识库RAG

研发技术资料的快速查询。

## 二、方案调研

### 2.2 Bedrock Agent + KB方案

**主要工作：**编写Lambda fuctions，实现对S3数据读取或者直接调用API获取相关信息
**优点：**托管服务，实现起来较为简单
**缺点：**

1. 托管服务，支持的Region有限，尤其中国区不能用。
2. 服务本身的限制，如Agent最多支持5个Action Group，Lambda返回到Agent的Body内容20k的限制等。
3. 需要自己实现前端UI

### 2.2 Langchain方案

**主要工作：** 基于Langchain开发
**优点：** 灵活性好、中国Region客户可用。
**缺点：**

1. 开发工作量较大。

**Sample：** https://github.com/aws-samples/bedrock-claude-chat

### 2.3 Dify方案

**主要工作：** 编写各种Tools
**优点：** 开发工作量小，中国Region客户可用。可以自己部署社区版（已经在EKS上部署成功，向量数据库使用Milvus）。
**缺点：**

1. UI无法灵活定制。
2. 除了Bedrock，AWS的其它服务需要自己集成。集成方式：1. API GateWay + Lambda开发各种tool，接入到Didy。 2/ 直接使用AWS SDK开发containerd APP。

## 三、运维分析Tools实现方式

1. 直接调用服务API
2. 读取S3/CloudWatch log的日志进行分析
3. 数据写入S3，构建数据湖，基于Athena进行分析。利用大模型Text2SQL。
