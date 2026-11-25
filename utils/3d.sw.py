import http.server
import json
import socketserver
import threading
import urllib.parse
import webbrowser
from pathlib import Path

PORT = 8765
VS_ASSETS_DIR = Path("D:/Vintagestory/assets/survival")
SHAPE_FILE = Path("assets/stickpiles/shapes/item/stick-pile.json")
PATCH_FILE = Path("assets/stickpiles/patches/stick-pile.json")
EXPORT_TXT_FILE = Path("exported-layer.txt")

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>VS Stick Pile 3D Editor</title>
<style>
  * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
  body { margin: 0; overflow: hidden; background: #181a1f; color: #e6e8ee; display: flex; height: 100vh; }
  #viewport { flex: 1; position: relative; }
  #hud {
    position: absolute; top: 12px; left: 12px; background: rgba(24,26,31,0.92);
    padding: 8px 12px; border-radius: 6px; border: 1px solid #323642; font-size: 12px; pointer-events: none;
    line-height: 1.55;
  }
  #keyBadge { margin-top: 4px; color: #61afef; font-weight: 600; }
  #sidebar {
    width: 355px; background: #21242b; border-left: 1px solid #323642;
    padding: 14px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px;
  }
  h2 { margin: 0 0 6px 0; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: #9aa4b8; }
  .card { background: #282c34; border: 1px solid #353b47; border-radius: 8px; padding: 10px 12px; }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; font-size: 13px; }
  .row:last-child { margin-bottom: 0; }
  .row label { width: 58px; color: #abb2bf; }
  input[type="range"] { flex: 1; accent-color: #61afef; }
  input[type="number"], select {
    width: 68px; background: #1b1e24; border: 1px solid #3e4451; color: #fff;
    border-radius: 4px; padding: 3px 6px; font-size: 12px;
  }
  select { width: auto; }
  button {
    background: #3a7afe; color: #fff; border: none; border-radius: 6px;
    padding: 7px 10px; font-size: 12px; font-weight: 600; cursor: pointer;
  }
  button:hover { background: #2b6be6; }
  button.secondary { background: #353b47; }
  button.secondary:hover { background: #434a59; }
  button.success { background: #2e8b57; }
  button.success:hover { background: #257347; }
  .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .nudge-row { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; font-size: 12px; }
  .nudge-row span { width: 46px; color: #abb2bf; font-weight: 600; }
  .nudge-row button { flex: 1; padding: 4px 0; font-size: 11px; }
  textarea {
    width: 100%; height: 135px; margin-top: 8px; background: #181a1f; color: #abb2bf;
    border: 1px solid #3e4451; border-radius: 6px; padding: 8px; font-family: Consolas, monospace;
    font-size: 11px; resize: vertical;
  }
  #status { font-size: 12px; color: #98c379; min-height: 16px; }
  .muted { color: #7f848e; font-size: 12px; }
</style>
<script type="importmap">
{
  "imports": {
    "three": "https://unpkg.com/three@0.169.0/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.169.0/examples/jsm/"
  }
}
</script>
</head>
<body>
<div id="viewport">
  <div id="hud">
    <div><b>Mouse:</b> Left-drag Orbit | Right-drag Pan | Scroll Zoom | Click Stick Select</div>
    <div><b>Rotate (Hold + Scroll):</b> <code>X</code> = X-Axis &nbsp;|&nbsp; <code>C</code> = Y-Axis &nbsp;|&nbsp; <code>Z</code> = Z-Axis &nbsp;(±1°, +Shift ±5°)</div>
    <div><b>Move (Ctrl + Hold + Scroll):</b> <code>Ctrl+X</code> = Pos X &nbsp;|&nbsp; <code>Ctrl+C</code> = Pos Y &nbsp;|&nbsp; <code>Ctrl+Z</code> = Pos Z &nbsp;(±0.05)</div>
    <div id="keyBadge">Active Shortcut: None</div>
  </div>
</div>

<div id="sidebar">
  <div class="card">
    <h2>Stack &amp; Hitbox Preview</h2>
    <div class="row">
      <label>Sticks</label>
      <input id="stackSlider" type="range" min="0" max="8" value="8" />
      <input id="stackNum" type="number" min="0" max="8" value="8" />
      <button class="secondary" id="showAllBtn" title="Show all sticks">All</button>
    </div>
    <div class="row">
      <label style="width:auto;"><input id="showHitbox" type="checkbox" checked /> Show GroundStorable Hitbox</label>
    </div>
    <div id="hitboxInfo" class="muted">Loading config...</div>
  </div>

  <div class="card">
    <h2>Selected Stick: <span id="selName" style="color:#61afef;">None</span></h2>
    <div id="inspectorControls" style="opacity:0.45; pointer-events:none;">
      <div class="row"><label>Pos X</label><input id="posX" type="range" min="-2" max="18" step="0.05"><input id="posXNum" type="number" step="0.05"></div>
      <div class="row"><label>Pos Y</label><input id="posY" type="range" min="-2" max="32" step="0.05"><input id="posYNum" type="number" step="0.05"></div>
      <div class="row"><label>Pos Z</label><input id="posZ" type="range" min="-2" max="18" step="0.05"><input id="posZNum" type="number" step="0.05"></div>

      <hr style="border:0; border-top:1px solid #353b47; margin:8px 0;">
      <div class="row">
        <label style="width:auto;">Scroll / Step Axis</label>
        <select id="rotSpace">
          <option value="world" selected>World Axes (X/Y/Z)</option>
          <option value="local">Stick Local Axes</option>
        </select>
      </div>
      <div class="nudge-row">
        <span style="color:#e06c75;">Rot X</span>
        <button class="secondary" data-rot="x:-15">-15°</button>
        <button class="secondary" data-rot="x:-1">-1°</button>
        <button class="secondary" data-rot="x:1">+1°</button>
        <button class="secondary" data-rot="x:15">+15°</button>
      </div>
      <div class="nudge-row">
        <span style="color:#98c379;">Rot Y</span>
        <button class="secondary" data-rot="y:-15">-15°</button>
        <button class="secondary" data-rot="y:-1">-1°</button>
        <button class="secondary" data-rot="y:1">+1°</button>
        <button class="secondary" data-rot="y:15">+15°</button>
      </div>
      <div class="nudge-row">
        <span style="color:#61afef;">Rot Z</span>
        <button class="secondary" data-rot="z:-15">-15°</button>
        <button class="secondary" data-rot="z:-1">-1°</button>
        <button class="secondary" data-rot="z:1">+1°</button>
        <button class="secondary" data-rot="z:15">+15°</button>
      </div>

      <div class="row" style="margin-top:8px;"><label>Euler X</label><input id="rotX" type="range" min="-180" max="180" step="1"><input id="rotXNum" type="number" min="-180" max="180" step="1"></div>
      <div class="row"><label>Euler Y</label><input id="rotY" type="range" min="-180" max="180" step="1"><input id="rotYNum" type="number" min="-180" max="180" step="1"></div>
      <div class="row"><label>Euler Z</label><input id="rotZ" type="range" min="-180" max="180" step="1"><input id="rotZNum" type="number" min="-180" max="180" step="1"></div>

      <div class="btn-grid" style="margin-top:8px;">
        <button class="secondary" id="flipYBtn">Flip 180° Y</button>
        <button class="secondary" id="resetRotBtn">Reset Rot (0,0,0)</button>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Save &amp; Export (1 Layer Only)</h2>
    <div class="btn-grid">
      <button id="saveBtn">Save Shape JSON</button>
      <button class="secondary" id="reloadBtn">Reload Disk</button>
    </div>
    <div class="row" style="margin-top:8px;">
      <label style="width:auto;">Layer #</label>
      <input id="exportLayerNum" type="number" min="1" max="24" value="1" style="width:54px;" />
      <button class="success" id="exportLayerBtn" style="flex:1;">Export 1 Layer</button>
    </div>
    <textarea id="exportBox" readonly placeholder="Click 'Export 1 Layer' to generate LAYER_RECIPE (8 sticks)..."></textarea>
    <div id="status" style="margin-top:6px;"></div>
  </div>
</div>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const viewport = document.getElementById('viewport');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x181a1f);

const camera = new THREE.PerspectiveCamera(45, viewport.clientWidth / viewport.clientHeight, 0.1, 400);
camera.position.set(22, 18, 24);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(viewport.clientWidth, viewport.clientHeight);
renderer.setPixelRatio(window.devicePixelRatio);
viewport.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(8, 2, 8);
controls.update();

scene.add(new THREE.AmbientLight(0xffffff, 1.35));
const dirLight = new THREE.DirectionalLight(0xffffff, 1.1);
dirLight.position.set(18, 30, 14);
scene.add(dirLight);

const grid = new THREE.GridHelper(16, 16, 0x4b5263, 0x2c313c);
grid.position.set(8, 0, 8);
scene.add(grid);

const blockOutline = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.BoxGeometry(16, 16, 16)),
  new THREE.LineBasicMaterial({ color: 0x3e4451 })
);
blockOutline.position.set(8, 8, 8);
scene.add(blockOutline);

// Block corner axis indicator: Red = X, Green = Y, Blue = Z
scene.add(new THREE.AxesHelper(4));

// Stick-centered axis gizmo shown on selected stick
const selectionGizmo = new THREE.AxesHelper(3.2);
selectionGizmo.visible = false;
scene.add(selectionGizmo);

const hitboxMesh = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)),
  new THREE.LineBasicMaterial({ color: 0x98c379 })
);
scene.add(hitboxMesh);

let shapeData = null;
let gsProps = null;
let stickGroups = [];
let selectedIdx = -1;
const textureCache = new Map();
const texLoader = new THREE.TextureLoader();

function deg2rad(d) { return (d || 0) * Math.PI / 180; }
function rad2deg(r) { return r * 180 / Math.PI; }
function round2(n) { return Math.round(n * 100) / 100; }
function round3(n) { return Math.round(n * 1000) / 1000; }
function wrap180(deg) {
  let a = ((deg + 180) % 360 + 360) % 360 - 180;
  return round2(Math.abs(a + 180) < 1e-4 ? 180 : a);
}

// Flatten sX_pivot -> sX_anchor wrappers so every stick rotates cleanly around its own center
function normalizeShapeForEditor(shape) {
  if (!shape || !Array.isArray(shape.elements)) return shape;
  shape.elements = shape.elements.map((el, idx) => {
    if (
      Array.isArray(el.children) &&
      el.children.length === 1 &&
      (el.children[0].name || '').endsWith('_anchor')
    ) {
      const ch = el.children[0];
      const pOrig = el.rotationOrigin || el.from || [0, 0, 0];
      const cPos = ch.from || [0, 0, 0];

      const qPivot = new THREE.Quaternion().setFromEuler(
        new THREE.Euler(deg2rad(el.rotationX), deg2rad(el.rotationY), deg2rad(el.rotationZ), 'XYZ')
      );
      const qAnchor = new THREE.Quaternion().setFromEuler(
        new THREE.Euler(deg2rad(ch.rotationX), deg2rad(ch.rotationY), deg2rad(ch.rotationZ), 'XYZ')
      );

      const relVec = new THREE.Vector3(cPos[0], cPos[1], cPos[2]).applyQuaternion(qPivot);
      const wx = round3(pOrig[0] + relVec.x);
      const wy = round3(pOrig[1] + relVec.y);
      const wz = round3(pOrig[2] + relVec.z);

      const qWorld = qPivot.clone().multiply(qAnchor);
      const eWorld = new THREE.Euler().setFromQuaternion(qWorld, 'XYZ');
      const rx = wrap180(rad2deg(eWorld.x));
      const ry = wrap180(rad2deg(eWorld.y));
      const rz = wrap180(rad2deg(eWorld.z));

      const flat = {
        name: `s${idx + 1}_anchor`,
        from: [wx, wy, wz],
        to: [wx, wy, wz],
        rotationOrigin: [wx, wy, wz],
        children: ch.children
      };
      if (Math.abs(rx) > 1e-3) flat.rotationX = rx;
      if (Math.abs(ry) > 1e-3) flat.rotationY = ry;
      if (Math.abs(rz) > 1e-3) flat.rotationZ = rz;
      return flat;
    }
    return el;
  });
  return shape;
}

function getTexture(texRef) {
  if (!texRef || !shapeData?.textures) return null;
  const key = texRef.startsWith('#') ? texRef.slice(1) : texRef;
  const assetPath = shapeData.textures[key];
  if (!assetPath) return null;
  if (textureCache.has(assetPath)) return textureCache.get(assetPath);

  const tex = texLoader.load('/texture?path=' + encodeURIComponent(assetPath));
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestFilter;
  tex.colorSpace = THREE.SRGBColorSpace;
  textureCache.set(assetPath, tex);
  return tex;
}

const FACE_ORDER = ['east', 'west', 'up', 'down', 'south', 'north'];

function buildElementNode(el, texW, texH, rootStickIdx, isRootAnchor = false) {
  const from = el.from || [0, 0, 0];
  const to = el.to || [0, 0, 0];
  const origin = el.rotationOrigin || [0, 0, 0];

  const pivot = new THREE.Group();
  pivot.position.set(origin[0], origin[1], origin[2]);
  // 'XYZ' matches Vintage Story ShapeElement rotation order (Rx * Ry * Rz)
  pivot.rotation.set(deg2rad(el.rotationX), deg2rad(el.rotationY), deg2rad(el.rotationZ), 'XYZ');

  const offset = new THREE.Group();
  offset.position.set(-origin[0], -origin[1], -origin[2]);
  pivot.add(offset);

  let selfMesh = null;
  let childAnchor = null;

  const sx = Math.abs(to[0] - from[0]);
  const sy = Math.abs(to[1] - from[1]);
  const sz = Math.abs(to[2] - from[2]);
  const faces = el.faces || {};
  const hasVisibleFace = FACE_ORDER.some(f => faces[f] && faces[f].enabled !== false);

  if (sx > 1e-5 && sy > 1e-5 && sz > 1e-5 && hasVisibleFace) {
    const geom = new THREE.BoxGeometry(sx, sy, sz);
    const uvAttr = geom.attributes.uv;
    const materials = [];

    FACE_ORDER.forEach((faceName, fIdx) => {
      const f = faces[faceName];
      if (!f || f.enabled === false) {
        materials.push(new THREE.MeshBasicMaterial({ visible: false }));
        return;
      }
      const uv = f.uv || [0, 0, texW, texH];
      const u1 = uv[0] / texW, u2 = uv[2] / texW;
      const vTop = 1 - (uv[1] / texH), vBot = 1 - (uv[3] / texH);
      const base = fIdx * 4;
      uvAttr.setXY(base + 0, u1, vTop);
      uvAttr.setXY(base + 1, u2, vTop);
      uvAttr.setXY(base + 2, u1, vBot);
      uvAttr.setXY(base + 3, u2, vBot);

      const tex = getTexture(f.texture);
      materials.push(new THREE.MeshStandardMaterial({
        map: tex,
        color: tex ? 0xffffff : 0x9c6f44,
        roughness: 0.85
      }));
    });
    uvAttr.needsUpdate = true;

    selfMesh = new THREE.Mesh(geom, materials);
    selfMesh.position.set((from[0] + to[0]) / 2, (from[1] + to[1]) / 2, (from[2] + to[2]) / 2);
    selfMesh.userData.stickIdx = rootStickIdx;
    offset.add(selfMesh);
  }

  if (Array.isArray(el.children)) {
    childAnchor = new THREE.Group();
    childAnchor.position.set(from[0], from[1], from[2]);
    offset.add(childAnchor);
    for (const ch of el.children) {
      childAnchor.add(buildElementNode(ch, texW, texH, rootStickIdx, false));
    }
  }

  if (isRootAnchor) {
    pivot.userData = { stickIdx: rootStickIdx, offsetGroup: offset, childAnchor, selfMesh, el };
  }

  return pivot;
}

function rebuildScene() {
  for (const g of stickGroups) scene.remove(g);
  stickGroups = [];

  const texW = shapeData.textureWidth || 16;
  const texH = shapeData.textureHeight || 16;

  shapeData.elements.forEach((el, idx) => {
    const g = buildElementNode(el, texW, texH, idx, true);
    scene.add(g);
    stickGroups.push(g);
  });

  const maxCount = stickGroups.length;
  const stackSlider = document.getElementById('stackSlider');
  const stackNum = document.getElementById('stackNum');
  stackSlider.max = maxCount;
  stackNum.max = maxCount;
  if (parseInt(stackSlider.value, 10) > maxCount) {
    stackSlider.value = maxCount;
    stackNum.value = maxCount;
  }

  const maxLayers = Math.max(1, Math.ceil(maxCount / 8));
  document.getElementById('exportLayerNum').max = maxLayers;

  updateVisibilityAndHitbox();
  selectStick(selectedIdx < maxCount ? selectedIdx : -1);
}

function updateVisibilityAndHitbox() {
  const count = parseInt(document.getElementById('stackSlider').value, 10);
  stickGroups.forEach((g, idx) => { g.visible = idx < count; });

  const showHb = document.getElementById('showHitbox').checked;
  hitboxMesh.visible = showHb && count > 0 && !!gsProps;

  if (gsProps && count > 0) {
    const cb = gsProps.collisionBox || { x1: 0, y1: 0, z1: 0, x2: 1, y2: 0.25, z2: 1 };
    const scaleY = gsProps.cbScaleYByLayer || 0;
    const layers = scaleY > 0 ? Math.max(1, Math.ceil(count * scaleY)) : 1;
    const w = (cb.x2 - cb.x1) * 16;
    const h = (cb.y2 - cb.y1) * 16 * layers;
    const d = (cb.z2 - cb.z1) * 16;

    hitboxMesh.scale.set(w, h, d);
    hitboxMesh.position.set(cb.x1 * 16 + w / 2, cb.y1 * 16 + h / 2, cb.z1 * 16 + d / 2);
    document.getElementById('hitboxInfo').textContent =
      `Showing ${count}/${stickGroups.length} | Layers: ${layers} | Box height: ${h.toFixed(2)}v`;
  } else {
    document.getElementById('hitboxInfo').textContent =
      count === 0 ? `0/${stickGroups.length} sticks shown` : 'No patch config found';
  }
}

function highlightStick(idx) {
  stickGroups.forEach((g, i) => {
    g.traverse(obj => {
      if (obj.isMesh && Array.isArray(obj.material)) {
        obj.material.forEach(m => {
          if (m.emissive) m.emissive.setHex(i === idx ? 0x284b7a : 0x000000);
        });
      }
    });
  });
}

function updateSelectionGizmo() {
  if (selectedIdx < 0 || !shapeData?.elements[selectedIdx]) {
    selectionGizmo.visible = false;
    return;
  }
  const el = shapeData.elements[selectedIdx];
  const pos = el.from || [0, 0, 0];
  selectionGizmo.visible = true;
  selectionGizmo.position.set(pos[0], pos[1], pos[2]);

  if (document.getElementById('rotSpace').value === 'local') {
    selectionGizmo.rotation.set(deg2rad(el.rotationX), deg2rad(el.rotationY), deg2rad(el.rotationZ), 'XYZ');
  } else {
    selectionGizmo.rotation.set(0, 0, 0);
  }
}

function selectStick(idx) {
  selectedIdx = idx;
  highlightStick(idx);
  const panel = document.getElementById('inspectorControls');
  const label = document.getElementById('selName');

  if (idx < 0 || !shapeData.elements[idx]) {
    label.textContent = 'None';
    panel.style.opacity = '0.45';
    panel.style.pointerEvents = 'none';
    selectionGizmo.visible = false;
    return;
  }

  document.getElementById('exportLayerNum').value = Math.floor(idx / 8) + 1;

  const el = shapeData.elements[idx];
  const leafName = getLeafModelName(el);
  label.textContent = `#${idx + 1} (${leafName})`;
  panel.style.opacity = '1';
  panel.style.pointerEvents = 'auto';

  const pos = el.from || [0, 0, 0];
  setPair('posX', pos[0]);
  setPair('posY', pos[1]);
  setPair('posZ', pos[2]);
  setPair('rotX', wrap180(el.rotationX || 0));
  setPair('rotY', wrap180(el.rotationY || 0));
  setPair('rotZ', wrap180(el.rotationZ || 0));
  updateSelectionGizmo();
}

function setPair(id, val) {
  document.getElementById(id).value = val;
  document.getElementById(id + 'Num').value = val;
}

// Gimbal-lock-free rotation step around World or Local X/Y/Z axis
function rotateSelectedAroundAxis(axis, deltaDeg) {
  if (selectedIdx < 0) return;
  const rx = parseFloat(document.getElementById('rotXNum').value) || 0;
  const ry = parseFloat(document.getElementById('rotYNum').value) || 0;
  const rz = parseFloat(document.getElementById('rotZNum').value) || 0;

  const qCur = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(deg2rad(rx), deg2rad(ry), deg2rad(rz), 'XYZ')
  );
  const axisVec = axis === 'x'
    ? new THREE.Vector3(1, 0, 0)
    : axis === 'y'
      ? new THREE.Vector3(0, 1, 0)
      : new THREE.Vector3(0, 0, 1);

  const qDelta = new THREE.Quaternion().setFromAxisAngle(axisVec, deg2rad(deltaDeg));
  const space = document.getElementById('rotSpace').value;
  const qNext = space === 'local'
    ? qCur.multiply(qDelta)   // Local stick axis
    : qDelta.multiply(qCur);  // Pure World X / Y / Z axis (no gimbal lock)

  const eNext = new THREE.Euler().setFromQuaternion(qNext, 'XYZ');
  setPair('rotX', wrap180(rad2deg(eNext.x)));
  setPair('rotY', wrap180(rad2deg(eNext.y)));
  setPair('rotZ', wrap180(rad2deg(eNext.z)));
  applyInspectorToSelected();
}

function applyInspectorToSelected() {
  if (selectedIdx < 0) return;
  const el = shapeData.elements[selectedIdx];
  const g = stickGroups[selectedIdx];

  const oldFrom = el.from || [0, 0, 0];
  const oldTo = el.to || [0, 0, 0];
  const oldOrigin = el.rotationOrigin || oldFrom;
  const relOrigin = [
    oldOrigin[0] - oldFrom[0],
    oldOrigin[1] - oldFrom[1],
    oldOrigin[2] - oldFrom[2]
  ];

  const px = round3(parseFloat(document.getElementById('posXNum').value) || 0);
  const py = round3(parseFloat(document.getElementById('posYNum').value) || 0);
  const pz = round3(parseFloat(document.getElementById('posZNum').value) || 0);
  const rx = wrap180(parseFloat(document.getElementById('rotXNum').value) || 0);
  const ry = wrap180(parseFloat(document.getElementById('rotYNum').value) || 0);
  const rz = wrap180(parseFloat(document.getElementById('rotZNum').value) || 0);

  const dx = px - oldFrom[0];
  const dy = py - oldFrom[1];
  const dz = pz - oldFrom[2];

  const ox = round3(px + relOrigin[0]);
  const oy = round3(py + relOrigin[1]);
  const oz = round3(pz + relOrigin[2]);

  el.from = [px, py, pz];
  el.to = [round3(oldTo[0] + dx), round3(oldTo[1] + dy), round3(oldTo[2] + dz)];
  el.rotationOrigin = [ox, oy, oz];

  if (Math.abs(rx) > 1e-3) el.rotationX = rx; else delete el.rotationX;
  if (Math.abs(ry) > 1e-3) el.rotationY = ry; else delete el.rotationY;
  if (Math.abs(rz) > 1e-3) el.rotationZ = rz; else delete el.rotationZ;

  g.position.set(ox, oy, oz);
  g.userData.offsetGroup.position.set(-ox, -oy, -oz);
  if (g.userData.childAnchor) {
    g.userData.childAnchor.position.set(px, py, pz);
  }
  if (g.userData.selfMesh) {
    g.userData.selfMesh.position.set(
      (el.from[0] + el.to[0]) / 2,
      (el.from[1] + el.to[1]) / 2,
      (el.from[2] + el.to[2]) / 2
    );
  }
  g.rotation.set(deg2rad(rx), deg2rad(ry), deg2rad(rz), 'XYZ');
  updateSelectionGizmo();
}

['posX', 'posY', 'posZ', 'rotX', 'rotY', 'rotZ'].forEach(id => {
  const slider = document.getElementById(id);
  const num = document.getElementById(id + 'Num');
  slider.addEventListener('input', () => { num.value = slider.value; applyInspectorToSelected(); });
  num.addEventListener('input', () => { slider.value = num.value; applyInspectorToSelected(); });
});

document.getElementById('rotSpace').addEventListener('change', updateSelectionGizmo);

document.querySelectorAll('[data-rot]').forEach(btn => {
  btn.addEventListener('click', () => {
    const [axis, degStr] = btn.dataset.rot.split(':');
    rotateSelectedAroundAxis(axis, parseFloat(degStr));
  });
});

document.getElementById('flipYBtn').addEventListener('click', () => {
  rotateSelectedAroundAxis('y', 180);
});

document.getElementById('resetRotBtn').addEventListener('click', () => {
  setPair('rotX', 0);
  setPair('rotY', 0);
  setPair('rotZ', 0);
  applyInspectorToSelected();
});

// --- Keyboard + Mouse Scroll Shortcuts (X/Z/C = Rotate, Ctrl+X/Z/C = Move) ---
const heldKeys = new Set();
let ctrlHeld = false;
let shiftHeld = false;

function getActiveAxisKey() {
  if (heldKeys.has('z')) return 'z';
  if (heldKeys.has('x')) return 'x';
  if (heldKeys.has('c')) return 'c';
  return null;
}

function updateShortcutHud() {
  const axisKey = getActiveAxisKey();
  controls.enabled = !axisKey;
  const badge = document.getElementById('keyBadge');
  if (!axisKey) {
    badge.textContent = 'Active Shortcut: None';
    badge.style.color = '#61afef';
    return;
  }
  const axisLabel = axisKey === 'x' ? 'X' : axisKey === 'z' ? 'Z' : 'Y';
  const spaceLabel = document.getElementById('rotSpace').value === 'local' ? 'Local' : 'World';
  if (ctrlHeld) {
    badge.textContent = `Active: Move Pos ${axisLabel} (±0.05 per scroll)`;
    badge.style.color = '#98c379';
  } else {
    const step = shiftHeld ? 5 : 1;
    badge.textContent = `Active: Rotate ${spaceLabel} ${axisLabel} (±${step}° per scroll)`;
    badge.style.color = '#e5c07b';
  }
}

window.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
  const k = e.key.toLowerCase();
  ctrlHeld = e.ctrlKey;
  shiftHeld = e.shiftKey;
  if (k === 'z' || k === 'x' || k === 'c') {
    heldKeys.add(k);
    if (e.ctrlKey) e.preventDefault();
  }
  updateShortcutHud();
});

window.addEventListener('keyup', e => {
  const k = e.key.toLowerCase();
  ctrlHeld = e.ctrlKey;
  shiftHeld = e.shiftKey;
  heldKeys.delete(k);
  updateShortcutHud();
});

window.addEventListener('blur', () => {
  heldKeys.clear();
  ctrlHeld = false;
  shiftHeld = false;
  updateShortcutHud();
});

window.addEventListener('wheel', e => {
  const axisKey = getActiveAxisKey();
  if (!axisKey) return;

  e.preventDefault();
  e.stopPropagation();

  if (selectedIdx < 0) return;
  const dir = e.deltaY < 0 ? 1 : -1;
  const isMove = e.ctrlKey || ctrlHeld;

  if (isMove) {
    const field = axisKey === 'x' ? 'posX' : axisKey === 'z' ? 'posZ' : 'posY';
    const cur = parseFloat(document.getElementById(field + 'Num').value) || 0;
    setPair(field, round3(cur + dir * 0.05));
    applyInspectorToSelected();
  } else {
    const axis = axisKey === 'x' ? 'x' : axisKey === 'z' ? 'z' : 'y';
    const step = (e.shiftKey || shiftHeld) ? 5 : 1;
    rotateSelectedAroundAxis(axis, dir * step);
  }
}, { passive: false, capture: true });

// --- Stack Slider & Raycast Selection ---
const stackSlider = document.getElementById('stackSlider');
const stackNum = document.getElementById('stackNum');
stackSlider.addEventListener('input', () => { stackNum.value = stackSlider.value; updateVisibilityAndHitbox(); });
stackNum.addEventListener('input', () => { stackSlider.value = stackNum.value; updateVisibilityAndHitbox(); });
document.getElementById('showAllBtn').addEventListener('click', () => {
  stackSlider.value = stickGroups.length;
  stackNum.value = stickGroups.length;
  updateVisibilityAndHitbox();
});
document.getElementById('showHitbox').addEventListener('change', updateVisibilityAndHitbox);

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let downPos = { x: 0, y: 0 };

renderer.domElement.addEventListener('pointerdown', e => { downPos = { x: e.clientX, y: e.clientY }; });
renderer.domElement.addEventListener('pointerup', e => {
  if (Math.hypot(e.clientX - downPos.x, e.clientY - downPos.y) > 4) return;
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);

  const hits = raycaster.intersectObjects(stickGroups, true).filter(h => {
    let p = h.object;
    while (p) { if (!p.visible) return false; p = p.parent; }
    return true;
  });
  selectStick(hits.length ? hits[0].object.userData.stickIdx : -1);
});

function getLeafModelName(el) {
  let leafName = el.name || 'stick0-1';
  let cur = el;
  while (cur.children && cur.children.length > 0) {
    cur = cur.children[0];
    if (cur.name && !cur.name.endsWith('_anchor')) {
      leafName = cur.name;
      break;
    }
  }
  return leafName.includes('_') ? leafName.split('_').slice(1).join('_') : leafName;
}

async function loadAll() {
  const res = await fetch('/api/data');
  const data = await res.json();
  shapeData = normalizeShapeForEditor(data.shape);
  gsProps = data.groundStorable;
  rebuildScene();
  document.getElementById('status').textContent = 'Loaded shape & patch.';
}

document.getElementById('reloadBtn').addEventListener('click', loadAll);
document.getElementById('saveBtn').addEventListener('click', async () => {
  const res = await fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(shapeData)
  });
  const out = await res.json();
  document.getElementById('status').textContent = out.message || 'Saved!';
});

