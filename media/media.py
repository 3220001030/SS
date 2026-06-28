from pathlib import Path
import re
import shutil
import pandas as pd
from tqdm.auto import tqdm

# ============================================================
# 1. 基础设置
# ============================================================

ROOT_DIR = Path("/Users/gurumakaza/Downloads")

# 输出目录：筛选后的 TXT 文件
OUT_DIR = ROOT_DIR / "classified_filtered_txt_by_region"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 是否清空旧输出目录
CLEAR_OUTPUT_DIR = False

# 是否覆盖同名文件
OVERWRITE = True

CASE_SENSITIVE = False

# 文件名规则：类型_地区-年份-序号.txt
FILENAME_RE = re.compile(
    r"^(?P<source_type>[^_]+)_(?P<region>[^-]+)-(?P<year>\d{4})-(?P<seq>\d+)\.txt$",
    re.IGNORECASE
)

# 避免扫描自己生成的目录
EXCLUDE_DIR_NAMES = {
    "txt_article_trend_figures",
    "txt_article_trend_figures_keyword",
    "txt_article_count_output",
    "classified_txt_by_region",
    "classified_articles_by_region",
    "classified_filtered_txt_by_region"
}


# ============================================================
# 2. 政治梗排除：明确排除政治梗，保留纯环保议题
# ============================================================

NEGATIVE_STRONG_KEYWORDS = [
    "吴敦义", "吳敦義", "Wu Den-yih", "Wu Den Yih", "Wu Dunyi",
    "吴副", "吳副",
    "吴主席", "吳主席",

    "白海豚会转弯", "白海豚會轉彎",
    "白海豚转弯", "白海豚轉彎",
    "会转弯的白海豚", "會轉彎的白海豚",
    "白海豚会不会转弯", "白海豚會不會轉彎",
    "white dolphin can turn",
    "white dolphins can turn",
    "dolphin can turn",
    "dolphins can turn",
    "海豚王子", "dolphin prince",

    "白贼义", "白賊義",
    "白贼", "白賊",

    "母猪说", "母豬說",
    "无薪假", "無薪假",
    "诺贝尔奖", "諾貝爾獎"
]

NEGATIVE_CONTEXT_KEYWORDS = [
    "2020大选", "2020大選", "2020 election",
    "台湾大选", "台灣大選", "Taiwan election",
    "总统大选", "總統大選", "presidential election",
    "总统初选", "總統初選", "presidential primary",
    "党内初选", "黨內初選", "party primary",
    "初选民调", "初選民調", "primary poll",
    "全民调", "全民調", "public poll",
    "征召", "徵召", "drafted candidate",
    "提名", "nomination",
    "换柱", "換柱",
    "全代会", "全代會", "party congress",
    "不分区立委", "不分區立委", "party-list legislator",

    "国民党", "國民黨", "Kuomintang", "KMT",
    "民进党", "民進黨", "Democratic Progressive Party", "DPP",
    "蓝营", "藍營", "pan-blue",
    "绿营", "綠營", "pan-green",
    "韩粉", "韓粉",
    "党员", "黨員", "party member",
    "党主席", "黨主席", "party chairman",

    "连战", "連戰", "Lien Chan",
    "柯文哲", "Ko Wen-je", "Ko Wen Je", "柯P", "柯Ｐ", "阿北",
    "韩国瑜", "韓國瑜", "Han Kuo-yu", "Han Kuo Yu", "韩市长", "韓市長",
    "朱立伦", "朱立倫", "Eric Chu", "Chu Li-luan",
    "王金平", "Wang Jin-pyng",
    "郭台铭", "郭台銘", "Terry Gou", "郭董",
    "洪秀柱", "Hung Hsiu-chu",
    "马英九", "馬英九", "Ma Ying-jeou",
    "蔡英文", "Tsai Ing-wen",
    "赖清德", "賴清德", "Lai Ching-te",
    "侯友宜", "Hou Yu-ih",
    "郝龙斌", "郝龍斌", "Hau Lung-bin",

    "总统", "總統", "president",
    "立委", "legislator",
    "选举", "選舉", "election",
    "选战", "選戰", "campaign",
    "参选", "參選", "run for office",
    "退选", "退選", "withdraw from election",
    "败选", "敗選", "lost election",
    "胜选", "勝選", "won election",
    "造势", "造勢", "campaign rally",
    "竞选", "競選", "election campaign",
    "辅选", "輔選",
    "选票", "選票", "ballot",
    "民调", "民調", "poll",
    "政治交易", "political deal",
    "地方派系", "local faction",
    "卖台", "賣台",
    "两岸", "兩岸", "cross-strait",
    "九二共识", "九二共識", "1992 Consensus"
]


# ============================================================
# 3. GD 内部海域正向关键词：中英双语
# ============================================================

