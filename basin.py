import geopandas as gpd
import pandas as pd
import json
import folium
import math

# ======================
# 1. 数据加载
# ======================
gdb = "/Users/gurumakaza/Downloads/RiverLakeBasins_Asia.gdb/RiverLakeBasins_Asia.gdb"
gdf9 = gpd.read_file(gdb, layer="level_9")
gdf10 = gpd.read_file(gdb, layer="level_10")

basins = pd.concat([gdf9, gdf10], ignore_index=True)
basins = gpd.GeoDataFrame(basins).to_crs("EPSG:4326")
basins = basins.cx[111.0:114.5, 21.0:25.5]

basins["Basin_ID"] = pd.to_numeric(basins["Basin_ID"], errors="coerce").astype("Int64")
basins["Down_ID"] = pd.to_numeric(basins["Down_ID"], errors="coerce").fillna(0).astype("Int64")
basins = basins.dropna(subset=["Basin_ID"]).reset_index(drop=True)

# Type 转为普通 int，方便后续判断
basins["Type_int"] = pd.to_numeric(basins["Type"], errors="coerce").fillna(-999).astype(int)

# ======================
# 2. 构建下游 & 上游关系（核心）
# ======================
down_dict = {int(row["Basin_ID"]): int(row["Down_ID"]) for _, row in basins.iterrows()}

# 反向映射：用于查找上游
upstream_dict = {}
for bid, did in down_dict.items():
    if did != 0:
        if did not in upstream_dict:
            upstream_dict[did] = []
        upstream_dict[did].append(bid)

def get_downstream_chain(bid, down_dict, max_depth=50):
    chain = []
    current = bid
    visited = set()
    while len(chain) < max_depth:
        if current in visited or current == 0:
            break
        visited.add(current)
        chain.append(current)
        current = down_dict.get(current, 0)
    return [str(x) for x in chain]

def get_upstream_chain(bid, upstream_dict, max_depth=50):
    chain = []
    to_visit = [bid]
    visited = set()
    while to_visit and len(chain) < max_depth * 2:
        current = to_visit.pop(0)
        if current in visited or current == 0:
            continue
        visited.add(current)
        chain.append(current)
        parents = upstream_dict.get(current, [])
        to_visit.extend(parents)
    chain = [x for x in chain if x != bid]
    return [str(x) for x in chain]

# 预计算所有 basin 的上下游链
basin_data = {}
basin_down_chains = {}
basin_up_chains = {}

# 每个 basin 的 Type 映射，给 JS resetAll 使用
basin_type_map = {}

for _, row in basins.iterrows():
    bid = int(row["Basin_ID"])
    bid_str = str(bid)
    type_int = int(row["Type_int"])

    basin_type_map[bid_str] = type_int
    
    basin_data[bid_str] = {
        "Basin_ID": bid,
        "Down_ID": int(row["Down_ID"]),
        "Type": row.get("Type"),
        "Area": row.get("Area"),
        "HylakID": row.get("HylakID"),
        "Ednor": row.get("Ednor")
    }
    
    basin_down_chains[bid_str] = get_downstream_chain(bid, down_dict)[1:]
    basin_up_chains[bid_str] = get_upstream_chain(bid, upstream_dict)


# ======================
# 2.5 隔离模块：预计算 hover 流动箭头数据
# 不影响原有 hover 高亮逻辑
# ======================

basin_points = {}

for _, row in basins.iterrows():
    bid = int(row["Basin_ID"])
    geom = row["geometry"]

    if geom is None or geom.is_empty:
        continue

    p = geom.representative_point()

    basin_points[str(bid)] = {
        "lat": float(p.y),
        "lng": float(p.x)
    }


