#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
 房產戰情室 · 實價登錄抓取器 v3（交叉比對版）
 永慶不動產 西屯安和創意店 · 李仕揚 · 0968-880183
------------------------------------------------------------
 v3 新增：5168(主) × 樂居(副) 交叉比對
   配對規則：同成交月 + 同樓層 + 坪數±0.5 + 總價±2%
   每筆標記：✓雙源一致 / ⚠僅5168 / ⚠僅樂居 / ✗價格不符(需人工核對)
   建議：只採「雙源一致」「僅5168」(5168最可靠)；
        「價格不符」會同時列出兩邊價格供你判斷。
------------------------------------------------------------
 模式：
   1) 5168 社區名自動抓（最方便）
   2) 5168 社區網址抓
   3) 內政部 OpenData CSV（最穩、整批）
   4) 5168 × 樂居 交叉比對  ← v3 重點
   5) 純樂居（Selenium）
 安裝：pip install requests beautifulsoup4
       交叉比對/樂居另需：pip install selenium webdriver-manager + Chrome
============================================================
"""
import os, sys, re, json, csv, time, datetime, urllib.parse, warnings

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

# ========== 5168 / houseprice （requests，已測準） ==========
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

def search_houseprice(name, city, district=""):
    url="https://community.houseprice.tw/list/"+urllib.parse.quote(city)+"_city/"
    if district: url+=urllib.parse.quote(district)+"_zip/"
    url+=urllib.parse.quote(name)+"_kw/"
    print(f"\n🔎 搜尋社區：{url}")
    code,html=fetch(url)
    if code!=200: return None
    m=re.search(r'/building/(\d+)',html)
    if m:
        bu=f"https://community.houseprice.tw/building/{m.group(1)}/"; print(f"   ✅ 命中：{bu}"); return bu
    print("   ⚠️ 沒找到，換關鍵字或加區。"); return None

def houseprice_by_name(name, city, district=""):
    bu=search_houseprice(name,city,district); return scrape_houseprice_url(bu) if bu else []

# ========== 內政部 OpenData CSV ==========
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

# ========== 樂居（Selenium 真瀏覽器） ==========
def parse_leju_html(html):
    soup=BeautifulSoup(html,"html.parser"); out=[]
    for tr in soup.select('tr.tr-item'):
        td=tr.find_all('td')
        if len(td)<7: continue
        g=lambda i: td[i].get_text(' ',strip=True) if i<len(td) else ""
        dm=re.search(r'(\d{2,3})\D+(\d{1,2})', re.sub(r'[.\-]','/',g(0)))
        mon=f"{int(dm.group(1))}/{int(dm.group(2)):02d}" if dm else ""
        out.append(rec(mon=mon, fl=floor_of(g(2)), age=num(g(3)), tp=num(g(4)), ta=num(g(6)),
                       cp=num(g(8)) if len(td)>8 else 0, ca=0))
    return out

def scrape_leju(url):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        print("   ❌ 樂居需： pip install selenium webdriver-manager"); return []
    print(f"\n🌍 開瀏覽器（樂居）：{url}")
    driver=webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=Options())
    try:
        driver.get(url)
        print("🛑 請在瀏覽器登入/關廣告/捲到成交明細，完成後回來按 Enter…"); input("   (Enter 繼續)")
        for y in (600,1400,2400): driver.execute_script(f"window.scrollTo(0,{y});"); time.sleep(1.2)
        html=driver.page_source
    finally:
        try: driver.quit()
        except: pass
    out=parse_leju_html(html); print(f"   ✅ 樂居解析 {len(out)} 筆（請人工核對單價）"); return out

# ========== ★ 交叉比對核心 ★ ==========
def cross_compare(a, b, tol_area=0.5, tol_tp=0.02):
    """a=5168(主) b=樂居(副)。配對 by 同月+同樓層+坪數±tol_area+總價±tol_tp。"""
    used=set(); out=[]
    cnt={'ok':0,'a_only':0,'b_only':0,'price':0}
    for ra in a:
        hit=None
        for j,rb in enumerate(b):
            if j in used: continue
            if ra['mon']!=rb['mon']: continue
            if ra['fl'] and rb['fl'] and ra['fl']!=rb['fl']: continue
            if abs(ra['ta']-rb['ta'])>tol_area: continue
            if ra['tp']>0 and rb['tp']>0:
                diff=abs(ra['tp']-rb['tp'])/max(ra['tp'],rb['tp'])
                hit=(j, 'ok' if diff<=tol_tp else 'price'); break
        r=dict(ra)
        if hit:
            used.add(hit[0])
            if hit[1]=='ok':
                r['src']='5168+樂居'; r['flag']='✓雙源一致'; cnt['ok']+=1
            else:
                r['src']='5168'; r['flag']='✗價格不符'; r['leju_tp']=b[hit[0]]['tp']; cnt['price']+=1
        else:
            r['src']='5168'; r['flag']='⚠僅5168'; cnt['a_only']+=1
        out.append(r)
    for j,rb in enumerate(b):
        if j in used: continue
        r=dict(rb); r['src']='樂居'; r['flag']='⚠僅樂居'; cnt['b_only']+=1; out.append(r)
    print(f"\n📊 交叉比對結果：✓一致 {cnt['ok']} ｜⚠僅5168 {cnt['a_only']} ｜⚠僅樂居 {cnt['b_only']} ｜✗價格不符 {cnt['price']}")
    if cnt['price']: print("   ⚠️ 有價格不符的筆數，已標記並附上樂居價(leju_tp)，請人工核對後再採用。")
    return out

# ========== 輸出 ==========
def output(records, compared=False):
    if not records: print("\n（無資料）"); return
    if not compared:
        seen,uniq=set(),[]
        for r in records:
            k=(r['mon'],r['tp'],r['ta'],r['fl'])
            if k not in seen: seen.add(k); uniq.append(r)
        records=uniq
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"records.json")
    with open(path,"w",encoding="utf-8") as f: json.dump(records,f,ensure_ascii=False,indent=2)
    print(f"\n💾 已輸出 {len(records)} 筆 → {path}")
    if compared:
        trust=[r for r in records if r.get('flag') in ('✓雙源一致','⚠僅5168')]
        print(f"   👉 建議採用（一致＋僅5168）共 {len(trust)} 筆；其餘請先人工核對。")
    print("📋 整段複製貼到「房產戰情室 → 行情估價 → 匯入框」：\n")
    print(json.dumps(records, ensure_ascii=False))

# ========== 主程式 ==========
def main():
    # 雲端/命令列模式：有給參數就直接跑，不進選單（GitHub Actions 用）
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg:
        if arg.lower().endswith('.csv'):
            output(parse_moi_csv(arg)); return
        if 'houseprice' in arg or arg.startswith('http'):
            output(scrape_houseprice_url(arg)); return
        print("⚠️ 參數無法辨識，請給 5168 社區網址或 .csv 路徑。"); return
    print("="*60); print(f" 房產戰情室 · 抓取器 v3 交叉比對   (今 民國 {NOW_MINGUO} 年)"); print("="*60)
    print("  1) 5168 社區名自動抓")
    print("  2) 5168 社區網址抓")
    print("  3) 內政部 OpenData CSV")
    print("  4) 5168 × 樂居 交叉比對  ← 比對相符才放心")
    print("  5) 純樂居（Selenium）")
    c=input("輸入 1~5：").strip()
    if c=='1':
        city=input("縣市(例 台中市)：").strip(); dist=input("行政區(可空白)：").strip(); name=input("社區名：").strip()
        output(houseprice_by_name(name,city,dist))
    elif c=='2':
        output(scrape_houseprice_url(input("5168 社區網址：").strip()))
    elif c=='3':
        output(parse_moi_csv(input("CSV 路徑：").strip().strip('"')))
    elif c=='4':
        print("\n【交叉比對】先抓 5168，再抓樂居，自動比對。")
        u5=input("5168 社區網址：").strip()
        a=scrape_houseprice_url(u5)
        ul=input("樂居 社區網址：").strip()
        b=scrape_leju(ul)
        output(cross_compare(a,b), compared=True)
    elif c=='5':
        output(scrape_leju(input("樂居 網址：").strip()))
    else:
        print("未選擇，結束。")

if __name__ == "__main__":
    main()
