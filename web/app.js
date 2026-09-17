const $ = (selector) => document.querySelector(selector);
const form = $("#search-form");
const question = $("#question");
const status = $("#status");
const dialog = $("#source-dialog");
let activeSearch = null;
let activeDetail = null;
let recentQueries = [];

function element(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}

function updateCount() {
  $("#character-count").textContent = `${question.value.length.toLocaleString("en-US")} / 1,000`;
}

function fillQuestion(text) {
  question.value = text;
  updateCount();
  question.focus();
}

function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function safeSourceLink(node, url) {
  const parsed = new URL(url);
  if (!["https:", "http:"].includes(parsed.protocol)) throw new Error("This source URL cannot be opened.");
  node.href = parsed.href;
  node.target = "_blank";
  node.rel = "noopener noreferrer";
  return parsed.hostname.replace(/^www\./, "");
}

function requestState() {
  const state = { controller: new AbortController(), cancelled: false, timedOut: false };
  state.timer = setTimeout(() => {
    state.timedOut = true;
    state.controller.abort();
  }, 15000);
  return state;
}

async function readResponse(response) {
  if (response.ok) return response.json();
  let message = "The request could not be completed. Please try again.";
  if (response.status === 422) message = "Enter a question of 1 to 1,000 characters and choose 3 or 5 sources.";
  if (response.status === 413) message = "This request is too large. Shorten your question and try again.";
  if (response.status === 404) message = "This archived record is no longer available in the current index. Run the search again.";
  if (response.status === 503) message = "The source collection is temporarily unavailable. Please try again shortly.";
  if (response.status === 429) {
    const retry = response.headers.get("Retry-After");
    const seconds = retry === null ? NaN : (/^\d+$/.test(retry) ? Number(retry) : Math.ceil((Date.parse(retry) - Date.now()) / 1000));
    message = Number.isFinite(seconds) ? `Too many requests. Wait ${Math.max(1, seconds)} seconds before trying again.` : "Too many requests. Please wait a moment before trying again.";
  }
  const requestId = response.headers.get("X-Request-ID");
  if (requestId && response.status >= 500) message += ` Support reference: ${requestId}.`;
  throw new Error(message);
}

function failureMessage(error, state) {
  if (state.cancelled) return "Search cancelled. Your question is ready to edit or try again.";
  if (state.timedOut) return "The request took longer than 15 seconds. Please try again.";
  if (error instanceof TypeError) return "Cannot reach HealthQuery. Check your connection and that the server is running.";
  return error.message || "Something went wrong. Please try again.";
}

function rememberQuery(text) {
  recentQueries = [text, ...recentQueries.filter((item) => item !== text)].slice(0, 5);
  renderHistory();
}

function renderHistory() {
  $("#recent-queries").replaceChildren();
  $("#recent-empty").hidden = recentQueries.length > 0;
  $("#clear-history").hidden = recentQueries.length === 0;
  recentQueries.forEach((text) => {
    const item = element("li", "");
    const button = element("button", text);
    button.type = "button";
    button.addEventListener("click", () => fillQuestion(text));
    item.append(button);
    $("#recent-queries").append(item);
  });
}

async function openArchived(result) {
  if (activeDetail) activeDetail.controller.abort();
  const state = requestState();
  activeDetail = state;
  $("#dialog-title").textContent = result.question;
  $("#dialog-content").textContent = "Loading archived text…";
  $("#dialog-content").setAttribute("aria-busy", "true");
  $("#dialog-source").hidden = true;
  $("#dialog-truncation").hidden = true;
  if (!dialog.open) dialog.showModal();
  try {
    if (!/^[a-f0-9]{64}$/.test(result.source_id)) throw new Error("This record does not have an archived-text identifier. Run the search again.");
    const response = await fetch(`/api/sources/${result.source_id}`, { cache: "no-store", signal: state.controller.signal });
    const data = await readResponse(response);
    if (activeDetail !== state || !dialog.open) return;
    $("#dialog-content").textContent = data.answer;
    $("#dialog-title").textContent = data.question;
    safeSourceLink($("#dialog-source"), data.source_url);
    $("#dialog-source").hidden = false;
    $("#dialog-truncation").hidden = !data.answer_truncated;
  } catch (error) {
    if (activeDetail === state && dialog.open) $("#dialog-content").textContent = failureMessage(error, state);
  } finally {
    clearTimeout(state.timer);
    if (activeDetail === state) $("#dialog-content").setAttribute("aria-busy", "false");
  }
}

async function copyCitation(result, feedback) {
  const citation = `${result.question} Archived MedQuAD record. Original source: ${result.source_url} (current page not verified).`;
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(citation);
    feedback.textContent = "Citation copied.";
  } catch {
    feedback.textContent = `Clipboard access is unavailable. Select and copy this citation: ${citation}`;
  }
  feedback.hidden = false;
}

