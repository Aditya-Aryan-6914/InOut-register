(function () {
  "use strict";

  const OPTION_TYPES = new Set(["dropdown", "checkbox"]);

  const canvas = document.getElementById("fieldCanvas");
  const emptyState = document.getElementById("canvasEmptyState");
  const cardTemplate = document.getElementById("fieldCardTemplate");
  const saveBtn = document.getElementById("saveFieldsBtn");
  const errorBanner = document.getElementById("saveErrorBanner");

  if (!canvas || !cardTemplate) return; // page not present; nothing to wire up

  // ---------- helpers ----------

  function toggleEmptyState() {       
    const hasCards = canvas.querySelectorAll(".ct-field-card").length > 0;
    if (emptyState) emptyState.hidden = hasCards;         
  }

  function addOptionTag(tagsContainer, value) {
    const tag = document.createElement("span");
    tag.className = "ct-option-tag"; 
    tag.textContent = value;
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "ct-option-remove";
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", function () {
      tag.remove();
    });
    tag.appendChild(removeBtn);
    tagsContainer.appendChild(tag);
  }

  function wireOptionsInput(card) {
    const input = card.querySelector(".ct-options-input");
    const tagsContainer = card.querySelector(".ct-options-tags");
    if (!input || !tagsContainer) return;

    input.addEventListener("keydown", function (evt) {
      if (evt.key === "Enter") {
        evt.preventDefault();
        const value = input.value.trim();
        if (value) {
          addOptionTag(tagsContainer, value);
          input.value = "";
        }
      }
    });
  }

  function createFieldCard(data) {
    const fragment = cardTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".ct-field-card");

    card.dataset.id = data.id || "";
    card.dataset.type = data.type;

    card.querySelector(".ct-field-label").value = data.label || "";
    card.querySelector(".ct-field-type-badge").textContent = data.type;
    card.querySelector(".ct-field-required-cb").checked = data.required !== false;

    const optionsEditor = card.querySelector(".ct-options-editor");
    if (OPTION_TYPES.has(data.type)) {
      optionsEditor.hidden = false;
      const tagsContainer = optionsEditor.querySelector(".ct-options-tags");
      (data.options || []).forEach(function (opt) {
        addOptionTag(tagsContainer, opt);
      });
    }

    wireOptionsInput(card);
    return card;
  }

  // ---------- drag-and-drop wiring ----------

  const bankEls = [document.getElementById("fieldBank"), document.getElementById("fieldBankGeneric")];

  bankEls.forEach(function (bankEl) {
    if (!bankEl) return;
    new Sortable(bankEl, {
      group: { name: "fields", pull: "clone", put: false },
      sort: false,
      animation: 150,
    });
  });

  new Sortable(canvas, {
    group: { name: "fields", pull: false, put: true },
    animation: 150,
    handle: ".ct-drag-handle",
    onAdd: function (evt) {
      const droppedChip = evt.item;
      const label = droppedChip.dataset.label || "";
      const type = droppedChip.dataset.type || "text";
      const presetOptions = droppedChip.dataset.options
        ? droppedChip.dataset.options.split(",").map(function (s) { return s.trim(); })
        : [];

      const newCard = createFieldCard({
        id: null,
        label: label,
        type: type,
        required: true,
        options: presetOptions,
      });

      canvas.insertBefore(newCard, droppedChip);
      droppedChip.remove();

      const labelInput = newCard.querySelector(".ct-field-label");
      if (labelInput) {
        labelInput.focus();
        if (!label) labelInput.select();
      }

      toggleEmptyState();
    },
  });

  // ---------- delete a field ----------

  canvas.addEventListener("click", function (evt) {
    const deleteBtn = evt.target.closest(".ct-field-delete");
    if (!deleteBtn) return;

    const card = deleteBtn.closest(".ct-field-card");
    const responseCount = parseInt(deleteBtn.dataset.responseCount || "0", 10);

    if (responseCount > 0) {
      const label = card.querySelector(".ct-field-label").value || "This field";
      const confirmed = window.confirm(
        label + " already has " + responseCount + " response(s) recorded. " +
        "Removing it will permanently delete that data too. Continue?"
      );
      if (!confirmed) return;
    }

    card.remove();
    toggleEmptyState();
  });

  // ---------- save ----------

  function collectFieldPayload() {
    const cards = canvas.querySelectorAll(".ct-field-card");
    const fields = [];

    cards.forEach(function (card) {
      const label = card.querySelector(".ct-field-label").value.trim();
      const type = card.dataset.type;
      const required = card.querySelector(".ct-field-required-cb").checked;

      let options = null;
      if (OPTION_TYPES.has(type)) {
        options = Array.from(card.querySelectorAll(".ct-option-tag"))
          .map(function (tag) { return tag.firstChild ? tag.firstChild.textContent : ""; })
          .map(function (s) { return s.trim(); })
          .filter(Boolean);
      }

      fields.push({
        id: card.dataset.id || null,
        label: label,
        field_type: type,
        is_required: required,
        options: options,
      });
    });

    return fields;
  }

  function showError(message) {
    if (!errorBanner) { window.alert(message); return; }
    errorBanner.textContent = message;
    errorBanner.style.display = "block";
    errorBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function clearError() {
    if (errorBanner) errorBanner.style.display = "none";
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", function () {
      clearError();

      const fields = collectFieldPayload();

      // Lightweight client-side pass so obvious mistakes don't need a
      // round trip — the server re-validates everything regardless,
      // since client-side checks can always be bypassed.
      for (const f of fields) {
        if (!f.label) {
          showError("Every field needs a label before you can save.");
          return;
        }
        if (OPTION_TYPES.has(f.field_type) && (!f.options || f.options.length === 0)) {
          showError("'" + f.label + "' needs at least one option.");
          return;
        }
      }

      saveBtn.disabled = true;
      saveBtn.textContent = "Saving…";

      fetch(window.location.pathname + "/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fields: fields }),
      })
        .then(function (res) {
          return res.json().then(function (data) { return { ok: res.ok, data: data }; });
        })
        .then(function (result) {
          if (result.ok && result.data.success) {
            window.location.reload();
          } else {
            showError(result.data.error || "Something went wrong. Please try again.");
            saveBtn.disabled = false;
            saveBtn.textContent = "Save changes";
          }
        })
        .catch(function () {
          showError("Couldn't reach the server. Check your connection and try again.");
          saveBtn.disabled = false;
          saveBtn.textContent = "Save changes";
        });
    });
  }

  // ---------- init ----------
  canvas.querySelectorAll(".ct-field-card").forEach(wireOptionsInput);
  toggleEmptyState();
})();
