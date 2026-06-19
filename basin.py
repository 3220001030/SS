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
# 2. 构建下游查找字典（key 转为字符串，方便 JS）
# ======================
down_dict = {str(bid): str(did) for bid, did in zip(basins["Basin_ID"], basins["Down_ID"])}

# ======================
# 3. 创建地图
# ======================
m = folium.Map(location=[22.2, 113.2], zoom_start=8, tiles="cartodbpositron")

# ======================
# 4. JavaScript 核心逻辑（增强版）
# ======================
js = f"""
<script>
// 下游映射（键为字符串）
var downMap = {json.dumps(down_dict)};
// 存储所有图层的引用
var layerMap = {{}};

// 重置所有图层到默认样式
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

// 高亮当前流域及其下游
function hoverHighlight(id) {{
    // 先重置所有
    resetAll();
    var idStr = String(id);
    
    // 高亮当前流域（红色）
    if (layerMap[idStr]) {{
        layerMap[idStr].setStyle({{
            color: "red",
            weight: 3,
            fillOpacity: 0.8
        }});
    }}
    
    // 高亮下游流域（蓝色），注意 Down_ID 可能为 "0" 表示无下游
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
# 5. 样式函数（默认和悬停高亮）
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
        "color": "yellow"   # 仅用作 Folium 内置高亮，但我们使用自定义 mouseover 覆盖
    }

# ======================
# 6. 逐个添加流域并绑定事件
# ======================
for _, row in basins.iterrows():
    bid = int(row["Basin_ID"])
    down_id = int(row["Down_ID"])
    btype = row["Type"] if "Type" in row else None

    popup_text = f"""
    <b>Basin ID:</b> {bid}<br>
    <b>Down ID:</b> {down_id}<br>
    <b>Type:</b> {btype}
    """

    geom = folium.GeoJson(
        row["geometry"],
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.Tooltip(popup_text)
    )
    geom.add_to(m)

    # 绑定自定义 mouseover 事件，并记录图层引用
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
# 7. 导出 HTML
# ======================
output_file = "/Users/gurumakaza/Downloads/basin_downstream_map.html"
m.save(output_file)
print(f"✅ 已导出: {output_file}")