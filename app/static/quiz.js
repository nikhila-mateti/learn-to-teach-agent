(() => {
  const root = document.getElementById("quiz-root");
  if (!root) return;

  const questions = JSON.parse(root.dataset.quiz || "[]");
  let index = 0;
  let score = 0;
  const missed = [];

  const progressEl = document.getElementById("quiz-progress");
  const questionEl = document.getElementById("quiz-question");
  const choicesEl = document.getElementById("quiz-choices");
  const feedbackEl = document.getElementById("quiz-feedback");
  const nextBtn = document.getElementById("quiz-next");
  const resultEl = document.getElementById("quiz-result");

  function renderQuestion() {
    const q = questions[index];
    progressEl.textContent = `Question ${index + 1} of ${questions.length}`;
    questionEl.textContent = q.question;
    feedbackEl.textContent = "";
    feedbackEl.className = "";
    nextBtn.classList.add("hidden");
    choicesEl.innerHTML = "";

    q.choices.forEach((choice, choiceIndex) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "quiz-choice";
      button.textContent = choice;
      button.addEventListener("click", () => onAnswer(choiceIndex, button));
      choicesEl.appendChild(button);
    });
  }

  function onAnswer(choiceIndex, button) {
    const q = questions[index];
    const buttons = [...choicesEl.querySelectorAll("button")];
    buttons.forEach((btn) => {
      btn.disabled = true;
    });

    const correct = choiceIndex === q.correct_index;
    if (correct) {
      score += 1;
      button.classList.add("is-correct");
      feedbackEl.className = "flash-success";
      feedbackEl.textContent = q.correct_explanation;
    } else {
      button.classList.add("is-incorrect");
      buttons[q.correct_index]?.classList.add("is-correct");
      feedbackEl.className = "flash-error";
      const incorrect = q.incorrect_explanations?.[choiceIndex] || "That choice is incorrect.";
      feedbackEl.textContent = `${incorrect} Correct: ${q.correct_explanation}`;
      missed.push(q.concept);
    }
    nextBtn.classList.remove("hidden");
  }

  nextBtn.addEventListener("click", () => {
    index += 1;
    if (index >= questions.length) {
      showResult();
    } else {
      renderQuestion();
    }
  });

  function showResult() {
    document.getElementById("quiz-active").classList.add("hidden");
    resultEl.classList.remove("hidden");
    const uniqueMissed = [...new Set(missed)];
    resultEl.innerHTML = `
      <h2>Score: ${score} / ${questions.length}</h2>
      <p class="muted">Concepts to revise:</p>
      <ul>${
        uniqueMissed.length
          ? uniqueMissed.map((c) => `<li>${c}</li>`).join("")
          : "<li>None — nice work.</li>"
      }</ul>
    `;
  }

  if (!questions.length) {
    root.innerHTML = "<p>No quiz questions available.</p>";
    return;
  }
  renderQuestion();
})();
