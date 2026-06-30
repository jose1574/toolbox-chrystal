(function () {
  const storageKey = "inventoryTransferGuideProgressV1";
  const state = {
    filter: "both",
    currentVisibleIndex: 0,
    completed: {},
  };

  const allWrappers = Array.from(document.querySelectorAll("[data-step-wrapper]"));
  const allCards = Array.from(document.querySelectorAll("[data-guide-step]"));
  const flowDots = Array.from(document.querySelectorAll("[data-flow-dot]"));

  const progressBar = document.getElementById("guide-progress-bar");
  const progressText = document.getElementById("guide-progress-text");
  const prevButton = document.getElementById("guide-prev");
  const nextButton = document.getElementById("guide-next");
  const resetButton = document.getElementById("guide-reset");
  const exportPdfButton = document.getElementById("guide-export-pdf");
  const exportPdfBaseUrl = exportPdfButton ? exportPdfButton.getAttribute("href") || "" : "";

  function loadState() {
    try {
      const rawState = window.localStorage.getItem(storageKey);
      if (!rawState) return;
      const parsed = JSON.parse(rawState);
      if (parsed && typeof parsed === "object") {
        state.completed = parsed.completed || {};
      }
    } catch (error) {
      console.warn("Could not load transfer guide state", error);
    }
  }

  function saveState() {
    try {
      window.localStorage.setItem(
        storageKey,
        JSON.stringify({
          completed: state.completed,
        })
      );
    } catch (error) {
      console.warn("Could not save transfer guide state", error);
    }
  }

  function visibleWrappers() {
    return allWrappers.filter((wrapper) => {
      const mode = (wrapper.getAttribute("data-mode") || "both").toLowerCase();
      if (state.filter === "both") return true;
      return mode === "both" || mode === state.filter;
    });
  }

  function normalizeCurrentVisibleIndex() {
    const visible = visibleWrappers();
    if (visible.length === 0) {
      state.currentVisibleIndex = 0;
      return;
    }

    if (state.currentVisibleIndex < 0) {
      state.currentVisibleIndex = 0;
    }

    if (state.currentVisibleIndex >= visible.length) {
      state.currentVisibleIndex = visible.length - 1;
    }
  }

  function updateFilterButtons() {
    const buttons = document.querySelectorAll("[data-guide-filter]");
    buttons.forEach((button) => {
      const value = button.getAttribute("data-guide-filter");
      const isActive = value === state.filter;
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function updateCardCompletionStyles() {
    allCards.forEach((card) => {
      const stepId = card.getAttribute("data-step-id") || "";
      const completeButton = card.querySelector("[data-complete-step]");
      const isCompleted = Boolean(state.completed[stepId]);

      card.classList.toggle("is-completed", isCompleted);

      if (!completeButton) return;
      completeButton.classList.toggle("btn-success", !isCompleted);
      completeButton.classList.toggle("btn-outline-success", isCompleted);
      completeButton.textContent = isCompleted ? "Completado" : "Marcar completado";
    });
  }

  function updateProgress() {
    const total = allCards.length;
    const completed = Object.keys(state.completed).length;
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

    if (progressBar) {
      progressBar.style.width = `${percentage}%`;
      progressBar.textContent = `${percentage}%`;
    }

    if (progressText) {
      progressText.textContent = `${completed} de ${total} pasos completados.`;
    }
  }

  function getCompletedStepIds() {
    return allCards
      .map((card) => card.getAttribute("data-step-id") || "")
      .filter((stepId) => Boolean(stepId) && Boolean(state.completed[stepId]));
  }

  function updateExportPdfLink() {
    if (!exportPdfButton || !exportPdfBaseUrl) return;

    const completedStepIds = getCompletedStepIds();
    if (completedStepIds.length === 0) {
      exportPdfButton.setAttribute("href", exportPdfBaseUrl);
      return;
    }

    const queryParams = new URLSearchParams({
      completed_steps: completedStepIds.join(","),
    });
    exportPdfButton.setAttribute("href", `${exportPdfBaseUrl}?${queryParams.toString()}`);
  }

  function updateFlowDots() {
    flowDots.forEach((dot) => {
      dot.classList.remove("is-active", "is-completed");
    });

    const visible = visibleWrappers();
    if (visible.length === 0) return;

    const currentCard = visible[state.currentVisibleIndex]?.querySelector("[data-guide-step]");
    if (!currentCard) return;

    const phase = (currentCard.getAttribute("data-phase") || "").toLowerCase();

    const phaseToDotIndex = {
      origin: 1,
      transit: 2,
      destination: 3,
    };

    const activeIndex = phaseToDotIndex[phase] ?? 0;

    flowDots.forEach((dot, index) => {
      if (index < activeIndex) dot.classList.add("is-completed");
      if (index === activeIndex) dot.classList.add("is-active");
    });
  }

  function updateVisibleCards() {
    const visible = visibleWrappers();

    allWrappers.forEach((wrapper) => {
      const shouldShow = visible.includes(wrapper);
      wrapper.classList.toggle("d-none", !shouldShow);
    });

    allCards.forEach((card) => {
      card.classList.remove("is-current");
    });

    normalizeCurrentVisibleIndex();

    const currentWrapper = visible[state.currentVisibleIndex];
    const currentCard = currentWrapper?.querySelector("[data-guide-step]");
    if (currentCard) {
      currentCard.classList.add("is-current");
      currentCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    const hasItems = visible.length > 0;
    if (prevButton) prevButton.disabled = !hasItems || state.currentVisibleIndex === 0;
    if (nextButton) nextButton.disabled = !hasItems || state.currentVisibleIndex >= visible.length - 1;

    updateFlowDots();
  }

  function setFilter(filter) {
    state.filter = filter;
    state.currentVisibleIndex = 0;
    updateFilterButtons();
    updateVisibleCards();
  }

  function toggleCompleteStep(stepId) {
    if (!stepId) return;

    if (state.completed[stepId]) {
      delete state.completed[stepId];
    } else {
      state.completed[stepId] = true;
    }

    saveState();
    updateCardCompletionStyles();
    updateProgress();
    updateExportPdfLink();
  }

  function resetProgress() {
    state.completed = {};
    saveState();
    updateCardCompletionStyles();
    updateProgress();
    updateExportPdfLink();
  }

  function attachEvents() {
    document.querySelectorAll("[data-guide-filter]").forEach((button) => {
      button.addEventListener("click", function () {
        const filter = this.getAttribute("data-guide-filter") || "both";
        setFilter(filter);
      });
    });

    document.querySelectorAll("[data-complete-step]").forEach((button) => {
      button.addEventListener("click", function () {
        const stepId = this.getAttribute("data-step-id") || "";
        toggleCompleteStep(stepId);
      });
    });

    if (prevButton) {
      prevButton.addEventListener("click", function () {
        state.currentVisibleIndex -= 1;
        normalizeCurrentVisibleIndex();
        updateVisibleCards();
      });
    }

    if (nextButton) {
      nextButton.addEventListener("click", function () {
        state.currentVisibleIndex += 1;
        normalizeCurrentVisibleIndex();
        updateVisibleCards();
      });
    }

    if (resetButton) {
      resetButton.addEventListener("click", function () {
        resetProgress();
      });
    }
  }

  function init() {
    loadState();
    attachEvents();
    updateCardCompletionStyles();
    updateProgress();
    updateExportPdfLink();
    setFilter("both");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