GD_AREA_KEYWORDS = {
    # xm = 厦门湾 / Xiamen Bay
    "xm": [
        "厦门湾", "廈門灣", "Xiamen Bay",
        "厦门", "廈門", "Xiamen", "Amoy",
        "厦门海域", "廈門海域", "Xiamen waters",
        "九龙江口", "九龍江口", "Jiulong River estuary", "Jiulongjiang Estuary",
        "九龙江", "九龍江", "Jiulong River", "Jiulongjiang",
        "金门", "金門", "Kinmen", "Quemoy",
        "大嶝", "大嶝岛", "大嶝島", "Dadeng", "Dadeng Island",
        "小嶝", "小嶝岛", "小嶝島", "Xiaodeng", "Xiaodeng Island",
        "同安湾", "同安灣", "Tong'an Bay", "Tongan Bay",
        "海沧湾", "海滄灣", "Haicang Bay",
        "翔安", "Xiang'an", "Xiangan",
        "集美", "Jimei",
        "厦门中华白海豚", "廈門中華白海豚", "Xiamen Chinese white dolphin",
        "厦门白海豚", "廈門白海豚", "Xiamen white dolphin",
        "厦门珍稀海洋物种国家级自然保护区",
        "廈門珍稀海洋物種國家級自然保護區",
        "Xiamen Rare Marine Species National Nature Reserve",
        "Xiamen Rare Marine Species National Nature Reserve for Chinese White Dolphins"
    ],

    # pr = 珠江口 / Pearl River Estuary
    # pr = 珠江口 / Pearl River Estuary
# pr = 珠江口 / Pearl River Estuary
"pr": [
    # ====================================================
    # A. 珠江口 / 珠三角 / 粤港澳大湾区明确空间词
    # ====================================================
    "珠江口",
    "珠江河口",
    "Pearl River Estuary",

    "珠江三角洲",
    "Pearl River Delta",

    "粤港澳大湾区",
    "粵港澳大灣區",
    "大湾区",
    "大灣區",
    "Greater Bay Area",
    "Guangdong-Hong Kong-Macao Greater Bay Area",
    "Guangdong-Hong Kong-Macau Greater Bay Area",

    "粤港澳",
    "粵港澳",
    "Guangdong-Hong Kong-Macao",
    "Guangdong-Hong Kong-Macau",

    # ====================================================
    # B. 伶仃洋 / 珠江口保护区 / 珠海核心海域
    # ====================================================
    "伶仃洋",
    "Lingdingyang",
    "Lingding Yang",

    "内伶仃",
    "內伶仃",
    "Neilingding",
    "Nei Lingding",

    "外伶仃",
    "Wailingding",

    "牛头岛",
    "牛頭島",
    "Niutou Island",

    "珠海",
    "Zhuhai",

    "淇澳",
    "Qi'ao",
    "Qi Ao",

    "关帝湾",
    "關帝灣",
    "Guandi Bay",

    "桂山",
    "Guishan",

    "万山",
    "萬山",
    "Wanshan",

    "担杆",
    "擔杆",
    "Dangan",

    "珠江口中华白海豚国家级自然保护区",
    "珠江口中華白海豚國家級自然保護區",
    "珠江口白海豚保护区",
    "珠江口白海豚保護區",
    "Pearl River Estuary Chinese White Dolphin National Nature Reserve",
    "Pearl River Estuary Chinese white dolphin reserve",

    # ====================================================
    # C. 江门 / 台山 / 川岛 / 珠江口西岸相关词
    # ====================================================
    "江门",
    "江門",
    "Jiangmen",

    "台山",
    "Taishan",

    "川岛",
    "川島",
    "Chuandao",

    "上川岛",
    "上川島",
    "Shangchuan",

    "下川岛",
    "下川島",
    "Xiachuan",

    "川山群岛",
    "川山群島",
    "Chuanshan",

    "广海湾",
    "廣海灣",
    "Guanghai Bay",

    "广海",
    "廣海",
    "Guanghai",

    "镇海湾",
    "鎮海灣",
    "Zhenhai Bay",

    "崖门",
    "崖門",
    "Yamen",

    "银洲湖",
    "銀洲湖",
    "Yinzhou Lake",

    "黄茅海",
    "黃茅海",
    "Huangmao Sea",

    "新会",
    "新會",
    "Xinhui",

    "恩平",
    "Enping",

    "开平",
    "開平",
    "Kaiping",

    "鹤山",
    "鶴山",
    "Heshan",

    # ====================================================
    # D. 香港 / 澳门 / 港珠澳及香港西部白海豚水域
    # ====================================================
    "香港",
    "Hong Kong",

    "澳门",
    "澳門",
    "Macao",
    "Macau",

    "港珠澳",
    "Hong Kong-Zhuhai-Macao",
    "Hong Kong-Zhuhai-Macau",

    "港珠澳大桥",
    "港珠澳大橋",
    "Hong Kong-Zhuhai-Macao Bridge",
    "Hong Kong-Zhuhai-Macau Bridge",

    "大屿山",
    "大嶼山",
    "Lantau",

    "西大屿",
    "西大嶼",
    "West Lantau",

    "南大屿",
    "南大嶼",
    "South Lantau",

    "北大屿",
    "北大嶼",
    "North Lantau",

    "赤鱲角",
    "Chek Lap Kok",

    "香港国际机场",
    "香港國際機場",
    "Hong Kong International Airport",

    "三跑",
    "third runway",
    "Three-Runway System",

    "屯门",
    "屯門",
    "Tuen Mun",

    "龙鼓洲",
    "龍鼓洲",
    "Lung Kwu Chau",

    "沙洲",
    "Sha Chau",

    "沙洲及龙鼓洲",
    "沙洲及龍鼓洲",
    "Sha Chau and Lung Kwu Chau",

    "沙洲及龙鼓洲海岸公园",
    "沙洲及龍鼓洲海岸公園",
    "Sha Chau and Lung Kwu Chau Marine Park",

    "北大屿海岸公园",
    "北大嶼海岸公園",
    "North Lantau Marine Park",

    "西南大屿海岸公园",
    "西南大嶼海岸公園",
    "Southwest Lantau Marine Park",

    "南大屿海岸公园",
    "南大嶼海岸公園",
    "South Lantau Marine Park",

    "大小磨刀",
    "大小磨刀洲",
    "The Brothers",
    "Tai Mo To",
    "Siu Mo To",

    "索罟群岛",
    "索罟群島",
    "Soko Islands",

    "南丫岛",
    "南丫島",
    "Lamma",

    # ====================================================
    # E. 深圳 / 广州 / 中山 / 东莞等珠江口沿岸明确空间词
    # ====================================================
    "深圳湾",
    "深圳灣",
    "Shenzhen Bay",

    "前海",
    "Qianhai",

    "大铲湾",
    "大鏟灣",
    "Dachan Bay",
    "Da Chan Bay",

    "蛇口",
    "Shekou",

    "妈湾",
    "媽灣",
    "Mawan",

    "宝安机场",
    "寶安機場",
    "Bao'an Airport",
    "Baoan Airport",

    "南沙",
    "Nansha",

    "广州南沙",
    "廣州南沙",
    "Guangzhou Nansha",

    "虎门",
    "虎門",
    "Humen",

    "虎门大桥",
    "虎門大橋",
    "Humen Bridge",

    "虎门港",
    "虎門港",
    "Humen Port",

    "深中通道",
    "Shenzhen-Zhongshan Link",

    "深中大桥",
    "深中大橋",
    "Shenzhen-Zhongshan Bridge",

    "深圳中山通道",

    "伶仃洋大桥",
    "伶仃洋大橋",
    "Lingdingyang Bridge",

    # ====================================================
    # F. 十五运会 / 残特奥会 / 吉祥物传播词
    # 原则：已有短词能覆盖长词时，全部删掉长词
    # ====================================================
    "十五运",
    "十五運",
    "15th National Games",

    "残特",
    "殘特",

    "残运",
    "殘運",

    "喜洋洋",
    "Xi Yangyang",
    "Xi Yang Yang",
    "Xiyangyang",

    "乐融融",
    "樂融融",
    "Le Rongrong",
    "Le Rong Rong",
    "Lerongrong",

    "大湾鸡",
    "大灣雞",

    "湾鸡",
    "灣雞",

    "走地鸡",
    "走地雞",

    "Greater Bay chicken",
    "Greater Bay Area chicken",

    "头顶三色浪花",
    "頭頂三色浪花",
    "三色浪花",

    "木棉红",
    "木棉紅",

    "紫荆紫",
    "紫荊紫",

    "莲花绿",
    "蓮花綠",

    "活力大湾区",
    "活力大灣區",

    "追梦大湾区",
    "追夢大灣區",

    "出彩人生路"
],

    # bb = 北部湾 / Beibu Gulf
    "bb": [
        "北部湾", "北部灣", "Beibu Gulf", "Gulf of Tonkin",
        "广西", "廣西", "Guangxi",
        "钦州", "欽州", "Qinzhou",
        "钦州湾", "欽州灣", "Qinzhou Bay",
        "三娘湾", "三娘灣", "Sanniang Bay",
        "大风江", "大風江", "Dafengjiang",
        "大风江口", "大風江口", "Dafengjiang Estuary",
        "南流江", "Nanliujiang", "Nanliu River",
        "南流江口", "Nanliujiang Estuary", "Nanliu River Estuary",
        "沙田", "Shatian",
        "草潭", "Caotan",
        "北海", "Beihai",
        "合浦", "Hepu",
        "合浦儒艮", "Hepu dugong",
        "合浦儒艮国家级自然保护区",
        "合浦儒艮國家級自然保護區",
        "Hepu Dugong National Nature Reserve",
        "防城港", "Fangchenggang",
        "北仑河", "北侖河", "Beilun River",
        "北仑河口", "北侖河口", "Beilun River Estuary",
        "涠洲岛", "潿洲島", "Weizhou Island",
        "北部湾大学", "北部灣大學", "Beibu Gulf University",
        "北部湾鲸豚", "北部灣鯨豚", "Beibu Gulf cetacean"
    ],

    # st = 汕头 / Shantou
    "st": [
        "汕头", "汕頭", "Shantou",
        "汕头湾", "汕頭灣", "Shantou Bay",
        "汕头海域", "汕頭海域", "Shantou waters",
        "韩江", "韓江", "Hanjiang", "Han River",
        "韩江口", "韓江口", "Hanjiang Estuary", "Han River Estuary",
        "榕江", "Rongjiang", "Rong River",
        "练江", "練江", "Lianjiang", "Lian River",
        "海门湾", "海門灣", "Haimen Bay",
        "海门", "海門", "Haimen",
        "南澳", "Nan'ao", "Nanao",
        "南澳岛", "南澳島", "Nan'ao Island", "Nanao Island",
        "青澳湾", "青澳灣", "Qing'ao Bay", "Qingao Bay",
        "东海岸新城", "東海岸新城", "East Coast New Town",
        "潮汕", "Chaoshan",
        "澄海", "Chenghai",
        "濠江", "Haojiang",
        "妈屿", "媽嶼", "Mayu Island", "Ma Yu"
    ],

    # lz = 雷州湾 / Leizhou Bay
    "lz": [
        "雷州湾", "雷州灣", "Leizhou Bay",
        "雷州", "Leizhou",
        "湛江", "Zhanjiang",
        "湛江港", "Zhanjiang Port",
        "徐闻", "徐聞", "Xuwen",
        "遂溪", "Suixi",
        "廉江", "Lianjiang",
        "吴川", "吳川", "Wuchuan",
        "麻章", "Mazhang",
        "东海岛", "東海島", "Donghai Island",
        "硇洲", "硇洲岛", "硇洲島", "Naozhou", "Naozhou Island",
        "特呈岛", "特呈島", "Techeng Island",
        "南三岛", "南三島", "Nansan Island",
        "雷州湾中华白海豚",
        "雷州灣中華白海豚",
        "Leizhou Bay Chinese white dolphin",
        "雷州湾中华白海豚市级自然保护区",
        "雷州灣中華白海豚市級自然保護區",
        "Leizhou Bay Chinese White Dolphin Municipal Nature Reserve",
        "雷州湾白海豚", "雷州灣白海豚",
        "Leizhou Bay white dolphin"
    ]
}

