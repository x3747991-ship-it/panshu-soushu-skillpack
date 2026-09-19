# Z-Library 凭据配置（可选）

本技能**开箱即用**，默认不需要此文件。为了启用可选的 Z-Library 源，
把登录 Z-Library 后浏览器 Cookie 里的两个值填到这里：

```json
{
  "remix_userid": "你的 remix_userid",
  "remix_userkey": "你的 remix_userkey"
}
```

## 如何获取

1. 浏览器登录 https://z-library.sk
2. F12 打开开发者工具 → Application/存储 → Cookies，找到站点 Cookie
3. 复制 `remix_userid` 和 `remix_userkey` 两个字段的值，填入上面 JSON

## 备选方式：环境变量

```bash
export Z_LIBRARY_ID=你的id
export Z_LIBRARY_KEY=你的key
```

## 安全提示

- `remix_userkey` 等同账号凭证，**请勿公开或分享此文件**。
- 分享技能包时删除真实值，只保留模板。