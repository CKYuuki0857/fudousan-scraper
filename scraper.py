#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
 房產戰情室 · 實價登錄抓取器 v4（5168 純淨版）
 永慶不動產 西屯安和創意店 · 李仕揚 · 0968-880183
------------------------------------------------------------
 v4 改版重點（拿掉樂居 / Selenium，把 5168 做到最順）：
   ✓ 搜尋會「列候選清單」讓你挑，不會抓錯同名社區（惟美、昂峰…）
   ✓ 全程免瀏覽器、免 webdriver —— 純 requests，貼了就跑
   ✓ 跑完自動「複製到剪貼簿」（需 pip install pyperclip；沒裝就改成終端機列出）
   ✓ 同時輸出兩份：
       records_社區名_日期.json  ←（存檔備查）
       records.json              ←（雲端 / 自動化固定名，不會被改名）
   ✓ 跑完印一張「摘要」：筆數 / 單價中位數 / 樓層分布 / 最近成交月
   ✓ 桌機、手機、雲端共用同一支：給參數(網址或 .csv)＝直接跑、不進選單（GitHub Actions 用）
------------------------------------------------------------
 模式：
   【日常 · 5168 貼了就跑】
     1) 社區名搜尋（會列候選給你挑）
     2) 社區網址直接抓
   【整批 · 內政部（要先自己下載 CSV）】
     3) 內政部 OpenData CSV
 安裝：pip install requests beautifulsoup4
       （選用）pip install pyperclip   ← 裝了才能「自動複製到剪貼簿」