# hk / mo 文件不拆海域，直接按地区输出筛选后的原文件
DIRECT_REGION_FOLDERS = {
    "hk": "hk",
    "mo": "mo"
}


# ============================================================
# 4. 工具函数
# ============================================================

def read_text_safely(path: Path) -> str:
    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk", "big5"]

    for enc in encodings:
        try:
            return path.read_text(encoding=enc, errors="strict")
        except UnicodeDecodeError:
            continue

    return path.read_text(encoding="gb18030", errors="ignore")


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")

def remove_wisers_boilerplate(text: str) -> str:
    """
    去掉：
    1. 每篇文章末尾的慧科内容声明；
    2. 文章或链接资源免责声明；
    3. 整个 TXT 末尾的慧科版权尾注。
    """

    text = normalize_text(text)

    # 1. 去掉每篇文章末尾的慧科内容声明
    article_notice_re = re.compile(
        r"\s*本内容经慧科的电子服务提供。"
        r"\s*以上内容、商标和标记属慧科、相关机构或版权拥有人所有，并保留一切权利。"
        r"\s*使用者提供的任何内容由使用者自行负责，慧科不会对该等内容、版权许可或由此引起的任何损害\s*[／/]\s*损失承担责任。"
        r"\s*",
        flags=re.S
    )
    text = article_notice_re.sub("\n", text)

    # 2. 去掉“所有文章或连结中所列载...”资源免责声明
    resource_notice_re = re.compile(
        r"\s*-{10,}\s*"
        r"所有文章或连结中所列载、可下载或提供之所有文字、图片、声带、影像、连结、档案及其他内容或资源"
        r"\(以上各项统称[\"“]资源[\"”]\)"
        r"均由有关媒体、网站拥有人或其他第三者拥有。"
        r"\s*阁下确认及同意，慧科讯业有限公司\([\"“]慧科[\"”]\)"
        r"对于该等资源并没有控制权及对该等资源的可用性、准确性、内容、合法性不需及不接受负任何责任，"
        r"慧科亦没有认可或推荐任何资源所涉的广告、产品或其他物品。"
        r"另外，阁下确认及同意，慧科不需就任何使用或依赖任何资源而引起或与之有关或任何其他的直接或间接的损害或损失负上任何责任。"
        r"\s*",
        flags=re.S
    )
    text = resource_notice_re.sub("\n", text)

    # 3. 去掉 TXT 文件末尾的慧科版权尾注
    footer_re = re.compile(
        r"\n?=+\s*\n"
        r"慧科讯业有限公司\s+查询请电:\s*\(852\)\s*2948\s*3888\s+"
        r"电邮速递:\s*sales@wisers\.com\s+网址:\s*http://www\.wisers\.com\s*\n"
        r"版权所有\s*©\s*\d{4}\s*慧科讯业\.\s*保留所有权利\.\s*",
        flags=re.S
    )
    text = footer_re.sub("\n", text)

    # 4. 清理多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

