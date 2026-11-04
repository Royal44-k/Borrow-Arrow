<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createArmorDecoys } from '../armorGeometry';
import { arrowVisualCount, hullHalfWidth, hullPoint, normalizeAngle, seededRandom, strawLayout, type BoatPart, type Point3 } from '../boatGeometry';

const props = withDefaults(defineProps<{
  mode: 'inspect' | 'river'; side: 'left' | 'right'; straw: boolean; decoy?:'straw'|'armor'|null; arrows: number; disabled?: boolean;
}>(), { disabled: false });
const emit = defineEmits<{
  inspect: [part: BoatPart]; orient: [angle: number]; ready: []; error: [message: string];
}>();
const host = ref<HTMLDivElement>();
const fault = ref('');
const label = computed(() => props.mode === 'inspect' ? '察看木船：拖动环视，滚轮缩放；方向键环视，加减号缩放，H 察看船体，S 察看外侧布置，L 察看船灯。' : '雾江船阵：拖动环视；方向键调整视角，H 察看船体，S 察看外侧布置，L 察看船灯。');
let renderer: THREE.WebGLRenderer | undefined;
let scene: THREE.Scene, camera: THREE.PerspectiveCamera, controls: OrbitControls;
let boat: THREE.Group, strawGroup: THREE.Group, armorGroup: THREE.Group, arrowsGroup: THREE.Group;
let river: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshStandardMaterial> | undefined;
let lamp: THREE.PointLight;
let frame = 0, disposed = false, observer: ResizeObserver | undefined;
let previousFrame = 0, elapsed = 0, pointerDown: { x: number; y: number } | undefined;
let targetYaw = 0;
let reducedMotion = false;
let removeListeners: (() => void) | undefined;
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function reportError() {
  if (fault.value || disposed) return;
  fault.value = '江面暂时未能展开。可以继续查看场景，稍后再试。';
  cancelAnimationFrame(frame);
  emit('error', 'WebGL scene unavailable');
}

function clothTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 256;
  const c = canvas.getContext('2d')!; const random = seededRandom(527);
  c.fillStyle = '#b4a58a'; c.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 2200; i++) {
    const x = random() * 256, y = random() * 256;
    c.strokeStyle = `rgba(46,37,23,${.02 + random() * .09})`; c.lineWidth = .4;
    c.beginPath(); c.moveTo(x, y); c.lineTo(x + 1 + random() * 9, y); c.stroke();
  }
  c.strokeStyle = 'rgba(52,43,28,.23)'; c.lineWidth = 1;
  for (let i = 0; i < 256; i += 32) { c.beginPath(); c.moveTo(i, 0); c.lineTo(i, 256); c.stroke(); }
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping; return texture;
}

function timberTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 128;
  const c = canvas.getContext('2d')!; const random = seededRandom(8);
  c.fillStyle = '#66503a'; c.fillRect(0, 0, 512, 128);
  for (let i = 0; i < 330; i++) {
    const y = random() * 128;
    c.strokeStyle = `rgba(${random() > .5 ? '211,174,121' : '24,18,13'},${.06 + random() * .25})`;
    c.lineWidth = .25 + random() * 1.2; c.beginPath(); c.moveTo(0, y);
    for (let x = 0; x <= 512; x += 24) c.lineTo(x, y + Math.sin(x / 82 + i) * (1 + random() * 2));
    c.stroke();
  }
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping; return texture;
}

function surface(points: Point3[], indices: number[], material: THREE.Material, part?: BoatPart) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(points.flat(), 3));
  const uv = points.map((_, i) => [(i % 2), Math.floor(i / 2) / Math.max(1, points.length / 2 - 1)]).flat();
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setIndex(indices); geo.computeVertexNormals();
  const mesh = new THREE.Mesh(geo, material); mesh.castShadow = mesh.receiveShadow = true;
  if (part) mesh.userData.part = part;
  return mesh;
}

function strip(points: Point3[], material: THREE.Material, part?: BoatPart) {
  const indices: number[] = [];
  for (let i = 0; i < points.length - 2; i += 2) indices.push(i, i + 1, i + 2, i + 1, i + 3, i + 2);
  return surface(points, indices, material, part);
}

