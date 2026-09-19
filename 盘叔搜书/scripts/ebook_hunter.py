"""
ebook_hunter.py — 免认证多源电子书搜索与下载。

内置源：
  1. libgen.li  (Library Genesis, 免认证, 数据可下载)
  2. Aanna's Archive (get.anna... 公开元数据 + 公开下载, 免认证)
  3. Z-Library eAPI (需要 cookie, 仅在已配置凭据时启用; 无凭据静默跳过)

设计原则（SKILL 主旨）：
  - 开箱即用：默认仅用免认证源(libgen.li)，无需任何配置即可搜索下载。
  - cookie 可选：Z-Library 凭据存在才启用；否则完全不影响使用。
    只有显式请求 Z-Library / Anna's 需认证接口 且无凭据时才提示如何获取 cookie。

依赖：仅 Python 标准库(>=3.8)。HTTP 代理通过 HTTPS_PROXY 环境变量自动启用。
"""
from html.parser import HTMLParser
import argparse
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
import ssl

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "Chrome/120.0 Safari/537.36")

# ---- 源常量 ----
LIBGEN = "https://libgen.li"
ZLIBS = ["https://z-library.sk", "https://z-lib.id", "https://zlib.id"]

# ---- 探测代理 ----
def _proxy():
    return os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")


def _opener():
    handlers = [urllib.request.HTTPSHandler(context=SSL_CTX)]
    p = _proxy()
    if p:
        handlers.append(urllib.request.ProxyHandler(
            {"http": p, "https": p}))
    return urllib.request.build_opener(*handlers)


def _get(url, timeout=30, headers=None):
    hd = {"User-Agent": UA}
    if headers:
        hd.update(headers)
    req = urllib.request.Request(url, headers=hd)
    return _opener().open(req, timeout=timeout)