def should_skip_path(path: Path) -> bool:
    return bool(set(path.parts) & EXCLUDE_DIR_NAMES)


def make_keyword_pattern(keywords, case_sensitive=False):
    valid_keywords = [str(kw).strip() for kw in keywords if kw and str(kw).strip()]
    if not valid_keywords:
        return None

    valid_keywords = sorted(set(valid_keywords), key=len, reverse=True)
    escaped = [re.escape(k) for k in valid_keywords]
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile("|".join(escaped), flags=flags)


def find_matched_keywords(text: str, keywords, case_sensitive=False):
    matched = []

    if not case_sensitive:
        text_cmp = text.lower()
        for kw in keywords:
            kw_str = str(kw).strip()
            if kw_str and kw_str.lower() in text_cmp:
                matched.append(kw_str)
    else:
        for kw in keywords:
            kw_str = str(kw).strip()
            if kw_str and kw_str in text:
                matched.append(kw_str)

    return sorted(set(matched), key=lambda x: (len(x), x), reverse=True)


NEGATIVE_STRONG_RE = make_keyword_pattern(NEGATIVE_STRONG_KEYWORDS, CASE_SENSITIVE)
NEGATIVE_CONTEXT_RE = make_keyword_pattern(NEGATIVE_CONTEXT_KEYWORDS, CASE_SENSITIVE)

