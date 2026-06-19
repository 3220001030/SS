import geopandas as gpd
import pandas as pd
import json
import folium

# ======================
# 1. 数据加载与预处理
# ======================
gdb = "/Users/gurumakaza/Downloads/RiverLakeBasins_Asia.gdb/RiverLakeBasins_Asia.gdb"
gdf9 = gpd.read_file(gdb, layer="level_9")
gdf10 = gpd.read_file(gdb, layer="level_10")

basins = pd.concat([gdf9, gdf10], ignore_index=True)
basins = gpd.GeoDataFrame(basins).to_crs("EPSG:4326")
basins = basins.cx[112.0:114.8, 21.0:23.5]

basins["Basin_ID"] = pd.to_numeric(basins["Basin_ID"], errors="coerce")
basins["Down_ID"] = pd.to_numeric(basins["Down_ID"], errors="coerce")

basins = basins.dropna(subset=["Basin_ID"])
basins["Basin_ID"] = basins["Basin_ID"].astype(int)
basins["Down_ID"] = basins["Down_ID"].fillna(0).astype(int)

# ======================
# 2. 构建下游查找字典
# ======================
down_dict = {str(bid): str(did) for bid, did in zip(basins["Basin_ID"], basins["Down_ID"])}

# ======================
# 3. 创建地图
# ======================
m = folium.Map(location=[22.2, 113.2], zoom_start=8, tiles="cartodbpositron")

# ======================
# 4. JS逻辑（不变）
# ======================
js = f"""
<script>
var downMap = {json.dumps(down_dict)};
var layerMap = {{}};

function resetAll() {{
    Object.values(layerMap).forEach(function(layer) {{
        if (layer && layer.setStyle) {{
            layer.setStyle({{
                fillColor: "#66c2a5",
                color: "#666",
                weight: 1,
                fillOpacity: 0.4
            }});
        }}
    }});
}}

function hoverHighlight(id) {{
    resetAll();
    var idStr = String(id);

    if (layerMap[idStr]) {{
        layerMap[idStr].setStyle({{
            color: "red",
            weight: 3,
            fillOpacity: 0.8
        }});
    }}

    var downId = downMap[idStr];
    if (downId && downId !== "0" && layerMap[downId]) {{
        layerMap[downId].setStyle({{
            color: "blue",
            weight: 3,
            fillOpacity: 0.7
        }});
    }}
}}
</script>
"""
m.get_root().html.add_child(folium.Element(js))

# ======================
# 5. 样式函数
# ======================
def style_function(feature):
    return {
        "fillColor": "#66c2a5",
        "color": "#666",
        "weight": 1,
        "fillOpacity": 0.4
    }

def highlight_function(feature):
    return {
        "weight": 3,
        "color": "yellow"
    }

# ======================
# 6. popup（⭐核心修改在这里）
# ======================
for _, row in basins.iterrows():
    bid = int(row["Basin_ID"])
    down_id = int(row["Down_ID"])

    # ---- 新增字段安全读取 ----
    btype = row.get("Type", None)
    area = row.get("Area", None)
    hylak = row.get("HylakID", None)
    ednor = row.get("Ednor", None)

    popup_text = f"""
    <div style="font-size:13px; line-height:1.6;">
        <b>Basin_ID（子流域ID）:</b> {bid}<br>
        <b>Down_ID（下游ID）:</b> {down_id}<br><hr>

        <b>Type（流域类型）:</b> {btype}<br>
        <b>Area（面积 km²）:</b> {area}<br>
        <b>HylakID（HydroLAKES ID）:</b> {hylak}<br>
        <b>Ednor（内外流标识）:</b> {ednor}<br><hr>

        <b>说明:</b><br>
        1=河流流域 ｜ 2=湖泊 ｜ 3=湖泊坡面<br>
        0=外流入海 ｜ -1=内流终点
    </div>
    """

    geom = folium.GeoJson(
        row["geometry"],
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.Tooltip(popup_text)
    )
    geom.add_to(m)

    geom.add_child(folium.Element(f"""
    <script>
    (function() {{
        var layer = {geom.get_name()};
        var key = "{bid}";
        layerMap[key] = layer;
        layer.on('mouseover', function() {{
            hoverHighlight(key);
        }});
    }})();
    </script>
    """))

# ======================
# 7. 导出
# ======================
output_file = "/Users/gurumakaza/Downloads/basin_downstream_map.html"
m.save(output_file)
print(f"✅ 已导出: {output_file}")