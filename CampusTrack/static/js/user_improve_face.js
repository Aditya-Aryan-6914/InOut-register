(function () {
  "use strict";

  const stepCapture = document.getElementById("faceStepCapture");
  const stepResult = document.getElementById("faceStepResult");
  if (!stepCapture || !stepResult) return; // page not present

  const faceStatus = document.getElementById("faceStatus");
  const faceVideo = document.getElementById("faceVideo");
  const faceCanvas = document.getElementById("faceCanvas");
  const facePreview = document.getElementById("facePreview");
  const captureBtn = document.getElementById("captureBtn");
  const retakeBtn = document.getElementById("retakeBtn");
  const submitBtn = document.getElementById("submitBtn");
  const captureAgainBtn = document.getElementById("captureAgainBtn");
  const resultIcon = document.getElementById("resultIcon");
  const resultTitle = document.getElementById("resultTitle");
  const resultMessage = document.getElementById("resultMessage");

  let faceStream = null;
  let capturedBlob = null;

  function startFaceCamera() {
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user" }, audio: false })
      .then(function (stream) {
        faceStream = stream;
        faceVideo.srcObject = stream;
      })
      .catch(function (err) {
        faceStatus.textContent = "Couldn't access the front camera: " + err.message;
      });
  }

  function stopFaceCamera() {
    if (faceStream) {
      faceStream.getTracks().forEach(function (track) { track.stop(); });
      faceStream = null;
    }
  }

  captureBtn.addEventListener("click", function () {
    const w = faceVideo.videoWidth || 320;
    const h = faceVideo.videoHeight || 320;
    faceCanvas.width = w;
    faceCanvas.height = h;
    const ctx = faceCanvas.getContext("2d");
    // Undo the mirrored preview so the saved image is right-reading,
    // matching how the registration photo was taken.
    ctx.translate(w, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(faceVideo, 0, 0, w, h);

    faceCanvas.toBlob(function (blob) {
      capturedBlob = blob;
      facePreview.src = URL.createObjectURL(blob);
      facePreview.hidden = false;
      faceVideo.hidden = true;
      stopFaceCamera();

      captureBtn.hidden = true;
      retakeBtn.hidden = false;
      submitBtn.hidden = false;
      faceStatus.textContent = "Looks good? Save it, or retake.";
    }, "image/jpeg", 0.9);
  });

  retakeBtn.addEventListener("click", function () {
    capturedBlob = null;
    facePreview.hidden = true;
    faceVideo.hidden = false;
    captureBtn.hidden = false;
    retakeBtn.hidden = true;
    submitBtn.hidden = true;
    faceStatus.textContent = "Center your face in frame, then capture.";
    startFaceCamera();
  });

  submitBtn.addEventListener("click", function () {
    if (!capturedBlob) return;

    submitBtn.disabled = true;
    submitBtn.textContent = "Saving…";

    const formData = new FormData();
    formData.append("photo", capturedBlob, "capture.jpg");

    fetch(window.location.pathname, { method: "POST", body: formData })
      .then(function (res) { return res.json(); })
      .then(showResult)
      .catch(function () {
        showResult({ success: false, error: "Couldn't reach the server. Check your connection and try again." });
      });
  });

  function showResult(data) {
    stepCapture.hidden = true;
    stepResult.hidden = false;

    if (data.success) {
      resultIcon.textContent = "✅";
      resultIcon.className = "ct-result-icon ct-result-success";
      resultTitle.textContent = "Saved";
      resultMessage.textContent = data.message || "Your face data was updated.";
    } else {
      resultIcon.textContent = "⚠️";
      resultIcon.className = "ct-result-icon ct-result-fail";
      resultTitle.textContent = "Couldn't save that photo";
      resultMessage.textContent = data.error || "Something went wrong. Please try again.";
    }
  }

  captureAgainBtn.addEventListener("click", function () {
    capturedBlob = null;
    submitBtn.disabled = false;
    submitBtn.textContent = "Save this photo";
    facePreview.hidden = true;
    faceVideo.hidden = false;
    captureBtn.hidden = false;
    retakeBtn.hidden = true;
    submitBtn.hidden = true;

    stepResult.hidden = true;
    stepCapture.hidden = false;
    faceStatus.textContent = "Center your face in frame, then capture.";
    startFaceCamera();
  });

  // ---------- init ----------
  startFaceCamera();

  window.addEventListener("beforeunload", function () {
    stopFaceCamera();
  });
})();
