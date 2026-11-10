// Wires the two scenes together: space landing page -> (zoom + wipe) -> pixel game.
import { createLanding } from "./landing.js";
import { createGame } from "./game.js";

const $ = (id) => document.getElementById(id);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const landingEl = $("landing"), gameEl = $("game"), wipe = $("wipe");

const landing = createLanding($("earth-canvas"));
landing.start();

let game = null, busy = false;

async function goToGame() {
  if (busy) return;
  busy = true;
  document.body.classList.add("leaving");                 // text fades out
  const ready = game ? Promise.resolve(game) : createGame({ onHome: goHome });
  await landing.zoomIn(1300);                              // fly into the planet
  wipe.classList.add("grow");                              // cream circle swallows the screen
  await wait(900);
  try {
    game = await ready;
  } catch (err) {
    console.error(err);
    wipe.className = "";
    document.body.classList.remove("leaving");
    landing.reset();
    alertBanner("Couldn't reach the game server. Start it with: python -m uvicorn server.app:app");
    busy = false;
    return;
  }
  landing.stop();
  landingEl.hidden = true;
  gameEl.hidden = false;
  gameEl.classList.add("enter");
  document.body.classList.replace("on-landing", "on-game");
  document.body.classList.remove("leaving");
  game.start();
  fillHowNote(game.meta);
  wipe.classList.add("fade");                              // reveal the game underneath
  await wait(550);
  wipe.className = "";
  gameEl.classList.remove("enter");
  busy = false;
}

async function goHome() {
  if (busy) return;
  busy = true;
  wipe.classList.add("grow");
  await wait(900);
  gameEl.hidden = true;
  landingEl.hidden = false;
  document.body.classList.replace("on-game", "on-landing");
  landing.reset();
  landing.start();
  wipe.classList.add("fade");
  await wait(550);
  wipe.className = "";
  busy = false;
}

function alertBanner(text) {
  const el = document.createElement("div");
  el.textContent = text;
  el.style.cssText = "position:fixed;left:50%;bottom:90px;transform:translateX(-50%);z-index:20;background:#ff7a59;color:#fff;" +
    "padding:12px 18px;border-radius:12px;font:600 14px 'Space Grotesk',sans-serif;max-width:90vw";
  document.body.append(el);
  setTimeout(() => el.remove(), 7000);
}

// show the measured accuracy in the how-to-play note, if the model has been evaluated
function fillHowNote(meta) {
  if (!meta || !meta.accuracy_six_doodles) return;
  const chance = Math.round(100 / meta.regions.length);
  $("how-note").textContent =
    `Guessing a region from a doodle is hard — small habits (which way you draw a circle, what your mailbox looks like) ` +
    `are the only clues. On test doodles the model picks the right region about ${Math.round(meta.accuracy_one_doodle * 100)}% of the time ` +
    `from one drawing and ${Math.round(meta.accuracy_six_doodles * 100)}% after six (random guessing: ${chance}%). ` +
    `Treat it as a fun experiment, not a passport check.`;
}
fetch("/api/meta").then((r) => r.json()).then(fillHowNote).catch(() => {});

// how-to-play modal
const how = $("how-overlay");
const openHow = () => { how.hidden = false; $("how-close").focus(); };
const closeHow = () => { how.hidden = true; };
$("btn-how").onclick = openHow;
$("btn-how-game").onclick = openHow;
$("how-close").onclick = closeHow;
how.addEventListener("click", (e) => { if (e.target === how) closeHow(); });
window.addEventListener("keydown", (e) => { if (e.key === "Escape") closeHow(); });

$("btn-play").onclick = goToGame;