def make_arrow_head(lat1, lng1, lat2, lng2):
    """
    根据 from -> to 生成箭头头部的两条边。
    这里在 Python 端提前算好，JS 只负责显示，避免破坏原逻辑。
    """
    mid_lat = (lat1 + lat2) / 2.0
    cos_lat = math.cos(math.radians(mid_lat))

    x1 = lng1 * cos_lat
    y1 = lat1
    x2 = lng2 * cos_lat
    y2 = lat2

    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)

    if length == 0:
        return None

    ux = dx / length
    uy = dy / length

    tip_x = x1 + dx * 0.72
    tip_y = y1 + dy * 0.72

    arrow_len = min(max(length * 0.18, 0.012), 0.04)
    arrow_wid = arrow_len * 0.45

    base_x = tip_x - ux * arrow_len
    base_y = tip_y - uy * arrow_len

    px = -uy
    py = ux

    left_x = base_x + px * arrow_wid
    left_y = base_y + py * arrow_wid

    right_x = base_x - px * arrow_wid
    right_y = base_y - py * arrow_wid

    tip_lat = tip_y
    tip_lng = tip_x / cos_lat

    left_lat = left_y
    left_lng = left_x / cos_lat

    right_lat = right_y
    right_lng = right_x / cos_lat

    return [
        [left_lat, left_lng],
        [tip_lat, tip_lng],
        [right_lat, right_lng]
    ]


flow_edges_by_basin = {}

for bid_str in basin_data.keys():
    active_set = set()
    active_set.add(bid_str)

    for did in basin_down_chains.get(bid_str, []):
        active_set.add(str(did))

    for uid in basin_up_chains.get(bid_str, []):
        active_set.add(str(uid))

    edges = []

    for sid in active_set:
        did = str(down_dict.get(int(sid), 0))

        if did in ["0", "-1"]:
            continue

        if did not in active_set:
            continue

        if sid not in basin_points or did not in basin_points:
            continue

        lat1 = basin_points[sid]["lat"]
        lng1 = basin_points[sid]["lng"]
        lat2 = basin_points[did]["lat"]
        lng2 = basin_points[did]["lng"]

        arrow_head = make_arrow_head(lat1, lng1, lat2, lng2)

        if arrow_head is None:
            continue

        edges.append({
            "line": [
                [lat1, lng1],
                [lat2, lng2]
            ],
            "head": arrow_head
        })

    flow_edges_by_basin[bid_str] = edges


# ======================
# 3. 地图 + CSS
# ======================
m = folium.Map(
    location=[22.2, 113.2],
    zoom_start=8,
    tiles="cartodbpositron",
    control_scale=False
)