// --- Export ONLY 1 Layer (8 sticks) ---
document.getElementById('exportLayerBtn').addEventListener('click', async () => {
  const layerNo = Math.max(1, parseInt(document.getElementById('exportLayerNum').value, 10) || 1);
  const start = (layerNo - 1) * 8;
  const slice = shapeData.elements.slice(start, start + 8);
  if (!slice.length) {
    document.getElementById('status').textContent = `Layer ${layerNo} has no sticks.`;
    return;
  }

  const minY = Math.min(...slice.map(el => (el.from || [0, 0, 0])[1]));
  const lines = ['LAYER_RECIPE = ['];
  for (const el of slice) {
    const modelName = getLeafModelName(el);
    const [px, py, pz] = el.from || [0, 0, 0];
    const rx = wrap180(el.rotationX || 0);
    const ry = wrap180(el.rotationY || 0);
    const rz = wrap180(el.rotationZ || 0);
    const entry = {
      model: modelName,
      pos: [round3(px), round3(py - minY), round3(pz)],
      rot: [rx, ry, rz]
    };
    lines.push('    ' + JSON.stringify(entry) + ',');
  }
  lines.push(']');
  const recipeText = lines.join('\n');

  const box = document.getElementById('exportBox');
  box.value = recipeText;
  box.select();

  try {
    await navigator.clipboard.writeText(recipeText);
  } catch (_) {}

  const res = await fetch('/api/export-layer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: recipeText, layer: layerNo })
  });
  const out = await res.json();
  document.getElementById('status').textContent = out.message || `Exported Layer ${layerNo} (1 layer)!`;
});