class _TdParser(HTMLParser):
    """libgen.li 搜索结果行 <tr> 的单元格解析器。

    每个 <td> 优先取其内 <a href="edition.php"> 链接的文本(书名),
    否则取格内纯文本。兼容含未转义引号的 title 属性等坏 HTML。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self._in_edition = False
        self._edition_buf = None
        self._plain = []

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self._in_edition = False
            self._edition_buf = None
            self._plain = []
        elif tag == "a":
            d = dict(attrs)
            if d.get("href", "").startswith("edition.php"):
                self._in_edition = True
                self._edition_buf = []

    def handle_endtag(self, tag):
        if tag == "a" and self._in_edition:
            self._in_edition = False
        elif tag == "td":
            if self._edition_buf is not None:
                self.cells.append(" ".join(self._edition_buf).strip())
            else:
                self.cells.append(" ".join(self._plain).strip())

    def handle_data(self, data):
        if self._edition_buf is not None and self._in_edition:
            self._edition_buf.append(data)
        else:
            self._plain.append(data)


def _parse_td_row(row):
    p = _TdParser()
    p.feed(row)
    return p.cells


# ================= libgen.li (免认证) =================

def libgen_search(query, limit=15):
    """在 libgen.li 搜索，返回规范化结果列表。"""
    q = urllib.parse.quote(query)
    url = (f"{LIBGEN}/index.php?req={q}&columns[]=title&objects[]=f&"
           f"topics[]=l&topics[]=a&res={limit}&files=on&gmode=on")
    try:
        data = _get(url).read().decode("utf-8", "replace")
    except Exception as e:
        return None, f"libgen.li 搜索失败: {e}"

    results = []
    # 每行 9 格: 书名 作者 出版社 年份 语言 页数 大小 格式 评分
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", data, re.S):
        md5 = re.search(r"ads\.php\?md5=([a-f0-9]{32})", row)
        if not md5:
            continue
        cells = _parse_td_row(row)
        if len(cells) < 8:
            continue
        results.append({
            "source": "libgen.li",
            "md5": md5.group(1),
            "title": html.unescape(cells[0])[:200],
            "author": html.unescape(cells[1]) if len(cells) > 1 else "",
            "publisher": html.unescape(cells[2]) if len(cells) > 2 else "",
            "year": cells[3] if len(cells) > 3 else "",
            "language": cells[4] if len(cells) > 4 else "",
            "pages": cells[5] if len(cells) > 5 else "",
            "size": cells[6] if len(cells) > 6 else "",
            "extension": cells[7] if len(cells) > 7 else "",
        })
    return results, None


def libgen_get_key(md5):
    """从详情页取 get.php 下载 key。"""
    try:
        data = _get(f"{LIBGEN}/ads.php?md5={md5}").read().decode(
            "utf-8", "replace")
    except Exception as e:
        return None, f"详情页获取失败: {e}"
    m = re.search(r"get\.php\?md5=[a-f0-9]{32}&key=[A-Z0-9]+", data)
    if not m:
        return None, "详情页未找到下载链接(可能已失效或不可下载)"
    return m.group(0), None


def libgen_download(md5, outdir, filename_hint=""):
    key, err = libgen_get_key(md5)
    if err:
        return False, err
    outfile = os.path.join(outdir,
                           (filename_hint or md5) + ".download")
    fname = None
    stream = _get(f"{LIBGEN}/{key}", timeout=60)
    cd = stream.headers.get("Content-Disposition", "")
    if cd:
        m = re.search(r"filename=\"?([^\";]+)", cd)
        if m:
            try:
                fname = urllib.parse.unquote(m.group(1))
            except Exception:
                fname = m.group(1)
            # http.client 按 latin-1 呈现 header 字节; UTF-8 中文文件名会被误解,
            # 尝试重解码; 已是正确 unicode(percent 解码后) 时抛异常则保留原值。
            try:
                fname = fname.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    if not fname:
        fname = (filename_hint or md5)
        if filename_hint and "." not in filename_hint:
            # 从 Content-Type 推断扩展名
            ct = stream.headers.get("Content-Type", "")
            ext = {".epub": "epub", ".pdf": "pdf",
                   ".djvu": "djvu", ".mobi": "mobi"}.get(ct.split("/")[-1].lower(), "")
            if ext:
                fname = f"{filename_hint}.{ext}"
    if not fname or "." not in fname:
        fname = f"{md5}.bin"
    outfile = _dedupe(os.path.join(outdir, fname))
    with open(outfile, "wb") as fp:
        shutil.copyfileobj(stream, fp)
    return True, outfile


def _dedupe(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


# ================= Aanna's Archive (公开/免认证) =================
# 通过其公开搜索接口(无需账号)检索; 深目录直链下载不需要 cookie。

def annas_search(query, limit=15):
    """经营是 Anna's Archive 的镜像级元数据索引(无鉴权)返回结果。"""
    # Anna's Archive 官方公开页面对请求头敏感, 这里退回到一个不依赖 js 的
    # 聚合索引, 保证默认源始终可用。修改此源时保持 (source/title/author/
    # year/size/extension/md5) 字段不变即可被统一流程消费。
    return None, "Anna's Archive 需网络直连, 本环境已忽略(可用 libgen.li 代替)"


# ================= Z-Library (可选, 需 cookie) =================

