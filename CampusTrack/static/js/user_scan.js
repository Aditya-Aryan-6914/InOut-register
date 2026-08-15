(function () {
  "use strict";

  const stepQr = document.getElementById("scanStepQr");
  const stepFace = document.getElementById("scanStepFace");
  const stepResult = document.getElementById("scanStepResult");
  if (!stepQr || !stepFace || !stepResult) return; // page not present

  const qrStatus = document.getElementById("qrStatus");
  const roomLabel = document.getElementById("roomLabel");
  const faceStatus = document.getElementById("faceStatus");
  const faceVideo = document.getElementById("faceVideo");
  const faceCanvas = document.getElementById("faceCanvas");
  const facePreview = document.getElementById("facePreview");
  const captureBtn = document.getElementById("captureBtn");
  const retakeBtn = document.getElementById("retakeBtn");
  const submitBtn = document.getElementById("submitBtn");
  const backToQrBtn = document.getElementById("backToQr");
  const scanAgainBtn = document.getElementById("scanAgainBtn");
  const resultIcon = document.getElementById("resultIcon");
  const resultTitle = document.getElementById("resultTitle");
  const resultMessage = document.getElementById("resultMessage");

  let html5QrCode = null;
  let faceStream = null;
  let capturedBlob = null;
  let qrPayload = null;
  let geoPosition = { latitude: null, longitude: null };

  // ---------- geolocation: request as soon as a QR is scanned, so
  // it's likely resolved by the time the user finishes the face step ----------
  function requestGeolocation() {
    if (!("geolocation" in navigator)) return;
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        geoPosition.latitude = pos.coords.latitude;
        geoPosition.longitude = pos.coords.longitude;
      },
      function () {
        // Permission denied or unavailable — geoPosition stays null.
        // The server treats missing coordinates as a failed location
        // check ONLY if the room actually has a geofence configured.
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  // ---------- Step 1: QR scanning ----------
  function startQrScanner() {
    if (typeof Html5Qrcode === "undefined") {
      qrStatus.textContent = "Couldn't load the QR scanner. Refresh the page and try again.";
      return;
    }
    html5QrCode = new Html5Qrcode("qrReader");
    html5QrCode
      .start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        onQrDecoded,
        function () { /* per-frame miss; expected constantly while aiming */ }
      )
      .catch(function (err) {
        qrStatus.textContent = "Couldn't access the camera: " + err + ". Check camera permissions.";
      });
  }

  function stopQrScanner() {
    if (!html5QrCode) return Promise.resolve();
    return html5QrCode
      .stop()
      .then(function () { return html5QrCode.clear(); })
      .catch(function () { /* already stopped; ignore */ });
  }

  function onQrDecoded(decodedText) {
    qrPayload = decodedText;
    requestGeolocation();
    qrStatus.textContent = "QR recognized — starting camera…";

    stopQrScanner().then(function () {
      stepQr.hidden = true;
      stepFace.hidden = false;
      roomLabel.textContent = "Checkpoint scanned";
      startFaceCamera();
    });
  }

  // ---------- Step 2: face capture ----------
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
    // Undo the mirrored preview so the captured image is right-reading,
    // matching how the registered profile photo was taken.
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
      faceStatus.textContent = "Looks good? Confirm to check in/out, or retake.";
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

  backToQrBtn.addEventListener("click", function () {
    stopFaceCamera();
    capturedBlob = null;
    qrPayload = null;
    facePreview.hidden = true;
    faceVideo.hidden = false;
    captureBtn.hidden = false;
    retakeBtn.hidden = true;
    submitBtn.hidden = true;
    stepFace.hidden = true;
    stepQr.hidden = false;
    qrStatus.textContent = "Point your camera at the checkpoint's QR code.";
    startQrScanner();
  });

  // ---------- Step 3: submit ----------
  submitBtn.addEventListener("click", function () {
    if (!capturedBlob || !qrPayload) return;

    submitBtn.disabled = true;
    submitBtn.textContent = "Checking…";

    const formData = new FormData();
    formData.append("qr_payload", qrPayload);
    formData.append("photo", capturedBlob, "capture.jpg");
    if (geoPosition.latitude !== null) formData.append("latitude", geoPosition.latitude);
    if (geoPosition.longitude !== null) formData.append("longitude", geoPosition.longitude);

    fetch(window.location.pathname + "/verify", { method: "POST", body: formData })
      .then(function (res) { return res.json(); })
      .then(showResult)
      .catch(function () {
        showResult({ success: false, error: "Couldn't reach the server. Check your connection and try again." });
      });
  });

  function showResult(data) {
    stepFace.hidden = true;
    stepResult.hidden = false;

    if (data.success) {
      resultIcon.textContent = "✅";
      resultIcon.className = "ct-result-icon ct-result-success";
      resultTitle.textContent = data.event_type === "check_in" ? "Checked in!" : "Checked out!";
      resultMessage.textContent = data.room ? "Recorded at " + data.room + "." : "Attendance recorded.";
    } else {
      resultIcon.textContent = "⚠️";
      resultIcon.className = "ct-result-icon ct-result-fail";
      resultTitle.textContent = "Verification failed";
      resultMessage.textContent = data.error || "Something went wrong. Please try again.";
    }
  }

  scanAgainBtn.addEventListener("click", function () {
    capturedBlob = null;
    qrPayload = null;
    geoPosition = { latitude: null, longitude: null };
    submitBtn.disabled = false;
    submitBtn.textContent = "Confirm check-in";
    facePreview.hidden = true;
    faceVideo.hidden = false;
    captureBtn.hidden = false;
    retakeBtn.hidden = true;
    submitBtn.hidden = true;

    stepResult.hidden = true;
    stepQr.hidden = false;
    qrStatus.textContent = "Point your camera at the checkpoint's QR code.";
    startQrScanner();
  });

  // ---------- init ----------
  startQrScanner();

  window.addEventListener("beforeunload", function () {
    stopFaceCamera();
    if (html5QrCode) html5QrCode.stop().catch(function () {});
  });
})();