css = """
<style>
    .leaflet-tooltip {
        background-color: rgba(255, 255, 255, 0.42) !important;
        border: 2px solid rgba(0,0,0,0.7) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
        color: #111 !important;
        font-size: 13.5px !important;
        line-height: 1.65 !important;
        padding: 8px 10px !important;
    }

    /* 隔离模块：hover 流动箭头线 */
    .basin-flow-line {
        stroke-dasharray: 10 14;
        animation: basinFlowMove 0.8s linear infinite;
        pointer-events: none;
    }

    @keyframes basinFlowMove {
        from {
            stroke-dashoffset: 24;
        }
        to {
            stroke-dashoffset: 0;
        }
    }

    .basin-flow-head {
        pointer-events: none;
    }

    /* 左下角知识产权与数据引用信息框 */
    .data-credit-box {
        position: fixed;
        left: 18px;
        bottom: 18px;
        width: 420px;
        max-height: 260px;
        overflow-y: auto;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.88);
        border: 1.5px solid rgba(0, 0, 0, 0.45);
        border-radius: 8px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
        padding: 12px 14px;
        font-family: Arial, "Microsoft YaHei", sans-serif;
        font-size: 11.5px;
        line-height: 1.55;
        color: #111;
    }

    .data-credit-box h4 {
        margin: 0 0 6px 0;
        font-size: 13.5px;
        font-weight: 700;
        color: #000;
    }

    .data-credit-box .section-title {
        font-weight: 700;
        margin-top: 8px;
        margin-bottom: 3px;
        color: #000;
    }

    .data-credit-box a {
        color: #0057b8;
        text-decoration: none;
    }

    .data-credit-box a:hover {
        text-decoration: underline;
    }

    /* 顶部经度刻度：无底色，刻度随地图走 */
    .coord-axis-top {
        position: fixed;
        top: 8px;
        left: 0;
        width: 100vw;
        height: 46px;
        z-index: 9998;
        pointer-events: none;
        font-family: Arial, "Microsoft YaHei", sans-serif;
        font-size: 11px;
        color: #111;
        background: transparent;
        border: none;
        box-shadow: none;
        overflow: hidden;
        text-shadow:
            -1px -1px 0 rgba(255,255,255,0.95),
             1px -1px 0 rgba(255,255,255,0.95),
            -1px  1px 0 rgba(255,255,255,0.95),
             1px  1px 0 rgba(255,255,255,0.95);
    }

    .coord-axis-top .coord-tick {
        position: absolute;
        transform: translateX(-50%);
        white-space: nowrap;
    }

    .coord-axis-top .coord-major {
        top: 3px;
        font-weight: 600;
    }

    .coord-axis-top .coord-major::after {
        content: "";
        display: block;
        width: 1px;
        height: 10px;
        background: #111;
        margin: 2px auto 0 auto;
        box-shadow: 0 0 2px rgba(255,255,255,0.95);
    }

    .coord-axis-top .coord-minor {
        top: 24px;
        width: 1px;
        height: 6px;
        background: #111;
        box-shadow: 0 0 2px rgba(255,255,255,0.95);
    }

    /* 左侧纬度刻度：加宽，防止 23.00°N 被裁切成 3.00°N */
    .coord-axis-left {
        position: fixed;
        left: 0;
        top: 0;
        width: 104px;
        height: 100vh;
        z-index: 9998;
        pointer-events: none;
        font-family: Arial, "Microsoft YaHei", sans-serif;
        font-size: 11px;
        color: #111;
        background: transparent;
        border: none;
        box-shadow: none;
        overflow: visible;
        text-shadow:
            -1px -1px 0 rgba(255,255,255,0.95),
             1px -1px 0 rgba(255,255,255,0.95),
            -1px  1px 0 rgba(255,255,255,0.95),
             1px  1px 0 rgba(255,255,255,0.95);
    }

    .coord-axis-left .coord-tick {
        position: absolute;
        transform: translateY(-50%);
        white-space: nowrap;
    }

    .coord-axis-left .coord-major {
        right: 14px;
        font-weight: 600;
    }

    .coord-axis-left .coord-major::after {
        content: "";
        display: inline-block;
        width: 10px;
        height: 1px;
        background: #111;
        margin-left: 5px;
        vertical-align: middle;
        box-shadow: 0 0 2px rgba(255,255,255,0.95);
    }

    .coord-axis-left .coord-minor {
        right: 0;
        width: 7px;
        height: 1px;
        background: #111;
        box-shadow: 0 0 2px rgba(255,255,255,0.95);
    }

    /* 右下角图例：整体上移 */
    .map-legend-box {
        position: fixed;
        right: 18px;
        bottom: 92px;
        width: 180px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.9);
        border: 1.5px solid rgba(0, 0, 0, 0.45);
        border-radius: 8px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
        padding: 10px 12px;
        font-family: Arial, "Microsoft YaHei", sans-serif;
        font-size: 12px;
        line-height: 1.55;
        color: #111;
    }

    .map-legend-title {
        font-weight: 700;
        font-size: 13px;
        margin-bottom: 6px;
    }

    .legend-row {
        display: flex;
        align-items: center;
        margin: 4px 0;
    }

    .legend-symbol {
        width: 24px;
        height: 12px;
        margin-right: 8px;
        box-sizing: border-box;
        flex-shrink: 0;
    }

    .legend-upstream {
        border: 3px solid #9932cc;
        background: rgba(153, 50, 204, 0.22);
    }

    .legend-current {
        border: 3px solid red;
        background: rgba(255, 255, 255, 0.45);
    }

    .legend-downstream {
        border: 3px solid #1e90ff;
        background: rgba(30, 144, 255, 0.22);
    }

    .legend-lake {
        border: 1px solid #003b8e;
        background: #003b8e;
    }

    .legend-flow {
        height: 0;
        border-top: 3px dashed #0057ff;
        background: transparent;
    }

    /* 右下角比例尺位置优化 */
    .leaflet-control-scale {
        margin-right: 18px !important;
        margin-bottom: 18px !important;
        background: rgba(255, 255, 255, 0.82);
        padding: 3px 5px;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    }
</style>
"""
m.get_root().html.add_child(folium.Element(css))