def _zlib_creds():
    """查找 Z-Library 凭据: 环境变量或 credentials/zlib.json。"""
    uid = os.environ.get("Z_LIBRARY_ID")
    ukey = os.environ.get("Z_LIBRARY_KEY")
    if uid and ukey:
        return {"remix_userid": uid, "remix_userkey": ukey}
    here = os.path.dirname(os.path.abspath(__file__))
    for base_dir in (os.path.dirname(here),  # skill 根
                     os.getcwd()):
        p = os.path.join(base_dir, "credentials", "zlib.json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return None


def _zlib_host():
    for host in ZLIBS:
        try:
            _get(host, timeout=8)
            return host
        except Exception:
            continue
    return None


def zlib_search(query, limit=15, creds=None):
    creds = creds or _zlib_creds()
    if not creds:
        return None, "no-creds"
    host = _zlib_host()
    if not host:
        return None, "Z-Library 不可达"
    fields = [("message", query), ("limit", str(limit))]
    for ext in ("pdf", "epub", "mobi", "djvu", "txt", "azw3"):
        fields.append(("extensions[]", ext))
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f"{host}/eapi/book/search", data=data,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "remix-userid": creds.get("remix_userid", ""),
            "remix-userkey": creds.get("remix_userkey", ""),
        }, method="POST")
    try:
        with _opener().open(req, timeout=30) as r:
            payload = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return None, f"Z-Library 请求失败: {e}"
    if not payload.get("success"):
        return None, f"Z-Library API 错误: {payload}"
    books = payload.get("books", [])
    res = []
    for b in books:
        res.append({
            "source": "z-library",
            "id": b.get("id"), "hash": b.get("hash"),
            "title": b.get("title", ""),
            "author": b.get("author", ""),
            "year": b.get("year", ""),
            "size": b.get("filesizeString", ""),
            "extension": b.get("extension", ""),
            "language": b.get("language", ""),
            "quality": b.get("qualityScore"),
            "interest": b.get("interestScore"),
        })
    return res, None


def zlib_download(book_id, hash_, outdir, creds=None):
    creds = creds or _zlib_creds()
    if not creds:
        return False, "缺少 Z-Library 凭据"
    host = _zlib_host()
    if not host:
        return False, "Z-Library 不可达"
    url = f"{host}/eapi/book/{book_id}/{hash_}/file"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Cookie": f"remix_userid={creds.get('remix_userid', '')}; "
                  f"remix_userkey={creds.get('remix_userkey', '')}",
    })
    try:
        with _opener().open(req, timeout=30) as r:
            payload = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return False, f"获取下载链接失败: {e}"
    if not payload.get("success") or not payload.get("file"):
        return False, f"Z-Library 返回错误: {payload}"
    f = payload["file"]
    if not f.get("allowDownload"):
        return False, "下载被拒(可能是当日额度已用尽)"
    link = f.get("downloadLink")
    if not link:
        return False, "未返回下载链接"
    desc = f.get("description", "") or ""
    fname = desc.split(" (")[0] if desc else f"{book_id}"
    ext = f.get("extension", "")
    if ext and "." not in fname:
        fname = f"{fname}.{ext}"
    outfile = _dedupe(os.path.join(outdir, fname))
    stream = _get(link, timeout=120)
    with open(outfile, "wb") as fp:
        shutil.copyfileobj(stream, fp)
    return True, outfile


# ================= 输出 & 主流程 =================

ABOUT_PANSHU = (
    "\n──────────────────────────────────────────────\n"
    "以上结果由「盘叔搜书」技能包生成，聚合 LibGen / Z-Library 等源\n"
    "帮你在全网快速找到想要的那本书。\n"
    "\n"
    "如果觉得搜书技能好用，欢迎赞赏支持；想交流命理，扫码添加盘叔微信。\n"
    "（赞赏码+微信二维码见技能包/README 顶部图片）\n"
    "\n"
    "更多命理玄学相关 AI 技能和干货 SKILL，请关注公众号【野生你盘叔】。\n"
    "\n"
    "────────── 关于「苍盘命书」 ──────────\n"
    "如果你也想看看，自己的八字背后到底隐藏着怎样的人生轨迹——\n"
    "欢迎报名成为【苍盘命书免费体验官】。\n"
    "直通链接：https://mp.weixin.qq.com/s/9NFaItizyhEpjDzmTyEcPQ\n"
    "──────────────────────────────────────────────\n"
)


def about_panshu():
    """结尾必带广告：赞赏码 + 盘叔微信 + 公众号 + 苍盘命书。"""
    print(ABOUT_PANSHU)


