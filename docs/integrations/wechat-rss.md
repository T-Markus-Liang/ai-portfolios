# 微信公众号文章接入

目标：把微信公众号文章转成 RSS/Atom，再接入 `全球投资动能监控`。

## 当前结论

- 不建议直接爬 `mp.weixin.qq.com` 正文页面：稳定性差，容易触发微信风控。
- `Wechat2RSS` 免费公开列表未覆盖当前两个公众号：`投资人六便士`、`击球区小能手1`。
- 推荐本地自建 `WeWe RSS`，用你提供的公众号文章分享链接订阅公众号，再输出 RSS。

## 本地启动 WeWe RSS

```bash
cd docker/wewe-rss
WEWE_RSS_AUTH_CODE='换成你自己的访问码' docker compose up -d
```

默认访问：`http://127.0.0.1:4000`。本配置使用官方 SQLite 镜像 `cooderl/wewe-rss-sqlite:latest`。

> `docker/wewe-rss/data/` 是本地数据目录，不要提交到 Git。

## 添加公众号

1. 打开 `http://127.0.0.1:4000`。
2. 用 `WEWE_RSS_AUTH_CODE` 登录。
3. 使用公众号文章分享链接添加公众号：
   - `https://mp.weixin.qq.com/s/MX4sDg8SMD1ZeLWPJzRnKA`
   - `https://mp.weixin.qq.com/s/I-KAr_dEtEwTJvD7Hn0Ppw`
4. 在 WeWe RSS 页面复制每个公众号的 RSS 链接，通常形如 `/feeds/<feed-id>.rss` 或 `/feeds/<feed-id>.atom`。
5. 填入 `config/article_sources.yaml` 的 `rss_url`。

## 配置示例

```yaml
article_sources:
  - name: 投资人六便士
    kind: wechat
    enabled: true
    rss_url: "http://127.0.0.1:4000/feeds/xxx.xml"
```

## GitHub Actions 注意

本地 `127.0.0.1` RSS URL 只对你电脑有效，GitHub Actions 访问不到。长期自动化有两种选择：

1. 把 WeWe RSS 部署到一台可公网访问的服务器，并用 HTTPS 地址填入 `rss_url`。
2. 保留 `manual_articles`，把重要单篇文章链接手动加入日报。
