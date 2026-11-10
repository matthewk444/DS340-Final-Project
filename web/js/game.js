// The game itself: rounds, whiteboard, live predictions, final verdict.
import { createMap, heat, heatColor } from "./map.js";

const ROUNDS = 6;
const SECONDS = 20;
const EMOJI = {
  circle: "⭕", house: "🏠", "power outlet": "🔌", chair: "🪑", bread: "🍞", mailbox: "📮",
  snowman: "⛄", bus: "🚌", cake: "🍰", cup: "☕", "traffic light": "🚦", tree: "🌳", sun: "☀️",
  face: "🙂", cat: "🐱", star: "⭐", fish: "🐟", flower: "🌸", car: "🚗", door: "🚪",
};
const withArticle = (w) => (w === "bread" ? "some bread" : w === "sun" ? "the sun" : `a ${w}`);
const $ = (id) => document.getElementById(id);
const pct = (p) => `${Math.round(p * 100)}%`;

export async function createGame({ onHome }) {
  const meta = await (await fetch("/api/meta")).json();
  const categories = meta.categories;
  const regionNames = meta.regions.map((r) => r.name);
  const nRegions = regionNames.length;
  const alphas = meta.combine_alphas || [1, 0.85, 0.75, 0.7, 0.65, 0.6];

  const map = await createMap($("map"), $("map-pin"));
  drawBuddy($("buddy"));

  // ---------- elements ----------
  const board = $("board"), wrap = $("board-wrap"), ctx = board.getContext("2d");
  const btnDone = $("btn-done"), btnUndo = $("btn-undo"), btnClear = $("btn-clear");
  const bubble = $("bubble"), buddy = $("buddy");

  // region bars (fixed order so they don't jump around)
  $("region-bars").innerHTML = regionNames
    .map((n) => `<li><span>${n}</span><span class="bar"><i></i></span><span class="pct">–</span></li>`).join("");
  const barRows = [...$("region-bars").children];

  // ---------- state ----------
  let round = 0, strokes = [], current = null;
  const drawn = new Set();       // objects the player has already drawn this game
  let phase = "idle";            // idle | drawing | confirm | review
  let timerStart = null;
  let roundLogs = [];            // log region-probabilities of each finished doodle
  let gallery = [];              // {img, word, guess, hit}
  let lastPred = null, inflight = false, dirty = false, token = 0;

  // ---------- whiteboard ----------
  function sizeBoard() {
    const dpr = window.devicePixelRatio || 1;
    board.width = Math.round(wrap.clientWidth * dpr);
    board.height = Math.round(wrap.clientHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    redraw();
  }
  function redraw() {
    ctx.clearRect(0, 0, wrap.clientWidth, wrap.clientHeight);
    ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.lineWidth = 5; ctx.strokeStyle = "#4a382b"; ctx.fillStyle = "#4a382b";
    for (const s of current ? [...strokes, current] : strokes) {
      if (s.length === 1) { ctx.beginPath(); ctx.arc(s[0][0], s[0][1], 2.5, 0, 7); ctx.fill(); continue; }
      ctx.beginPath(); ctx.moveTo(s[0][0], s[0][1]);
      for (let i = 1; i < s.length; i++) ctx.lineTo(s[i][0], s[i][1]);
      ctx.stroke();
    }
  }
  new ResizeObserver(sizeBoard).observe(wrap);

  const point = (e) => {
    const r = board.getBoundingClientRect();
    return [Math.round((e.clientX - r.left) * 10) / 10, Math.round((e.clientY - r.top) * 10) / 10];
  };
  board.addEventListener("pointerdown", (e) => {
    if (phase !== "drawing") return;
    e.preventDefault();
    try { board.setPointerCapture(e.pointerId); } catch (err) { /* synthetic pointers cannot be captured */ }
    current = [point(e)];
    if (timerStart === null) timerStart = performance.now();
    $("board-hint").classList.add("gone");
    redraw();
  });
  board.addEventListener("pointermove", (e) => {
    if (!current) return;
    const batch = e.getCoalescedEvents ? e.getCoalescedEvents() : [];
    for (const ev of batch.length ? batch : [e]) {
      const p = point(ev), q = current[current.length - 1];
      if (Math.hypot(p[0] - q[0], p[1] - q[1]) >= 1.5) current.push(p);
    }
    redraw();
    requestPrediction();
  });
  const endStroke = () => {
    if (!current) return;
    strokes.push(current); current = null;
    redraw(); requestPrediction();
  };
  board.addEventListener("pointerup", endStroke);
  board.addEventListener("pointercancel", endStroke);

  btnUndo.onclick = () => { if (phase === "drawing" && strokes.length) { strokes.pop(); redraw(); requestPrediction(); } };
  btnClear.onclick = () => { if (phase === "drawing") { strokes = []; redraw(); requestPrediction(); } };

  // ---------- predictions ----------
  /** category = null lets the model use its own guess of what the doodle is. */
  async function fetchPrediction(category = null) {
    const all = current ? [...strokes, current] : strokes;
    if (!all.length) return null;
    const res = await fetch("/api/predict", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strokes: all, category }),
    });
    if (!res.ok) throw new Error(`predict failed: ${res.status}`);
    const out = await res.json();
    return out.category_probs ? out : null;
  }
  async function requestPrediction() {
    if (phase !== "drawing") return;
    if (inflight) { dirty = true; return; }
    inflight = true;
    const mine = token;
    try {
      const pred = await fetchPrediction();
      if (mine === token && phase === "drawing") { lastPred = pred; showPrediction(); }
    } catch (err) {
      say("Oops — I lost my connection to the model. Is the server running?");
    }
    inflight = false;
    if (dirty) { dirty = false; setTimeout(requestPrediction, 120); }
  }

  /** Combine the finished doodles (+ the live one) into one belief over regions. */
  function belief(extra) {
    const logs = extra ? [...roundLogs, extra.region_probs.map(Math.log)] : roundLogs;
    if (!logs.length) return null;
    const alpha = alphas[Math.min(logs.length, alphas.length) - 1];
    const sum = Array.from({ length: nRegions }, (_, r) => alpha * logs.reduce((s, l) => s + l[r], 0));
    const m = Math.max(...sum);
    const e = sum.map((v) => Math.exp(v - m));
    const z = e.reduce((a, b) => a + b, 0);
    return { probs: e.map((v) => v / z), count: logs.length };
  }

  function showRegions(b) {
    map.setBelief(b ? b.probs : null);
    if (!b) {
      $("region-name").textContent = "???";
      $("meter-fill").style.width = "0%";
      $("conf-num").textContent = "0%";
      $("conf-note").textContent = "draw to give me a clue";
      barRows.forEach((li) => { li.classList.remove("top"); li.querySelector("i").style.width = "0%"; li.querySelector(".pct").textContent = "–"; });
      return;
    }
    const top = b.probs.indexOf(Math.max(...b.probs));
    $("region-name").textContent = regionNames[top];
    $("meter-fill").style.width = pct(b.probs[top]);
    $("meter-fill").style.backgroundColor = heatColor(Math.max(0.5, heat(b.probs[top], nRegions)));
    $("conf-num").textContent = pct(b.probs[top]);
    $("conf-note").textContent = `based on ${b.count} doodle${b.count > 1 ? "s" : ""}`;
    barRows.forEach((li, r) => {
      li.classList.toggle("top", r === top);
      const bar = li.querySelector("i");
      bar.style.width = pct(b.probs[r]);
      bar.style.backgroundColor = heatColor(heat(b.probs[r], nRegions));
      li.querySelector(".pct").textContent = pct(b.probs[r]);
    });
  }

  function showCategories(pred, confirmed = -1) {
    const list = $("cat-list");
    if (!pred) { list.innerHTML = `<li class="empty">Nothing yet — start doodling!</li>`; return null; }
    const ranked = pred.category_probs.map((p, i) => [p, i]).sort((a, b) => b[0] - a[0]).slice(0, 3);
    list.innerHTML = ranked.map(([p, i]) =>
      `<li class="${i === confirmed ? "hit" : ""}"><span class="name">${EMOJI[categories[i]] || ""} ${categories[i]}</span>` +
      `<span>${pct(p)}</span><span class="bar"><i style="width:${pct(p)}"></i></span></li>`).join("");
    return ranked[0];
  }

  function showPrediction() {
    const top = showCategories(lastPred);
    showRegions(belief(lastPred));
    if (!top) { say("Draw anything from my list — I'm watching!"); return; }
    const [p, i] = top;
    const name = `${withArticle(categories[i])} ${EMOJI[categories[i]] || ""}`;
    if (p < 0.3) say("Hmm… I see squiggles. Keep going!");
    else if (p < 0.65) say(`Is it ${name}?`);
    else say(`Ooh, I think it's ${name}! Keep going, every stroke is a clue.`);
  }

  function say(text) { bubble.textContent = text; }
  function hop() { buddy.classList.remove("happy"); void buddy.offsetWidth; buddy.classList.add("happy"); }

  // ---------- rounds ----------
  function renderPips() {
    $("round-pips").innerHTML = Array.from({ length: ROUNDS }, (_, i) =>
      `<span class="pip ${i < round ? "done" : i === round ? "now" : ""}"></span>`).join("");
  }
  function renderKnown() {
    $("known-list").innerHTML = categories.map((c, i) =>
      `<span class="chip ${drawn.has(i) ? "used" : ""}">${EMOJI[c] || ""} ${c}</span>`).join("");
  }

  function startRound() {
    token++;
    strokes = []; current = null; lastPred = null; timerStart = null;
    phase = "drawing";
    $("prompt-label").textContent = `Round ${round + 1} of ${ROUNDS}`;
    $("prompt-word").textContent = round === 0 ? "Draw anything!" : "Draw another!";
    $("timer-num").textContent = SECONDS;
    $("timer").classList.remove("hurry");
    $("timer-fill").style.transform = "scaleX(1)";
    $("board-hint").classList.remove("gone");
    $("confirm").hidden = true;
    wrap.classList.remove("locked");
    btnDone.textContent = "Done ✓";
    btnDone.disabled = btnUndo.disabled = btnClear.disabled = false;
    renderPips(); renderKnown(); redraw();
    showCategories(null);
    showRegions(belief(null));
    say(round === 0 ? "Hi! I'm Pip. Pick anything from my list, don't tell me what — just draw, and I'll guess!"
                    : "Next one! Pick something different and surprise me.");
  }

  /** Time is up (or Done was pressed): Pip commits to a guess and asks if it is right. */
  async function endRound() {
    if (phase !== "drawing") return;
    endStroke();
    if (!strokes.length) {
      // nothing on the board: reset the clock instead of ending the round
      timerStart = null;
      $("timer-num").textContent = SECONDS; $("timer").classList.remove("hurry");
      $("timer-fill").style.transform = "scaleX(1)";
      say("Draw something first — even a quick scribble!");
      return;
    }
    phase = "confirm"; token++;
    wrap.classList.add("locked");
    btnDone.disabled = btnUndo.disabled = btnClear.disabled = true;
    try { lastPred = (await fetchPrediction()) || lastPred; } catch (err) { /* keep the last live prediction */ }
    if (!lastPred) { say("I couldn't reach the model — is the server running?"); phase = "drawing"; btnDone.disabled = false; return; }
    const guess = showCategories(lastPred)[1];
    say(`My guess: ${withArticle(categories[guess])} ${EMOJI[categories[guess]] || ""} — did I get it?`);

    // ask the player: right or wrong? (and if wrong, what was it?)
    const box = $("confirm"), pick = $("confirm-pick");
    $("confirm-q").textContent = `Is it ${withArticle(categories[guess])}?`;
    $("confirm-btns").hidden = false; pick.hidden = true; box.hidden = false;
    $("confirm-yes").onclick = () => finishRound(guess, guess);
    $("confirm-no").onclick = () => {
      $("confirm-q").textContent = "Oops! What was it?";
      $("confirm-btns").hidden = true; pick.hidden = false;
      pick.innerHTML = categories.map((c, i) => i === guess ? "" :
        `<button class="chip chip--btn" data-c="${i}">${EMOJI[c] || ""} ${c}</button>`).join("") +
        `<button class="chip chip--btn chip--other" data-c="-1">something else</button>`;
      pick.querySelectorAll("button").forEach((b) => { b.onclick = () => finishRound(guess, +b.dataset.c); });
    };
  }

  /** truth = index of what the player really drew, or -1 for something Pip doesn't know. */
  async function finishRound(guess, truth) {
    if (phase !== "confirm") return;
    phase = "review";
    $("confirm").hidden = true;
    const hit = guess === truth;
    const img = board.toDataURL("image/png");
    if (truth >= 0) {
      // the region head works best when it knows what the object is, so re-ask with the confirmed answer
      if (!hit) { try { lastPred = (await fetchPrediction(truth)) || lastPred; } catch (err) { /* keep previous */ } }
      roundLogs.push(lastPred.region_probs.map(Math.log));
      drawn.add(truth);
    }
    showCategories(lastPred, truth);
    showRegions(belief(null));
    gallery.push({ img, word: truth >= 0 ? categories[truth] : "something else", guess: categories[guess], hit });
    round++;
    const more = round < ROUNDS ? "Ready for the next one?" : "That's all six!";
    if (hit) { say(`Yes! ${withArticle(categories[guess])[0].toUpperCase() + withArticle(categories[guess]).slice(1)}! ${more}`); hop(); }
    else if (truth >= 0) say(`Ahh, ${withArticle(categories[truth])}! Thanks — that's still a clue about where you're from. ${more}`);
    else say(`I don't know that one yet, so I won't count it as a clue. ${more}`);
    renderPips(); renderKnown();
    btnDone.disabled = false;
    btnDone.textContent = round < ROUNDS ? "Next doodle →" : "See Pip's guess ★";
  }

  btnDone.onclick = () => {
    if (phase === "drawing") endRound();
    else if (phase === "review") { if (round < ROUNDS) startRound(); else showResult(); }
  };

  function tick(now) {
    if (phase === "drawing" && timerStart !== null) {
      const left = SECONDS - (now - timerStart) / 1000;
      $("timer-num").textContent = Math.max(0, Math.ceil(left));
      $("timer-fill").style.transform = `scaleX(${Math.max(0, left / SECONDS)})`;
      $("timer").classList.toggle("hurry", left <= 5);
      if (left <= 0) endRound();
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  // ---------- final verdict ----------
  function showResult() {
    const b = belief(null);
    const hits = gallery.filter((g) => g.hit).length;
    $("result-score").textContent = `Pip named ${hits} of your ${gallery.length} doodles`;
    if (!b) {
      $("result-region").textContent = "No idea!";
      $("result-conf-num").textContent = "0%"; $("result-meter").style.width = "0%";
      $("runner-ups").innerHTML = "<li>I didn't recognise enough doodles to guess a region</li>";
      $("gallery").innerHTML = ""; $("feedback").hidden = true;
      $("result-overlay").hidden = false;
      return;
    }
    $("feedback").hidden = false;
    const order = b.probs.map((p, r) => [p, r]).sort((x, y) => y[0] - x[0]);
    const [topP, top] = order[0];
    $("result-region").textContent = regionNames[top];
    $("result-conf-num").textContent = pct(topP);
    $("result-meter").style.width = "0%";
    requestAnimationFrame(() => { $("result-meter").style.width = pct(topP); });
    $("result-meter").style.backgroundColor = heatColor(Math.max(0.5, heat(topP, nRegions)));
    $("runner-ups").innerHTML = order.slice(1, 4).map(([p, r]) => `<li>${regionNames[r]} · ${pct(p)}</li>`).join("");
    $("gallery").innerHTML = gallery.map((g) =>
      `<figure><img src="${g.img}" alt="Your ${g.word} doodle"><figcaption class="${g.hit ? "ok" : "miss"}">` +
      `${g.hit ? `✓ ${g.word}` : `${g.word}<br>(I saw ${g.guess})`}</figcaption></figure>`).join("");

    // feedback: was the guess right?
    $("fb-msg").textContent = ""; $("fb-regions").hidden = true;
    $("fb-yes").disabled = $("fb-no").disabled = false;
    const record = (correct, msg) => {
      let stats = { plays: 0, correct: 0 };
      try { stats = JSON.parse(localStorage.getItem("doodle-atlas-stats")) || stats; } catch (err) { /* private mode */ }
      stats.plays++; if (correct) stats.correct++;
      try { localStorage.setItem("doodle-atlas-stats", JSON.stringify(stats)); } catch (err) { /* ignore */ }
      $("fb-yes").disabled = $("fb-no").disabled = true; $("fb-regions").hidden = true;
      $("fb-msg").textContent = `${msg} Pip has been right ${stats.correct} of ${stats.plays} time${stats.plays > 1 ? "s" : ""} on this computer.`;
    };
    $("fb-yes").onclick = () => record(true, "Yay! 🎉");
    $("fb-no").onclick = () => {
      $("fb-regions").hidden = false;
      $("fb-msg").textContent = "Where are you really from?";
      $("fb-regions").innerHTML = regionNames.map((n, r) => r === top ? "" : `<button class="px-btn px-btn--small" data-r="${r}">${n}</button>`).join("");
      $("fb-regions").querySelectorAll("button").forEach((btn) => {
        btn.onclick = () => {
          const r = +btn.dataset.r, rank = order.findIndex((o) => o[1] === r) + 1;
          record(false, `${regionNames[r]} — that was my #${rank} guess (${pct(b.probs[r])}). Thanks for teaching me!`);
        };
      });
    };
    $("result-overlay").hidden = false;
  }

  function start() {
    $("result-overlay").hidden = true;
    round = 0; roundLogs = []; gallery = []; drawn.clear();
    sizeBoard();
    startRound();
  }

  $("btn-again").onclick = start;
  const home = () => { phase = "idle"; token++; $("result-overlay").hidden = true; onHome(); };
  $("btn-home").onclick = home;
  $("btn-result-home").onclick = home;

  return { start, meta };
}

/** Pip: a tiny pixel-art globe with a face, drawn procedurally on a 16x16 canvas. */
function drawBuddy(canvas) {
  const g = canvas.getContext("2d");
  const land = ["................", "................", "......##........", "....####........", "...####.....#...",
    "...###.....###..", "..........####..", "...........##...", "................", "................",
    "....#...........", "...###.....#....", "....###...###...", ".....#.....#....", "................", "................"];
  for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
    const d = Math.hypot(x - 7.5, y - 7.5);
    if (d > 7.6) continue;
    g.fillStyle = d > 6.6 ? "#5a4232" : land[y][x] === "#" ? "#9ed36a" : (x + y < 10 ? "#a5e6f2" : "#7fd3e6");
    g.fillRect(x, y, 1, 1);
  }
  g.fillStyle = "#5a4232"; g.fillRect(5, 7, 1, 2); g.fillRect(10, 7, 1, 2);        // eyes
  g.fillRect(7, 10, 2, 1); g.fillRect(6, 9, 1, 1); g.fillRect(9, 9, 1, 1);          // smile
  g.fillStyle = "#ffa8bd"; g.fillRect(3, 9, 2, 1); g.fillRect(11, 9, 2, 1);         // cheeks
}