# ======================
# 3.5 左下角数据引用与知识产权信息框
# ======================
credit_html = """
<div class="data-credit-box">
    <h4>珠江口河-湖拓扑关系的多层级流域数据集(2025年)</h4>

    <div class="section-title">a. 论文引用规范</div>
    Liu, J., Zhang, B., Que, Y., Xu, J., Hou, W., &amp; Yang, W. (2026).
    <i>RiverLakeBasins: a global dataset of nested river-watersheds and lake-hillslopes.</i>
    International Journal of Geographical Information Science, 1-23.
    doi:
    <a href="https://doi.org/10.1080/13658816.2026.2620024" target="_blank">
        https://doi.org/10.1080/13658816.2026.2620024
    </a>.

    <div class="section-title">b. 数据引用规范</div>
    <b>论文引用：</b><br>
    Liu, J., Zhang, B., Que, Y., Xu, J., Hou, W., &amp; Yang, W. (2026).
    <i>RiverLakeBasins: a global dataset of nested river-watersheds and lake-hillslopes.</i>
    International Journal of Geographical Information Science, 1-23.
    doi:
    <a href="https://doi.org/10.1080/13658816.2026.2620024" target="_blank">
        https://doi.org/10.1080/13658816.2026.2620024
    </a>.
    <br><br>

    <b>中文数据引用：</b><br>
    刘军志，张斌等，2026，“全球表达河-湖拓扑关系的多层级流域数据集（2025年）”，
    <a href="https://doi.org/10.12009/YRDR.2026.1006.ver1.db" target="_blank">
        https://doi.org/10.12009/YRDR.2026.1006.ver1.db
    </a>，
    国家地球系统科学数据中心-长江三角洲分中心，第一版。
    （<a href="http://geodata.nnu.edu.cn" target="_blank">http://geodata.nnu.edu.cn</a>）
    <br><br>

    <b>English data citation:</b><br>
    Junzhi Liu, Bin Zhang et al. 2026,
    “RiverLakeBasins: Global Nested Dataset of River Watersheds and Lake Hillslopes (2025)”,
    <a href="https://doi.org/10.12009/YRDR.2026.1006.ver1.db" target="_blank">
        https://doi.org/10.12009/YRDR.2026.1006.ver1.db
    </a>,
    Yangtze River Delta Science Data Center,
    National Earth System Science Data Sharing Infrastructure, V1.
    (<a href="http://geodata.nnu.edu.cn" target="_blank">http://geodata.nnu.edu.cn</a>)
    <br><br>

    <b>中文致谢：</b><br>
    “感谢国家科技资源共享服务平台-国家地球系统科学数据中心-长江三角洲分中心
    (<a href="http://geodata.nnu.edu.cn/" target="_blank">http://geodata.nnu.edu.cn/</a>)
    提供数据支撑。”
    <br><br>

    <b>English acknowledgement:</b><br>
    Acknowledgement for the data support from
    “Yangtze River Delta Science Data Center, National Earth System Science Data Center,
    National Science &amp; Technology Infrastructure of China.
    (<a href="http://geodata.nnu.edu.cn/" target="_blank">http://geodata.nnu.edu.cn/</a>)”.

    <div class="section-title">c. 数据联系人</div>
    <b>数据研发团队联系人：</b><br>
    姓名：刘军志、张斌<br>
    Email：liujunzhi@lzu.edu.cn<br>
    单位：兰州大学泛第三极环境中心<br><br>

    <b>数据共享服务联系人：</b><br>
    姓名：李杨、戴玲<br>
    Email：geodata@njnu.edu.cn<br>
    单位：南京师范大学地理科学学院<br>
    Tel：025-85891253
</div>
"""
m.get_root().html.add_child(folium.Element(credit_html))


