"""AutoDL GPU 型号、区域、价格数据。"""

# GPU 型号及参考价格（按量计费，¥/小时）
GPU_TYPES = [
    {"name": "RTX 2080Ti", "vram": "11GB", "price": 0.88},
    {"name": "RTX 3080", "vram": "10GB", "price": 1.08},
    {"name": "RTX 3090", "vram": "24GB", "price": 1.32},
    {"name": "RTX 4090", "vram": "24GB", "price": 1.98},
    {"name": "RTX 4090D", "vram": "24GB", "price": 2.22},
    {"name": "RTX 5090", "vram": "32GB", "price": 2.88},
    {"name": "RTX 6000 Ada", "vram": "48GB", "price": 3.68},
    {"name": "A40", "vram": "48GB", "price": 3.14},
    {"name": "V100", "vram": "32GB", "price": 2.28},
    {"name": "A100 40GB", "vram": "40GB", "price": 3.45},
    {"name": "A100 80GB", "vram": "80GB", "price": 5.28},
    {"name": "A800 80GB", "vram": "80GB", "price": 4.98},
    {"name": "H20", "vram": "96GB", "price": 7.58},
    {"name": "H800", "vram": "80GB", "price": 8.88},
    {"name": "L20", "vram": "48GB", "price": 2.68},
    {"name": "PRO6000", "vram": "96GB", "price": 9.98},
]

# Pro API 专用 GPU（更贵）
PRO_GPU_TYPES = [
    {"name": "4090D-48G", "vram": "48GB", "price": 18.80},
    {"name": "PRO6000-96G", "vram": "96GB", "price": 22.00},
    {"name": "H800-80G", "vram": "80GB", "price": 32.00},
    {"name": "4080(S)-32G", "vram": "32GB", "price": 12.00},
    {"name": "3090-48G", "vram": "48GB", "price": 8.50},
    {"name": "5090-32G", "vram": "32GB", "price": 15.00},
]

REGIONS = [
    "北京A区", "北京B区", "北京C区",
    "内蒙A区", "内蒙B区",
    "深圳A区", "深圳B区",
    "重庆A区",
    "西北B区",
    "佛山",
    "上海A区",
    "广州A区",
]

# 按来源合并
ALL_GPU_TYPES = GPU_TYPES.copy()

def find_gpu(name: str) -> dict | None:
    """根据名称查找 GPU 信息。"""
    for g in GPU_TYPES + PRO_GPU_TYPES:
        if g["name"].lower() == name.lower():
            return g
    # 模糊匹配
    for g in GPU_TYPES + PRO_GPU_TYPES:
        if name.lower() in g["name"].lower() or g["name"].lower() in name.lower():
            return g
    return None

def get_gpu_price(name: str) -> float:
    """获取 GPU 参考价格。"""
    gpu = find_gpu(name)
    return gpu["price"] if gpu else 0.0