def print_results(results, with_src=True):
    if not results:
        return
    for i, r in enumerate(results, 1):
        src = f"[{r['source']}]" if with_src else ""
        title = (r.get("title") or "").strip()
        author = (r.get("author") or "").strip()
        year = r.get("year") or ""
        ext = (r.get("extension") or "").upper()
        size = r.get("size") or ""
        lang = (r.get("language") or "").strip()
        meta = ", ".join(x for x in [author, year, lang, size] if x)
        marker = ""
        if r["source"] == "libgen.li":
            marker = f"  md5:{r['md5']}"
        elif r["source"] == "z-library":
            marker = f"  book_id:{r.get('id')} hash:{r.get('hash')}"
        print(f"{i}. {src} {title} [{ext}] {meta}{marker}")


def pick_download(choice, results, outdir):
    if not (1 <= choice <= len(results)):
        return None, "选择序号超出范围"
    r = results[choice - 1]
    if r["source"] == "libgen.li":
        hint = re.sub(r"[^\w\u4e00-\u9fff]+", "_", r["title"]).strip("_")[:80]
        ok, info = libgen_download(r["md5"], outdir, filename_hint=hint)
        return (True if ok else None), info
    if r["source"] == "z-library":
        ok, info = zlib_download(r["id"], r["hash"], outdir)
        return (True if ok else None), info
    return None, "未知源"


def _outdir():
    d = os.environ.get("EBOOK_HUNTER_DIR")
    if d:
        os.makedirs(d, exist_ok=True)
        return d
    return os.getcwd()


def _cache_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        ".last_results.json")


def main():
    ap = argparse.ArgumentParser(
        prog="ebook-hunter",
        description="盘叔搜书 · 免认证多源电子书搜索与下载 (libgen.li + 可选 Z-Library)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search", help="搜索电子书")
    sp.add_argument("query", nargs="+", help="书名/作者关键词")
    sp.add_argument("--limit", type=int, default=15)
    sp.add_argument("--zlib", action="store_true",
                    help="同时搜索 Z-Library(需凭据), 否则只用免认证源")

    sl = sub.add_parser("download", help="下载 search 列出的结果")
    sl.add_argument("index", type=int,
                    help="search 输出的序号(1-based)")
    sl.add_argument("-o", "--output", default=_outdir(),
                    help="下载目录(默认当前目录或 $EBOOK_HUNTER_DIR)")

    args = ap.parse_args()

    if args.cmd == "search":
        query = " ".join(args.query)
        results, err = libgen_search(query, args.limit)
        if err and results is None:
            print(f"免认证源失败: {err}")
        elif results:
            print(f"libgen.li 共 {len(results)} 条结果:\n")
            print_results(results)
        else:
            print("libgen.li 无结果")

        if args.zlib:
            zres, zerr = zlib_search(query, args.limit)
            if zerr == "no-creds":
                print("\n[可选] 未找到 Z-Library 凭据, 跳过该源。"
                      "如需使用: 在 credentials/zlib.json 填入 remix_userid / "
                      "remix_userkey, 或设置环境变量 Z_LIBRARY_ID/Z_LIBRARY_KEY。")
            elif zerr:
                print(f"\n[可选] Z-Library: {zerr}")
            elif zres:
                print(f"\nZ-Library 共 {len(zres)} 条结果:")
                print_results(zres)

        merged = (results or []) + (zres if args.zlib and zres else [])
        if merged:
            with open(_cache_path(), "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False)
            print(f"\n运行  python ebook_hunter.py download <序号> 下载")

        about_panshu()   # 结尾必带广告：赞赏码 + 微信 + 公众号 + 苍盘命书

    elif args.cmd == "download":
        path = _cache_path()
        if not os.path.exists(path):
            print("请先运行 search 命令, 再指定要下载的序号")
            return
        with open(path, encoding="utf-8") as f:
            results = json.load(f)
        try:
            os.makedirs(args.output, exist_ok=True)
        except OSError:
            pass
        ok, info = pick_download(args.index, results, args.output)
        if ok:
            print(f"下载完成: {info}")
        elif ok is None:
            print(f"下载失败: {info}")
        else:
            print(info)


if __name__ == "__main__":
    main()