# ======================
# 3.6 右下角图例
# ======================
legend_html = """
<div class="map-legend-box">
    <div class="map-legend-title">图例</div>

    <div class="legend-row">
        <div class="legend-symbol legend-upstream"></div>
        <div>上游流域</div>
    </div>

    <div class="legend-row">
        <div class="legend-symbol legend-current"></div>
        <div>当前流域</div>
    </div>

    <div class="legend-row">
        <div class="legend-symbol legend-downstream"></div>
        <div>下游流域</div>
    </div>

    <div class="legend-row">
        <div class="legend-symbol legend-lake"></div>
        <div>湖泊</div>
    </div>

    <div class="legend-row">
        <div class="legend-symbol legend-flow"></div>
        <div>流动方向</div>
    </div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))


# ======================
# 4. 添加图层
# ======================
geojson_layers = []

def make_style_function(type_int):
    def style_function(feature):
        if type_int == 2:
            return {
                "fillColor": "#003b8e",
                "color": "#003b8e",
                "weight": 1.4,
                "fillOpacity": 0.75
            }
        else:
            return {
                "fillColor": "#66c2a5",
                "color": "#666",
                "weight": 1,
                "fillOpacity": 0.4
            }
    return style_function

for _, row in basins.iterrows():
    bid = int(row["Basin_ID"])
    bid_str = str(bid)
    type_int = int(row["Type_int"])
    
    popup_text = f"""
    <div style="min-width:280px;">
        <b>Basin_ID:</b> {bid}<br>
        <b>Down_ID:</b> {int(row["Down_ID"])}<br><hr>
        <b>Type:</b> {row.get("Type")}<br>
        <b>Area (km²):</b> {row.get("Area")}<br>
        <b>HylakID:</b> {row.get("HylakID")}<br>
        <b>Ednor:</b> {row.get("Ednor")}<br><hr>
        1=河流流域 | 2=湖泊 | 3=湖泊坡面<br>
        0=外流 | -1=内流
    </div>
    """
    
    geojson = folium.GeoJson(
        row["geometry"],
        style_function=make_style_function(type_int),
        tooltip=folium.Tooltip(popup_text, sticky=True, direction="right")
    )
    geojson.add_to(m)
    geojson_layers.append((bid_str, geojson))


# ======================
# 5. 大 JS 块（上下游同时高亮 + 经纬度刻度 + 比例尺）
# ======================
js_code = """
<script>
var basinData = """ + json.dumps(basin_data) + """;
var basinDownChains = """ + json.dumps(basin_down_chains) + """;
var basinUpChains = """ + json.dumps(basin_up_chains) + """;
var flowEdgesByBasin = """ + json.dumps(flow_edges_by_basin) + """;
var basinTypeMap = """ + json.dumps(basin_type_map) + """;

var layerMap = {};

// ======================
// 经纬度刻度 + 比例尺
// 逻辑：主刻度带数字，子刻度不带数字
// ======================
var coordAxisTop = null;
var coordAxisLeft = null;
var scaleControlAdded = false;
var coordTickRaf = null;

// 经度整体右移像素
var LON_LABEL_X_SHIFT = 28;

function getNiceStep(span, targetTicks) {
    var rawStep = span / targetTicks;
    var pow10 = Math.pow(10, Math.floor(Math.log10(rawStep)));
    var frac = rawStep / pow10;
    var niceFrac;

    if (frac <= 1) {
        niceFrac = 1;
    } else if (frac <= 2) {
        niceFrac = 2;
    } else if (frac <= 5) {
        niceFrac = 5;
    } else {
        niceFrac = 10;
    }

    return niceFrac * pow10;
}

function decimalPlaces(step) {
    if (step >= 1) {
        return 0;
    }

    var s = step.toFixed(10);
    s = s.replace(/0+$/, "");
    var idx = s.indexOf(".");

    if (idx < 0) {
        return 0;
    }

    return Math.min(4, s.length - idx - 1);
}

function isNearMajor(value, majorStep) {
    var ratio = value / majorStep;
    return Math.abs(ratio - Math.round(ratio)) < 1e-6;
}

function initCoordAxes() {
    if (!coordAxisTop) {
        coordAxisTop = document.createElement("div");
        coordAxisTop.className = "coord-axis-top";
        document.body.appendChild(coordAxisTop);
    }

    if (!coordAxisLeft) {
        coordAxisLeft = document.createElement("div");
        coordAxisLeft.className = "coord-axis-left";
        document.body.appendChild(coordAxisLeft);
    }

    updateCoordAxes();

    var mapObj = """ + m.get_name() + """;

    mapObj.on("move", requestCoordAxesUpdate);
    mapObj.on("zoom", requestCoordAxesUpdate);
    mapObj.on("zoomanim", requestCoordAxesUpdate);
    mapObj.on("resize", requestCoordAxesUpdate);
    mapObj.on("viewreset", requestCoordAxesUpdate);
    mapObj.on("moveend zoomend", updateCoordAxes);

    if (!scaleControlAdded) {
        L.control.scale({
            position: "bottomright",
            metric: true,
            imperial: false,
            maxWidth: 160,
            updateWhenIdle: false
        }).addTo(mapObj);

        scaleControlAdded = true;
    }
}