function tube(points: Point3[], radius: number, material: THREE.Material, parent: THREE.Object3D = boat) {
  const curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p)));
  const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(8, points.length * 3), radius, 6, false), material);
  mesh.castShadow = true; parent.add(mesh); return mesh;
}

function rod(a: Point3, b: Point3, radius: number, material: THREE.Material, parent: THREE.Object3D = boat) {
  const start = new THREE.Vector3(...a), end = new THREE.Vector3(...b), delta = end.clone().sub(start);
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius * .8, radius, delta.length(), 7), material);
  mesh.position.copy(start).add(end).multiplyScalar(.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), delta.normalize()); mesh.castShadow = true;
  parent.add(mesh); return mesh;
}

function buildBoat() {
  boat = new THREE.Group(); scene.add(boat);
  const woodMap = timberTexture();
  const wood = Array.from({ length: 6 }, (_, i) => new THREE.MeshStandardMaterial({ color: new THREE.Color().setHSL(.08, .23, .29 + i * .019), map: woodMap, roughness: .9, side: THREE.DoubleSide }));
  const darkWood = new THREE.MeshStandardMaterial({ color: '#32271e', roughness: .92 });
  const rope = new THREE.MeshStandardMaterial({ color: '#93836a', roughness: 1 });
  const iron = new THREE.MeshStandardMaterial({ color: '#292b29', metalness: .48, roughness: .7 });
  const canvas = new THREE.MeshStandardMaterial({ color: '#b7ac91', map: clothTexture(), roughness: 1, side: THREE.DoubleSide });

  // Eight curved strakes per side; tiny seams retain individual plank relief.
  for (const side of [-1, 1] as const) {
    for (let k = 0; k < 8; k++) {
      const points: Point3[] = [];
      for (let i = 0; i <= 48; i++) {
        const x = -4.8 + i * .2;
        points.push(hullPoint(x, k / 8 + .002, side), hullPoint(x, (k + 1) / 8 - .002, side));
      }
      boat.add(strip(points, wood[k % wood.length], 'hull'));
    }
    const gunwale: Point3[] = [];
    for (let x = -4.8; x <= 4.8; x += .3) gunwale.push(hullPoint(x, 1, side));
    tube(gunwale, .065, darkWood).userData.part = 'hull';
  }
  const keel: Point3[] = [];
  for (let x = -4.75; x <= 4.8; x += .3) keel.push([x, hullPoint(x, 0, 1)[1] - .035, 0]);
  tube(keel, .075, darkWood);
  // Long deck boards follow the hull perimeter instead of a rectangular box.
  for (let plank = 0; plank < 12; plank++) {
    const points: Point3[] = [];
    for (let i = 0; i <= 40; i++) {
      const x = -4.55 + i * 9.1 / 40, y = .25 + .53 * Math.pow(Math.abs(x / 4.8), 4);
      const width = hullHalfWidth(x) * .94;
      points.push([x, y, width * (-1 + plank / 6 + .003)], [x, y, width * (-1 + (plank + 1) / 6 - .003)]);
    }
    boat.add(strip(points, wood[(plank + 2) % 6], 'hull'));
  }
  for (let x = -3.8; x <= 3.8; x += 1.25) {
    const w = hullHalfWidth(x) * .92;
    rod([x, .31, -w], [x, .31, w], .055, darkWood).userData.part = 'hull';
  }
  // Bamboo ribs and a sewn, slightly irregular cloth canopy, open at each end.
  for (const x of [-2.55, -1.55, -.55, .45]) {
    const arc: Point3[] = [];
    for (let i = 0; i <= 16; i++) {
      const theta = i / 16 * Math.PI;
      arc.push([x, .42 + Math.sin(theta) * 1.53, Math.cos(theta) * 1.06]);
    }
    tube(arc, .035, rope);
  }
  for (let seg = 0; seg < 14; seg++) {
    const points: Point3[] = [];
    for (let j = 0; j <= 20; j++) {
      const x = -2.6 + j * 3.1 / 20;
      for (const n of [seg, seg + 1]) {
        const theta = n / 14 * Math.PI;
        points.push([x, .45 + Math.sin(theta) * (1.55 + Math.sin(j * .9) * .017), Math.cos(theta) * 1.08]);
      }
    }
    boat.add(strip(points, canvas));
  }
  for (const z of [-1.1, 1.1]) {
    tube([[-2.6, .45, z], [-1.5, .41, z], [-.5, .43, z], [.5, .45, z]], .025, rope);
  }
  // Mast, imperfect yard and a compact furled-sail-like canvas.
  rod([1.23, .3, 0], [1.23, 3.65, 0], .07, darkWood);
  rod([1.23, 3.28, -1], [1.23, 3.24, 1], .045, wood[3]);
  rod([1.23, 1.82, -.78], [1.23, 1.8, .78], .038, wood[3]);
  for (let k = 0; k < 12; k++) {
    const points: Point3[] = [];
    for (let j = 0; j <= 14; j++) {
      const v = j / 14;
      for (const q of [k, k + 1]) {
        const u = q / 12;
        points.push([1.23 + Math.sin(u * Math.PI) * Math.sin(v * Math.PI) * .23, 1.82 + v * 1.4, (u - .5) * (1.56 + v * .4)]);
      }
    }
    boat.add(strip(points, canvas));
  }
  tube([[1.23, 3.62, 0], [2.6, 1.4, .45], [4, .6, .63]], .015, rope);
  tube([[1.23, 3.62, 0], [.4, 1.65, -1], [-.8, .3, -1.22]], .015, rope);
  tube([[1.23, 3.62, 0], [.4, 1.65, 1], [-.8, .3, 1.22]], .015, rope);
  // Bound ropes around the working perimeter; stern steering oar and side oars.
  for (const side of [-1, 1] as const) {
    for (const x of [-3.4, 2.65]) {
      rod([x, .5, side * .8], [x - 1.1, -.2, side * 2.05], .027, wood[3]);
      const blade = new THREE.Mesh(new THREE.BoxGeometry(.12, .065, .68), wood[4]);
      blade.position.set(x - 1.14, -.23, side * 2.1); blade.rotation.y = side * .7; blade.rotation.z = .15;
      boat.add(blade);
    }
    tube([[-3.6, .76, side * .9], [-1.8, .64, side * 1.51], [1, .64, side * 1.5], [3.6, .76, side * .9]], .024, rope);
  }
  rod([-3.9, .85, -.2], [-5.1, -.25, .35], .04, darkWood);

  strawGroup = new THREE.Group(); boat.add(strawGroup);
  const strawMat = new THREE.MeshStandardMaterial({ color: '#aa9161', roughness: 1 });
  const random = seededRandom(39); const layouts = strawLayout();
  const stems = new THREE.InstancedMesh(new THREE.CylinderGeometry(.007, .012, 1, 4), strawMat, layouts.length * 42);
  const dummy = new THREE.Object3D(); let stemIndex = 0;
  for (const p of layouts) {
    // Visible fibre ends rather than a solid yellow cylinder.
    for (let i = 0; i < 42; i++) {
      const a = random() * Math.PI * 2, radius = .04 + random() * .19, length = .72 + random() * .48;
      dummy.position.set(p.x + Math.cos(a) * radius, .33 + length / 2, p.z + Math.sin(a) * radius);
      dummy.rotation.set((random() - .5) * .22, 0, (random() - .5) * .18);
      dummy.scale.set(1, length, 1); dummy.updateMatrix(); stems.setMatrixAt(stemIndex++, dummy.matrix);
    }
    for (const y of [.54, .86]) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(.17, .019, 5, 16), rope);
      ring.position.set(p.x, y, p.z); ring.rotation.x = Math.PI / 2; strawGroup.add(ring);
    }
    const target = new THREE.Mesh(new THREE.CylinderGeometry(.23, .23, 1, 8), new THREE.MeshBasicMaterial({ visible: false }));
    target.position.set(p.x, .85, p.z); target.userData.part = 'straw'; strawGroup.add(target);
  }
  stems.castShadow = true; stems.userData.part = 'straw'; strawGroup.add(stems);
  armorGroup=createArmorDecoys(layouts);boat.add(armorGroup);armorGroup.visible=props.decoy==='armor';

  // A small period-inspired lamp with frame, paper shade and practical amber light.
  const lantern = new THREE.Group(); lantern.position.set(2.65, .4, -.67); lantern.userData.part = 'lantern'; boat.add(lantern);
  rod([0, 0, 0], [0, 1.1, 0], .028, darkWood, lantern);
  rod([0, 1.1, 0], [.28, 1.1, 0], .028, darkWood, lantern);
  const shade = new THREE.Mesh(new THREE.CylinderGeometry(.14, .18, .3, 12), new THREE.MeshStandardMaterial({ color: '#e8bb6c', emissive: '#da7d24', emissiveIntensity: .6, transparent: true, opacity: .9, roughness: 1 }));
  shade.position.set(.28, .83, 0); shade.userData.part = 'lantern'; lantern.add(shade);
  for (const y of [.67, .99]) {
    const rim = new THREE.Mesh(new THREE.CylinderGeometry(.19, .19, .028, 12), iron); rim.position.set(.28, y, 0); rim.userData.part = 'lantern'; lantern.add(rim);
  }
  for (const z of [-.13, .13]) rod([.28, .67, z], [.28, .99, z], .01, iron, lantern);
  lamp = new THREE.PointLight('#ffc67d', 9, 6, 2); lamp.position.set(2.93, 1.25, -.67); boat.add(lamp);
  arrowsGroup = new THREE.Group(); boat.add(arrowsGroup); rebuildArrows();
  strawGroup.visible = props.straw;
}