window.addEventListener('resize', () => {
  camera.aspect = viewport.clientWidth / viewport.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(viewport.clientWidth, viewport.clientHeight);
});

loadAll();
(function animate() {
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
})();
</script>
</body>
</html>
"""


class EditorHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/data":
            shape = json.loads(SHAPE_FILE.read_text(encoding="utf-8"))
            gs_props = None
            if PATCH_FILE.exists():
                patch = json.loads(PATCH_FILE.read_text(encoding="utf-8"))
                for op in patch:
                    for b in op.get("value", []):
                        if isinstance(b, dict) and b.get("name") == "GroundStorable":
                            gs_props = b.get("properties")
            self._send_json({"shape": shape, "groundStorable": gs_props})
            return

        if parsed.path == "/texture":
            qs = urllib.parse.parse_qs(parsed.query)
            raw_tex = qs.get("path", [""])[0].removeprefix("game:").replace("\\", "/")
            tex_path = VS_ASSETS_DIR / "textures" / f"{raw_tex}.png"
            if tex_path.exists():
                img = tex_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(img)))
                self.end_headers()
                self.wfile.write(img)
            else:
                self.send_response(404)
                self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))

        if self.path == "/api/save":
            SHAPE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            self._send_json({"message": f"Saved -> {SHAPE_FILE.as_posix()}"})
            return

        if self.path == "/api/export-layer":
            recipe_text = payload.get("text", "")
            layer_no = payload.get("layer", 1)
            EXPORT_TXT_FILE.write_text(recipe_text + "\n", encoding="utf-8")
            self._send_json({
                "message": f"Exported Layer {layer_no} (1 layer) -> copied & saved to {EXPORT_TXT_FILE.as_posix()}"
            })
            return

        self.send_response(404)
        self.end_headers()


def main():
    if not SHAPE_FILE.exists():
        raise FileNotFoundError(f"Run gen-piles.py first so {SHAPE_FILE} exists.")

    with socketserver.TCPServer(("127.0.0.1", PORT), EditorHandler) as httpd:
        url = f"http://127.0.0.1:{PORT}"
        print(f"3D Stick Pile Editor running at {url} (Ctrl+C to stop)")
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped editor.")


if __name__ == "__main__":
    main()