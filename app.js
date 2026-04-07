const manifestUrl = "./assets/manifest.json";

const state = {
  deck: [],
  cursor: 0,
  current: null,
  flipped: false,
};

const card = document.querySelector("#card");
const cardButton = document.querySelector("#cardButton");
const frontImage = document.querySelector("#frontImage");
const nameCropImage = document.querySelector("#nameCropImage");
const progressText = document.querySelector("#progressText");
const statusText = document.querySelector("#statusText");
const flipButton = document.querySelector("#flipButton");
const nextButton = document.querySelector("#nextButton");
const timerText = document.querySelector("#timerText");
const timerButton = document.querySelector("#timerButton");
const stopTimerButton = document.querySelector("#stopTimerButton");

const timerState = {
  startedAt: null,
  intervalId: null,
  running: false,
  elapsedMs: 0,
};

function formatElapsed(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function renderTimer() {
  const elapsed = timerState.running && timerState.startedAt
    ? timerState.elapsedMs + (Date.now() - timerState.startedAt)
    : timerState.elapsedMs;
  timerText.textContent = formatElapsed(elapsed);
  timerButton.textContent = timerState.running ? "计时中" : "开始计时";
  timerButton.classList.toggle("is-running", timerState.running);
  timerButton.disabled = timerState.running;
  stopTimerButton.disabled = !timerState.running;
}

function startTimer() {
  if (timerState.running) return;
  timerState.startedAt = Date.now();
  timerState.running = true;
  renderTimer();
  if (timerState.intervalId) {
    window.clearInterval(timerState.intervalId);
  }
  timerState.intervalId = window.setInterval(renderTimer, 1000);
}

function stopTimer() {
  if (!timerState.running) return;
  timerState.elapsedMs += Date.now() - timerState.startedAt;
  timerState.startedAt = null;
  timerState.running = false;
  if (timerState.intervalId) {
    window.clearInterval(timerState.intervalId);
    timerState.intervalId = null;
  }
  renderTimer();
}

function shuffle(items) {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function updateControls() {
  flipButton.disabled = !state.current || state.flipped;
  nextButton.disabled = !state.current;
  flipButton.textContent = state.flipped ? "已翻开" : "翻开答案";
  nextButton.textContent = state.flipped ? "下一张" : "跳过这张";
}

function renderCard() {
  if (!state.current) {
    statusText.textContent = "没有可用图片。";
    progressText.textContent = "0 / 0";
    frontImage.removeAttribute("src");
    nameCropImage.removeAttribute("src");
    updateControls();
    return;
  }

  const { assetPath } = state.current;
  frontImage.src = assetPath;
  nameCropImage.src = assetPath;
  card.classList.toggle("is-flipped", state.flipped);

  const currentIndex = Math.min(state.cursor, state.deck.length);
  progressText.textContent = `${currentIndex} / ${state.deck.length}`;
  statusText.textContent = state.flipped
    ? "答案已揭晓，再点一下换下一张。"
    : "城市名已遮住，先猜一猜再翻卡。";

  updateControls();
}

function drawNextCard() {
  if (!state.deck.length) return;

  if (state.cursor >= state.deck.length) {
    state.deck = shuffle(state.deck);
    state.cursor = 0;
  }

  state.current = state.deck[state.cursor];
  state.cursor += 1;
  state.flipped = false;
  renderCard();
}

function handleCardAction() {
  if (!state.current) return;

  if (!state.flipped) {
    state.flipped = true;
    renderCard();
    return;
  }

  drawNextCard();
}

async function init() {
  try {
    const response = await fetch(manifestUrl);
    const manifest = await response.json();
    const available = manifest.items
      .filter((item) => item.optimized && item.file)
      .map((item) => ({
        ...item,
        assetPath: `./assets/${item.file}`,
      }));

    state.deck = shuffle(available);
    drawNextCard();
  } catch (error) {
    statusText.textContent = "图片清单读取失败，请检查 assets 目录。";
    progressText.textContent = "读取失败";
    console.error(error);
    updateControls();
  }
}

cardButton.addEventListener("click", handleCardAction);
flipButton.addEventListener("click", () => {
  if (!state.flipped) {
    handleCardAction();
  }
});
nextButton.addEventListener("click", drawNextCard);
timerButton.addEventListener("click", startTimer);
stopTimerButton.addEventListener("click", stopTimer);

window.addEventListener("keydown", (event) => {
  if (event.code === "Space" || event.code === "Enter") {
    event.preventDefault();
    handleCardAction();
  }
});

init();
renderTimer();
