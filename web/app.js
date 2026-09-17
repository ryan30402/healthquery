const form = document.querySelector("#search-form");
const question = document.querySelector("#question");
const submitButton = document.querySelector("#submit-button");
const status = document.querySelector("#status");
const section = document.querySelector("#results-section");
const results = document.querySelector("#results");
const predictedType = document.querySelector("#predicted-type");
const notice = document.querySelector("#archive-notice");

document.querySelector("#example-button").addEventListener("click", () => {
  question.value = "What causes asthma?";
  question.focus();
});

function element(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = question.value.trim();
  status.className = "";
  section.hidden = true;
  results.replaceChildren();
  if (!text) {
    status.textContent = "Please enter a medical information question.";
    question.focus();
    return;
  }
  submitButton.disabled = true;
  form.setAttribute("aria-busy", "true");
  status.textContent = "Searching archived sources…";
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({ question: text, top_k: 3 }),
    });
    if (!response.ok) {
      throw new Error(response.status === 422 ? "Enter a question containing 1 to 1,000 characters." : "The search could not be completed. Please try again.");
    }
    const data = await response.json();
    predictedType.textContent = data.predicted_type;
    notice.textContent = data.notice;
    for (const result of data.results) {
      const card = element("article", "", "source-card");
      const heading = element("h3", result.question);
      const type = element("p", `Source question type: ${result.question_type}`, "muted");
      const excerpt = element("p", `Archived excerpt: ${result.excerpt}`, "excerpt");
      const link = element("a", `Open source: ${result.source_url}`, "source-link");
      link.href = result.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      card.append(heading, type, excerpt, link);
      results.append(card);
    }
    section.hidden = false;
    status.textContent = data.results.length ? `Found ${data.results.length} related source candidates.` : "No matching source found. Try a more specific medical topic.";
  } catch (error) {
    status.className = "error";
    status.textContent = error instanceof TypeError ? "Cannot reach HealthQuery. Check that the local server is running." : error.message;
  } finally {
    submitButton.disabled = false;
    form.setAttribute("aria-busy", "false");
  }
});
