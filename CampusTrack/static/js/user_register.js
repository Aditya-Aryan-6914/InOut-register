(function () {
  "use strict";

  const step1 = document.getElementById("step1");
  const step2 = document.getElementById("step2");
  if (!step1 || !step2) return; // page not present

  const instituteSelect = document.getElementById("institute_select");
  const institutePasswordInput = document.getElementById("institute_password_input");
  const continueBtn = document.getElementById("continueBtn");
  const step1Error = document.getElementById("step1Error");

  const backToStep1Btn = document.getElementById("backToStep1");
  const step2InstituteLabel = document.getElementById("step2InstituteLabel");
  const instituteIdInput = document.getElementById("institute_id_input");
  const institutePasswordHidden = document.getElementById("institute_password_hidden");

  const dynamicFieldset = document.getElementById("dynamicFieldset");
  const dynamicFieldsetLegend = document.getElementById("dynamicFieldsetLegend");
  const dynamicFields = document.getElementById("dynamicFields");

  function showStep1Error(message) {
    step1Error.textContent = message;
    step1Error.style.display = "block";
  }
  function clearStep1Error() {
    step1Error.style.display = "none";
  }

  // ---------- build one input for a custom field, from its JSON definition ----------
  function buildFieldRow(field) {
    const wrap = document.createElement("div");
    wrap.className = "ct-field";

    const label = document.createElement("label");
    label.setAttribute("for", "field_" + field.id);
    label.textContent = field.label + (field.is_required ? "" : " ");
    if (!field.is_required) {
      const hint = document.createElement("span");
      hint.className = "ct-hint";
      hint.textContent = "optional";
      label.appendChild(hint);
    }
    wrap.appendChild(label);

    if (field.field_type === "dropdown") {
      const select = document.createElement("select");
      select.id = "field_" + field.id;
      select.name = "field_" + field.id;
      if (field.is_required) select.required = true;

      const blank = document.createElement("option");
      blank.value = "";
      blank.textContent = "Select…";
      select.appendChild(blank);

      (field.options || []).forEach(function (opt) {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = opt;
        select.appendChild(o);
      });
      wrap.appendChild(select);

    } else if (field.field_type === "checkbox") {
      const group = document.createElement("div");
      group.className = "ct-checkbox-group";
      (field.options || []).forEach(function (opt) {
        const optLabel = document.createElement("label");
        optLabel.className = "ct-checkbox-option";
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.name = "field_" + field.id;
        cb.value = opt;
        optLabel.appendChild(cb);
        optLabel.appendChild(document.createTextNode(opt));
        group.appendChild(optLabel);
      });
      wrap.appendChild(group);

    } else {
      const input = document.createElement("input");
      input.id = "field_" + field.id;
      input.name = "field_" + field.id;
      if (field.is_required) input.required = true;

      const typeMap = { file: "file", date: "date", number: "number", email: "email", phone: "tel" };
      input.type = typeMap[field.field_type] || "text";
      wrap.appendChild(input);
    }

    return wrap;
  }

  function renderDynamicFields(fields) {
    dynamicFields.innerHTML = "";
    if (!fields || fields.length === 0) {
      dynamicFieldset.hidden = true;
      return;
    }
    fields.forEach(function (field) {
      dynamicFields.appendChild(buildFieldRow(field));
    });
    dynamicFieldset.hidden = false;
  }

  // ---------- step 1 -> step 2 ----------
  continueBtn.addEventListener("click", function () {
    clearStep1Error();

    const instituteId = instituteSelect.value;
    const institutePassword = institutePasswordInput.value;

    if (!instituteId) {
      showStep1Error("Select your institute first.");
      return;
    }
    if (!institutePassword) {
      showStep1Error("Enter the institute password.");
      return;
    }

    continueBtn.disabled = true;
    continueBtn.textContent = "Checking…";

    fetch(window.location.pathname + "/verify-institute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ institute_id: instituteId, institute_password: institutePassword }),
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        continueBtn.disabled = false;
        continueBtn.textContent = "Continue";

        if (!result.ok) {
          showStep1Error(result.data.error || "Something went wrong. Please try again.");
          return;
        }

        instituteIdInput.value = result.data.institute_id;
        institutePasswordHidden.value = institutePassword;
        step2InstituteLabel.textContent = instituteSelect.options[instituteSelect.selectedIndex].textContent;

        if (dynamicFieldset) {
          dynamicFieldsetLegend.textContent = step2InstituteLabel.textContent + " also asks for";
          renderDynamicFields(result.data.fields);
        }

        step1.hidden = true;
        step2.hidden = false;
      })
      .catch(function () {
        continueBtn.disabled = false;
        continueBtn.textContent = "Continue";
        showStep1Error("Couldn't reach the server. Check your connection and try again.");
      });
  });

  // ---------- step 2 -> back to step 1 ----------
  if (backToStep1Btn) {
    backToStep1Btn.addEventListener("click", function () {
      step2.hidden = true;
      step1.hidden = false;
      instituteIdInput.value = "";
      institutePasswordHidden.value = "";
    });
  }
})();
