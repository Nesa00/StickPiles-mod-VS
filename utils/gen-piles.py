import copy
import json
import math
import re
from pathlib import Path

# --- Your 1-Layer Recipe (8 Sticks) ---
LAYER_RECIPE = [
    {"model": "anchor", "pos": [8.65, 4.1, 7.95], "rot": [18, 2, 7]},
    {"model": "anchor", "pos": [6.35, 0, 8.2], "rot": [-31, 31, -37]},
    {"model": "anchor", "pos": [7.75, 3.25, 8], "rot": [4, 0, 2]},
    {"model": "anchor", "pos": [6.1, 3.3, 8.05], "rot": [-103, 111, 13]},
    {"model": "anchor", "pos": [8.2, 4.2, 9.25], "rot": [-69, 44, -17]},
    {"model": "anchor", "pos": [10.3, 0.85, 9], "rot": [-57, 340, 11]},
    {"model": "anchor", "pos": [7.8, 2.65, 7.75], "rot": [36, 0, -1]},
    {"model": "anchor", "pos": [10.15, 7.65, 8.1], "rot": [-44, 40, -36]},
]

# 1-based placement order of the 8 sticks per layer
PLACEMENT_ORDER = [1, 2, 3, 4, 5, 7, 8, 6]

LEGACY_ANCHOR_FALLBACK = [
    {"model": "stick0-3", "rel_pos": [-7.6, 0.0, -0.1], "rot": [-19.0, 88.38, 0.0]},
    {"model": "stick0-6", "rel_pos": [-5.7, 0.55, -0.1], "rot": [45.0, 85.0, 0.0]},
    {"model": "stick0-1", "rel_pos": [-2.65, 0.0, -0.349], "rot": [-4.0, 95.0, 0.0]},
    {"model": "stick0-5", "rel_pos": [-1.7, 1.1, -0.25], "rot": [85.0, 92.0, 0.0]},
    {"model": "stick0-2", "rel_pos": [0.15, 1.2, -0.05], "rot": [77.0, 90.0, 0.0]},
    {"model": "stick1-7", "rel_pos": [6.3, 0.55, 0.05], "rot": [57.0, 86.0, 0.0]},
    {"model": "stick1-8", "rel_pos": [3.55, 0.25, -0.4], "rot": [-38.0, 88.12, 0.0]},
    {"model": "stick0-4", "rel_pos": [4.5, 0.0, -0.05], "rot": [54.0, 88.0, 0.0]},
]

# --- Full-Block Stack Settings (8 Layers x 2.0 Voxels = 16 Voxels / 64 Sticks) ---
LAYERS = 8                       # 8 layers x 8 sticks = 64 max stack size
ROTATE_PER_LAYER_DEG = 90.0      # Rotates each added layer by +90° around block center (8, 8)
LAYER_Y_SCALE = 0.85             # Ignored when LAYER_Y_STEP_OVERRIDE is set
LAYER_Y_STEP_OVERRIDE = 2.0      # Exact 2.0 voxels per layer -> 8 layers = 16.0 voxels (full block)
GROUND_Y_OFFSET = 0.0
HITBOX_HEIGHT_SCALE = 1.0

VS_ASSETS_DIR = Path("D:/Vintagestory/assets/survival")
OUT_SHAPES_DIR = Path("assets/stickpiles/shapes/item")
OUT_PATCHES_DIR = Path("assets/stickpiles/patches")