function clearGroup(group: THREE.Group) {
  group.traverse(object => {
    if (object instanceof THREE.Mesh) {
      object.geometry.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach(m => m.dispose());
    }
  });
  group.clear();
}

function rebuildArrows() {
  if (!arrowsGroup) return;
  clearGroup(arrowsGroup);
  const count = props.straw || props.decoy==='armor' ? arrowVisualCount(props.arrows) : 0;
  if (!count) return;
  const shafts = new THREE.InstancedMesh(new THREE.CylinderGeometry(.009, .009, .78, 4), new THREE.MeshStandardMaterial({ color: '#725941', roughness: 1 }), count);
  const feathers = new THREE.InstancedMesh(new THREE.BoxGeometry(.065, .13, .008), new THREE.MeshStandardMaterial({ color: '#bdb59e', roughness: 1 }), count);
  const dummy = new THREE.Object3D(), random = seededRandom(92), layout = strawLayout();
  for (let i = 0; i < count; i++) {
    const p = layout[i % layout.length];
    const anchor = new THREE.Vector3(p.x + (random() - .5) * .3, .65 + random() * .45, p.z);
    const direction = new THREE.Vector3((random() - .5) * .35, .5 + random() * .3, p.side * (.45 + random() * .3)).normalize();
    dummy.position.copy(anchor).addScaledVector(direction, .31);
    dummy.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction); dummy.scale.set(1, 1, 1); dummy.updateMatrix();
    shafts.setMatrixAt(i, dummy.matrix);
    dummy.position.copy(anchor).addScaledVector(direction, .66); dummy.updateMatrix(); feathers.setMatrixAt(i, dummy.matrix);
  }
  arrowsGroup.add(shafts, feathers);
}