GD_AREA_RE = {
    area_code: make_keyword_pattern(keywords, CASE_SENSITIVE)
    for area_code, keywords in GD_AREA_KEYWORDS.items()
}


def article_pass_global_filter(block: str) -> bool:
    """
    明确排除政治梗，但保留纯环保议题。
    """

    block = normalize_text(block)

    if NEGATIVE_STRONG_RE is not None and NEGATIVE_STRONG_RE.search(block):
        return False

    political_near_dolphin_re = re.compile(
        r"(白海豚|中華白海豚|中华白海豚|Chinese white dolphin|Indo-Pacific humpback dolphin|pink dolphin).{0,40}"
        r"(国民党|國民黨|Kuomintang|KMT|民进党|民進黨|DPP|总统|總統|president|"
        r"选举|選舉|election|选战|選戰|campaign|初选|初選|primary|立委|legislator|"
        r"党员|黨員|party member|韩国瑜|韓國瑜|Han Kuo-yu|柯文哲|Ko Wen-je|柯P|阿北|"
        r"连战|連戰|Lien Chan|朱立伦|朱立倫|Eric Chu|王金平|Wang Jin-pyng|"
        r"郭台铭|郭台銘|Terry Gou|蔡英文|Tsai Ing-wen|赖清德|賴清德|Lai Ching-te|"
        r"卖台|賣台|两岸|兩岸|cross-strait|九二共识|九二共識|1992 Consensus)"
        r"|"
        r"(国民党|國民黨|Kuomintang|KMT|民进党|民進黨|DPP|总统|總統|president|"
        r"选举|選舉|election|选战|選戰|campaign|初选|初選|primary|立委|legislator|"
        r"党员|黨員|party member|韩国瑜|韓國瑜|Han Kuo-yu|柯文哲|Ko Wen-je|柯P|阿北|"
        r"连战|連戰|Lien Chan|朱立伦|朱立倫|Eric Chu|王金平|Wang Jin-pyng|"
        r"郭台铭|郭台銘|Terry Gou|蔡英文|Tsai Ing-wen|赖清德|賴清德|Lai Ching-te|"
        r"卖台|賣台|两岸|兩岸|cross-strait|九二共识|九二共識|1992 Consensus)"
        r".{0,40}(白海豚|中華白海豚|中华白海豚|Chinese white dolphin|Indo-Pacific humpback dolphin|pink dolphin)",
        flags=0 if CASE_SENSITIVE else re.IGNORECASE
    )

    if political_near_dolphin_re.search(block):
        return False

    return True


