(function () {
  const progressBar = document.getElementById("exam-progress-bar");
  const progressText = document.getElementById("exam-progress-text");
  const questionInputs = Array.from(document.querySelectorAll("input[data-exam-question]"));

  if (!progressBar || !progressText || questionInputs.length === 0) {
    return;
  }

  const questionIds = Array.from(
    new Set(
      questionInputs.map((input) => input.getAttribute("data-exam-question")).filter(Boolean)
    )
  );

  function countAnsweredQuestions() {
    return questionIds.filter((questionId) => {
      return Boolean(
        document.querySelector(`input[data-exam-question="${questionId}"]:checked`)
      );
    }).length;
  }

  function renderProgress() {
    const total = questionIds.length;
    const answered = countAnsweredQuestions();
    const percentage = total > 0 ? Math.round((answered / total) * 100) : 0;

    progressBar.style.width = `${percentage}%`;
    progressBar.textContent = `${percentage}%`;
    progressText.textContent = `${answered} de ${total} preguntas respondidas.`;
  }

  questionInputs.forEach((input) => {
    input.addEventListener("change", renderProgress);
  });

  renderProgress();
})();
