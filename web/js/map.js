// Pixel world map. Every land cell belongs to one of the 9 regions; a region
// heats up (green -> yellow -> coral) and gets a pulsing halo as the model
// becomes more confident the player is from there.

const CELL = 8;                     // canvas pixels per map cell
const LAND = [[166, 219, 124], [152, 209, 112]];   // two greens so neighbours differ
const WARM = [255, 214, 92];
const HOT = [255, 122, 89];

const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
const rgb = (c) => `rgb(${c[0]},${c[1]},${c[2]})`;

/** Map a probability to 0..1 "heat": chance level (1/9) is cold, 60%+ is fully hot. */
export function heat(p, n = 9) {
  const base = 1 / n;
  return Math.max(0, Math.min(1, (p - base) / (0.6 - base)));
}
export function heatColor(h) {
  return rgb(h < 0.5 ? mix(LAND[0], WARM, h * 2) : mix(WARM, HOT, (h - 0.5) * 2));
}

export async function createMap(canvas, pin) {
  const data = await (await fetch("assets/worldmap.json")).json();
  const { width: W, height: H, rows } = data;
  const n = data.regions.length;
  canvas.width = W * CELL;
  canvas.height = H * CELL;
  const ctx = canvas.getContext("2d");

  // cells per region + a label anchor (the cell closest to the region's centre of mass)
  const cells = Array.from({ length: n }, () => []);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++)
      if (rows[y][x] !== ".") cells[+rows[y][x]].push([x, y]);
  const anchors = cells.map((list) => {
    // ignore cells that wrap around the date line when averaging
    const xs = list.map((c) => c[0]).sort((a, b) => a - b);
    const medianX = xs[xs.length >> 1];
    const near = list.filter((c) => Math.abs(c[0] - medianX) < W / 4);
    const cx = near.reduce((s, c) => s + c[0], 0) / near.length;
    const cy = near.reduce((s, c) => s + c[1], 0) / near.length;
    let best = near[0], bd = Infinity;
    for (const c of near) {
      const d = (c[0] - cx) ** 2 + (c[1] - cy) ** 2;
      if (d < bd) { bd = d; best = c; }
    }
    return best;
  });

  // pre-render one blurred halo sprite per region (cheap to composite every frame)
  const halos = cells.map((list) => {
    const c = document.createElement("canvas");
    c.width = canvas.width; c.height = canvas.height;
    const g = c.getContext("2d");
    g.shadowColor = "rgba(255, 226, 120, 1)";
    g.shadowBlur = 22;
    g.fillStyle = "rgba(255, 240, 170, 1)";
    for (const [x, y] of list) g.fillRect(x * CELL, y * CELL, CELL, CELL);
    return c;
  });

  let target = new Array(n).fill(0);     // heat we are animating toward
  const shown = new Array(n).fill(0);    // heat currently on screen
  let topRegion = -1;

  function draw(now) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const pulse = 0.82 + 0.18 * Math.sin(now / 320);
    for (let r = 0; r < n; r++) shown[r] += (target[r] - shown[r]) * 0.08;

    // halos first (under the land), brighter with confidence
    ctx.globalCompositeOperation = "lighter";
    for (let r = 0; r < n; r++) {
      if (shown[r] < 0.03) continue;
      ctx.globalAlpha = Math.min(1, shown[r] * 1.15) * pulse;
      ctx.drawImage(halos[r], 0, 0);
      if (shown[r] > 0.55) ctx.drawImage(halos[r], 0, 0);
    }
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;

    // land cells, with a 1px gap so it reads as pixel art
    for (let r = 0; r < n; r++) {
      const h = shown[r];
      const hot = h < 0.5 ? mix(LAND[0], WARM, h * 2) : mix(WARM, HOT, (h - 0.5) * 2);
      const hotAlt = h < 0.5 ? mix(LAND[1], WARM, h * 2) : hot;
      for (const [x, y] of cells[r]) {
        ctx.fillStyle = rgb((x + y) % 2 ? hot : hotAlt);
        ctx.fillRect(x * CELL, y * CELL, CELL - 1, CELL - 1);
      }
      if (h > 0.08) {                  // sparkle highlight on the top-left of each cell
        ctx.fillStyle = `rgba(255,255,255,${0.35 * h * pulse})`;
        for (const [x, y] of cells[r]) ctx.fillRect(x * CELL, y * CELL, 3, 3);
      }
    }
    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);

  return {
    regions: data.regions,
    /** probs: array of 9 probabilities, or null to cool everything down. */
    setBelief(probs) {
      if (!probs) { target = new Array(n).fill(0); topRegion = -1; pin.hidden = true; return; }
      target = probs.map((p) => heat(p, n));
      const top = probs.indexOf(Math.max(...probs));
      if (target[top] > 0.12) {
        const [ax, ay] = anchors[top];
        pin.style.left = `${((ax + 0.5) / W) * 100}%`;
        pin.style.top = `${((ay + 0.2) / H) * 100}%`;
        pin.hidden = false;
        topRegion = top;
      } else {
        pin.hidden = true; topRegion = -1;
      }
    },
  };
}