function requestCoordAxesUpdate() {
    if (coordTickRaf !== null) {
        cancelAnimationFrame(coordTickRaf);
    }

    coordTickRaf = requestAnimationFrame(function() {
        updateCoordAxes();
        coordTickRaf = null;
    });
}

function updateCoordAxes() {
    if (!coordAxisTop || !coordAxisLeft) {
        return;
    }

    var mapObj = """ + m.get_name() + """;
    var bounds = mapObj.getBounds();
    var center = mapObj.getCenter();
    var container = mapObj.getContainer();
    var rect = container.getBoundingClientRect();

    var west = bounds.getWest();
    var east = bounds.getEast();
    var south = bounds.getSouth();
    var north = bounds.getNorth();

    var lonSpan = east - west;
    var latSpan = north - south;

    var lonMajorStep = getNiceStep(lonSpan, 10);
    var latMajorStep = getNiceStep(latSpan, 8);

    var lonMinorStep = lonMajorStep / 5.0;
    var latMinorStep = latMajorStep / 5.0;

    var lonDecimals = Math.max(2, decimalPlaces(lonMajorStep));
    var latDecimals = Math.max(2, decimalPlaces(latMajorStep));

    coordAxisTop.innerHTML = "";
    coordAxisLeft.innerHTML = "";

    // ======================
    // 经度子刻度：不显示数字
    // ======================
    var lonMinorStart = Math.floor(west / lonMinorStep) * lonMinorStep;
    var lonMinorEnd = Math.ceil(east / lonMinorStep) * lonMinorStep;

    for (var lngMinor = lonMinorStart; lngMinor <= lonMinorEnd + lonMinorStep * 0.5; lngMinor += lonMinorStep) {
        if (lngMinor < west || lngMinor > east) {
            continue;
        }

        if (isNearMajor(lngMinor, lonMajorStep)) {
            continue;
        }

        var minorPoint = mapObj.latLngToContainerPoint([center.lat, lngMinor]);
        var minorX = rect.left + minorPoint.x + LON_LABEL_X_SHIFT;

        var minorTick = document.createElement("div");
        minorTick.className = "coord-tick coord-minor";
        minorTick.style.left = minorX + "px";

        coordAxisTop.appendChild(minorTick);
    }

    // ======================
    // 经度主刻度：显示数字
    // ======================
    var lonMajorStart = Math.floor(west / lonMajorStep) * lonMajorStep;
    var lonMajorEnd = Math.ceil(east / lonMajorStep) * lonMajorStep;

    for (var lng = lonMajorStart; lng <= lonMajorEnd + lonMajorStep * 0.5; lng += lonMajorStep) {
        if (lng < west || lng > east) {
            continue;
        }

        var point = mapObj.latLngToContainerPoint([center.lat, lng]);
        var x = rect.left + point.x + LON_LABEL_X_SHIFT;

        var tick = document.createElement("div");
        tick.className = "coord-tick coord-major";
        tick.style.left = x + "px";
        tick.innerHTML = lng.toFixed(lonDecimals) + "°E";

        coordAxisTop.appendChild(tick);
    }

    // ======================
    // 纬度子刻度：不显示数字
    // ======================
    var latMinorStart = Math.floor(south / latMinorStep) * latMinorStep;
    var latMinorEnd = Math.ceil(north / latMinorStep) * latMinorStep;

    for (var latMinor = latMinorStart; latMinor <= latMinorEnd + latMinorStep * 0.5; latMinor += latMinorStep) {
        if (latMinor < south || latMinor > north) {
            continue;
        }

        if (isNearMajor(latMinor, latMajorStep)) {
            continue;
        }

        var pointMinorY = mapObj.latLngToContainerPoint([latMinor, center.lng]);
        var minorY = rect.top + pointMinorY.y;

        var minorTickY = document.createElement("div");
        minorTickY.className = "coord-tick coord-minor";
        minorTickY.style.top = minorY + "px";

        coordAxisLeft.appendChild(minorTickY);
    }

    // ======================
    // 纬度主刻度：显示完整数字，例如 23.00°N
    // ======================
    var latMajorStart = Math.floor(south / latMajorStep) * latMajorStep;
    var latMajorEnd = Math.ceil(north / latMajorStep) * latMajorStep;

    for (var lat = latMajorStart; lat <= latMajorEnd + latMajorStep * 0.5; lat += latMajorStep) {
        if (lat < south || lat > north) {
            continue;
        }

        var pointY = mapObj.latLngToContainerPoint([lat, center.lng]);
        var y = rect.top + pointY.y;

        var tickY = document.createElement("div");
        tickY.className = "coord-tick coord-major";
        tickY.style.top = y + "px";
        tickY.innerHTML = lat.toFixed(latDecimals) + "°N";

        coordAxisLeft.appendChild(tickY);
    }
}