function configureMode() {
  if (!scene) return;
  if (river) { scene.remove(river); river.geometry.dispose(); river.material.dispose(); river = undefined; }
  scene.fog = props.mode === 'river' ? new THREE.FogExp2('#101f29', .023) : null;
  if (props.mode === 'river') {
    river = new THREE.Mesh(new THREE.PlaneGeometry(100, 100, 60, 60), new THREE.MeshStandardMaterial({ color: '#18323c', metalness: .48, roughness: .32, transparent: true, opacity: .92 }));
    river.rotation.x = -Math.PI / 2; river.position.y = -.36; river.receiveShadow = true; scene.add(river);
  }
}

function resize() {
  if (!renderer || !host.value) return;
  const { width, height } = host.value.getBoundingClientRect();
  if (width < 1 || height < 1) return;
  renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix();
}

function emitOrientation() { emit('orient', Math.round(normalizeAngle(controls.getAzimuthalAngle() * 180 / Math.PI))); }

function keydown(event: KeyboardEvent) {
  if (props.disabled || fault.value) return;
  const key = event.key.toLowerCase();
  if (['h', 's', 'l'].includes(key)) {
    if (key !== 's' || props.straw || props.decoy==='armor') emit('inspect', ({ h: 'hull', s: props.decoy==='armor'?'armor':'straw', l: 'lantern' } as const)[key as 'h' | 's' | 'l']);
    event.preventDefault(); return;
  }
  if (!['arrowleft', 'arrowright', 'arrowup', 'arrowdown', '+', '=', '-', '_', 'home'].includes(key)) return;
  event.preventDefault();
  if (key === 'home') { camera.position.set(8.7, 4.7, 9); controls.target.set(0, .65, 0); }
  else {
    const offset = camera.position.clone().sub(controls.target);
    const spherical = new THREE.Spherical().setFromVector3(offset);
    if (key === 'arrowleft') spherical.theta -= .14;
    if (key === 'arrowright') spherical.theta += .14;
    if (key === 'arrowup') spherical.phi = Math.max(.24, spherical.phi - .1);
    if (key === 'arrowdown') spherical.phi = Math.min(Math.PI / 2 - .08, spherical.phi + .1);
    if (key === '+' || key === '=') spherical.radius = Math.max(7, spherical.radius * .9);
    if (key === '-' || key === '_') spherical.radius = Math.min(22, spherical.radius * 1.1);
    camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
  }
  controls.update(); emitOrientation();
}

