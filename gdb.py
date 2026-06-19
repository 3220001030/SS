import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import numpy as np

# ======================
# 1. basin数据
# ======================
gdb = "/Users/gurumakaza/Downloads/RiverLakeBasins_Asia.gdb/RiverLakeBasins_Asia.gdb"

gdf9 = gpd.read_file(gdb, layer="level_9")
gdf10 = gpd.read_file(gdb, layer="level_10")

basins = pd.concat([gdf9, gdf10], ignore_index=True)
basins = gpd.GeoDataFrame(basins).to_crs("EPSG:4326")

# ======================
# 2. 真实河网（HydroRIVERS）
# ======================
rivers = gpd.read_file(
    "/Users/gurumakaza/Downloads/HydroRIVERS_v10_as_shp/HydroRIVERS_v10_as_shp/HydroRIVERS_v10_as.shp"
)
rivers = rivers.to_crs("EPSG:4326")

# ======================
# 3. ROI
# ======================
minx, maxx = 112.0, 114.8
miny, maxy = 21.0, 23.5

basins = basins.cx[minx:maxx, miny:maxy]
rivers = rivers.cx[minx:maxx, miny:maxy]

# ======================
# 4. 清洗
# ======================
basins["Down_ID"] = pd.to_numeric(basins["Down_ID"], errors="coerce")
basins["Basin_ID"] = pd.to_numeric(basins["Basin_ID"], errors="coerce")
basins["Type"] = pd.to_numeric(basins["Type"], errors="coerce")

# ======================
# 5. upstream grouping（保持你逻辑）
# ======================
upstream_map = basins.groupby("Down_ID")["Basin_ID"].apply(list).to_dict()
outlets = basins[basins["Down_ID"] == 0]["Basin_ID"].tolist()

visited = set()
groups = {}

def bfs(root):
    stack = [root]
    nodes = []

    while stack:
        n = stack.pop()
        if n in visited:
            continue
        visited.add(n)
        nodes.append(n)
        if n in upstream_map:
            stack.extend(upstream_map[n])

    return nodes

for i, o in enumerate(outlets):
    groups[i] = bfs(o)

# ======================
# 6. 🚀 河网升级：主干 + 流量加权
# ======================

# 安全字段处理
if "ORD_STRA" in rivers.columns:
    rivers_main = rivers[rivers["ORD_STRA"] >= 3].copy()
else:
    rivers_main = rivers.copy()

if "DIS_AV_CMS" in rivers_main.columns:
    rivers_main["DIS_AV_CMS"] = rivers_main["DIS_AV_CMS"].fillna(0.1)
    rivers_main["width"] = np.log1p(rivers_main["DIS_AV_CMS"])
    rivers_main["width"] = (
        rivers_main["width"] - rivers_main["width"].min()
    ) / (
        rivers_main["width"].max() - rivers_main["width"].min() + 1e-9
    )
    rivers_main["width"] = 0.3 + rivers_main["width"] * 2.5
else:
    rivers_main["width"] = 1.0

# ======================
# 7. 可视化
# ======================
fig, ax = plt.subplots(figsize=(12, 10), dpi=300)

# 🌫️ basin boundary
basins.boundary.plot(

    ax=ax,

    color="#8C8C8C",   # ⭐ 更深一点（关键）

    linewidth=0.6,     # ⭐ 加粗（关键）

    alpha=0.85,        # ⭐ 提升对比

    zorder=1

)

# ======================

# 🌊 河网（优化权重压缩）

# ======================

if "ORD_STRA" in rivers.columns:

    rivers_main = rivers[rivers["ORD_STRA"] >= 2].copy()  # ⭐ 降低门槛（关键）

else:

    rivers_main = rivers.copy()

# --- 流量处理 ---

if "DIS_AV_CMS" in rivers_main.columns:

    rivers_main["DIS_AV_CMS"] = rivers_main["DIS_AV_CMS"].fillna(0.1)

    # ⚠️ 核心修改：压缩差异（避免极端粗细）

    rivers_main["width"] = np.log1p(rivers_main["DIS_AV_CMS"])

    rivers_main["width"] = (

        rivers_main["width"] - rivers_main["width"].min()

    ) / (

        rivers_main["width"].max() - rivers_main["width"].min() + 1e-9

    )

    # ⭐ 关键：压缩范围（0.6 ~ 1.8，不再夸张）

    rivers_main["width"] = 0.6 + rivers_main["width"] * 1.2

else:

    rivers_main["width"] = 0.8

# ======================

# 🌊 绘制河网（优化可见性）

# ======================

rivers_main.plot(

    ax=ax,

    color="#1E90FF",

    linewidth=rivers_main["width"],

    alpha=0.85,

    zorder=4,

    label="Main river network (Stream order ≥2, smoothed)"

)

# 🌈 basin grouping
colors = plt.cm.tab20(np.linspace(0, 1, len(groups)))

for i, nodes in enumerate(groups.values()):
    sub = basins[basins["Basin_ID"].isin(nodes)]
    sub.plot(
        ax=ax,
        color=colors[i],
        alpha=0.45,
        linewidth=0,
        zorder=2
    )

# 🔴 outlet
outflow = basins[basins["Down_ID"] == 0]
outflow.plot(
    ax=ax,
    color="yellow",
    edgecolor="black",
    linewidth=0.8,
    zorder=5
)

# 🟦 lakes
lakes = basins[basins["Type"] == 2]
lakes.plot(
    ax=ax,
    color="#00BFFF",
    edgecolor="#003A75",
    linewidth=1.2,
    alpha=0.85,
    zorder=6
)



# ======================
# LEGEND（右下，无框）
# ======================
legend_elements = [

    mlines.Line2D([], [], color="#1E90FF",
                  linewidth=2,
                  label="Main river network (Strahler ≥ 3)"),

    mlines.Line2D([], [], color="#D0D0D0",
                  linewidth=2,
                  label="Sub-watershed boundary"),

    mpatches.Patch(color=colors[0],
                   alpha=0.5,
                   label="Upstream basin groups"),

    mpatches.Patch(color="yellow",
                   label="Outflow basins"),

    mpatches.Patch(color="#00BFFF",
                   label="Lakes (Type=2)")
]

ax.legend(
    handles=legend_elements,
    loc="lower right",
    frameon=False,
    fontsize=10
)

# ======================
# layout
# ======================
ax.set_aspect("equal", adjustable="box")
ax.set_title("Basin + Main River Network (Stream Order + Flow-weighted)")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")

plt.show()