// ======================
// 隔离模块：hover 流动箭头
// ======================
var flowArrowLayerGroup = null;

function initFlowArrowLayerGroup() {
    if (flowArrowLayerGroup === null) {
        flowArrowLayerGroup = L.layerGroup().addTo(""" + m.get_name() + """);
    }
}

function clearFlowArrowsOnly() {
    if (flowArrowLayerGroup !== null) {
        flowArrowLayerGroup.clearLayers();
    }
}

function drawFlowArrowsOnly(id) {
    initFlowArrowLayerGroup();
    clearFlowArrowsOnly();

    var idStr = String(id);
    var edges = flowEdgesByBasin[idStr] || [];

    edges.forEach(function(edge) {
        var line = L.polyline(edge.line, {
            color: "#0057ff",
            weight: 3,
            opacity: 0.95,
            dashArray: "10 14",
            className: "basin-flow-line",
            interactive: false
        });

        flowArrowLayerGroup.addLayer(line);

        var head = L.polyline(edge.head, {
            color: "#0057ff",
            weight: 3,
            opacity: 0.95,
            className: "basin-flow-head",
            interactive: false
        });

        flowArrowLayerGroup.addLayer(head);
    });
}

function resetAll() {
    Object.keys(layerMap).forEach(function(idStr) {
        var layer = layerMap[idStr];
        var typeVal = basinTypeMap[idStr];

        if (layer && layer.setStyle) {
            if (typeVal === 2) {
                layer.setStyle({
                    fillColor: "#003b8e",
                    color: "#003b8e",
                    weight: 1.4,
                    fillOpacity: 0.75
                });
            } else {
                layer.setStyle({
                    fillColor: "#66c2a5",
                    color: "#666",
                    weight: 1,
                    fillOpacity: 0.4
                });
            }
        }
    });
}

function hoverHighlight(id) {
    resetAll();
    var idStr = String(id);
    
    if (layerMap[idStr]) {
        layerMap[idStr].setStyle({
            color: "red",
            weight: 6,
            fillOpacity: basinTypeMap[idStr] === 2 ? 0.85 : 0.95
        });
    }
    
    var downChain = basinDownChains[idStr] || [];
    downChain.forEach(function(did, index) {
        if (layerMap[did]) {
            var op = Math.max(0.5, 0.88 - index * 0.07);
            layerMap[did].setStyle({
                color: "#1e90ff",
                weight: 4.5,
                fillOpacity: basinTypeMap[did] === 2 ? 0.85 : op
            });
        }
    });
    
    var upChain = basinUpChains[idStr] || [];
    upChain.forEach(function(uid, index) {
        if (layerMap[uid]) {
            var op = Math.max(0.5, 0.85 - index * 0.06);
            layerMap[uid].setStyle({
                color: "#9932cc",
                weight: 4.5,
                fillOpacity: basinTypeMap[uid] === 2 ? 0.85 : op
            });
        }
    });

    drawFlowArrowsOnly(idStr);
}

// 绑定所有图层
document.addEventListener('DOMContentLoaded', function() {
    initCoordAxes();
"""

for bid_str, geojson in geojson_layers:
    layer_name = geojson.get_name()
    js_code += f"""
    layerMap["{bid_str}"] = {layer_name};
    {layer_name}.on('mouseover', function() {{ hoverHighlight("{bid_str}"); }});
    {layer_name}.on('mouseout', function() {{ clearFlowArrowsOnly(); resetAll(); }});
"""

js_code += """
});
</script>
"""

m.get_root().html.add_child(folium.Element(js_code))

# ======================
# 6. 保存
# ======================
output_file = "/Users/gurumakaza/Downloads/basin_downstream_map.html"
m.save(output_file)
print(f"✅ 已导出: {output_file}")