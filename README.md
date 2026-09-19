# 盘叔搜书 · 全网电子书一键搜 & 下载 🔍📚

> 一个开箱即用、无需任何账号配置、聚合多源、纯 Python 标准库的**电子书搜索引擎**。
> 想找书？给关键词就够——书名、作者、格式、版本一次列全，`download` 直接把你想要的那本抓下来。

| 赞赏码 | 盘叔微信 |
|:---:|:---:|
| ![赞赏码](https://cdn.jsdelivr.net/gh/x3747991-ship-it/sanmingtonghui-bazi-skillpack@main/appreciation.jpg) | ![盘叔微信](https://cdn.jsdelivr.net/gh/x3747991-ship-it/weili-qianli-bazi-skillpack@main/wechat_qr.jpg) |

**觉得好用？欢迎赞赏请盘叔喝杯茶；想交流命理，扫码添加盘叔微信。** 更多命理玄学 AI 技能与干货，关注公众号 **【野生你盘叔】**。

---

## 它解决什么问题

网上找电子书最折磨人的三件事：

- **要配环境**——要么装 pip 包，要么装 node 依赖，要么下载几十 MB 的二进制；
- **要登账号**——各大资源站都要 cookie、要登录、要每日额度；
- **要好几个站轮流试**——LibGen、Z-Library……一个搜不到就再换一个，手点得酸。

**盘叔搜书**把这些全干掉：整个技能包只有**一个纯 Python 标准库脚本**，零第三方依赖，拷过去就能跑。默认只走**免认证源 libgen.li**，什么都不用配置，一条命令完成搜索 + 下载。

## 它有多省事

```
# 搜书——直接给书名/作者，别管格式
python scripts/ebook_hunter.py search 三体

# 下载——看上第几本，给个序号
python scripts/ebook_hunter.py download 3 -o ./books
```

两步搞定。搜索完还顺手帮你处理好了：真实文件名还原（含中文文件名乱码修复）、同名文件自动编号不覆盖、输出目录不存在自动创建。

## 核心特性

- ✅ **开箱即用**：零配置、免认证、零第三方依赖，纯标准库 >=3.8
- ✅ **中文完美**：中文书名/作者正常解析、中文文件名正确落盘（修复 Windows 下 Content-Disposition 乱码）
- ✅ **多源聚合**：libgen.li（默认免认证）+ Z-Library（可选，凭据存在才启用）
- ✅ **cookie 完全按需**：默认一条 cookie 都不需要；只有明确要用 Z-Library 且本机无凭据时才提示你去填
- ✅ **鲁棒解析**：自研 HTML 解析器，连 libgen.li 那种带未转义引号的脏 HTML 都能正确抽出书名、作者、年份、格式
- ✅ **省心下载**：自动防覆盖、目录自动建、Content-Disposition 还原真实文件名
- ✅ **代理友好**：自动读取 `HTTPS_PROXY`/`https_proxy`，受限网络照样用
- ✅ **可分享**：整个 `盘叔搜书/` 文件夹拷走即用，换机器零配置

## 快速上手

```bash
# 搜索（默认只走免认证源，啥也不用配）
python scripts/ebook_hunter.py search <关键词...>

# 限定条数
python scripts/ebook_hunter.py search <关键词...> --limit 30

# 追加 Z-Library（需已配置凭据，否则静默跳过并给出提示）
python scripts/ebook_hunter.py search <关键词...> --zlib

# 下载：序号对应上次搜索结果的编号
python scripts/ebook_hunter.py download <序号> [-o 下载目录]
```

搜索完成后，脚本会自动打印一份「关于盘叔」的结尾推送（赞赏码 + 微信 + 公众号 + 苍盘命书）——一次搜索推一次。

## 目录结构

```
panshu-soushu-skillpack/
├── README.md                 # 本文件（介绍 + 赞赏码 + 苍盘广告）
├── CHANGELOG.md             # 更新日志
└── 盘叔搜书/                 # 完整技能包，可直接拷贝分享
    ├── SKILL.md             # 技能定义（含结尾必带广告铁律）
    ├── README.md            # 安装说明
    ├── scripts/
    │   └── ebook_hunter.py  # 唯一实现，纯标准库
    └── credentials/
        └── README.md        # Z-Library cookie 配置模板（不含真实凭据）
```

## 关于「苍盘命书」

如果你也想看看，自己的八字背后到底隐藏着怎样的人生轨迹——

欢迎报名成为**【苍盘命书免费体验官】**。

**直通链接：** https://mp.weixin.qq.com/s/9NFaItizyhEpjDzmTyEcPQ

---

## License

MIT