def load_vs_json(path: Path):
    raw = path.read_text(encoding="utf-8-sig")

    def _sq_to_dq(inner: str) -> str:
        converted = re.sub(
            r'\\(.)|"',
            lambda m: (
                "'" if m.group(1) == "'"
                else f"\\{m.group(1)}" if m.group(1) is not None
                else '\\"'
            ),
            inner,
        )
        return f'"{converted}"'

    token_re = re.compile(
        r'(?P<dstr>"(?:\\.|[^"\\])*")'
        r"|(?P<sstr>'(?:\\.|[^'\\])*')"
        r"|(?P<lcom>//[^\r\n]*)"
        r"|(?P<bcom>/\*[\s\S]*?\*/)"
        r"|(?P<ldot>(?<![A-Za-z0-9_.])[+-]?\.\d+(?:[eE][+-]?\d+)?)"
        r"|(?P<tdot>(?<![A-Za-z0-9_.])-?\d+\.(?=\s*[,}\]]))"
        r"|(?P<lplus>(?<![A-Za-z0-9_.])\+\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    )

    def _replace_token(m: re.Match) -> str:
        kind = m.lastgroup
        if kind == "dstr":
            return m.group(0)
        if kind == "sstr":
            return _sq_to_dq(m.group(0)[1:-1])
        if kind == "lcom":
            return ""
        if kind == "bcom":
            return re.sub(r"[^\r\n]", "", m.group(0))
        if kind == "ldot":
            val = m.group(0).lstrip("+")
            return f"-0.{val[2:]}" if val.startswith("-.") else f"0.{val[1:]}"
        if kind == "tdot":
            return f"{m.group(0)}0"
        if kind == "lplus":
            return m.group(0)[1:]
        return m.group(0)

    text = token_re.sub(_replace_token, raw)
    text = re.sub(
        r'("(?:\\.|[^"\\])*")|([{,]\s*)([A-Za-z_$][A-Za-z0-9_$-]*)(\s*:)',
        lambda m: m.group(1) if m.group(1) is not None else f'{m.group(2)}"{m.group(3)}"{m.group(4)}',
        text,
    )
    text = re.sub(
        r'("(?:\\.|[^"\\])*")|,\s*(?=[}\]])',
        lambda m: m.group(1) if m.group(1) is not None else "",
        text,
    )
    return json.loads(text, strict=False)


def add_game_domain(asset_path: str) -> str:
    cleaned = asset_path.replace("\\", "/")
    return cleaned if ":" in cleaned else f"game:{cleaned}"


def _mat_mul(a, b):
    return [
        [sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
        for i in range(4)
    ]


def _mat_translate(dx, dy, dz):
    return [
        [1.0, 0.0, 0.0, dx],
        [0.0, 1.0, 0.0, dy],
        [0.0, 0.0, 1.0, dz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat_rotate_xyz(rx_deg, ry_deg, rz_deg):
    """Exact Vintage Story ShapeElement rotation order: Rx * Ry * Rz."""
    rx, ry, rz = math.radians(rx_deg), math.radians(ry_deg), math.radians(rz_deg)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    mx = [[1.0, 0.0, 0.0, 0.0], [0.0, cx, -sx, 0.0], [0.0, sx, cx, 0.0], [0.0, 0.0, 0.0, 1.0]]
    my = [[cy, 0.0, sy, 0.0], [0.0, 1.0, 0.0, 0.0], [-sy, 0.0, cy, 0.0], [0.0, 0.0, 0.0, 1.0]]
    mz = [[cz, -sz, 0.0, 0.0], [sz, cz, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    return _mat_mul(mx, _mat_mul(my, mz))


def _decompose_xyz(m):
    """Decompose 4x4 rotation matrix back into VS 'XYZ' Euler angles (rx, ry, rz) in degrees."""
    sy = max(-1.0, min(1.0, m[0][2]))
    ry = math.asin(sy)
    cy = math.cos(ry)

    if abs(cy) > 1e-6:
        rx = math.atan2(-m[1][2], m[2][2])
        rz = math.atan2(-m[0][1], m[0][0])
    else:
        rx = math.atan2(m[2][1], m[1][1])
        rz = 0.0

    return (
        round(math.degrees(rx), 3),
        round(math.degrees(ry), 3),
        round(math.degrees(rz), 3),
    )


def _transform_pt(m, x, y, z):
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
    )


def collect_rotated_points(elements, parent_mat=None):
    if parent_mat is None:
        parent_mat = _mat_translate(0.0, 0.0, 0.0)

    pts = []
    for el in elements:
        ef = el.get("from", [0.0, 0.0, 0.0])
        et = el.get("to", [0.0, 0.0, 0.0])
        origin = el.get("rotationOrigin", [0.0, 0.0, 0.0])
        rx = float(el.get("rotationX", 0.0))
        ry = float(el.get("rotationY", 0.0))
        rz = float(el.get("rotationZ", 0.0))

        rot_mat = _mat_mul(
            _mat_translate(origin[0], origin[1], origin[2]),
            _mat_mul(_mat_rotate_xyz(rx, ry, rz), _mat_translate(-origin[0], -origin[1], -origin[2])),
        )
        el_mat = _mat_mul(parent_mat, rot_mat)

        has_size = any(abs(et[i] - ef[i]) > 1e-6 for i in range(3))
        faces = el.get("faces", {})
        has_visible_face = any(f.get("enabled", True) for f in faces.values())

        if has_size and has_visible_face:
            for x in (ef[0], et[0]):
                for y in (ef[1], et[1]):
                    for z in (ef[2], et[2]):
                        pts.append(_transform_pt(el_mat, x, y, z))

        if "children" in el:
            child_mat = _mat_mul(el_mat, _mat_translate(ef[0], ef[1], ef[2]))
            pts.extend(collect_rotated_points(el["children"], child_mat))

    return pts


def count_all_elements(elements) -> int:
    total = 0
    for el in elements:
        total += 1
        if "children" in el:
            total += count_all_elements(el["children"])
    return total


def remap_element_tree(el, key_map: dict, prefix: str, shift=None):
    clone = copy.deepcopy(el)
    clone["name"] = f"{prefix}_{clone.get('name', 'part')}"

    if shift is not None:
        has_rot = any(abs(float(clone.get(axis, 0.0))) > 1e-6 for axis in ("rotationX", "rotationY", "rotationZ"))
        if has_rot and "rotationOrigin" not in clone:
            clone["rotationOrigin"] = [0.0, 0.0, 0.0]

        dx, dy, dz = shift
        for field in ("from", "to", "rotationOrigin"):
            if field in clone:
                clone[field] = [
                    round(clone[field][0] + dx, 4),
                    round(clone[field][1] + dy, 4),
                    round(clone[field][2] + dz, 4),
                ]

    clone.pop("renderPass", None)

    for face in clone.get("faces", {}).values():
        if face.get("enabled", True) and face.get("texture") in key_map:
            face["texture"] = key_map[face["texture"]]

    if "children" in clone:
        clone["children"] = [
            remap_element_tree(child, key_map, prefix, shift=None)
            for child in clone["children"]
        ]

    return clone


def resolve_recipe(raw_recipe: list) -> list:
    """Resolve nested 'anchor' entries into exact flat stick poses before reordering."""
    resolved = []
    for idx, entry in enumerate(raw_recipe):
        if entry["model"] != "anchor":
            resolved.append({
                "model": entry["model"],
                "pos": list(entry["pos"]),
                "rot": list(entry["rot"]),
            })
            continue

        inner = LEGACY_ANCHOR_FALLBACK[idx % len(LEGACY_ANCHOR_FALLBACK)]
        px_out, py_out, pz_out = entry["pos"]
        rx_out, ry_out, rz_out = entry["rot"]
        rx_in, ry_in, rz_in = inner["rot"]
        ix, iy, iz = inner["rel_pos"]

        r_out = _mat_rotate_xyz(rx_out, ry_out, rz_out)
        r_in = _mat_rotate_xyz(rx_in, ry_in, rz_in)
        dx, dy, dz = _transform_pt(r_out, ix, iy, iz)

        world_pos = [round(px_out + dx, 3), round(py_out + dy, 3), round(pz_out + dz, 3)]
        world_rot = list(_decompose_xyz(_mat_mul(r_out, r_in)))
        resolved.append({"model": inner["model"], "pos": world_pos, "rot": world_rot})

    return resolved


def build_stick_anchor(v: dict, key_map: dict, piece_idx: int, max_stick_elems: int, pos, rot):
    px, py, pz = pos
    rx, ry, rz = rot

    child = remap_element_tree(
        v["node"],
        key_map,
        f"s{piece_idx}",
        shift=(-v["cx"], -v["min_y"], -v["cz"]),
    )
    children = [child]

    for pad_i in range(max_stick_elems - v["elem_count"]):
        children.append({
            "name": f"s{piece_idx}_pad{pad_i}",
            "from": [0.0, 0.0, 0.0],
            "to": [0.0, 0.0, 0.0],
            "faces": {},
        })

    anchor = {
        "name": f"s{piece_idx}_anchor",
        "from": [px, py, pz],
        "to": [px, py, pz],
        "rotationOrigin": [px, py, pz],
        "children": children,
    }
    if abs(rx) > 1e-4:
        anchor["rotationX"] = rx
    if abs(ry) > 1e-4:
        anchor["rotationY"] = ry
    if abs(rz) > 1e-4:
        anchor["rotationZ"] = rz
    return anchor


def main():
    src_path = VS_ASSETS_DIR / "shapes/item/stick-pile.json"
    src = load_vs_json(src_path)
    raw_elements = src.get("elements", [])

    if len(raw_elements) == 1 and raw_elements[0].get("children"):
        stick_nodes = raw_elements[0]["children"]
    else:
        stick_nodes = raw_elements

    models_by_name = {}
    max_stick_elems = 0

    for node in stick_nodes:
        pts = collect_rotated_points([node])
        if not pts:
            continue

        min_x = min(p[0] for p in pts)
        max_x = max(p[0] for p in pts)
        min_y = min(p[1] for p in pts)
        min_z = min(p[2] for p in pts)
        max_z = max(p[2] for p in pts)

        elem_count = count_all_elements([node])
        max_stick_elems = max(max_stick_elems, elem_count)
        name = node.get("name", "")
        models_by_name[name] = {
            "name": name,
            "node": node,
            "elem_count": elem_count,
            "cx": (min_x + max_x) / 2.0,
            "min_y": min_y - GROUND_Y_OFFSET,
            "cz": (min_z + max_z) / 2.0,
        }

    resolved_all = resolve_recipe(LAYER_RECIPE)
    base_recipe = [resolved_all[i - 1] for i in PLACEMENT_ORDER]

    textures = {f"sp_{k}": add_game_domain(v) for k, v in src.get("textures", {}).items()}
    key_map = {f"#{k}": f"#sp_{k}" for k in src.get("textures", {})}

    # Ground Layer 1's lowest stick corner on Y = 0.0
    probe_elements = [
        build_stick_anchor(models_by_name[entry["model"]], key_map, idx, max_stick_elems, entry["pos"], entry["rot"])
        for idx, entry in enumerate(base_recipe, start=1)
    ]
    probe_pts = collect_rotated_points(probe_elements)
    min_world_y = min(p[1] for p in probe_pts)
    max_world_y = max(p[1] for p in probe_pts)
    layer_height = max(0.5, max_world_y - min_world_y)

    for entry in base_recipe:
        entry["pos"][1] = round(entry["pos"][1] - min_world_y, 3)

    layer_y_step = (
        round(float(LAYER_Y_STEP_OVERRIDE), 3)
        if LAYER_Y_STEP_OVERRIDE is not None
        else round(layer_height * LAYER_Y_SCALE, 3)
    )

    items_per_layer = len(base_recipe)
    max_pieces = LAYERS * items_per_layer
    elems_per_piece = 2 + max_stick_elems

    elements = []
    piece_idx = 0

    for layer_idx in range(LAYERS):
        layer_angle = round((layer_idx * ROTATE_PER_LAYER_DEG) % 360.0, 2)
        layer_y = round(layer_idx * layer_y_step, 3)

        for entry in base_recipe:
            v = models_by_name[entry["model"]]
            piece_idx += 1

            px, py, pz = entry["pos"]
            rel_pos = [round(px - 8.0, 4), round(py, 4), round(pz - 8.0, 4)]
            stick_anchor = build_stick_anchor(v, key_map, piece_idx, max_stick_elems, rel_pos, entry["rot"])

            layer_pivot = {
                "name": f"s{piece_idx}_pivot",
                "from": [8.0, layer_y, 8.0],
                "to": [8.0, layer_y, 8.0],
                "rotationOrigin": [8.0, layer_y, 8.0],
                "children": [stick_anchor],
            }
            if abs(layer_angle) > 1e-4:
                layer_pivot["rotationY"] = layer_angle

            elements.append(layer_pivot)

    all_final_pts = collect_rotated_points(elements)
    total_top_y = max(p[1] for p in all_final_pts)

    OUT_SHAPES_DIR.mkdir(parents=True, exist_ok=True)
    out_shape_name = "stick-pile"
    shape_out = OUT_SHAPES_DIR / f"{out_shape_name}.json"
    shape_out.write_text(
        json.dumps(
            {
                "editor": {"allAngles": True, "singleTexture": False},
                "textureWidth": src.get("textureWidth", 16),
                "textureHeight": src.get("textureHeight", 16),
                "textures": textures,
                "elements": elements,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    stick_rel = "itemtypes/resource/stick.json"
    stick_data = load_vs_json(VS_ASSETS_DIR / stick_rel)
    behaviors = copy.deepcopy(stick_data.get("behaviors", []))

    pile_voxel_height = (
        LAYERS * float(LAYER_Y_STEP_OVERRIDE)
        if LAYER_Y_STEP_OVERRIDE is not None
        else total_top_y
    )
    max_y2 = min(1.0, (pile_voxel_height / 16.0) * HITBOX_HEIGHT_SCALE)
    step_y2 = round(max_y2 / LAYERS, 4)
    cb_scale = round(1.0 / items_per_layer, 5)

    props = {
        "layout": "Stacking",
        "ctrlKey": False,
        "stackingModel": f"stickpiles:item/{out_shape_name}",
        "upSolid": False,
        "modelItemsToStackSizeRatio": float(elems_per_piece),
        "stackingCapacity": max_pieces,
        "transferQuantity": 1,
        "bulkTransferQuantity": items_per_layer,
        "collisionBox": {"x1": 0, "y1": 0, "z1": 0, "x2": 1, "y2": step_y2, "z2": 1},
        "cbScaleYByLayer": cb_scale,
    }

    replaced = False
    for b in behaviors:
        if isinstance(b, dict) and b.get("name") == "GroundStorable":
            b["properties"] = props
            replaced = True
    if not replaced:
        behaviors.append({"name": "GroundStorable", "properties": props})

    OUT_PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    patch_out = OUT_PATCHES_DIR / "stick-pile.json"
    patch_out.write_text(
        json.dumps(
            [
                {
                    "file": f"game:{stick_rel}",
                    "op": "replace",
                    "path": "/behaviors",
                    "value": behaviors,
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated {LAYERS}x{items_per_layer} ({max_pieces} sticks) full-block pile -> {shape_out.as_posix()}\n"
        f"  Layer step = {layer_y_step:.2f}v (+90° Y/layer) | Nominal height = {pile_voxel_height:.1f}v | Mesh top = {total_top_y:.2f}v\n"
        f"  Patch -> {patch_out.as_posix()} (stepY2={step_y2}, cbScaleYByLayer={cb_scale})"
    )


if __name__ == "__main__":
    main()