============================================================
"""
import os, sys, re, json, csv, datetime, urllib.parse, warnings

try:
    import requests
    from bs4 import BeautifulSoup
    warnings.filterwarnings("ignore")
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("⚠️ 缺套件，請先： pip install requests beautifulsoup4"); sys.exit(1)

PING = 0.3025
NOW_MINGUO = datetime.date.today().year - 1911
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"}

# ======================= 共用小工具 =======================
def num(x):
    try: return float(re.sub(r'[^\d.\-]', '', str(x)))
    except: return 0.0

def rec(mon="", fl=0, age=0, tp=0, ta=0, cp=0, ca=0, land=0):
    return {"mon": mon, "fl": int(fl or 0), "age": round(num(age),1), "tp": round(num(tp),1),
            "ta": round(num(ta),2), "cp": round(num(cp),1), "ca": round(num(ca),2), "land": round(num(land),2)}

CN = {'零':0,'〇':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
def cn_num(t):
    if t is None: return 0
    t=str(t).strip(); m=re.search(r'-?\d+',t)
    if m: return int(m.group())
    if '十' in t:
        a,_,b=t.partition('十'); return (CN.get(a[:1],1) if a else 1)*10+(CN.get(b[:1],0) if b else 0)
    return CN.get(t[:1],0) if t else 0

def floor_of(s):
    if not s: return 0
    s=str(s)
    if '地下' in s: return 0
    s=s.split('，')[0].split(',')[0].split('/')[0]
    s=s.replace('層','').replace('樓','').replace('F','').replace('f','')
    return cn_num(s)

def fetch(url):
    r=requests.get(url, headers=HEADERS, verify=False, timeout=20)
    r.encoding=r.apparent_encoding or 'utf-8'
    return r.status_code, r.text

# ============== 5168 / houseprice 解析（沿用 v3 已測準，未更動） ==============
def parse_houseprice_text(text):
    out=[]; matches=list(re.finditer(r'(\d{3})年(\d{1,2})月', text))
    for k,m in enumerate(matches):
        end=matches[k+1].start() if k+1<len(matches) else m.start()+300
        seg=text[m.start():end]; rest=re.sub(r'^\s*\d{3}年\d{1,2}月','',seg)
        tp_m=re.search(r'([\d,]+(?:\.\d+)?)\s*萬',seg); area_m=re.search(r'([\d,]+(?:\.\d+)?)\s*坪',seg)
        if not (tp_m and area_m): continue
        y=int(m.group(1)); mo=int(m.group(2))
        cp_m=re.search(r'含車位\s*([\d,]+(?:\.\d+)?)\s*萬',seg)
        ca_m=re.search(r'(?:含車位|坡道平面|坡道機械|升降平面|升降機械|機械|平面)\s*([\d.]+)\s*坪',seg)
        fl_m=re.search(r'(\d+)\s*/\s*\d+',seg); age_m=re.search(r'([\d.]+)\s*年',rest)
        out.append(rec(mon=f"{y}/{mo:02d}", fl=int(fl_m.group(1)) if fl_m else 0,
                       age=num(age_m.group(1)) if age_m else 0, tp=num(tp_m.group(1)),
                       ta=num(area_m.group(1)), cp=num(cp_m.group(1)) if cp_m else 0,
                       ca=num(ca_m.group(1)) if ca_m else 0))
    return out

def scrape_houseprice_url(url):
    if '/building/' in url and not url.rstrip('/').endswith('building') and not url.endswith('/'): url+='/'
    print(f"\n🌐 5168 社區頁：{url}")
    code,html=fetch(url); print(f"   HTTP {code} · {len(html)} 字元")
    if code!=200: print("   ❌ 取得頁面失敗。"); return []
    out=parse_houseprice_text(BeautifulSoup(html,"html.parser").get_text(" "))
    print(f"   ✅ 解析出 {len(out)} 筆"); return out

# ============== 5168 搜尋：改成「列候選清單」（修掉抓錯同名社區的風險） ==============
def search_houseprice_candidates(name, city, district="", limit=8):
    base="https://community.houseprice.tw/list/"+urllib.parse.quote(city)+"_city/"
    if district: base+=urllib.parse.quote(district)+"_zip/"
    base+=urllib.parse.quote(name)+"_kw/"
    print(f"\n🔎 搜尋：{base}")
    code,html=fetch(base)
    if code!=200: print(f"   ❌ HTTP {code}，搜尋頁取得失敗。"); return []
    soup=BeautifulSoup(html,"html.parser")
    seen=set(); cands=[]
    for a in soup.find_all('a', href=True):
        m=re.search(r'/building/(\d+)', a['href'])
        if not m: continue
        bid=m.group(1)
        if bid in seen: continue
        seen.add(bid)
        label=re.sub(r'\s+',' ', a.get_text(' ', strip=True))[:40]
        cands.append({'id':bid, 'name':label,
                      'url':f"https://community.houseprice.tw/building/{bid}/"})
        if len(cands)>=limit: break
    return cands

def houseprice_by_name(name, city, district=""):
    """回傳 (records, 社區名標籤)。多筆會列清單讓使用者挑。"""
    cands=search_houseprice_candidates(name, city, district)
    if not cands:
        print("   ⚠️ 沒找到，換個關鍵字或加上行政區再試。"); return [], name
    if len(cands)==1:
        c=cands[0]; print(f"   ✅ 只有一筆，直接抓：{c['name'] or c['url']}")
        return scrape_houseprice_url(c['url']), (c['name'] or name)
    print(f"\n   找到 {len(cands)} 個社區：")
    for i,c in enumerate(cands,1):
        print(f"     {i}) {c['name'] or '(無名稱)'}   {c['url']}")
    sel=input("   選哪個？輸入編號（預設 1，輸 0 取消）：").strip() or "1"
    if sel=="0":
        print("   已取消。"); return [], name
    try:
        idx=int(sel)-1
        if not (0<=idx<len(cands)): raise ValueError
    except ValueError:
        print("   編號不對，改抓第 1 個。"); idx=0
    c=cands[idx]
    return scrape_houseprice_url(c['url']), (c['name'] or name)

# ============== 內政部 OpenData CSV（沿用 v3，未更動） ==============
def minguo_date_csv(s):
    if s is None: return ""
    d=re.sub(r'\D','',str(s))
    if len(d)<5: return ""
    try:
        y=int(d[:-4]); mo=int(d[-4:-2]); mo=mo if 1<=mo<=12 else 1
        return f"{y}/{mo:02d}"
    except: return ""

def age_from_build(s):
    if s is None: return 0
    d=re.sub(r'\D','',str(s))
    if len(d)<5: return 0
    try:
        a=NOW_MINGUO-int(d[:-4]); return a if 0<=a<=120 else 0
    except: return 0

def parse_moi_csv(path):
    print(f"\n📄 內政部 OpenData CSV：{path}")
    with open(path, encoding='utf-8-sig', errors='ignore') as f: rows=list(csv.reader(f))
    if len(rows)<3: print("   ❌ 內容太少。"); return []
    head=rows[0]
    def col(*names):
        for i,h in enumerate(head):
            for nm in names:
                if nm in h: return i
        return -1
    ci={'date':col('交易年月日'),'tp':col('總價元'),'ta':col('建物移轉總面積'),'fl':col('移轉層次'),
        'build':col('建築完成年月'),'cp':col('車位總價'),'ca':col('車位移轉總面積'),
        'land':col('土地移轉總面積'),'kind':col('交易標的')}
    if ci['tp']<0 or ci['ta']<0: print("   ❌ 非買賣 CSV。"); return []
    out=[]
    for r in rows[2:]:
        if len(r)<=ci['tp']: continue
        kind=r[ci['kind']] if ci['kind']>=0 else ""
        if kind and '車位' in kind and '建物' not in kind and '房地' not in kind: continue
        tp=num(r[ci['tp']])/10000.0; ta=num(r[ci['ta']])*PING
        if tp<=0 or ta<=0: continue
        out.append(rec(mon=minguo_date_csv(r[ci['date']]) if ci['date']>=0 else "",
                       fl=floor_of(r[ci['fl']]) if ci['fl']>=0 else 0,
                       age=age_from_build(r[ci['build']]) if ci['build']>=0 else 0, tp=tp, ta=ta,
                       cp=(num(r[ci['cp']])/10000.0) if ci['cp']>=0 else 0,
                       ca=(num(r[ci['ca']])*PING) if ci['ca']>=0 else 0,
                       land=(num(r[ci['land']])*PING) if ci['land']>=0 else 0))
    print(f"   ✅ 解析出 {len(out)} 筆"); return out

# ======================= 摘要 =======================
def _unit_price(r):
    """房屋單價（萬/坪）＝（總價 − 車位價）/（建物坪 − 車位坪），不含車位。"""
    tp=r.get('tp',0); cp=r.get('cp',0); ta=r.get('ta',0); ca=r.get('ca',0)
    net_tp = tp-cp if (cp and 0<cp<tp) else tp
    net_ta = ta-ca if (ca and 0<ca<ta) else ta
    return (net_tp/net_ta) if net_ta>0 else 0

def _mon_key(m):
    mm=re.match(r'(\d+)\D+(\d+)', m or '')
    return (int(mm.group(1)), int(mm.group(2))) if mm else (-1,-1)

def _median(xs):
    xs=sorted(xs); n=len(xs)
    if n==0: return 0
    return xs[n//2] if n%2 else (xs[n//2-1]+xs[n//2])/2

def summary(records):
    if not records: return
    ups=[u for u in (_unit_price(r) for r in records) if u>0]
    months=[r.get('mon','') for r in records if _mon_key(r.get('mon',''))!=(-1,-1)]
    b1=b2=b3=b0=0
    for r in records:
        f=r.get('fl',0)
        if   1<=f<=5:  b1+=1
        elif 6<=f<=10: b2+=1
        elif f>=11:    b3+=1
        else:          b0+=1
    print("\n" + "─"*48)
    print(f"📊 摘要（共 {len(records)} 筆）")
    if ups:
        print(f"   單價中位數：{_median(ups):.1f} 萬/坪（扣車位）   區間 {min(ups):.1f}–{max(ups):.1f}")
    if months:
        print(f"   成交月：最近 {max(months,key=_mon_key)}   最早 {min(months,key=_mon_key)}")
    print(f"   樓層分布：1–5F {b1} ｜ 6–10F {b2} ｜ 11F+ {b3} ｜ 其他 {b0}")
    print("─"*48)

# ======================= 剪貼簿 =======================
def copy_clip(text):
    """有裝 pyperclip 就自動複製；沒裝就回 False（改走終端機列出，不會塞亂碼進剪貼簿）。"""
    try:
        import pyperclip; pyperclip.copy(text); return True
    except Exception:
        return False

# ======================= 檔名 / 輸出 =======================
def safe_name(s):
    s=re.sub(r'[\\/:*?"<>|，、\s]+','_', (s or '').strip()).strip('_')
    return s or 'records'

def output(records, name="records"):
    if not records:
        print("\n（無資料，沒有可輸出的內容）"); return
    # 去重（同月＋同總價＋同坪＋同樓層 視為同一筆）
    seen,uniq=set(),[]
    for r in records:
        k=(r.get('mon'),r.get('tp'),r.get('ta'),r.get('fl'))
        if k not in seen: seen.add(k); uniq.append(r)
    records=uniq

    try: here=os.path.dirname(os.path.abspath(__file__))
    except NameError: here=os.getcwd()
    pretty=json.dumps(records, ensure_ascii=False, indent=2)
    compact=json.dumps(records, ensure_ascii=False)
    named=os.path.join(here, f"records_{safe_name(name)}_{datetime.date.today():%Y%m%d}.json")
    fixed=os.path.join(here, "records.json")
    for p in (named, fixed):
        with open(p,"w",encoding="utf-8") as f: f.write(pretty)

    print(f"\n💾 已輸出 {len(records)} 筆")
    print(f"   • {named}   ←（存檔備查）")
    print(f"   • {fixed}   ←（雲端 / 自動化固定名）")
    summary(records)

    if copy_clip(compact):
        print("\n📋 已自動複製到剪貼簿！直接到「房產戰情室 → 行情估價 → 匯入框」貼上即可。")
    else:
        print("\n📋（沒裝 pyperclip，無法自動複製）請整段複製下面這串，貼到「行情估價 → 匯入框」：\n")
        print(compact)

# ======================= 主程式 =======================
def main():
    # 雲端 / 命令列：給參數就直接跑、不進選單（GitHub Actions 用）
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg:
        if arg.lower().endswith('.csv'):
            output(parse_moi_csv(arg), name="內政部CSV"); return
        if 'houseprice' in arg or arg.startswith('http'):
            mm=re.search(r'/building/(\d+)', arg)
            output(scrape_houseprice_url(arg), name="5168_"+(mm.group(1) if mm else "cloud")); return
        print("⚠️ 參數無法辨識，請給 5168 社區網址或 .csv 路徑。"); return

    print("="*60)
    print(f" 房產戰情室 · 抓取器 v4（5168 純淨版）   今 民國 {NOW_MINGUO} 年")
    print("="*60)
    print(" 【日常 · 5168 貼了就跑】")
    print("   1) 社區名搜尋（會列候選給你挑）")
    print("   2) 社區網址直接抓")
    print(" 【整批 · 內政部（要先自己下載 CSV）】")
    print("   3) 內政部 OpenData CSV")
    c=input("\n輸入 1~3：").strip()
    if c=='1':
        city=input("縣市（例 台中市）：").strip()
        dist=input("行政區（可空白）：").strip()
        name=input("社區名：").strip()
        recs,label=houseprice_by_name(name, city, dist)
        output(recs, name=label)
    elif c=='2':
        output(scrape_houseprice_url(input("5168 社區網址：").strip()), name="5168")
    elif c=='3':
        output(parse_moi_csv(input("CSV 路徑：").strip().strip('"')), name="內政部CSV")
    else:
        print("未選擇，結束。")

if __name__ == "__main__":
    main()