def split_article_blocks(text: str):
    """
    将一个 TXT 切成文章块。
    优先用 1. 2. 3. 文章序号切分；
    没有序号时，用文章编号兜底。
    返回每篇文章的完整 block。
    """

    text = remove_wisers_boilerplate(text)

    # 去掉文件开头文章总数说明
    text_body = re.sub(
        r"^\s*文章总数\s*[:：]\s*\d+\s*篇\s*\n=+\s*",
        "",
        text,
        flags=re.S
    )

    start_re = re.compile(r"(?m)^\s*(?P<idx>\d+)\.\s+(?P<header>.+?)\s*$")
    starts = list(start_re.finditer(text_body))

    blocks = []

    if starts:
        for i, start in enumerate(starts):
            block_start = start.start()
            block_end = starts[i + 1].start() if i + 1 < len(starts) else len(text_body)
            block = text_body[block_start:block_end].strip()

            id_match = re.search(r"文章编号\s*[:：]\s*([^\s\r\n]+)", block)
            article_id = id_match.group(1).strip() if id_match else f"item_{i + 1:04d}"

            blocks.append({
                "old_index": int(start.group("idx")),
                "article_id": article_id,
                "block": block
            })

        return blocks

    # 兜底：没有序号行，用文章编号切
    id_iter = list(re.finditer(r"文章编号\s*[:：]\s*([^\s\r\n]+)", text_body))

    if id_iter:
        prev_end = 0
        seen_ids = set()

        for i, m in enumerate(id_iter):
            article_id = m.group(1).strip()

            if article_id in seen_ids:
                prev_end = m.end()
                continue

            seen_ids.add(article_id)

            block = text_body[prev_end:m.end()].strip()

            blocks.append({
                "old_index": i + 1,
                "article_id": article_id,
                "block": block
            })

            prev_end = m.end()

    return blocks


def reindex_article_block(block: str, new_index: int):
    """
    把文章开头的旧编号改成新编号。
    例如：
    23. xxx
    改成：
    1. xxx
    """

    block = normalize_text(block).strip()

    if re.match(r"^\s*\d+\.\s+", block):
        block = re.sub(
            r"^\s*\d+\.\s+",
            f"{new_index}. ",
            block,
            count=1
        )
    else:
        block = f"{new_index}. {block}"

    return block


def build_filtered_txt(article_blocks):
    """
    根据筛选后的文章块，重新生成一个 Wisers 风格 TXT。
    """

    lines = []
    lines.append(f"文章总数: {len(article_blocks)} 篇")
    lines.append("=" * 30)
    lines.append("")

    for i, item in enumerate(article_blocks, start=1):
        clean_block = remove_wisers_boilerplate(item["block"])
        lines.append(reindex_article_block(clean_block, i))
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def get_matched_gd_areas(block: str):
    """
    对 gd 单篇文章做海域分类。
    只使用 gd 内部正向关键词。
    """

    matched_areas = []
    matched_keywords_by_area = {}

    for area_code, area_re in GD_AREA_RE.items():
        if area_re is not None and area_re.search(block):
            matched_areas.append(area_code)
            matched_keywords_by_area[area_code] = find_matched_keywords(
                block,
                GD_AREA_KEYWORDS[area_code],
                CASE_SENSITIVE
            )

    return sorted(matched_areas), matched_keywords_by_area


def build_output_filename(source_type, target_region, year, seq):
    """
    输出命名不再使用 gd，而使用所属地区/海域。
    例如：
    press_gd-2020-01.txt -> press_pr-2020-01.txt
    forum_gd-2018-12.txt -> forum_lz-2018-12.txt
    """

    return f"{source_type}_{target_region}-{int(year):04d}-{int(seq):02d}.txt"


def safe_write_text(dst_path: Path, content: str):
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if dst_path.exists() and not OVERWRITE:
        stem = dst_path.stem
        suffix = dst_path.suffix
        i = 1
        while True:
            candidate = dst_path.parent / f"{stem}__copy{i}{suffix}"
            if not candidate.exists():
                dst_path = candidate
                break
            i += 1

    dst_path.write_text(content, encoding="utf-8-sig")
    return dst_path


def copy_or_write_direct_region_file(txt_path, info, target_region):
    """
    hk / mo / 其他非 gd 地区：
    也按文章做政治梗过滤，然后重写一个同结构 TXT。
    如果不想过滤 hk/mo，可把这里改成 shutil.copy2。
    """

    source_type = info["source_type"]
    year = int(info["year"])
    seq = int(info["seq"])

    text = read_text_safely(txt_path)
    articles = split_article_blocks(text)

    kept_articles = [
        item for item in articles
        if article_pass_global_filter(item["block"])
    ]

    if not kept_articles:
        return None, 0, len(articles)

    out_text = build_filtered_txt(kept_articles)
    out_name = build_output_filename(source_type, target_region, year, seq)
    dst_path = OUT_DIR / target_region / out_name

    written_path = safe_write_text(dst_path, out_text)

    return written_path, len(kept_articles), len(articles)


