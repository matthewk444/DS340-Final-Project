// Landing scene: a real-looking, slowly spinning Earth (three.js + NASA-derived textures).
import * as THREE from "../vendor/three.module.min.js";

const ATMOSPHERE_VERT = `
  varying vec3 vNormal;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;
const ATMOSPHERE_FRAG = `
  // outer halo (drawn on the back faces of a bigger sphere): brightest at the
  // planet's edge, fading to nothing at the halo's own edge
  varying vec3 vNormal;
  void main() {
    float glow = pow(clamp(-vNormal.z / 0.52, 0.0, 1.0), 2.4);
    gl_FragColor = vec4(0.30, 0.60, 1.0, 1.0) * glow * 1.5;
  }`;
const RIM_FRAG = `
  // thin blue haze over the lit edge of the planet itself
  varying vec3 vNormal;
  void main() {
    float rim = pow(1.0 - clamp(vNormal.z, 0.0, 1.0), 3.5);
    gl_FragColor = vec4(0.35, 0.65, 1.0, 1.0) * rim * 0.9;
  }`;

export function createLanding(canvas) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (err) {
    // no WebGL: the CSS gradient behind the canvas is the fallback
    return { zoomIn: () => Promise.resolve(), reset() {}, stop() {}, start() {} };
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
  const HOME = { camZ: 4.6, earthX: 1.25, earthY: -0.55 };
  camera.position.z = HOME.camZ;

  const tex = new THREE.TextureLoader();
  const load = (name) => {
    const t = tex.load(`assets/${name}`);
    t.anisotropy = 8;
    return t;
  };
  const colorMap = load("earth_atmos_2048.jpg");
  colorMap.colorSpace = THREE.SRGBColorSpace;

  const globe = new THREE.Group();
  globe.position.set(HOME.earthX, HOME.earthY, 0);
  globe.rotation.z = 0.41;                       // Earth's axial tilt
  scene.add(globe);

  const earth = new THREE.Mesh(
    new THREE.SphereGeometry(1.5, 96, 96),
    new THREE.MeshPhongMaterial({
      map: colorMap,
      specularMap: load("earth_specular_2048.jpg"),
      normalMap: load("earth_normal_2048.jpg"),
      normalScale: new THREE.Vector2(0.8, 0.8),
      specular: new THREE.Color(0x35506e),
      shininess: 16,
    })
  );
  earth.rotation.y = 4.2;
  globe.add(earth);

  const clouds = new THREE.Mesh(
    new THREE.SphereGeometry(1.52, 64, 64),
    new THREE.MeshLambertMaterial({ map: load("earth_clouds_1024.png"), transparent: true, opacity: 0.85, depthWrite: false })
  );
  globe.add(clouds);

  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(1.5, 64, 64),
    new THREE.ShaderMaterial({
      vertexShader: ATMOSPHERE_VERT, fragmentShader: ATMOSPHERE_FRAG,
      blending: THREE.AdditiveBlending, side: THREE.BackSide, transparent: true, depthWrite: false,
    })
  );
  atmosphere.scale.setScalar(1.17);
  atmosphere.position.copy(globe.position);
  scene.add(atmosphere);
  const rim = new THREE.Mesh(
    new THREE.SphereGeometry(1.53, 64, 64),
    new THREE.ShaderMaterial({
      vertexShader: ATMOSPHERE_VERT, fragmentShader: RIM_FRAG,
      blending: THREE.AdditiveBlending, transparent: true, depthWrite: false,
    })
  );
  globe.add(rim);

  // sunlight from the upper left, a faint blue fill so the night side is not pure black
  const sun = new THREE.DirectionalLight(0xffffff, 3.0);
  sun.position.set(-4, 2.2, 3.5);
  scene.add(sun, new THREE.AmbientLight(0x4a6aa8, 0.28));

  // stars
  const starCount = 1800;
  const pos = new Float32Array(starCount * 3);
  for (let i = 0; i < starCount; i++) {
    const r = 30 + Math.random() * 30, th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
    pos.set([r * Math.sin(ph) * Math.cos(th), r * Math.sin(ph) * Math.sin(th), -Math.abs(r * Math.cos(ph)) - 4], i * 3);
  }
  const starGeo = new THREE.BufferGeometry();
  starGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xe8f0ff, size: 0.11, sizeAttenuation: true, transparent: true, opacity: 0.9 }));
  scene.add(stars);

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // on narrow screens, centre the planet under the text instead of beside it
    const narrow = w / h < 1.05;
    HOME.earthX = narrow ? 0 : 1.25;
    HOME.earthY = narrow ? -1.9 : -0.55;
    if (!zoom) { globe.position.set(HOME.earthX, HOME.earthY, 0); atmosphere.position.copy(globe.position); }
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);

  const mouse = { x: 0, y: 0 };
  window.addEventListener("pointermove", (e) => {
    mouse.x = e.clientX / window.innerWidth - 0.5;
    mouse.y = e.clientY / window.innerHeight - 0.5;
  });

  let running = false, zoom = null, last = 0;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function frame(now) {
    if (!running) return;
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    const spin = reduceMotion ? 0 : dt;
    earth.rotation.y += spin * 0.045;
    clouds.rotation.y += spin * 0.06;
    stars.rotation.y += spin * 0.004;

    if (zoom) {
      // fly toward the planet: ease-in so it starts gently and rushes at the end
      const t = Math.min((now - zoom.start) / zoom.ms, 1);
      const e = t * t * t;
      globe.position.x = HOME.earthX * (1 - Math.min(t * 1.6, 1));
      globe.position.y = HOME.earthY * (1 - Math.min(t * 1.6, 1));
      atmosphere.position.copy(globe.position);
      camera.position.z = HOME.camZ - (HOME.camZ - 1.75) * e;
      earth.rotation.y += dt * 0.5 * t;
      if (t >= 1) { const done = zoom.resolve; zoom = null; done(); }
    } else {
      camera.position.x += (mouse.x * 0.25 - camera.position.x) * 0.04;
      camera.position.y += (-mouse.y * 0.18 - camera.position.y) * 0.04;
    }
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }

  return {
    start() {
      if (running) return;
      running = true; last = performance.now();
      resize();
      requestAnimationFrame(frame);
    },
    stop() { running = false; },
    /** Fly into the planet; resolves when the camera is close enough to wipe. */
    zoomIn(ms = 1300) {
      if (!running || reduceMotion) return Promise.resolve();
      return new Promise((resolve) => { zoom = { start: performance.now(), ms, resolve }; });
    },
    reset() {
      zoom = null;
      camera.position.set(0, 0, HOME.camZ);
      globe.position.set(HOME.earthX, HOME.earthY, 0);
      atmosphere.position.copy(globe.position);
    },
  };
}