function sourceCard(result, position) {
  const card = element("article", "", "source-card");
  const meta = element("div", "", "source-meta");
  const link = element("a", "Open original source ↗", "source-link");
  const hostname = safeSourceLink(link, result.source_url);
  meta.append(element("span", String(position + 1).padStart(2, "0"), "source-number"), element("span", hostname), element("span", result.question_type, "source-type"));
  const heading = element("h3", result.question);
  const excerpt = element("p", "", "excerpt");
  excerpt.append(element("span", "Archived excerpt", "excerpt-label"), document.createTextNode(result.excerpt));
  const actions = element("div", "", "source-actions");
  const archived = element("button", "Read archived text", "text-button archive-button");
  archived.type = "button";
  archived.addEventListener("click", () => openArchived(result));
  const copy = element("button", "Copy citation", "text-button copy-button");
  copy.type = "button";
  const feedback = element("p", "", "citation-status");
  feedback.setAttribute("role", "status");
  feedback.hidden = true;
  copy.addEventListener("click", () => copyCitation(result, feedback));
  actions.append(link, archived, copy);
  card.append(meta, heading, excerpt, actions, feedback);
  return card;
}

function renderResults(data) {
  $("#results").replaceChildren(...data.results.map(sourceCard));
  $("#predicted-type").textContent = data.predicted_type;
  $("#archive-notice").textContent = data.notice;
  $("#searched-question").textContent = data.question;
  const elapsed = Number.isFinite(data.elapsed_ms) ? ` · ${Math.round(data.elapsed_ms)} ms server time` : "";
  $("#result-summary").textContent = `${data.results.length} sources${elapsed}`;
  $("#results-section").hidden = false;
  $("#welcome-panel").hidden = true;
  $("#empty-results").hidden = data.results.length > 0;
  setStatus(data.results.length ? `Found ${data.results.length} related source candidates. Review each source for relevance.` : "Search complete. No matching source found.");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (activeSearch) return;
  const text = question.value.trim();
  if (!text || text.length > 1000) {
    setStatus("Please enter a medical information question of 1 to 1,000 characters.", true);
    question.focus();
    return;
  }
  const state = requestState();
  activeSearch = state;
  $("#submit-button").disabled = true;
  $("#submit-label").textContent = "Searching…";
  $("#cancel-button").hidden = false;
  form.setAttribute("aria-busy", "true");
  $("#results-section").hidden = true;
  setStatus("Searching the archived collection…");
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: state.controller.signal,
      body: JSON.stringify({ question: text, top_k: Number($("#top-k").value) }),
    });
    const data = await readResponse(response);
    if (state.cancelled || state.timedOut) return;
    renderResults(data);
    rememberQuery(text);
  } catch (error) {
    setStatus(failureMessage(error, state), !state.cancelled);
  } finally {
    clearTimeout(state.timer);
    activeSearch = null;
    $("#submit-button").disabled = false;
    $("#submit-label").textContent = "Find sources";
    $("#cancel-button").hidden = true;
    form.setAttribute("aria-busy", "false");
  }
});

document.querySelectorAll(".nav-link").forEach((link) => link.addEventListener("click", () => {
  document.querySelectorAll(".nav-link").forEach((item) => item.classList.toggle("active", item === link));
}));
question.addEventListener("input", updateCount);
question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    form.requestSubmit();
  }
});
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => fillQuestion(button.dataset.example)));
$("#cancel-button").addEventListener("click", () => {
  if (!activeSearch) return;
  activeSearch.cancelled = true;
  activeSearch.controller.abort();
});
$("#clear-history").addEventListener("click", () => {
  recentQueries = [];
  renderHistory();
  setStatus("Recent questions cleared from this page.");
});
dialog.addEventListener("close", () => {
  if (activeDetail) activeDetail.controller.abort();
  activeDetail = null;
});

async function loadCollection() {
  const state = requestState();
  const fields = { indexed_records: "#record-count", source_urls: "#source-count", question_types: "#type-count" };
  try {
    const response = await fetch("/api/info", { cache: "no-store", signal: state.controller.signal });
    const data = await readResponse(response);
    Object.entries(fields).forEach(([key, selector]) => {
      $(selector).textContent = Number.isInteger(data[key]) && data[key] >= 0 ? data[key].toLocaleString("en-US") : "Unavailable";
    });
  } catch {
    Object.values(fields).forEach((selector) => { $(selector).textContent = "Unavailable"; });
  } finally {
    clearTimeout(state.timer);
  }
}

updateCount();
loadCollection();