def process_gd_file(txt_path, info):
    """
    gd 文件：
    从原 TXT 中筛出命中各海域正向关键词的文章，
    分别写成 press_pr-2020-01.txt、press_lz-2020-01.txt 等。
    """

    source_type = info["source_type"]
    year = int(info["year"])
    seq = int(info["seq"])

    text = read_text_safely(txt_path)
    articles = split_article_blocks(text)

    area_articles = {area_code: [] for area_code in GD_AREA_KEYWORDS.keys()}
    area_keywords = {area_code: set() for area_code in GD_AREA_KEYWORDS.keys()}

    political_removed_count = 0
    unmatched_article_count = 0

    for item in articles:
        block = item["block"]

        if not article_pass_global_filter(block):
            political_removed_count += 1
            continue

        matched_areas, matched_keywords_by_area = get_matched_gd_areas(block)

        if not matched_areas:
            unmatched_article_count += 1
            continue

        for area_code in matched_areas:
            area_articles[area_code].append(item)
            for kw in matched_keywords_by_area.get(area_code, []):
                area_keywords[area_code].add(kw)

    written_records = []

    for area_code, kept_articles in area_articles.items():
        if not kept_articles:
            continue

        out_text = build_filtered_txt(kept_articles)
        out_name = build_output_filename(source_type, area_code, year, seq)
        dst_path = OUT_DIR / area_code / out_name

        written_path = safe_write_text(dst_path, out_text)

        written_records.append({
            "目标地区/海域": area_code,
            "输出文件": str(written_path),
            "写出文章数": len(kept_articles),
            "命中关键词": ", ".join(sorted(area_keywords[area_code]))
        })

    return {
        "总文章数": len(articles),
        "政治梗排除文章数": political_removed_count,
        "未命中海域文章数": unmatched_article_count,
        "写出记录": written_records
    }


# ============================================================
# 5. 收集 TXT 文件
# ============================================================

def collect_txt_files(root_dir: Path):
    all_txt_files = list(root_dir.rglob("*.txt"))

    target_files = []
    unmatched_files = []

    for txt_path in tqdm(all_txt_files, desc="扫描 TXT 文件", unit="file"):
        if should_skip_path(txt_path):
            continue

        match = FILENAME_RE.match(txt_path.name)

        if match:
            target_files.append((txt_path, match.groupdict()))
        else:
            unmatched_files.append(txt_path)

    return target_files, unmatched_files, len(all_txt_files)


# ============================================================
# 6. 主流程：文件级筛选重写
# ============================================================

if CLEAR_OUTPUT_DIR and OUT_DIR.exists():
    shutil.rmtree(OUT_DIR)

OUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 90)
print("开始文件级筛选归类")
print("=" * 90)
print(f"扫描目录：{ROOT_DIR}")
print(f"输出目录：{OUT_DIR}")
print("说明：不会拆成单篇文章文件；会把原 TXT 筛选后重写为新的 TXT。")
print("示例：press_gd-2020-01.txt -> press_pr-2020-01.txt")

target_files, unmatched_files, all_txt_count = collect_txt_files(ROOT_DIR)

records = []
error_records = []

print()
print(f"扫描到 TXT 文件总数：{all_txt_count}")
print(f"符合命名规则文件数：{len(target_files)}")
print(f"文件名不符合规则文件数：{len(unmatched_files)}")
print()
print("开始处理文件...")