function animate(time: number) {
  if (disposed || fault.value || !renderer) return;
  frame = requestAnimationFrame(animate);
  if (document.hidden || time - previousFrame < 28) return; // Cap costly rendering near 35 fps.
  const dt = Math.min(.08, (time - previousFrame) / 1000 || .016); previousFrame = time; elapsed += dt;
  boat.rotation.y += (targetYaw - boat.rotation.y) * Math.min(1, dt * 3.5);
  if (!reducedMotion && props.mode === 'river') {
    boat.position.y = Math.sin(elapsed * .9) * .035; boat.rotation.x = Math.sin(elapsed * .7) * .008;
  } else { boat.position.y = 0; boat.rotation.x = 0; }
  if (river && !reducedMotion) {
    const position = river.geometry.attributes.position;
    for (let i = 0; i < position.count; i++) position.setZ(i, Math.sin(position.getX(i) * .62 + elapsed * .7) * .045 + Math.cos(position.getY(i) * .4 + elapsed * .43) * .025);
    position.needsUpdate = true;
  }
  lamp.intensity = reducedMotion ? 9 : 8.6 + Math.sin(elapsed * 5.7) * .25;
  controls.update(); renderer.render(scene, camera);
}

onMounted(() => {
  try {
    reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
    renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.28;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.domElement.tabIndex = 0; renderer.domElement.setAttribute('aria-label', label.value);
    host.value!.appendChild(renderer.domElement);
    scene = new THREE.Scene(); camera = new THREE.PerspectiveCamera(38, 1, .1, 150); camera.position.set(8.7, 4.7, 9);
    controls = new OrbitControls(camera, renderer.domElement); controls.target.set(0, .65, 0);
    controls.enableDamping = true; controls.dampingFactor = .09; controls.enablePan = false;
    controls.minDistance = 7; controls.maxDistance = 22; controls.maxPolarAngle = Math.PI / 2 - .08; controls.minPolarAngle = .24;
    controls.enabled = !props.disabled; controls.addEventListener('end', emitOrientation);
    scene.add(new THREE.HemisphereLight('#a4b9cb', '#554431', 2.2));
    const key = new THREE.DirectionalLight('#e4d2ac', 4); key.position.set(-4, 8, 5); key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024); key.shadow.camera.left = -8; key.shadow.camera.right = 8; key.shadow.camera.top = 7; key.shadow.camera.bottom = -7; key.shadow.normalBias = .035; scene.add(key);
    const rim = new THREE.DirectionalLight('#83a7c0', 2.6); rim.position.set(4, 4, -7); scene.add(rim);
    buildBoat(); targetYaw = props.side === 'right' ? Math.PI : 0; boat.rotation.y = targetYaw;
    configureMode(); resize(); observer = new ResizeObserver(resize); observer.observe(host.value!);
    const canvas = renderer.domElement;
    const down = (e: PointerEvent) => { pointerDown = { x: e.clientX, y: e.clientY }; };
    const up = (e: PointerEvent) => {
      if (!pointerDown || props.disabled || Math.hypot(e.clientX - pointerDown.x, e.clientY - pointerDown.y) > 7) { pointerDown = undefined; return; }
      pointerDown = undefined; const r = canvas.getBoundingClientRect();
      pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObject(boat, true);
      for (const hit of hits) {
        let target: THREE.Object3D | null = hit.object;
        while (target && !target.userData.part) target = target.parent;
        if (target?.userData.part && (target.userData.part !== 'straw' || props.straw) && (target.userData.part !== 'armor' || props.decoy==='armor')) { emit('inspect', target.userData.part as BoatPart); break; }
      }
    };
    const lost = (e: Event) => { e.preventDefault(); reportError(); };
    canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointerup', up); canvas.addEventListener('keydown', keydown); canvas.addEventListener('webglcontextlost', lost);
    removeListeners = () => { canvas.removeEventListener('pointerdown', down); canvas.removeEventListener('pointerup', up); canvas.removeEventListener('keydown', keydown); canvas.removeEventListener('webglcontextlost', lost); };
    controls.update(); renderer.render(scene, camera);
    frame = requestAnimationFrame(animate); emit('ready');
  } catch { reportError(); }
});