for txt_path, info in tqdm(target_files, desc="筛选归类 TXT", unit="file"):
    original_region = info["region"].lower()
    source_type = info["source_type"]
    year = int(info["year"])
    seq = int(info["seq"])

    try:
        # hk / mo：按地区输出筛选后的 TXT
        if original_region in DIRECT_REGION_FOLDERS:
            target_region = DIRECT_REGION_FOLDERS[original_region]

            written_path, kept_count, total_count = copy_or_write_direct_region_file(
                txt_path=txt_path,
                info=info,
                target_region=target_region
            )

            records.append({
                "原始文件": txt_path.name,
                "原始地区": original_region,
                "类型": source_type,
                "年份": year,
                "序号": seq,
                "目标地区/海域": target_region,
                "总文章数": total_count,
                "写出文章数": kept_count,
                "政治梗排除文章数": total_count - kept_count,
                "未命中海域文章数": "",
                "命中关键词": "",
                "输出文件": str(written_path) if written_path else "",
                "状态": "已写出" if written_path else "筛选后无文章，未写出",
                "原路径": str(txt_path)
            })

        # gd：筛选成 xm / pr / bb / st / lz 多个 TXT
        elif original_region == "gd":
            result = process_gd_file(txt_path, info)

            if result["写出记录"]:
                for item in result["写出记录"]:
                    records.append({
                        "原始文件": txt_path.name,
                        "原始地区": original_region,
                        "类型": source_type,
                        "年份": year,
                        "序号": seq,
                        "目标地区/海域": item["目标地区/海域"],
                        "总文章数": result["总文章数"],
                        "写出文章数": item["写出文章数"],
                        "政治梗排除文章数": result["政治梗排除文章数"],
                        "未命中海域文章数": result["未命中海域文章数"],
                        "命中关键词": item["命中关键词"],
                        "输出文件": item["输出文件"],
                        "状态": "已写出",
                        "原路径": str(txt_path)
                    })
            else:
                records.append({
                    "原始文件": txt_path.name,
                    "原始地区": original_region,
                    "类型": source_type,
                    "年份": year,
                    "序号": seq,
                    "目标地区/海域": "gd_no_match",
                    "总文章数": result["总文章数"],
                    "写出文章数": 0,
                    "政治梗排除文章数": result["政治梗排除文章数"],
                    "未命中海域文章数": result["未命中海域文章数"],
                    "命中关键词": "",
                    "输出文件": "",
                    "状态": "gd筛选后无海域命中文章，未写出",
                    "原路径": str(txt_path)
                })

        # 其他地区：按原地区输出筛选后的 TXT
        else:
            target_region = original_region

            written_path, kept_count, total_count = copy_or_write_direct_region_file(
                txt_path=txt_path,
                info=info,
                target_region=target_region
            )

            records.append({
                "原始文件": txt_path.name,
                "原始地区": original_region,
                "类型": source_type,
                "年份": year,
                "序号": seq,
                "目标地区/海域": target_region,
                "总文章数": total_count,
                "写出文章数": kept_count,
                "政治梗排除文章数": total_count - kept_count,
                "未命中海域文章数": "",
                "命中关键词": "",
                "输出文件": str(written_path) if written_path else "",
                "状态": "已写出" if written_path else "筛选后无文章，未写出",
                "原路径": str(txt_path)
            })

    except Exception as e:
        error_records.append({
            "文件名": txt_path.name,
            "原路径": str(txt_path),
            "原因": str(e)
        })


# ============================================================
# 7. 文件名不符合规则的 TXT：只记录，不处理
# ============================================================

for txt_path in unmatched_files:
    records.append({
        "原始文件": txt_path.name,
        "原始地区": "",
        "类型": "",
        "年份": "",
        "序号": "",
        "目标地区/海域": "_unmatched_filename",
        "总文章数": "",
        "写出文章数": "",
        "政治梗排除文章数": "",
        "未命中海域文章数": "",
        "命中关键词": "",
        "输出文件": "",
        "状态": "文件名不符合规则，未处理",
        "原路径": str(txt_path)
    })


# ============================================================
# 8. 输出 manifest 和简明汇总
# ============================================================

records_df = pd.DataFrame(records)
error_df = pd.DataFrame(error_records)

manifest_path = OUT_DIR / "_classification_manifest.csv"
records_df.to_csv(manifest_path, index=False, encoding="utf-8-sig")

if not error_df.empty:
    error_path = OUT_DIR / "_classification_errors.csv"
    error_df.to_csv(error_path, index=False, encoding="utf-8-sig")
else:
    error_path = None

print()
print("=" * 90)
print("文件级筛选归类完成")
print("=" * 90)
print(f"输出目录：{OUT_DIR}")
print(f"Manifest：{manifest_path}")

if error_path:
    print(f"错误文件记录：{error_path}")

print(f"总记录数：{len(records_df)}")
print(f"失败文件数：{len(error_df)}")

written_df = records_df[records_df["状态"] == "已写出"].copy()

if not written_df.empty:
    summary_df = (
        written_df
        .groupby("目标地区/海域", as_index=False)["输出文件"]
        .nunique()
        .rename(columns={"输出文件": "写出TXT文件数"})
        .sort_values("目标地区/海域")
        .reset_index(drop=True)
    )

    article_summary_df = (
        written_df
        .groupby("目标地区/海域", as_index=False)["写出文章数"]
        .sum()
        .sort_values("目标地区/海域")
        .reset_index(drop=True)
    )

    print()
    print("各分类写出 TXT 文件数：")
    print(summary_df.to_string(index=False))

    print()
    print("各分类写出文章数：")
    print(article_summary_df.to_string(index=False))
else:
    print()
    print("没有写出任何筛选后的 TXT。")

status_df = (
    records_df
    .groupby("状态", as_index=False)["原始文件"]
    .count()
    .rename(columns={"原始文件": "记录数"})
    .sort_values("状态")
    .reset_index(drop=True)
)

print()
print("处理状态汇总：")
print(status_df.to_string(index=False))

if not error_df.empty:
    print()
    print("失败文件：")
    print(error_df.to_string(index=False))