watch(() => props.side, side => { targetYaw = side === 'right' ? Math.PI : 0; });
watch(() => props.straw, value => { if (strawGroup) strawGroup.visible = value; rebuildArrows(); });
watch(() => props.decoy, value => { if(armorGroup) armorGroup.visible=value==='armor'; rebuildArrows(); });
watch(() => props.arrows, rebuildArrows);
watch(() => props.mode, configureMode);
watch(() => props.disabled, value => { if (controls) controls.enabled = !value; });
watch(label, value => renderer?.domElement.setAttribute('aria-label', value));

onBeforeUnmount(() => {
  disposed = true; cancelAnimationFrame(frame); observer?.disconnect(); removeListeners?.(); controls?.dispose();
  const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>(), textures = new Set<THREE.Texture>();
  scene?.traverse(object => {
    if (object instanceof THREE.Mesh) {
      geometries.add(object.geometry);
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
        materials.add(material);
        for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
      }
    }
    if (object instanceof THREE.Light && 'shadow' in object) (object as THREE.DirectionalLight).shadow?.map?.dispose();
  });
  geometries.forEach(x => x.dispose()); materials.forEach(x => x.dispose()); textures.forEach(x => x.dispose());
  renderer?.dispose(); renderer?.domElement.remove(); renderer = undefined;
});
</script>

<template>
  <div ref="host" class="boat-stage" :class="[`boat-stage--${mode}`, { 'boat-stage--unavailable': fault }]">
    <div v-if="fault" class="boat-stage__fallback" role="status">
      <p>{{ fault }}</p>
      <div aria-label="察看船上物件">
        <button type="button" :disabled="disabled" @click="emit('inspect', 'hull')">察看船体</button>
        <button v-if="straw" type="button" :disabled="disabled" @click="emit('inspect', 'straw')">察看草把</button>
        <button type="button" :disabled="disabled" @click="emit('inspect', 'lantern')">察看船灯</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.boat-stage { width:100%; height:100%; min-height:300px; position:relative; overflow:hidden; background:radial-gradient(ellipse at 50% 38%,#23303970,transparent 62%); }
.boat-stage--river { background:linear-gradient(#172b36b0,#0b1826b0); }
.boat-stage :deep(canvas) { display:block; width:100%; height:100%; cursor:grab; touch-action:none; outline:none; }
.boat-stage :deep(canvas:active) { cursor:grabbing; }
.boat-stage :deep(canvas:focus-visible) { outline:1px solid #d1b87a; outline-offset:-5px; }
.boat-stage__fallback { position:absolute; inset:0; display:grid; place-content:center; gap:1rem; text-align:center; padding:2rem; color:#e3d6b9; background:radial-gradient(ellipse,#25343b,#0a141c); }
.boat-stage__fallback p { max-width:26rem; line-height:1.8; }
.boat-stage__fallback div { display:flex; flex-wrap:wrap; gap:.6rem; justify-content:center; }
.boat-stage__fallback button { border:1px solid #9e885457; border-radius:2rem; background:#11202c; color:#e3d6b9; padding:.65rem 1rem; cursor:pointer; }
.boat-stage__fallback button:disabled { opacity:.45; cursor:default; }
</style>
